import { useCallback, useEffect, useRef, useState } from 'react';

export type SessionItem = { id: string; title: string; model: string; created_at: string };

const STORAGE_KEY = 'tldw-chat-sessions';
const MAX_SESSIONS = 50;

export function useChatSessions() {
  const [sessions, setSessions] = useState<SessionItem[]>([]);
  const lastSessionIdRef = useRef<string | null>(null);

  const persistSessions = useCallback((list: SessionItem[]) => {
    try { localStorage.setItem(STORAGE_KEY, JSON.stringify(list)); } catch {}
  }, []);

  const loadSessions = useCallback(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      if (stored) {
        setSessions(JSON.parse(stored));
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const addSession = useCallback((item: SessionItem) => {
    lastSessionIdRef.current = item.id;
    setSessions((prev) => {
      if (prev.some((s) => s.id === item.id)) return prev;
      const next = [item, ...prev].slice(0, MAX_SESSIONS);
      persistSessions(next);
      return next;
    });
  }, [persistSessions]);

  const mergeSessions = useCallback((incoming: SessionItem[]) => {
    if (!incoming.length) return;
    setSessions((prev) => {
      const ids = new Set(prev.map((p) => p.id));
      const merged = [...prev, ...incoming.filter((m) => !ids.has(m.id))];
      persistSessions(merged);
      return merged;
    });
  }, [persistSessions]);

  const migrateSessionId = useCallback((fromId: string, toId: string) => {
    if (!fromId || !toId || fromId === toId) return;
    setSessions((prev) => {
      const changed = prev.some((s) => s.id === fromId);
      if (!changed) return prev;
      const next = prev.map((s) => (s.id === fromId ? { ...s, id: toId } : s));
      persistSessions(next);
      return next;
    });
    lastSessionIdRef.current = toId;
  }, [persistSessions]);

  return {
    sessions,
    addSession,
    mergeSessions,
    migrateSessionId,
    lastSessionIdRef,
  };
}
