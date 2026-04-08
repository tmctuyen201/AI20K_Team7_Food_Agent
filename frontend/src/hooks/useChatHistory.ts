import { useState, useCallback, useEffect } from "react";
import type { ChatSession, AgentVersion } from "../types";

const STORAGE_KEY = "foodie_chat_sessions";
const MAX_SESSIONS = 50;

export function useChatHistory() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);

  // Load from localStorage on mount
  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) {
        setSessions(JSON.parse(raw) as ChatSession[]);
      }
    } catch {
      // ignore parse errors
    }
  }, []);

  // Persist to localStorage on change
  useEffect(() => {
    try {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(sessions));
    } catch {
      // ignore storage errors
    }
  }, [sessions]);

  const saveSession = useCallback((session: ChatSession) => {
    setSessions((prev) => {
      const existing = prev.findIndex((s) => s.id === session.id);
      let updated: ChatSession[];
      if (existing >= 0) {
        updated = [...prev];
        updated[existing] = session;
      } else {
        updated = [session, ...prev];
      }
      // Prune to MAX_SESSIONS
      return updated.slice(0, MAX_SESSIONS);
    });
  }, []);

  const deleteSession = useCallback((id: string) => {
    setSessions((prev) => prev.filter((s) => s.id !== id));
  }, []);

  const createSession = useCallback(
    (user_id: string, model: string, version: AgentVersion): ChatSession => {
      return {
        id: `sess_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`,
        user_id,
        model,
        version,
        title: "",
        preview: "",
        turns: [],
        created_at: Date.now(),
        updated_at: Date.now(),
      };
    },
    [],
  );

  const updateSession = useCallback(
    (id: string, updates: Partial<ChatSession>) => {
      setSessions((prev) =>
        prev.map((s) => (s.id === id ? { ...s, ...updates, updated_at: Date.now() } : s)),
      );
    },
    [],
  );

  return { sessions, saveSession, deleteSession, createSession, updateSession };
}
