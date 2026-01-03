import { useCallback, useEffect, useRef, useState } from 'react';

export type SessionItem = { id: string; title: string; model: string; created_at: string };

const STORAGE_KEY = 'tldw-chat-sessions';
const MAX_SESSIONS = 50;

const isSessionItem = (value: unknown): value is SessionItem => {
  if (!value || typeof value !== 'object') return false;
  const record = value as Record<string, unknown>;
  return (
    typeof record.id === 'string'
    && typeof record.title === 'string'
    && typeof record.model === 'string'
    && typeof record.created_at === 'string'
  );
};

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
        const parsed = JSON.parse(stored);
        if (Array.isArray(parsed)) {
          const next = parsed.filter(isSessionItem).slice(0, MAX_SESSIONS);
          if (next.length) {
            setSessions(next);
          }
        }
      }
    } catch {}
  }, []);

  useEffect(() => {
    loadSessions();
  }, [loadSessions]);

  const addSession = useCallback((item: SessionItem) => {
    lastSessionIdRef.current = item.id;
    setSessions((prev) => {
      const existingIndex = prev.findIndex((s) => s.id === item.id);
      if (existingIndex >= 0) {
        const next = [...prev];
        next[existingIndex] = { ...prev[existingIndex], ...item };
        persistSessions(next);
        return next;
      }
      const next = [item, ...prev].slice(0, MAX_SESSIONS);
      persistSessions(next);
      return next;
    });
  }, [persistSessions]);

  const mergeSessions = useCallback((incoming: SessionItem[]) => {
    if (!incoming.length) return;
    const normalized = incoming.filter(isSessionItem);
    if (!normalized.length) return;
    setSessions((prev) => {
      const ids = new Set(prev.map((p) => p.id));
      const incomingById = new Map(normalized.map((item) => [item.id, item]));
      const merged = prev.map((item) => incomingById.get(item.id) ?? item);
      const additions = normalized.filter((item) => !ids.has(item.id));
      const trimmed = [...merged, ...additions].slice(0, MAX_SESSIONS);
      persistSessions(trimmed);
      return trimmed;
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
