import { useState, useCallback, useRef, useEffect } from "react";
import type {
  AgentTurn,
  AgentVersion,
  ChatSession,
  CompareResult,
  ConnectionStatus,
  ParsedPlace,
  ReasoningStep,
  ScoredPlace,
  ToolResultEntry,
  WsMessage,
  ChatHistoryMessage,
  ChatHistoryResponse,
} from "../types";
import {
  storageService,
  type StoredSelection,
} from "../services/storageService";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const RECONNECT_DELAY = 3000;

/** Parse restaurant cards from plain-text LLM response */
function parsePlacesFromText(text: string): ParsedPlace[] {
  const results: ParsedPlace[] = [];
  const blocks = text.split(/\n\s*\n/);

  for (const block of blocks) {
    const lines = block
      .trim()
      .split("\n")
      .map((l) => l.trim())
      .filter(Boolean);
    if (lines.length < 2) continue;

    const nameLine = lines[0]
      .replace(/^#+\s*\*?\*?\d+[\.\)]\s*/i, "")
      .replace(/\*\*/g, "")
      .trim();
    if (!nameLine) continue;

    const ratingMatch = lines
      .join(" ")
      .match(/(?:rating[:\s]*)?(\d+\.?\d*)\s*(?:\/\s*5\s*sao|sao|★|\/5)/i);
    const rating = ratingMatch ? parseFloat(ratingMatch[1]) : 0;

    const distMatch =
      lines
        .join(" ")
        .match(/(?:khoảng\s*cách|distance)[:\s]*(\d+\.?\d*)\s*km/i) ||
      lines.join(" ").match(/(\d+\.?\d*)\s*km/);
    const distance_km = distMatch ? parseFloat(distMatch[1]) : 0;

    const descLines = lines
      .slice(1)
      .filter(
        (l) => !/(?:rating|khoảng\s*cách|distance|\d+\.?\d*\s*km)/i.test(l),
      );
    const description = descLines.join(" ").replace(/\*\*/g, "").trim();

    results.push({ name: nameLine, rating, distance_km, description });
  }

  return results;
}

interface SessionInfo {
  session_id: string;
  user_id: string;
  token: string;
}

const MOCK_USERS = [
  { user_id: "u01", name: "Minh", city: "Hà Nội - Hoàn Kiếm" },
  { user_id: "u02", name: "Linh", city: "TP.HCM - Quận 1" },
  { user_id: "u03", name: "Hùng", city: "Đà Nẵng - Hải Châu" },
  { user_id: "u04", name: "Lan", city: "Cần Thơ - Ninh Kiều" },
  { user_id: "u05", name: "Nam", city: "Hải Phòng - Lê Chân" },
  { user_id: "u06", name: "Mai", city: "TP.HCM - Thủ Đức" },
  { user_id: "u07", name: "Tuấn", city: "Vĩnh Phúc - Vĩnh Yên" },
  { user_id: "u08", name: "Hoa", city: "Nha Trang - Vĩnh Hải" },
  { user_id: "u09", name: "Bình", city: "Quy Nhơn - Nhơn Bình" },
  { user_id: "u10", name: "Dung", city: "Đà Lạt - Phường 1" },
];

// Fix u04 duplicate name
MOCK_USERS[3].name = "Lan";

interface UseChatReturn {
  status: ConnectionStatus;
  turns: AgentTurn[];
  lastPlaces: ScoredPlace[];
  selectedUserId: string;
  setSelectedUserId: (id: string) => void;
  sendMessage: (text: string) => void;
  selectPlace: (place: ScoredPlace) => void;
  reset: () => void;
  users: typeof MOCK_USERS;
  sessionInfo: SessionInfo | null;
  savedSelections: StoredSelection[];
  removeSavedSelection: (place_id: string) => void;
  clearSavedSelections: () => void;
  selectedModel: string;
  setSelectedModel: (model: string) => void;
  selectedVersion: AgentVersion;
  setSelectedVersion: (version: AgentVersion) => void;
  isComparing: boolean;
  setIsComparing: (comparing: boolean) => void;
  compareResult: CompareResult | null;
  setCompareResult: (result: CompareResult | null) => void;
  showSidebar: boolean;
  setShowSidebar: (show: boolean) => void;
  chatSessions: ChatSession[];
  setChatSessions: React.Dispatch<React.SetStateAction<ChatSession[]>>;
  currentSessionId: string;
  setCurrentSessionId: (id: string) => void;
  createNewChat: () => void;
  loadChatSession: (id: string) => void;
  deleteChatSession: (id: string) => void;
  chatHistory: ChatHistoryMessage[];
  chatHistoryLoading: boolean;
  chatHistoryError: string | null;
  fetchChatHistory: (sessionId: string) => Promise<void>;
}

export function useChat(): UseChatReturn {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [lastPlaces, setLastPlaces] = useState<ScoredPlace[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("u01");
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [savedSelections, setSavedSelections] = useState<StoredSelection[]>([]);

  // ── New state for sidebar, versioning, and comparison ───────────────────────
  const [selectedModel, setSelectedModel] = useState("gpt-4o-mini");
  const [selectedVersion, setSelectedVersion] = useState<AgentVersion>("v2");
  const [isComparing, setIsComparing] = useState(false);
  const [compareResult, setCompareResult] = useState<CompareResult | null>(
    null,
  );
  const [showSidebar, setShowSidebar] = useState(true);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState("");

  // ── Chat history state ──────────────────────────────────────────────────────
  const [chatHistory, setChatHistory] = useState<ChatHistoryMessage[]>([]);
  const [chatHistoryLoading, setChatHistoryLoading] = useState(false);
  const [chatHistoryError, setChatHistoryError] = useState<string | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userIdRef = useRef(selectedUserId);
  const sessionIdRef = useRef("");
  const lastMessageSent = useRef<string>("");

  useEffect(() => {
    userIdRef.current = selectedUserId;
    // Reset last message when user changes
    lastMessageSent.current = "";
  }, [selectedUserId]);

  // ── Fetch all backend sessions for a user ───────────────────────────────────

  const fetchUserSessions = useCallback(
    async (user_id: string): Promise<Array<{ session_id: string; created_at: string; user_id: string }>> => {
      try {
        const res = await fetch(`${BACKEND_URL}/api/sessions/${encodeURIComponent(user_id)}`);
        if (!res.ok) {
          console.error(`Failed to fetch sessions for user ${user_id}:`, res.status);
          return [];
        }
        const data = await res.json();
        console.log('Fetched backend sessions:', data);
        return data;
      } catch (error) {
        console.error('Error fetching user sessions:', error);
        return [];
      }
    },
    [],
  );

  // ── Fetch chat history ──────────────────────────────────────────────────────

  const fetchChatHistory = useCallback(
    async (sessionId: string) => {
      if (!sessionId) return;

      setChatHistoryLoading(true);
      setChatHistoryError(null);

      try {
        const response = await fetch(
          `${BACKEND_URL}/api/session/${sessionId}/history`,
        );

        if (!response.ok) {
          throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        const data: ChatHistoryResponse = await response.json();

        // Convert backend format to frontend format if needed
        const formattedMessages: ChatHistoryMessage[] = data.messages.map(msg => ({
          timestamp: msg.timestamp,
          role: msg.role as 'user' | 'assistant',
          content: msg.content,
        }));

        setChatHistory(formattedMessages);
        console.log(`Loaded ${formattedMessages.length} messages for session ${sessionId}`);
      } catch (error) {
        const errorMessage = error instanceof Error ? error.message : "Unknown error";
        setChatHistoryError(errorMessage);
        console.error("[useChat] Failed to fetch chat history:", error);
      } finally {
        setChatHistoryLoading(false);
      }
    },
    [],
  );

  // ── Step 1: Create session → get JWT (auto on mount) ────────────────────────

  const createSession = useCallback(
    async (user_id: string): Promise<SessionInfo> => {
      const res = await fetch(
        `${BACKEND_URL}/api/session?user_id=${encodeURIComponent(user_id)}`,
        { method: "GET" },
      );

      if (!res.ok) {
        const err = await res.json().catch(() => ({ detail: "Unknown error" }));
        throw new Error(err.detail || `HTTP ${res.status}`);
      }

      const data = await res.json();
      return {
        session_id: data.session_id,
        user_id: data.user_id,
        token: data.token,
      };
    },
    [],
  );

  // ── Auto-init: load backend sessions on mount ────────────────────────

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      try {
        // 1. Fetch all backend sessions for this user
        const backendSessions = await fetchUserSessions(selectedUserId);
        if (!mounted) return;

        // 2. Convert backend sessions to ChatSession format for sidebar
        const chatSessionsFromBackend: ChatSession[] = backendSessions.map((s) => ({
          id: s.session_id,
          user_id: selectedUserId,
          model: selectedModel,
          version: selectedVersion,
          title: `Session ${s.session_id.slice(-8)}`,
          preview: "",
          turns: [],
          created_at: new Date(s.created_at).getTime(),
          updated_at: new Date(s.created_at).getTime(),
        }));

        setChatSessions(chatSessionsFromBackend);

        // 3. Create a new session for the current visit
        const newSession = await createSession(selectedUserId);
        if (!mounted) return;

        sessionIdRef.current = newSession.session_id;
        setCurrentSessionId(newSession.session_id);
        setSessionInfo(newSession);

        // Add the new session to the top of the list
        const newChatSession: ChatSession = {
          id: newSession.session_id,
          user_id: selectedUserId,
          model: selectedModel,
          version: selectedVersion,
          title: "New Chat",
          preview: "",
          turns: [],
          created_at: Date.now(),
          updated_at: Date.now(),
        };

        setChatSessions((prev) => [newChatSession, ...prev]);

        // Connect WebSocket and load chat history
        await connectWs(newSession.token);
        fetchChatHistory(newSession.session_id);
      } catch (err) {
        if (!mounted) return;
        console.error("[useChat] init failed:", err);
        setStatus("error");
      }
    };

    init();

    return () => {
      mounted = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Step 2: Connect WebSocket with token ────────────────────────────────────

  const connectWs = useCallback(
    async (token: string) => {
      if (wsRef.current?.readyState === WebSocket.OPEN) {
        return;
      }

      setStatus("connecting");

      const ws = new WebSocket(
        `${BACKEND_URL}/ws/chat?token=${encodeURIComponent(token)}`,
      );
      wsRef.current = ws;

      ws.onopen = () => {
        setStatus("connected");
      };

      ws.onmessage = (event) => {
        let msg: WsMessage;
        try {
          msg = JSON.parse(event.data as string) as WsMessage;
        } catch {
          return;
        }

        if (msg.type === "token") {
          const tokenData = (msg as WsMessage & { data: string }).data;
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            const newMessage =
              last?.role === "assistant" ? last.message + tokenData : tokenData;

            const parsed = parsePlacesFromText(newMessage);

            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  message: newMessage,
                  parsedPlaces: parsed.length ? parsed : last.parsedPlaces,
                },
              ];
            }
            return prev;
          });
        } else if (msg.type === "done") {
          const doneMsg = msg as WsMessage & {
            data?: { places?: ScoredPlace[] };
          };
          const places: ScoredPlace[] = (doneMsg.data?.places ??
            []) as ScoredPlace[];
          setLastPlaces(places);

          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  message: last.message,
                  places,
                  timestamp: Date.now(),
                },
              ];
            }
            // No assistant turn yet — create one (handles v2 non-food path)
            return [
              ...prev,
              { role: "assistant", message: "", places, timestamp: Date.now() },
            ];
          });
        } else if (msg.type === "error") {
          const errMsg =
            (msg as WsMessage & { message?: string }).message ||
            "Unknown error";
          setTurns((prev) => [
            ...prev,
            {
              role: "assistant",
              message: `❌ Lỗi: ${errMsg}`,
              timestamp: Date.now(),
            },
          ]);
          setStatus("error");
        } else if ((msg as { type: string }).type === "success") {
          const successMsg =
            (msg as WsMessage & { message?: string }).message ||
            "Đã lưu lựa chọn!";
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && !last.message) {
              return [
                ...prev.slice(0, -1),
                { ...last, message: successMsg, timestamp: Date.now() },
              ];
            }
            return [
              ...prev,
              { role: "assistant", message: successMsg, timestamp: Date.now() },
            ];
          });
          setLastPlaces([]);
        } else if (msg.type === "reasoning") {
          const rm = msg as WsMessage & {
            step: number;
            text: string;
            tool: string | null;
          };
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              const reasoningStep: ReasoningStep = {
                step: rm.step,
                text: rm.text,
                tool: rm.tool,
              };
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  reasoningSteps: [
                    ...(last.reasoningSteps || []),
                    reasoningStep,
                  ],
                },
              ];
            }
            return prev;
          });
        } else if (msg.type === "tool_result") {
          const tr = msg as WsMessage & {
            tool: string;
            result: unknown;
            error: string | null;
          };
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              const toolEntry: ToolResultEntry = {
                tool: tr.tool,
                result: tr.result,
                error: tr.error,
              };
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  toolResults: [...(last.toolResults || []), toolEntry],
                },
              ];
            }
            return prev;
          });
        } else if (msg.type === "compare_result") {
          const cr = msg as WsMessage & { versions: CompareResult };
          setCompareResult(cr.versions);
        }
      };

      ws.onerror = () => {
        setStatus("error");
      };

      ws.onclose = () => {
        setStatus("disconnected");
        wsRef.current = null;
        reconnectTimer.current = setTimeout(() => {
          if (sessionInfo?.token) {
            connectWs(sessionInfo.token);
          }
        }, RECONNECT_DELAY);
      };
    },
    [sessionInfo?.token],
  ); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 3: Send message ────────────────────────────────────────────────────

  const sendMessage = useCallback(
    async (text: string) => {
      console.log(`[FE] sendMessage called with: "${text}"`);

      // Prevent duplicate sends
      if (text.trim() === lastMessageSent.current) {
        console.log(`[FE] Skipping duplicate message: "${text}"`);
        return;
      }
      lastMessageSent.current = text.trim();
      console.log(`[FE] Processing new message: "${text}"`);

      const userTurn: AgentTurn = {
        role: "user",
        message: text,
        timestamp: Date.now(),
      };
      setTurns((prev) => [...prev, userTurn]);

      const parsed = parsePlacesFromText("");
      setTurns((prev) => [
        ...prev,
        {
          role: "assistant",
          message: "",
          timestamp: Date.now(),
          parsedPlaces: parsed,
        },
      ]);

      let currentSession = sessionInfo;
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        try {
          currentSession = await createSession(userIdRef.current);
          sessionIdRef.current = currentSession.session_id;
          setSessionInfo(currentSession);
          // Update currentSessionId to the REAL backend session ID so history API works
          setCurrentSessionId(currentSession.session_id);
          await connectWs(currentSession.token);
        } catch (err) {
          const errMsg = err instanceof Error ? err.message : "Cannot connect";
          setTurns((prev) => [
            ...prev,
            {
              role: "assistant",
              message: `❌ Lỗi kết nối: ${errMsg}`,
              timestamp: Date.now(),
            },
          ]);
          return;
        }
        // connectWs set wsRef.current — re-read after awaiting
        console.log(`Sending message via NEW WebSocket connection: "${text}"`);
        wsRef.current?.send(
          JSON.stringify({
            text,
            model: selectedModel || undefined,
            version: selectedVersion,
            compare: isComparing,
          }),
        );
      } else {
        console.log(`Sending message via EXISTING WebSocket connection: "${text}"`);
        ws.send(
          JSON.stringify({
            text,
            model: selectedModel || undefined,
            version: selectedVersion,
            compare: isComparing,
          }),
        );
      }

      // Refresh chat history after sending message
      if (sessionIdRef.current) {
        // Update the current session's preview with the last message
        setChatSessions(prev =>
          prev.map(s =>
            s.id === sessionIdRef.current
              ? { ...s, preview: text.length > 50 ? text.substring(0, 50) + "..." : text, updated_at: Date.now() }
              : s
          )
        );
      }

    },
    [sessionInfo, createSession, connectWs, selectedModel, selectedVersion, isComparing],
  );

  // ── Switch user → new session ───────────────────────────────────────────────

  const handleSetUserId = useCallback(
    async (newId: string) => {
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      setSelectedUserId(newId);
      setTurns([]);
      setLastPlaces([]);
      setSessionInfo(null);
      setStatus("disconnected");
      setCompareResult(null);
      setChatHistory([]);

      try {
        // Fetch all backend sessions for the new user
        const backendSessions = await fetchUserSessions(newId);

        // Convert to ChatSession format
        const chatSessionsFromBackend: ChatSession[] = backendSessions.map((s) => ({
          id: s.session_id,
          user_id: newId,
          model: selectedModel,
          version: selectedVersion,
          title: `Session ${s.session_id.slice(-6)}`,
          preview: "",
          turns: [],
          created_at: new Date(s.created_at).getTime(),
          updated_at: new Date(s.created_at).getTime(),
        }));

        // Create a new session for the current visit
        const session = await createSession(newId);
        sessionIdRef.current = session.session_id;
        setCurrentSessionId(session.session_id);
        setSessionInfo(session);

        // Add new session to the top
        const newChatSession: ChatSession = {
          id: session.session_id,
          user_id: newId,
          model: selectedModel,
          version: selectedVersion,
          title: "New Chat",
          preview: "",
          turns: [],
          created_at: Date.now(),
          updated_at: Date.now(),
        };

        setChatSessions([newChatSession, ...chatSessionsFromBackend]);
        await connectWs(session.token);
        fetchChatHistory(session.session_id);
      } catch (err) {
        console.error("[useChat] switch user failed:", err);
        setStatus("error");
      }
    },
    [createSession, connectWs, fetchChatHistory, fetchUserSessions, selectedModel, selectedVersion],
  );

  // ── Select place → send select_place via WebSocket ──────────────────────────

  const selectPlace = useCallback(async (place: ScoredPlace) => {
    const user_id = userIdRef.current;

    // 1. Save to localStorage immediately
    const updated = storageService.save(place, user_id);
    setSavedSelections(updated);

    // 2. Send select_place via WebSocket
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      console.warn("[useChat] WebSocket not open, cannot select place");
      return;
    }

    wsRef.current.send(JSON.stringify({ type: "select_place", place }));

    // 3. Clear lastPlaces so old food cards disappear after selection
    setLastPlaces([]);
  }, []);

  // ── Saved selections helpers ────────────────────────────────────────────────

  const removeSavedSelection = useCallback((place_id: string) => {
    const updated = storageService.remove(place_id, userIdRef.current);
    setSavedSelections(updated);
  }, []);

  const clearSavedSelections = useCallback(() => {
    storageService.clearAll();
    setSavedSelections([]);
  }, []);

  // ── Reset conversation ──────────────────────────────────────────────────────

  const reset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setTurns([]);
    setLastPlaces([]);
    setSessionInfo(null);
    setStatus("disconnected");
    setCompareResult(null);
    // Keep savedSelections — they persist across resets
  }, []);

  // ── Chat session management ──────────────────────────────────────────────────

  const createNewChat = useCallback(async () => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }

    try {
      // Create a new backend session
      const session = await createSession(selectedUserId);
      sessionIdRef.current = session.session_id;
      setSessionInfo(session);

      const newChatSession: ChatSession = {
        id: session.session_id,
        user_id: selectedUserId,
        model: selectedModel,
        version: selectedVersion,
        title: "New Chat",
        preview: "",
        turns: [],
        created_at: Date.now(),
        updated_at: Date.now(),
      };

      // Add new session to the top of the list
      setChatSessions((prev) => [newChatSession, ...prev]);

      setCurrentSessionId(session.session_id);
      setTurns([]);
      setLastPlaces([]);
      setStatus("disconnected");
      setCompareResult(null);
      setChatHistory([]);

      await connectWs(session.token);
      console.log(`Created new chat session: ${session.session_id}`);
    } catch (err) {
      console.error("[useChat] createNewChat failed:", err);
      setStatus("error");
    }
  }, [selectedUserId, selectedModel, selectedVersion, createSession, connectWs]);

  const loadChatSession = useCallback(
    async (id: string) => {
      const session = chatSessions.find((s) => s.id === id);
      if (!session) {
        console.error(`Session ${id} not found in chatSessions:`, chatSessions);
        return;
      }

      setCurrentSessionId(id);
      setCompareResult(null);

      console.log(`Fetching chat history for session: ${id}`);
      // Fetch chat history from backend for the selected session
      await fetchChatHistory(id);

      // Also load the messages into the main chat window
      try {
        const response = await fetch(`${BACKEND_URL}/api/session/${id}/history`);
        if (response.ok) {
          const data: ChatHistoryResponse = await response.json();

          // Convert chat history messages to AgentTurn format for main chat
          const turnsFromHistory: AgentTurn[] = data.messages.map((msg, index) => ({
            role: msg.role as 'user' | 'assistant',
            message: msg.content,
            timestamp: new Date(msg.timestamp).getTime(),
            // Add basic properties, places and other fields will be empty for historical messages
            places: [],
            parsedPlaces: [],
          }));

          setTurns(turnsFromHistory);
          console.log(`Loaded ${turnsFromHistory.length} turns into main chat for session ${id}`);
        }
      } catch (error) {
        console.error(`Failed to load chat history into main chat for session ${id}:`, error);
      }
    },
    [chatSessions],
  );

  const deleteChatSession = useCallback(
    (id: string) => {
      // Remove from local state
      setChatSessions((prev) => prev.filter((s) => s.id !== id));

      if (currentSessionId === id) {
        if (wsRef.current) {
          wsRef.current.close();
          wsRef.current = null;
        }
        setTurns([]);
        setCurrentSessionId("");
        setStatus("disconnected");
        setCompareResult(null);
        setChatHistory([]);
      }

      console.log(`Deleted session: ${id}`);
    },
    [currentSessionId],
  );



  // ── Cleanup on unmount ──────────────────────────────────────────────────────

  useEffect(() => {
    return () => {
      if (reconnectTimer.current) clearTimeout(reconnectTimer.current);
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  return {
    status,
    turns,
    lastPlaces,
    selectedUserId,
    setSelectedUserId: handleSetUserId,
    sendMessage,
    selectPlace,
    reset,
    users: MOCK_USERS,
    sessionInfo,
    savedSelections,
    removeSavedSelection,
    clearSavedSelections,
    selectedModel,
    setSelectedModel,
    selectedVersion,
    setSelectedVersion,
    isComparing,
    setIsComparing,
    compareResult,
    setCompareResult,
    showSidebar,
    setShowSidebar,
    chatSessions,
    setChatSessions,
    currentSessionId,
    setCurrentSessionId,
    createNewChat,
    loadChatSession,
    deleteChatSession,
    chatHistory,
    chatHistoryLoading,
    chatHistoryError,
    fetchChatHistory,
  };
}
