import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('rate limiter', () => {
  beforeEach(() => {
    vi.useFakeTimers();
    vi.resetModules();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it('allows requests under the limit', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      expect(checkRateLimit('127.0.0.1').allowed).toBe(true);
    }
  });

  it('blocks requests over the limit', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      checkRateLimit('127.0.0.1');
    }
    const result = checkRateLimit('127.0.0.1');
    expect(result.allowed).toBe(false);
    expect(result.retryAfterSeconds).toBeGreaterThan(0);
  });

  it('resets after the window expires', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      checkRateLimit('127.0.0.1');
    }
    expect(checkRateLimit('127.0.0.1').allowed).toBe(false);
    vi.advanceTimersByTime(61_000);
    expect(checkRateLimit('127.0.0.1').allowed).toBe(true);
  });

  it('tracks different IPs independently', async () => {
    const { checkRateLimit } = await import('../rate-limiter');
    for (let i = 0; i < 10; i++) {
      checkRateLimit('1.1.1.1');
    }
    expect(checkRateLimit('1.1.1.1').allowed).toBe(false);
    expect(checkRateLimit('2.2.2.2').allowed).toBe(true);
  });
});
