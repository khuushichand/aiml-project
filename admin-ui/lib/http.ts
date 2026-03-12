import { getApiKey, logout } from './auth';

export class ApiError extends Error {
  status: number;
  detail?: unknown;

  constructor(status: number, message: string, detail?: unknown) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.detail = detail;
  }
}

type ResponseType = 'json' | 'text' | 'blob';

export const buildProxyUrl = (endpoint: string): string => {
  if (!endpoint) return '/api/proxy';
  return `/api/proxy${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};

export const buildAuthHeaders = (): Record<string, string> => {
  const headers: Record<string, string> = {};

  const apiKey = getApiKey();
  if (apiKey) {
    headers['X-API-KEY'] = apiKey;
  }

  return headers;
};

const toApiErrorMessage = (detail: unknown): string => {
  if (!detail) return 'Request failed';
  if (typeof detail === 'string') return detail;
  if (detail && typeof detail === 'object') {
    const record = detail as { detail?: unknown; message?: unknown };
    if (typeof record.detail === 'string') return record.detail;
    if (typeof record.message === 'string') return record.message;
  }
  return 'Request failed';
};

const buildRequestHeaders = (method: string, overrides?: HeadersInit): Headers => {
  const headers = new Headers(buildAuthHeaders());
  if (overrides) {
    const overrideHeaders = new Headers(overrides);
    overrideHeaders.forEach((value, key) => {
      headers.set(key, value);
    });
  }
  return headers;
};

const requestRaw = async <T>(
  endpoint: string,
  responseType: ResponseType,
  options: RequestInit = {}
): Promise<T> => {
  const method = options.method || 'GET';
  const headers = buildRequestHeaders(method, options.headers);

  if (responseType === 'json' && typeof options.body === 'string' && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(buildProxyUrl(endpoint), {
    ...options,
    headers,
    credentials: 'include',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Request failed' }));

    if (response.status === 401 && typeof window !== 'undefined') {
      await logout();
      if (!window.location.pathname.startsWith('/login')) {
        window.location.href = '/login';
      }
    }

    if (response.status === 403) {
      const detail = (error as { detail?: unknown })?.detail || '';
      if (typeof detail === 'string' && detail.toLowerCase().includes('csrf')) {
        throw new ApiError(
          response.status,
          'CSRF validation failed. Please refresh the page and try again.',
          error
        );
      }
    }

    throw new ApiError(response.status, toApiErrorMessage(error), error);
  }

  if (responseType === 'text') {
    return response.text() as Promise<T>;
  }

  if (responseType === 'blob') {
    return response.blob() as Promise<T>;
  }

  const text = await response.text();
  if (!text) return {} as T;
  return JSON.parse(text);
};

export const requestJson = async <T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> => requestRaw<T>(endpoint, 'json', options);

export const requestText = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<string> => requestRaw<string>(endpoint, 'text', options);

export const requestBlob = async (
  endpoint: string,
  options: RequestInit = {}
): Promise<Blob> => requestRaw<Blob>(endpoint, 'blob', options);
