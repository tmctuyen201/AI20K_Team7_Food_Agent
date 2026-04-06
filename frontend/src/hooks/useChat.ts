import { useState, useCallback, useRef, useEffect } from 'react';
import type { AgentTurn, ConnectionStatus, ScoredPlace } from '../types';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const RECONNECT_DELAY = 3000;

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
  { user_id: 'u01', name: 'Minh', city: 'Hà Nội - Hoàn Kiếm' },
  { user_id: 'u02', name: 'Linh', city: 'TP.HCM - Quận 1' },
  { user_id: 'u03', name: 'Hùng', city: 'Đà Nẵng - Hải Châu' },
  { user_id: 'u04', name: 'Lan',  name: 'Lan',  city: 'Cần Thơ - Ninh Kiều' },
  { user_id: 'u05', name: 'Nam',  city: 'Hải Phòng - Lê Chân' },
  { user_id: 'u06', name: 'Mai',  city: 'TP.HCM - Thủ Đức' },
  { user_id: 'u07', name: 'Tuấn', city: 'Vĩnh Phúc - Vĩnh Yên' },
  { user_id: 'u08', name: 'Hoa',  city: 'Nha Trang - Vĩnh Hải' },
  { user_id: 'u09', name: 'Bình', city: 'Quy Nhơn - Nhơn Bình' },
  { user_id: 'u10', name: 'Dung', city: 'Đà Lạt - Phường 1' },
];

// Fix u04 duplicate name
MOCK_USERS[3].name = 'Lan';

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
}

export function useChat(): UseChatReturn {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [lastPlaces, setLastPlaces] = useState<ScoredPlace[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('u01');
  const [sessionInfo, setSessionInfo] = useState<SessionInfo | null>(null);

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const userIdRef = useRef(selectedUserId);
  const sessionIdRef = useRef('');

  // Keep refs in sync with state
  useEffect(() => { userIdRef.current = selectedUserId; }, [selectedUserId]);

  // ── Step 1: Create session → get JWT ──────────────────────────────────────

  const createSession = useCallback(async (user_id: string): Promise<SessionInfo> => {
    const res = await fetch(`${BACKEND_URL}/api/session`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id, name: '', latitude: 21.0285, longitude: 105.8542 }),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({ detail: 'Unknown error' }));
      throw new Error(err.detail || `HTTP ${res.status}`);
    }

    const data = await res.json();
    return {
      session_id: data.session_id,
      user_id: data.user_id,
      token: data.token,
    };
  }, []);

  // ── Step 2: Connect WebSocket with token ────────────────────────────────────

  const connectWs = useCallback(async (token: string) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      return;
    }

    setStatus('connecting');

    const ws = new WebSocket(`${BACKEND_URL}/ws/chat?token=${encodeURIComponent(token)}`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
    };

    ws.onmessage = (event) => {
      let msg: WsMessage;
      try {
        msg = JSON.parse(event.data as string) as WsMessage;
      } catch {
        return;
      }

      if (msg.type === 'token') {
        // Streaming token — accumulate in last assistant turn
        setTurns((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...last, message: last.message + (msg.data as string) },
            ];
          }
          return prev;
        });
      } else if (msg.type === 'done') {
        const places: ScoredPlace[] = ((msg as unknown as { data?: { places?: ScoredPlace[] } }).data?.places ?? []) as ScoredPlace[];
        setLastPlaces(places);

        setTurns((prev) => {
          const last = prev[prev.length - 1];
          if (last?.role === 'assistant') {
            return [
              ...prev.slice(0, -1),
              { ...last, places, timestamp: Date.now() },
            ];
          }
          return prev;
        });
      } else if (msg.type === 'error') {
        const errMsg = (msg as WsMessage & { message?: string }).message || 'Unknown error';
        setTurns((prev) => [
          ...prev,
          {
            role: 'assistant',
            message: `❌ Lỗi: ${errMsg}`,
            timestamp: Date.now(),
          },
        ]);
        setStatus('error');
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      reconnectTimer.current = setTimeout(() => {
        if (sessionInfo?.token) {
          connectWs(sessionInfo.token);
        }
      }, RECONNECT_DELAY);
    };
  }, [sessionInfo?.token]); // eslint-disable-line react-hooks/exhaustive-deps

  // ── Step 3: Send message ────────────────────────────────────────────────────

  const sendMessage = useCallback(async (text: string) => {
    // Append user turn immediately
    const userTurn: AgentTurn = {
      role: 'user',
      message: text,
      timestamp: Date.now(),
    };
    setTurns((prev) => [...prev, userTurn]);

    // Start assistant turn
    setTurns((prev) => [
      ...prev,
      { role: 'assistant', message: '', timestamp: Date.now() },
    ]);

    // Ensure WebSocket is connected
    let currentSession = sessionInfo;
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      try {
        currentSession = await createSession(userIdRef.current);
        sessionIdRef.current = currentSession.session_id;
        setSessionInfo(currentSession);
        await connectWs(currentSession.token);
      } catch (err) {
        const errMsg = err instanceof Error ? err.message : 'Cannot connect';
        setTurns((prev) => [
          ...prev,
          {
            role: 'assistant',
            message: `❌ Lỗi kết nối: ${errMsg}`,
            timestamp: Date.now(),
          },
        ]);
        return;
      }
    }

    // Send in the format backend expects
    wsRef.current.send(JSON.stringify({ text }));
  }, [sessionInfo, createSession, connectWs]);

  // ── Switch user → new session ───────────────────────────────────────────────

  const handleSetUserId = useCallback((newId: string) => {
    setSelectedUserId(newId);
    // Close existing WS, reconnect with new session
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setSessionInfo(null);
    setStatus('disconnected');
  }, []);

  // ── Select place ────────────────────────────────────────────────────────────

  const selectPlace = useCallback(async (place: ScoredPlace) => {
    const msg = `Tôi chọn quán số: ${place.name}`;
    await sendMessage(msg);
  }, [sendMessage]);

  // ── Reset conversation ──────────────────────────────────────────────────────

  const reset = useCallback(() => {
    if (wsRef.current) {
      wsRef.current.close();
      wsRef.current = null;
    }
    setTurns([]);
    setLastPlaces([]);
    setSessionInfo(null);
    setStatus('disconnected');
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
  };
}
