const MAX_REQUESTS = 10;
const WINDOW_MS = 60_000;
const MAX_ENTRIES = 10_000;

const store = new Map<string, number[]>();

function pruneEntry(timestamps: number[], now: number): number[] {
  const cutoff = now - WINDOW_MS;
  return timestamps.filter((t) => t > cutoff);
}

function pruneStore(): void {
  if (store.size <= MAX_ENTRIES) return;
  const now = Date.now();
  for (const [key, timestamps] of store) {
    const active = pruneEntry(timestamps, now);
    if (active.length === 0) {
      store.delete(key);
    } else {
      store.set(key, active);
    }
  }
}

/**
 * Extract client IP from standard proxy headers.
 * Falls back to 'unknown' if no headers present (e.g., direct localhost access).
 */
export function extractClientIp(headers: {
  get(name: string): string | null;
}): string {
  return (
    headers.get('x-forwarded-for')?.split(',')[0]?.trim() ??
    headers.get('x-real-ip') ??
    'unknown'
  );
}

export function checkRateLimit(ip: string): {
  allowed: boolean;
  retryAfterSeconds?: number;
} {
  const now = Date.now();
  pruneStore();

  const timestamps = pruneEntry(store.get(ip) ?? [], now);

  if (timestamps.length >= MAX_REQUESTS) {
    const oldestInWindow = timestamps[0];
    const retryAfterMs = oldestInWindow + WINDOW_MS - now;
    return {
      allowed: false,
      retryAfterSeconds: Math.ceil(Math.max(retryAfterMs, 1000) / 1000),
    };
  }

  timestamps.push(now);
  store.set(ip, timestamps);
  return { allowed: true };
}
