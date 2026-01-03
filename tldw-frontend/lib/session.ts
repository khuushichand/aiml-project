const SESSION_STORAGE_KEY = 'tldw-session-id';
export const SESSION_HEADER_NAME = 'X-Session-ID';
const SESSION_ID_PATTERN = /^[A-Za-z0-9._:-]{1,128}$/;
const SESSION_PREFIX = 'sess_';

function normalizeSessionId(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  if (!trimmed || !SESSION_ID_PATTERN.test(trimmed)) return null;
  return trimmed;
}

export function readSessionId(): string | null {
  if (typeof window === 'undefined') return null;
  try {
    return normalizeSessionId(localStorage.getItem(SESSION_STORAGE_KEY));
  } catch {
    return null;
  }
}

export function writeSessionId(value: unknown): string | null {
  if (typeof window === 'undefined') return null;
  const normalized = normalizeSessionId(value);
  if (!normalized) return null;
  try {
    const existing = localStorage.getItem(SESSION_STORAGE_KEY);
    if (existing !== normalized) {
      localStorage.setItem(SESSION_STORAGE_KEY, normalized);
    }
  } catch {
    // Best-effort storage only.
  }
  return normalized;
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
