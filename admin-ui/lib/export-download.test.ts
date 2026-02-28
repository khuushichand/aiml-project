/* @vitest-environment jsdom */
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { downloadExportFile, getFilenameFromDisposition } from './export-download';

vi.mock('@/lib/api-config', () => ({
  buildApiUrl: (endpoint: string) => `https://api.example.test${endpoint}`,
}));

vi.mock('@/lib/http', () => ({
  buildAuthHeaders: () => ({
    Authorization: 'Bearer test-token',
  }),
}));

describe('export-download', () => {
  const fetchMock = vi.fn<typeof fetch>();
  const createObjectURLMock = vi.fn(() => 'blob:download');
  const revokeObjectURLMock = vi.fn();

  beforeEach(() => {
    vi.stubGlobal('fetch', fetchMock);
    Object.defineProperty(window.URL, 'createObjectURL', {
      configurable: true,
      value: createObjectURLMock,
    });
    Object.defineProperty(window.URL, 'revokeObjectURL', {
      configurable: true,
      value: revokeObjectURLMock,
    });
    vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {});
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  it('parses filename and filename* content-disposition values', () => {
    expect(getFilenameFromDisposition('attachment; filename="users.csv"')).toBe('users.csv');
    expect(getFilenameFromDisposition("attachment; filename*=UTF-8''usage%20report.csv")).toBe('usage report.csv');
    expect(getFilenameFromDisposition(null)).toBeNull();
  });

  it('downloads using filename from content-disposition header', async () => {
    fetchMock.mockResolvedValue(new Response('csv-data', {
      status: 200,
      headers: {
        'content-disposition': "attachment; filename*=UTF-8''usage%20report.csv",
      },
    }));
    const appendSpy = vi.spyOn(document.body, 'appendChild');
    await downloadExportFile({
      endpoint: '/admin/usage/daily/export.csv',
      params: { start: '2026-02-01', end: '2026-02-15' },
      fallbackFilename: 'fallback.csv',
    });

    expect(fetchMock).toHaveBeenCalledWith(
      'https://api.example.test/admin/usage/daily/export.csv?start=2026-02-01&end=2026-02-15',
      expect.objectContaining({
        credentials: 'include',
        headers: { Authorization: 'Bearer test-token' },
      }),
    );
    expect(HTMLAnchorElement.prototype.click).toHaveBeenCalledTimes(1);
    const anchor = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe('usage report.csv');
    expect(createObjectURLMock).toHaveBeenCalledTimes(1);
    expect(revokeObjectURLMock).toHaveBeenCalledWith('blob:download');
  });

  it('falls back to provided filename when content-disposition is missing', async () => {
    fetchMock.mockResolvedValue(new Response('csv-data', { status: 200 }));
    const appendSpy = vi.spyOn(document.body, 'appendChild');

    await downloadExportFile({
      endpoint: '/admin/users/export',
      params: {},
      fallbackFilename: 'users.csv',
    });

    const anchor = appendSpy.mock.calls[0]?.[0] as HTMLAnchorElement;
    expect(anchor.download).toBe('users.csv');
  });

  it('throws timeout error when fetch aborts by timeout', async () => {
    vi.useFakeTimers();
    fetchMock.mockImplementation((_url: string | URL | Request, init?: RequestInit) => {
      return new Promise((_resolve, reject) => {
        const signal = init?.signal;
        if (signal) {
          signal.addEventListener('abort', () => {
            reject(new DOMException('Aborted', 'AbortError'));
          }, { once: true });
        }
      });
    });

    const downloadPromise = downloadExportFile({
      endpoint: '/admin/audit-log/export',
      params: {},
      fallbackFilename: 'audit.csv',
      timeoutMs: 10,
    });

    const assertion = expect(downloadPromise).rejects.toThrow('Download aborted: timeout');
    await vi.advanceTimersByTimeAsync(10);
    await assertion;
  });

  it('throws response body text when the server responds with an error', async () => {
    fetchMock.mockResolvedValue(new Response('service unavailable', { status: 503 }));

    await expect(downloadExportFile({
      endpoint: '/admin/usage/top/export.csv',
      params: {},
      fallbackFilename: 'usage_top.csv',
    })).rejects.toThrow('service unavailable');
  });
});
