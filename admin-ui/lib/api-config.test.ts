import { describe, expect, it, vi } from 'vitest';

describe('buildApiUrlForRequest', () => {
  it('maps the single-user real-backend UI port to the single-user backend port in e2e mode', async () => {
    vi.resetModules();
    process.env.TLDW_ADMIN_E2E_REAL_BACKEND = 'true';
    process.env.NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8101';

    const { buildApiUrlForRequest } = await import('./api-config');

    expect(
      buildApiUrlForRequest(
        { url: 'http://127.0.0.1:3102/login' },
        '/users/me',
      ),
    ).toBe('http://127.0.0.1:8102/api/v1/users/me');
  });

  it('falls back to the configured API host when real-backend e2e mode is disabled', async () => {
    vi.resetModules();
    delete process.env.TLDW_ADMIN_E2E_REAL_BACKEND;
    process.env.NEXT_PUBLIC_API_URL = 'http://127.0.0.1:8101';

    const { buildApiUrlForRequest } = await import('./api-config');

    expect(
      buildApiUrlForRequest(
        { url: 'http://127.0.0.1:3102/login' },
        '/users/me',
      ),
    ).toBe('http://127.0.0.1:8101/api/v1/users/me');
  });
});
