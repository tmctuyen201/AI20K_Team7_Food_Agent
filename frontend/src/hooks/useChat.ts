import { useState, useCallback, useRef, useEffect } from "react";
import type { AgentTurn, ConnectionStatus, ScoredPlace, ParsedPlace } from "../types";
import { storageService, type StoredSelection } from "../services/storageService";

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || "http://localhost:8000";
const RECONNECT_DELAY = 3000;

/** Parse restaurant cards from plain-text LLM response */
function parsePlacesFromText(text: string): ParsedPlace[] {
  const results: ParsedPlace[] = [];
  // Split by blank-line-separated blocks
  const blocks = text.split(/\n\s*\n/);

  for (const block of blocks) {
    const lines = block.trim().split('\n').map((l) => l.trim()).filter(Boolean);
    if (lines.length < 2) continue;

    // 1. Extract name — first non-empty line (may be bold/markdown)
    const nameLine = lines[0].replace(/^#+\s*\*?\*?\d+[\.\)]\s*/i, '').replace(/\*\*/g, '').trim();
    if (!nameLine) continue;

    // 2. Extract rating — e.g. "Rating: 4.7/5" or "4.7/5 sao"
    const ratingMatch = lines.join(' ').match(/(?:rating[:\s]*)?(\d+\.?\d*)\s*(?:\/\s*5\s*sao|sao|★|\/5)/i);
    const rating = ratingMatch ? parseFloat(ratingMatch[1]) : 0;

    // 3. Extract distance — e.g. "0.4 km", "0.9km", "Khoảng cách: 0.9 km"
    const distMatch = lines.join(' ').match(/(?:khoảng\s*cách|distance)[:\s]*(\d+\.?\d*)\s*km/i)
      || lines.join(' ').match(/(\d+\.?\d*)\s*km/);
    const distance_km = distMatch ? parseFloat(distMatch[1]) : 0;

    // 4. Description — remaining lines joined (skip rating/dist lines)
    const descLines = lines.slice(1).filter(
      (l) => !/(?:rating|khoảng\s*cách|distance|\d+\.?\d*\s*km)/i.test(l),
    );
    const description = descLines.join(' ').replace(/\*\*/g, '').trim();

    results.push({ name: nameLine, rating, distance_km, description });
  }

  return results;
}

interface SessionInfo {
  session_id: string;
  user_id: string;
  token: string;
}

interface WsMessage {
  type: string;
  text?: string;
  user_id?: string;
  data?: unknown;
  places?: ScoredPlace[];
  message?: string;
  detail?: string;
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
}

export function useChat(): UseChatReturn {
  const [status, setStatus] = useState<ConnectionStatus>("disconnected");
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [lastPlaces, setLastPlaces] = useState<ScoredPlace[]>([]);
  const [selectedUserId, setSelectedUserId] = useState("u01");
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);
  const [savedSelections, setSavedSelections] = useState<StoredSelection[]>([]);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userIdRef = useRef(selectedUserId);
  const sessionIdRef = useRef("");

  // Keep refs in sync with state
  useEffect(() => {
    userIdRef.current = selectedUserId;
  }, [selectedUserId]);

  // ── Step 1: Create session → get JWT (auto on mount) ───────────────────────

  const createSession = useCallback(
    async (user_id: string): Promise<SessionInfo> => {
      // Use GET /api/session — auto-creates session without body
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

  // ── Auto-init: create session + connect WS on mount ─────────────────────────

  useEffect(() => {
    let mounted = true;

    const init = async () => {
      try {
        const session = await createSession(selectedUserId);
        if (!mounted) return;
        sessionIdRef.current = session.session_id;
        setSessionInfo(session);
        await connectWs(session.token);
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
          // Streaming token — accumulate in last assistant turn
          // and try to parse restaurant cards from accumulated text
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            const newMessage = last?.role === "assistant"
              ? last.message + (msg.data as string)
              : (msg.data as string);

            const parsed = parsePlacesFromText(newMessage);

            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { ...last, message: newMessage, parsedPlaces: parsed.length ? parsed : last.parsedPlaces },
              ];
            }
            return prev;
          });
        } else if (msg.type === "done") {
          const places: ScoredPlace[] = ((
            msg as unknown as { data?: { places?: ScoredPlace[] } }
          ).data?.places ?? []) as ScoredPlace[];
          setLastPlaces(places);

          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant") {
              return [
                ...prev.slice(0, -1),
                { ...last, places, timestamp: Date.now() },
              ];
            }
            return prev;
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
        } else if (msg.type === "success") {
          // select_place confirmed — show as assistant message, no places
          const successMsg =
            (msg as WsMessage & { message?: string }).message || "Đã lưu lựa chọn!";
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === "assistant" && !last.message) {
              return [...prev.slice(0, -1), { ...last, message: successMsg, timestamp: Date.now() }];
            }
            return [
              ...prev,
              { role: "assistant", message: successMsg, timestamp: Date.now() },
            ];
          });
          setLastPlaces([]);
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
      // Append user turn immediately
      const userTurn: AgentTurn = {
        role: "user",
        message: text,
        timestamp: Date.now(),
      };
      setTurns((prev) => [...prev, userTurn]);

      // Start assistant turn with parsed places ready
      const parsed = parsePlacesFromText("");
      setTurns((prev) => [
        ...prev,
        { role: "assistant", message: "", timestamp: Date.now(), parsedPlaces: parsed },
      ]);

      // Ensure WebSocket is connected
      let currentSession = sessionInfo;
      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        try {
          currentSession = await createSession(userIdRef.current);
          sessionIdRef.current = currentSession.session_id;
          setSessionInfo(currentSession);
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
        wsRef.current?.send(JSON.stringify({ text }));
      } else {
        ws.send(JSON.stringify({ text }));
      }
    },
    [sessionInfo, createSession, connectWs],
  );

  // ── Switch user → new session ───────────────────────────────────────────────

  const handleSetUserId = useCallback(
    async (newId: string) => {
      // Close existing WS
      if (wsRef.current) {
        wsRef.current.close();
        wsRef.current = null;
      }

      setSelectedUserId(newId);
      setTurns([]);
      setLastPlaces([]);
      setSessionInfo(null);
      setStatus("disconnected");

      // Create new session + reconnect WS for the new user
      try {
        const session = await createSession(newId);
        sessionIdRef.current = session.session_id;
        setSessionInfo(session);
        await connectWs(session.token);
      } catch (err) {
        console.error("[useChat] switch user failed:", err);
        setStatus("error");
      }
    },
    [createSession, connectWs],
  );

  // ── Select place → send select_place via WebSocket ─────────────────────────

  const selectPlace = useCallback(
    async (place: ScoredPlace) => {
      const user_id = userIdRef.current;

      // 1. Save to localStorage immediately
      const updated = storageService.save(place, user_id);
      setSavedSelections(updated);

      // 2. Send select_place via WebSocket (backend calls save_user_selection)
      if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
        console.warn("[useChat] WebSocket not open, cannot select place");
        return;
      }

      wsRef.current.send(JSON.stringify({ type: "select_place", place }));

      // 3. Clear lastPlaces so old food cards disappear after selection
      setLastPlaces([]);
    },
    [],
  );

  // ── Saved selections helpers ──────────────────────────────────────────────────

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
    // Keep savedSelections — they persist across resets
  }, []);

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
  };
}
