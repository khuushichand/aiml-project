import axios, { AxiosError, AxiosInstance } from 'axios';
import { addRequestHistory } from '@/lib/history';

// Resolve API base URL with sensible defaults
const apiHost = process.env.NEXT_PUBLIC_API_URL || 'http://127.0.0.1:8000';
const apiVersion = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const baseURL = `${apiHost.replace(/\/$/, '')}/api/${apiVersion}`;

// Read cookie value on client
function getCookie(name: string): string | null {
  if (typeof document === 'undefined') return null;
  const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
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
  (config) => {
    // Attach metadata for timing
    (config as any).metadata = { start: Date.now() };
    if (typeof window !== 'undefined') {
      // Bearer token (multi-user JWT auth)
      const token = localStorage.getItem('access_token');
      if (token) {
        (config.headers as any).Authorization = `Bearer ${token}`;
      }

      // Static API auth options via env or localStorage
      const envApiKey = process.env.NEXT_PUBLIC_X_API_KEY;
      const envApiBearer = process.env.NEXT_PUBLIC_API_BEARER;
      const storedApiKey = localStorage.getItem('x_api_key');

      // Prefer explicit API bearer if provided (for chat module API_BEARER)
      if (envApiBearer && !(config.headers as any).Authorization) {
        (config.headers as any).Authorization = `Bearer ${envApiBearer}`;
      }

      // X-API-KEY (single-user mode convenience)
      const xApiKey = storedApiKey || envApiKey;
      if (xApiKey) {
        (config.headers as any)['X-API-KEY'] = xApiKey;
      }

      // CSRF token for modifying requests when not using X-API-KEY auth
      const method = (config.method || 'get').toUpperCase();
      const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(method) && !xApiKey;
      if (needsCsrf) {
        const csrf = getCookie('csrf_token');
        if (csrf) {
          (config.headers as any)['X-CSRF-Token'] = csrf;
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
      const cfg: any = response.config || {};
      const start = cfg.metadata?.start || Date.now();
      const duration = Date.now() - start;
      addRequestHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        method: (response.config.method || 'get').toUpperCase(),
        url: response.config.url || '',
        baseURL: (response.config as any).baseURL || api.defaults.baseURL,
        status: response.status,
        ok: response.status >= 200 && response.status < 300,
        duration_ms: duration,
        timestamp: new Date().toISOString(),
        requestHeaders: (response.config.headers as any) || undefined,
        requestBody: (response.config as any).data,
        responseBody: response.data,
      });
    } catch {}
    return response;
  },
  async (error: AxiosError) => {
    try {
      const cfg: any = error.config || {};
      const start = cfg.metadata?.start || Date.now();
      const duration = Date.now() - start;
      addRequestHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        method: (cfg.method || 'get').toUpperCase(),
        url: cfg.url || '',
        baseURL: (cfg as any).baseURL || api.defaults.baseURL,
        status: error.response?.status,
        ok: false,
        duration_ms: duration,
        timestamp: new Date().toISOString(),
        requestHeaders: (cfg.headers as any) || undefined,
        requestBody: (cfg as any).data,
        responseBody: error.response?.data,
        errorMessage: (error.response?.data as any)?.detail || error.message,
      });
    } catch {}
    if (error.response?.status === 401) {
      if (typeof window !== 'undefined') {
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
        // Redirect to login only if not using env-based API auth
        const hasEnvAuth = !!(process.env.NEXT_PUBLIC_X_API_KEY || process.env.NEXT_PUBLIC_API_BEARER);
        if (!hasEnvAuth) window.location.href = '/login';
      }
    }
    if (error.response?.status === 403) {
      // Likely CSRF failure for modifying request
      const detail = (error.response.data as any)?.detail;
      if (detail && typeof detail === 'string' && detail.toLowerCase().includes('csrf')) {
        return Promise.reject(new Error('CSRF validation failed. Refresh the page and try again.'));
      }
    }

    const message =
      (error.response?.data as any)?.detail ||
      (error.response?.data as any)?.message ||
      error.message ||
      'An unexpected error occurred';

    return Promise.reject(new Error(message));
  }
);

// Helper functions for common HTTP methods
export const apiClient = {
  get: <T = any>(url: string, config?: any) => api.get<T>(url, config).then((res) => res.data),
  post: <T = any>(url: string, data?: any, config?: any) => api.post<T>(url, data, config).then((res) => res.data),
  put: <T = any>(url: string, data?: any, config?: any) => api.put<T>(url, data, config).then((res) => res.data),
  delete: <T = any>(url: string, config?: any) => api.delete<T>(url, config).then((res) => res.data),
  patch: <T = any>(url: string, data?: any, config?: any) => api.patch<T>(url, data, config).then((res) => res.data),
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

    const envApiBearer = process.env.NEXT_PUBLIC_API_BEARER;
    if (envApiBearer && !headers['Authorization']) {
      headers['Authorization'] = `Bearer ${envApiBearer}`;
    }

    const storedApiKey = localStorage.getItem('x_api_key');
    const envApiKey = process.env.NEXT_PUBLIC_X_API_KEY;
    const xApiKey = storedApiKey || envApiKey;
    if (xApiKey) headers['X-API-KEY'] = xApiKey;

    // CSRF for modifying requests when not using X-API-KEY
    const methodUp = method.toUpperCase();
    const needsCsrf = ['POST', 'PUT', 'PATCH', 'DELETE'].includes(methodUp) && !xApiKey;
    if (needsCsrf) {
      const cookie = (name: string): string | null => {
        const match = document.cookie.match(new RegExp('(?:^|; )' + name.replace(/([.$?*|{}()\[\]\\\/\+^])/g, '\\$1') + '=([^;]*)'));
        return match ? decodeURIComponent(match[1]) : null;
      };
      const csrf = cookie('csrf_token');
      if (csrf) headers['X-CSRF-Token'] = csrf;
    }
  }

  return headers;
}
