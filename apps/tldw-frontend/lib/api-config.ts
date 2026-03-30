import { buildApiBaseUrl, resolvePublicApiOrigin } from '@web/lib/api-base';

const DEPLOYMENT_ENV = {
  NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE: process.env.NEXT_PUBLIC_TLDW_DEPLOYMENT_MODE,
  NEXT_PUBLIC_API_URL: process.env.NEXT_PUBLIC_API_URL,
};
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';

const resolvePageOrigin = (request?: RequestLike): string | undefined => {
  if (request?.url) {
    try {
      return new URL(request.url).origin;
    } catch {
      return undefined;
    }
  }

  return typeof window !== 'undefined' ? window.location?.origin : undefined;
};

const resolveApiBaseUrl = (request?: RequestLike): string =>
  buildApiBaseUrl(resolvePublicApiOrigin(DEPLOYMENT_ENV, resolvePageOrigin(request)), API_VERSION);

export const API_BASE_URL = resolveApiBaseUrl();

export const buildApiUrl = (endpoint?: string): string => {
  const baseUrl = resolveApiBaseUrl();
  if (!endpoint) {
    return baseUrl;
  }

  return `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};

type RequestLike = {
  url?: string;
};

export const buildApiUrlForRequest = (
  request: RequestLike,
  endpoint?: string,
): string => {
  const baseUrl = resolveApiBaseUrl(request);
  if (!endpoint) {
    return baseUrl;
  }

  return `${baseUrl}${endpoint.startsWith('/') ? endpoint : `/${endpoint}`}`;
};
