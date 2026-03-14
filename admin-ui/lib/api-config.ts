const API_HOST = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const REAL_BACKEND_E2E_PORT_MAP: Record<string, string> = {
  '3101': '8101',
  '3102': '8102',
};

export const API_BASE_URL = `${API_HOST.replace(/\/$/, '')}/api/${API_VERSION}`;

export const buildApiUrl = (endpoint?: string): string => {
  if (!endpoint) return API_BASE_URL;
  return `${API_BASE_URL}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};

type RequestLike = {
  url?: string;
};

const isRealBackendE2eMode = (): boolean =>
  process.env.TLDW_ADMIN_E2E_REAL_BACKEND === 'true';

const getRealBackendApiHost = (request: RequestLike): string | null => {
  if (!isRealBackendE2eMode() || !request.url) {
    return null;
  }

  try {
    const url = new URL(request.url);
    const mappedPort = REAL_BACKEND_E2E_PORT_MAP[url.port];
    if (!mappedPort) {
      return null;
    }
    return `${url.protocol}//${url.hostname}:${mappedPort}`;
  } catch {
    return null;
  }
};

export const buildApiUrlForRequest = (request: RequestLike, endpoint?: string): string => {
  const apiHost = getRealBackendApiHost(request);
  if (!apiHost) {
    return buildApiUrl(endpoint);
  }

  const apiBaseUrl = `${apiHost.replace(/\/$/, '')}/api/${API_VERSION}`;
  if (!endpoint) {
    return apiBaseUrl;
  }
  return `${apiBaseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};
