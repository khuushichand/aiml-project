import { renderHook, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const authStorageMocks = vi.hoisted(() => ({
  setRuntimeApiBearer: vi.fn(),
  setRuntimeApiKey: vi.fn(),
}));

vi.mock('@web/lib/authStorage', () => authStorageMocks);

describe('useConfig networking', () => {
  beforeEach(() => {
    vi.resetModules();
    vi.clearAllMocks();
    localStorage.clear();
    vi.unstubAllGlobals();
    delete process.env.NEXT_PUBLIC_API_URL;
    delete process.env.NEXT_PUBLIC_API_BASE_URL;
    delete process.env.NEXT_PUBLIC_API_VERSION;
    delete process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE;
  });

  it('keeps a relative /api/v1 base in quickstart mode', async () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = 'quickstart';

    const apiModule = await import('@web/lib/api');
    const { ConfigProvider, useConfig } = await import('@web/hooks/useConfig');

    const { result } = renderHook(() => useConfig(), {
      wrapper: ({ children }) => <ConfigProvider>{children}</ConfigProvider>,
    });

    await waitFor(() => {
      expect(apiModule.getApiBaseUrl()).toBe('/api/v1');
    });

    expect(result.current.config.apiVersion).toBe('v1');
  });

  it('does not let a stored absolute host override quickstart mode', async () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = 'quickstart';
    localStorage.setItem('tldw-api-host', 'http://127.0.0.1:8000');

    const apiModule = await import('@web/lib/api');
    const { ConfigProvider, useConfig } = await import('@web/hooks/useConfig');

    renderHook(() => useConfig(), {
      wrapper: ({ children }) => <ConfigProvider>{children}</ConfigProvider>,
    });

    await waitFor(() => {
      expect(apiModule.getApiBaseUrl()).toBe('/api/v1');
    });

    expect(localStorage.getItem('tldw-api-host')).not.toBe('http://127.0.0.1:8000');
  });

  it('fetches docs-info from the quickstart same-origin api root', async () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = 'quickstart';

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { ConfigProvider, useConfig } = await import('@web/hooks/useConfig');

    const { result } = renderHook(() => useConfig(), {
      wrapper: ({ children }) => <ConfigProvider>{children}</ConfigProvider>,
    });

    await result.current.reloadBootstrapConfig();

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/config/docs-info', {
      credentials: 'omit',
    });
  });

  it('pins quickstart docs-info fetches to api v1 even when a different version is stored', async () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = 'quickstart';
    localStorage.setItem('tldw-api-version', 'v9');

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { ConfigProvider, useConfig } = await import('@web/hooks/useConfig');

    const { result } = renderHook(() => useConfig(), {
      wrapper: ({ children }) => <ConfigProvider>{children}</ConfigProvider>,
    });

    await result.current.reloadBootstrapConfig();

    expect(fetchMock).toHaveBeenCalledWith('/api/v1/config/docs-info', {
      credentials: 'omit',
    });
  });

  it('fetches docs-info from the advanced api origin', async () => {
    process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE = 'advanced';
    process.env.NEXT_PUBLIC_API_URL = 'https://api.example.test';

    const fetchMock = vi.fn().mockResolvedValue({
      ok: true,
      json: async () => ({}),
    });
    vi.stubGlobal('fetch', fetchMock);

    const { ConfigProvider, useConfig } = await import('@web/hooks/useConfig');

    const { result } = renderHook(() => useConfig(), {
      wrapper: ({ children }) => <ConfigProvider>{children}</ConfigProvider>,
    });

    await result.current.reloadBootstrapConfig();

    expect(fetchMock).toHaveBeenCalledWith('https://api.example.test/api/v1/config/docs-info', {
      credentials: 'omit',
    });
  });
});
