import type { NextApiRequest, NextApiResponse } from 'next';

export const ACCESS_TOKEN_COOKIE = 'tldw_access_token';
export const REFRESH_TOKEN_COOKIE = 'tldw_refresh_token';
export const SESSION_MARKER_COOKIE = 'tldw_session';
export const AUTH_MODE_COOKIE = 'tldw_auth_mode';

type CookieDefinition = {
  name: string;
  value: string;
  httpOnly: boolean;
  sameSite: 'Lax';
  secure: boolean;
  path: '/';
  maxAge?: number;
};

type HostedSessionCookies = {
  access: CookieDefinition;
  refresh: CookieDefinition;
  session: CookieDefinition;
  authMode: CookieDefinition;
};

const isSecureCookie = (): boolean => process.env.NODE_ENV === 'production';

const buildHttpOnlyCookie = (
  name: string,
  value: string,
  maxAge?: number,
): CookieDefinition => ({
  name,
  value,
  httpOnly: true,
  sameSite: 'Lax',
  secure: isSecureCookie(),
  path: '/',
  ...(typeof maxAge === 'number' ? { maxAge } : {}),
});

const buildMarkerCookie = (
  name: string,
  value: string,
  maxAge?: number,
): CookieDefinition => ({
  name,
  value,
  httpOnly: false,
  sameSite: 'Lax',
  secure: isSecureCookie(),
  path: '/',
  ...(typeof maxAge === 'number' ? { maxAge } : {}),
});

const serializeCookie = (cookie: CookieDefinition): string => {
  const parts = [
    `${cookie.name}=${encodeURIComponent(cookie.value)}`,
    `Path=${cookie.path}`,
    `SameSite=${cookie.sameSite}`,
  ];

  if (typeof cookie.maxAge === 'number') {
    parts.push(`Max-Age=${cookie.maxAge}`);
  }
  if (cookie.httpOnly) {
    parts.push('HttpOnly');
  }
  if (cookie.secure) {
    parts.push('Secure');
  }

  return parts.join('; ');
};

const getExistingSetCookieHeader = (
  response: NextApiResponse,
): string[] => {
  const existing = response.getHeader('Set-Cookie');
  if (!existing) {
    return [];
  }
  if (Array.isArray(existing)) {
    return existing.map((value) => String(value));
  }
  return [String(existing)];
};

const appendResponseCookies = (
  response: NextApiResponse,
  cookies: CookieDefinition[],
): void => {
  response.setHeader('Set-Cookie', [
    ...getExistingSetCookieHeader(response),
    ...cookies.map(serializeCookie),
  ]);
};

const readHeaderValue = (
  request: NextApiRequest,
  name: string,
): string | null => {
  const rawValue = request.headers[name.toLowerCase()] ?? request.headers[name];
  if (Array.isArray(rawValue)) {
    return rawValue[0] || null;
  }
  return typeof rawValue === 'string' ? rawValue : null;
};

const parseCookieHeader = (value?: string | null): Record<string, string> => {
  if (!value) {
    return {};
  }

  return value
    .split(';')
    .map((chunk) => chunk.trim())
    .filter(Boolean)
    .reduce<Record<string, string>>((acc, chunk) => {
      const [name, ...rest] = chunk.split('=');
      if (!name) {
        return acc;
      }
      acc[name] = decodeURIComponent(rest.join('=') || '');
      return acc;
    }, {});
};

const readCookieValue = (
  request: NextApiRequest,
  name: string,
): string | null => {
  const cookieValue = request.cookies?.[name];
  if (typeof cookieValue === 'string' && cookieValue.trim()) {
    return cookieValue.trim();
  }

  const parsedCookies = parseCookieHeader(readHeaderValue(request, 'cookie'));
  const parsedValue = parsedCookies[name];
  return typeof parsedValue === 'string' && parsedValue.trim()
    ? parsedValue.trim()
    : null;
};

export const buildHostedSessionCookies = (payload: {
  accessToken: string;
  refreshToken?: string;
  expiresIn?: number;
}): HostedSessionCookies => ({
  access: buildHttpOnlyCookie(
    ACCESS_TOKEN_COOKIE,
    payload.accessToken,
    payload.expiresIn,
  ),
  refresh: buildHttpOnlyCookie(
    REFRESH_TOKEN_COOKIE,
    payload.refreshToken || '',
  ),
  session: buildMarkerCookie(
    SESSION_MARKER_COOKIE,
    '1',
    payload.expiresIn,
  ),
  authMode: buildMarkerCookie(
    AUTH_MODE_COOKIE,
    'jwt',
    payload.expiresIn,
  ),
});

export const clearHostedSessionCookies = (): HostedSessionCookies => ({
  access: buildHttpOnlyCookie(ACCESS_TOKEN_COOKIE, '', 0),
  refresh: buildHttpOnlyCookie(REFRESH_TOKEN_COOKIE, '', 0),
  session: buildMarkerCookie(SESSION_MARKER_COOKIE, '', 0),
  authMode: buildMarkerCookie(AUTH_MODE_COOKIE, '', 0),
});

export const setHostedSessionCookies = (
  response: NextApiResponse,
  payload: {
    accessToken: string;
    refreshToken?: string;
    expiresIn?: number;
  },
): void => {
  appendResponseCookies(
    response,
    Object.values(buildHostedSessionCookies(payload)),
  );
};

export const clearHostedSessionOnResponse = (
  response: NextApiResponse,
): void => {
  appendResponseCookies(
    response,
    Object.values(clearHostedSessionCookies()),
  );
};

export const getBackendAuthHeaders = (request: NextApiRequest): Headers => {
  const headers = new Headers();
  const accessToken = readCookieValue(request, ACCESS_TOKEN_COOKIE);

  if (accessToken) {
    headers.set('Authorization', `Bearer ${accessToken}`);
  }

  return headers;
};

export const appendProxyHeaders = (
  request: NextApiRequest,
  headers: Headers,
): void => {
  const passthroughHeaders = [
    'accept',
    'content-type',
    'if-none-match',
    'if-modified-since',
    'range',
  ];

  for (const name of passthroughHeaders) {
    const value = readHeaderValue(request, name);
    if (value) {
      headers.set(name, value);
    }
  }
};

export const getRequestBody = (
  request: NextApiRequest,
): BodyInit | undefined => {
  if (request.method === 'GET' || request.method === 'HEAD') {
    return undefined;
  }

  const body = request.body;
  if (body == null || body === '') {
    return undefined;
  }

  if (
    typeof body === 'string' ||
    body instanceof URLSearchParams ||
    body instanceof Blob ||
    body instanceof FormData ||
    body instanceof ArrayBuffer ||
    ArrayBuffer.isView(body)
  ) {
    return body;
  }

  return JSON.stringify(body);
};

export const readJsonBody = <T>(
  request: NextApiRequest,
): T | null => {
  const body = request.body;
  if (body == null) {
    return null;
  }

  if (typeof body === 'string') {
    try {
      return JSON.parse(body) as T;
    } catch {
      return null;
    }
  }

  if (typeof body === 'object') {
    return body as T;
  }

  return null;
};

export const readRequestContentType = (
  request: NextApiRequest,
): string | null => readHeaderValue(request, 'content-type');

export const readHostedSessionState = (
  request: NextApiRequest,
): {
  accessToken: string | null;
  refreshToken: string | null;
  authMode: string | null;
} => ({
  accessToken: readCookieValue(request, ACCESS_TOKEN_COOKIE),
  refreshToken: readCookieValue(request, REFRESH_TOKEN_COOKIE),
  authMode: readCookieValue(request, AUTH_MODE_COOKIE),
});

export const sanitizeTokenPayload = <T extends Record<string, unknown>>(
  payload: T | null,
): Record<string, unknown> | null => {
  if (!payload) {
    return null;
  }

  const sanitized = { ...payload };
  delete sanitized.access_token;
  delete sanitized.refresh_token;
  return sanitized;
};

export const readBackendJson = async <T>(
  response: Response,
): Promise<T | null> => {
  const contentType = response.headers.get('content-type') || '';

  if (contentType.includes('application/json')) {
    return (await response.json().catch(() => null)) as T | null;
  }

  const text = await response.text().catch(() => '');
  if (!text) {
    return null;
  }

  try {
    return JSON.parse(text) as T;
  } catch {
    return { detail: text } as T;
  }
};

export const setForwardedResponseHeaders = (
  response: Response,
  apiResponse: NextApiResponse,
): void => {
  response.headers.forEach((value, key) => {
    const lowerKey = key.toLowerCase();
    if (
      lowerKey === 'content-length' ||
      lowerKey === 'content-encoding' ||
      lowerKey === 'transfer-encoding' ||
      lowerKey === 'set-cookie'
    ) {
      return;
    }

    apiResponse.setHeader(key, value);
  });
};

export const sendMethodNotAllowed = (
  response: NextApiResponse,
  allowedMethods: string[],
): void => {
  response.setHeader('Allow', allowedMethods.join(', '));
  response.status(405).json({ detail: 'Method not allowed' });
};
