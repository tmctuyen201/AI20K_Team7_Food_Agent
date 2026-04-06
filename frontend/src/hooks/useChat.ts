import { useState, useCallback, useRef } from 'react';
import type { AgentTurn, ConnectionStatus, ScoredPlace } from '../types';

const BACKEND_URL = import.meta.env.VITE_BACKEND_URL || 'http://localhost:8000';
const RECONNECT_DELAY = 3000;

const MOCK_USERS = [
  { user_id: 'u01', name: 'Minh', city: 'Hà Nội - Hoàn Kiếm' },
  { user_id: 'u02', name: 'Linh', city: 'TP.HCM - Quận 1' },
  { user_id: 'u03', name: 'Hùng', city: 'Đà Nẵng - Hải Châu' },
  { user_id: 'u04', name: 'Lan',  city: 'Cần Thơ - Ninh Kiều' },
  { user_id: 'u05', name: 'Nam',  city: 'Hải Phòng - Lê Chân' },
  { user_id: 'u06', name: 'Mai',  city: 'TP.HCM - Thủ Đức' },
  { user_id: 'u07', name: 'Tuấn', city: 'Vĩnh Phúc - Vĩnh Yên' },
  { user_id: 'u08', name: 'Hoa',  city: 'Nha Trang - Vĩnh Hải' },
  { user_id: 'u09', name: 'Bình', city: 'Quy Nhơn - Nhơn Bình' },
  { user_id: 'u10', name: 'Dung', city: 'Đà Lạt - Phường 1' },
];

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
}

export function useChat(): UseChatReturn {
  const [status, setStatus] = useState<ConnectionStatus>('disconnected');
  const [turns, setTurns] = useState<AgentTurn[]>([]);
  const [lastPlaces, setLastPlaces] = useState<ScoredPlace[]>([]);
  const [selectedUserId, setSelectedUserId] = useState('u01');

  const wsRef = useRef<WebSocket | null>(null);
  const reconnectTimer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const pendingResolve = useRef<((data: Record<string, unknown>) => void) | null>(null);
  const pendingReject = useRef<((err: Error) => void) | null>(null);

  const connect = useCallback(() => {
    if (wsRef.current?.readyState === WebSocket.OPEN) return;

    setStatus('connecting');
    const ws = new WebSocket(`ws://${BACKEND_URL}/ws/chat`);
    wsRef.current = ws;

    ws.onopen = () => {
      setStatus('connected');
      // Authenticate with user_id
      ws.send(JSON.stringify({ type: 'auth', user_id: selectedUserId }));
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data as string) as Record<string, unknown>;

        if (data.type === 'token' || data.type === 'chunk') {
          // Streaming token — accumulate in last assistant turn
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              return [
                ...prev.slice(0, -1),
                { ...last, message: last.message + (data.data as string) },
              ];
            }
            return prev;
          });
        } else if (data.type === 'done') {
          // Final response
          const places = (data.data as { places?: ScoredPlace[] })?.places ?? [];
          setLastPlaces(places);

          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              return [
                ...prev.slice(0, -1),
                {
                  ...last,
                  places,
                  timestamp: Date.now(),
                },
              ];
            }
            return prev;
          });

          pendingResolve.current?.(data as Record<string, unknown>);
          pendingResolve.current = null;
          pendingReject.current = null;
        } else if (data.type === 'tool_result') {
          // Tool call result from backend
          setTurns((prev) => {
            const last = prev[prev.length - 1];
            if (last?.role === 'assistant') {
              const toolCalls = [
                ...(last.toolCalls ?? []),
                data as { tool: string; args: Record<string, unknown>; result?: string; error?: string },
              ];
              return [{ ...last, toolCalls }];
            }
            return prev;
          });
        } else if (data.type === 'error') {
          const err = new Error((data.detail as string) || 'Unknown error');
          pendingReject.current?.(err);
          pendingReject.current = null;
          pendingResolve.current = null;
          setStatus('error');
        }
      } catch {
        // ignore parse errors
      }
    };

    ws.onerror = () => {
      setStatus('error');
    };

    ws.onclose = () => {
      setStatus('disconnected');
      wsRef.current = null;
      // Auto-reconnect
      reconnectTimer.current = setTimeout(connect, RECONNECT_DELAY);
    };
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const sendMessage = useCallback(
    async (text: string) => {
      const userTurn: AgentTurn = {
        role: 'user',
        message: text,
        timestamp: Date.now(),
      };
      setTurns((prev) => [...prev, userTurn]);

      // Start assistant turn
      setTurns((prev) => [
        ...prev,
        {
          role: 'assistant',
          message: '',
          toolCalls: [],
          timestamp: Date.now(),
        },
      ]);

      const ws = wsRef.current;
      if (!ws || ws.readyState !== WebSocket.OPEN) {
        connect();
        // Wait for connection then send
        await new Promise<void>((resolve) => {
          const check = setInterval(() => {
            if (wsRef.current?.readyState === WebSocket.OPEN) {
              clearInterval(check);
              resolve();
            }
          }, 200);
        });
        wsRef.current.send(JSON.stringify({
          type: 'message',
          text,
          user_id: selectedUserId,
        }));
      } else {
        ws.send(JSON.stringify({
          type: 'message',
          text,
          user_id: selectedUserId,
        }));
      }
    },
    [selectedUserId, connect],
  );

  const selectPlace = useCallback(
    async (place: ScoredPlace) => {
      const msg = `Tôi chọn quán số: ${place.name}`;
      await sendMessage(msg);
    },
    [sendMessage],
  );

  const reset = useCallback(() => {
    setTurns([]);
    setLastPlaces([]);
  }, []);

  // Cleanup on unmount
  // (not using useEffect to avoid rule of hooks issues in custom hook)

  return {
    status,
    turns,
    lastPlaces,
    selectedUserId,
    setSelectedUserId,
    sendMessage,
    selectPlace,
    reset,
    users: MOCK_USERS,
  };
}
