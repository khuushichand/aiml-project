const SESSION_STORAGE_KEY = 'tldw-session-id';
export const SESSION_HEADER_NAME = 'X-Session-ID';
const SESSION_ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const SESSION_PREFIX = 'sess_';
const SESSION_TTL_MS = 30 * 24 * 60 * 60 * 1000;

type SessionStorageData = {
  id: string;
  timestamp: number;
};

type StoredSessionResult = {
  data: SessionStorageData;
  fromLegacy: boolean;
};

let cachedSession: SessionStorageData | null = null;

function normalizeSessionId(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed || !SESSION_ID_PATTERN.test(trimmed)) return null;
  return trimmed;
}

function isSessionExpired(timestamp: number): boolean {
  return Date.now() - timestamp > SESSION_TTL_MS;
}

function normalizeSessionData(value: unknown): SessionStorageData | null {
  if (!value) return null;
  if (typeof value === 'string') {
    const id = normalizeSessionId(value);
    if (!id) return null;
    return { id, timestamp: Date.now() };
  }
  if (typeof value !== 'object') return null;
  const record = value as Record<string, unknown>;
  const id = normalizeSessionId(record.id);
  const timestamp = typeof record.timestamp === 'number' ? record.timestamp : Number(record.timestamp);
  if (!id || !Number.isFinite(timestamp)) return null;
  return { id, timestamp };
}

function parseStoredSession(raw: string | null): StoredSessionResult | null {
  if (!raw) return null;
  try {
    const parsed = JSON.parse(raw);
    const normalized = normalizeSessionData(parsed);
    if (normalized) {
      return { data: normalized, fromLegacy: false };
    }
  } catch {}
  const normalized = normalizeSessionData(raw);
  return normalized ? { data: normalized, fromLegacy: true } : null;
}

function persistSession(data: SessionStorageData): void {
  cachedSession = data;
  try {
    localStorage.setItem(SESSION_STORAGE_KEY, JSON.stringify(data));
  } catch {
    // Best-effort storage only.
  }
}

export function readSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  if (cachedSession && !isSessionExpired(cachedSession.timestamp)) {
    return cachedSession.id;
  }
  try {
    const stored = parseStoredSession(localStorage.getItem(SESSION_STORAGE_KEY));
    if (!stored) {
      cachedSession = null;
      return null;
    }
    if (isSessionExpired(stored.data.timestamp)) {
      cachedSession = null;
      localStorage.removeItem(SESSION_STORAGE_KEY);
      return null;
    }
    cachedSession = stored.data;
    if (stored.fromLegacy) {
      persistSession(stored.data);
    }
    return stored.data.id;
  } catch {
    return null;
  }
}

export function writeSessionId(value: unknown): string | null {
  if (typeof window === 'undefined') return null;
  const normalized = normalizeSessionData(value);
  if (!normalized) return null;
  try {
    const existing = parseStoredSession(localStorage.getItem(SESSION_STORAGE_KEY));
    let nextTimestamp = normalized.timestamp;
    if (existing && existing.data.id === normalized.id && !isSessionExpired(existing.data.timestamp)) {
      nextTimestamp = existing.data.timestamp;
    }
    const next = { id: normalized.id, timestamp: nextTimestamp };
    if (!existing || existing.data.id !== next.id || existing.data.timestamp !== next.timestamp) {
      persistSession(next);
    } else {
      cachedSession = next;
    }
  } catch {
    // Best-effort storage only.
  }
  return normalized.id;
}

function generateSessionId(): string | null {
  if (typeof crypto === 'undefined') return null;
  if ('randomUUID' in crypto) {
    return `${SESSION_PREFIX}${crypto.randomUUID()}`;
  }
  if ('getRandomValues' in crypto) {
    const bytes = new Uint8Array(16);
    crypto.getRandomValues(bytes);
    const hex = Array.from(bytes).map((b) => b.toString(16).padStart(2, '0')).join('');
    return `${SESSION_PREFIX}${hex}`;
  }
  return null;
}

export function getOrCreateSessionId(): string | null {
  const existing = readSessionId();
  if (existing) return existing;
  const generated = generateSessionId();
  if (!generated) return null;
  return writeSessionId(generated) || generated;
}

export function captureSessionIdFromHeaders(
  headers: Headers | Record<string, string | string[] | undefined> | null | undefined
): string | null {
  if (!headers) return null;
  let raw: unknown = null;
  if (typeof Headers !== 'undefined' && headers instanceof Headers) {
    raw = headers.get(SESSION_HEADER_NAME) || headers.get(SESSION_HEADER_NAME.toLowerCase());
  } else {
    const record = headers as Record<string, string | string[] | undefined>;
    raw = record[SESSION_HEADER_NAME] || record[SESSION_HEADER_NAME.toLowerCase()];
  }
  if (Array.isArray(raw)) {
    raw = raw[0];
  }
  return writeSessionId(raw);
}

if (typeof window !== 'undefined') {
  window.addEventListener('storage', (event: StorageEvent) => {
    if (event.key !== SESSION_STORAGE_KEY) return;
    const stored = parseStoredSession(event.newValue);
    if (!stored) {
      cachedSession = null;
      return;
    }
    if (isSessionExpired(stored.data.timestamp)) {
      cachedSession = null;
      return;
    }
    cachedSession = stored.data;
  });
}
