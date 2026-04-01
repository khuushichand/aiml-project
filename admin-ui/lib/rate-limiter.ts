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
 * Extract client IP with an explicit proxy trust model.
 * Only reads x-forwarded-for / x-real-ip when TRUST_PROXY_HEADERS=true.
 * Without a trusted proxy, all clients share the 'unknown' bucket —
 * deploy behind a reverse proxy (nginx, traefik, etc.) for per-IP limiting.
 */
export function extractClientIp(headers: {
  get(name: string): string | null;
}): string {
  if (process.env.TRUST_PROXY_HEADERS === 'true') {
    const forwarded = headers.get('x-forwarded-for')?.split(',')[0]?.trim();
    if (forwarded) return forwarded;
    const realIp = headers.get('x-real-ip');
    if (realIp) return realIp;
  }
  return 'unknown';
}

export function checkRateLimit(ip: string): {
  allowed: boolean;
  retryAfterSeconds?: number;
} {
  const now = Date.now();
  if (Math.random() < 0.01) pruneStore();

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
