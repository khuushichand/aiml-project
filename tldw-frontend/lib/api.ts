import axios, { AxiosError, AxiosInstance, AxiosRequestConfig, InternalAxiosRequestConfig } from 'axios';
import { addRequestHistory } from '@/lib/history';
import { getApiBearer, getApiKey } from '@/lib/authStorage';
import type { AxiosConfigWithMetadata, ApiErrorResponse } from '@/types/common';

// Custom error type that preserves HTTP status and retry hints while remaining compatible with Error
export class ApiError extends Error {
  status?: number;
  statusCode?: number;
  detail?: string;
  retryAfter?: number;

  constructor(message: string, options?: { status?: number; detail?: string; retryAfter?: number }) {
    super(message);
    this.name = 'ApiError';
    if (options?.status !== undefined) {
      this.status = options.status;
      this.statusCode = options.status;
    }
    if (options?.detail !== undefined) {
      this.detail = options.detail;
    }
    if (options?.retryAfter !== undefined) {
      this.retryAfter = options.retryAfter;
    }
  }
}

// Resolve API base URL with sensible defaults
const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const apiVersion = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const baseURL = `${apiHost.replace(/\/$/, '')}/api/${apiVersion}`;

// Read cookie value on client
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
  return match ? decodeURIComponent(match[1]) : null;
}

// Create axios instance with base configuration
const api: AxiosInstance = axios.create({
  baseURL,
  headers: {
    'Content-Type': 'application/json',
  },
  withCredentials: true, // include cookies for CSRF protection when needed
  timeout: 30000, // 30 second timeout
});

// Request interceptor to add auth and CSRF headers
api.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    // Attach metadata for timing
    (config as AxiosConfigWithMetadata).metadata = { start: Date.now() };
    if (typeof window !== 'undefined') {
      // Bearer token (multi-user JWT auth)
      const token = localStorage.getItem('access_token');
      if (token) {
        config.headers.set('Authorization', `Bearer ${token}`);
      }

      // Static API auth options via env or localStorage
      // Prefer explicit API bearer if provided (for chat module API_BEARER)
      const apiBearer = getApiBearer();
      if (apiBearer && !config.headers.get('Authorization')) {
        config.headers.set('Authorization', `Bearer ${apiBearer}`);
      }

      // X-API-KEY (single-user mode convenience)
      const xApiKey = getApiKey();
      if (xApiKey) {
        config.headers.set('X-API-KEY', xApiKey);
      }

      // CSRF token for modifying requests when not using X-API-KEY auth
      const method = (config.method || 'get').toUpperCase();
      const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !xApiKey;
      if (needsCsrf) {
        const csrf = getCookie('csrf_token');
        if (csrf) {
          config.headers.set('X-CSRF-Token', csrf);
        }
      }
    }
    return config;
  },
  (error) => Promise.reject(error)
);

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    try {
      const cfg = response.config as AxiosConfigWithMetadata;
      const start = cfg.metadata?.start || Date.now();
      const duration = Date.now() - start;
      addRequestHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        method: (response.config.method || 'get').toUpperCase(),
        url: response.config.url || '',
        baseURL: response.config.baseURL || api.defaults.baseURL,
        status: response.status,
        ok: response.status >= 200 && response.status < 300,
        duration_ms: duration,
        timestamp: new Date().toISOString(),
        requestHeaders: response.config.headers as Record<string, string> | undefined,
        requestBody: response.config.data as unknown,
        responseBody: response.data as unknown,
      });
    } catch {
      // Silently ignore history logging errors to not disrupt API responses
    }
    return response;
  },
  async (error: AxiosError<ApiErrorResponse>) => {
    try {
      const cfg = (error.config || {}) as AxiosConfigWithMetadata;
      const start = cfg.metadata?.start || Date.now();
      const duration = Date.now() - start;
      addRequestHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        method: (cfg.method || 'get').toUpperCase(),
        url: cfg.url || '',
        baseURL: cfg.baseURL || api.defaults.baseURL,
        status: error.response?.status,
        ok: false,
        duration_ms: duration,
        timestamp: new Date().toISOString(),
        requestHeaders: cfg.headers as Record<string, string> | undefined,
        requestBody: cfg.data as unknown,
        responseBody: error.response?.data as unknown,
        errorMessage: error.response?.data?.detail || error.message,
      });
    } catch {
      // Silently ignore history logging errors to not disrupt error handling
    }

    const status = error.response?.status;
    if (status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        // Redirect to login only if not using env-based API auth
        const hasEnvAuth = !!(process.env.NEXT_PUBLIC_X_API_KEY || process.env.NEXT_PUBLIC_API_BEARER);
        const hasStoredAuth = !!(getApiKey() || getApiBearer());
        if (!hasEnvAuth && !hasStoredAuth) window.location.href = '/login';
      }
    }
    if (status === 403) {
      // Likely CSRF failure for modifying request
      const detail = error.response?.data?.detail;
      if (detail && typeof detail === 'string' && detail.toLowerCase().includes('csrf')) {
        return Promise.reject(new Error('CSRF validation failed. Refresh the page and try again.'));
      }
    }

    const data = (error.response?.data || {}) as ApiErrorResponse;
    const detail = data.detail || data.message;
    const retryAfterHeader = error.response?.headers?.['retry-after'];
    const retryAfter =
      typeof retryAfterHeader === 'string' ? parseInt(retryAfterHeader, 10) || undefined : undefined;
    const message =
      detail ||
      error.message ||
      'An unexpected error occurred';

    const apiError = new ApiError(message, {
      status,
      detail,
      retryAfter,
    });

    return Promise.reject(apiError);
  }
);

// Helper functions for common HTTP methods
export const apiClient = {
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  get: <T = any>(url: string, config?: AxiosRequestConfig) => api.get<T>(url, config).then((res) => res.data),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  post: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => api.post<T>(url, data, config).then((res) => res.data),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  put: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => api.put<T>(url, data, config).then((res) => res.data),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  delete: <T = any>(url: string, config?: AxiosRequestConfig) => api.delete<T>(url, config).then((res) => res.data),
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  patch: <T = any>(url: string, data?: unknown, config?: AxiosRequestConfig) => api.patch<T>(url, data, config).then((res) => res.data),
};

export default api;

// Streaming helpers
export const API_BASE_URL = baseURL;

export function getApiBaseUrl(): string {
  return api.defaults.baseURL || API_BASE_URL;
}

export function buildAuthHeaders(method: string = 'GET', contentType?: string): Record<string, string> {
  const headers: Record<string, string> = {};
  if (contentType) headers['Content-Type'] = contentType;

  if (typeof window !== 'undefined') {
    const token = localStorage.getItem('access_token');
    if (token) headers['Authorization'] = `Bearer ${token}`;

    const apiBearer = getApiBearer();
    if (apiBearer && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${apiBearer}`;
    }

    const xApiKey = getApiKey();
    if (xApiKey) headers['X-API-KEY'] = xApiKey;

    // CSRF for modifying requests when not using X-API-KEY
    const methodUp = method.toUpperCase();
    const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(methodUp) && !xApiKey;
    if (needsCsrf) {
      const cookie = (name: string): string | null => {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()[\]\\/+^])/g, '\\$1') + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : null;
      };
      const csrf = cookie('csrf_token');
      if (csrf) headers['X-CSRF-Token'] = csrf;
    }
  }

  return headers;
}
