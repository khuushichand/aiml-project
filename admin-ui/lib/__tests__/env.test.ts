import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';

describe('env validation', () => {
  const originalEnv = process.env;

  beforeEach(() => {
    vi.resetModules();
    process.env = { ...originalEnv };
  });

  afterEach(() => {
    process.env = originalEnv;
  });

  it('succeeds when NEXT_PUBLIC_API_URL is set', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
    const { validateEnv } = await import('../env');
    expect(() => validateEnv()).not.toThrow();
  });

  it('throws when NEXT_PUBLIC_API_URL is missing', async () => {
    delete process.env.NEXT_PUBLIC_API_URL;
    const { validateEnv } = await import('../env');
    expect(() => validateEnv()).toThrow(/NEXT_PUBLIC_API_URL/);
  });

  it('throws when NEXT_PUBLIC_API_URL is not a valid URL', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'not-a-url';
    const { validateEnv } = await import('../env');
    expect(() => validateEnv()).toThrow();
  });

  it('defaults NEXT_PUBLIC_API_VERSION to v1', async () => {
    process.env.NEXT_PUBLIC_API_URL = 'http://localhost:8000';
    delete process.env.NEXT_PUBLIC_API_VERSION;
    const { validateEnv } = await import('../env');
    const env = validateEnv();
    expect(env.NEXT_PUBLIC_API_VERSION).toBe('v1');
  });
});
