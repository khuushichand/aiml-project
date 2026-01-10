import { NextRequest, NextResponse } from 'next/server';
import { buildApiUrl } from '@/lib/api-config';

const AUTH_COOKIE_NAMES = ['access_token', 'x_api_key', 'x-api-key'] as const;

type AuthTokenKind = 'jwt' | 'apiKey';

const AUTH_CACHE_TTL_MS = 30_000;
const AUTH_NEGATIVE_CACHE_TTL_MS = 5_000;
const MAX_CACHE_SIZE = 500;
const authCache = new Map<string, { ok: boolean; expiresAt: number }>();

const hashToken = async (token: string): Promise<string> => {
  const subtle = globalThis.crypto?.subtle;
  if (!subtle) {
    throw new Error('crypto.subtle unavailable');
  }
  const digest = await subtle.digest('SHA-256', new TextEncoder().encode(token));
  return Array.from(new Uint8Array(digest))
    .map((byte) => byte.toString(16).padStart(2, '0'))
    .join('');
};

const buildAuthCacheKey = async (
  kind: AuthTokenKind,
  token: string
): Promise<string | null> => {
  try {
    const hashedToken = await hashToken(token);
    return `${kind}:${hashedToken}`;
  } catch {
    return null;
  }
};

const pruneExpiredCacheEntries = (): void => {
  const now = Date.now();
  for (const [key, entry] of authCache) {
    if (entry.expiresAt <= now) {
      authCache.delete(key);
    }
  }
};

const enforceCacheSizeLimit = (): void => {
  while (authCache.size > MAX_CACHE_SIZE) {
    const oldestKey = authCache.keys().next().value;
    if (oldestKey === undefined) return;
    authCache.delete(oldestKey);
  }
};

const getCachedAuth = (cacheKey: string): boolean | null => {
  pruneExpiredCacheEntries();
  const cached = authCache.get(cacheKey);
  if (!cached) return null;
  if (cached.expiresAt <= Date.now()) {
    authCache.delete(cacheKey);
    return null;
  }
  authCache.delete(cacheKey);
  authCache.set(cacheKey, cached);
  return cached.ok;
};

const setCachedAuth = (cacheKey: string, ok: boolean, ttlMs: number): void => {
  if (ttlMs <= 0) return;
  pruneExpiredCacheEntries();
  if (authCache.has(cacheKey)) {
    authCache.delete(cacheKey);
  }
  authCache.set(cacheKey, { ok, expiresAt: Date.now() + ttlMs });
  enforceCacheSizeLimit();
};

const safeDecodeCookieValue = (value: string): string => {
  try {
    return decodeURIComponent(value);
  } catch {
    return value;
  }
};

const normalizeToken = (value: string): string => {
  const trimmed = value.trim();
  if (!trimmed) return '';
  return trimmed.replace(/^Bearer\s+/i, '').trim();
};

const BEARER_TOKEN_PATTERN = /^Bearer\s+(\S+)$/i;
const API_KEY_PATTERN = /^[A-Za-z0-9._-]+$/;

const parseBearerHeader = (authorization: string): string | null => {
  const match = authorization.trim().match(BEARER_TOKEN_PATTERN);
  if (!match) return null;
  return match[1];
};

const isValidApiKeyFormat = (apiKey: string): boolean => API_KEY_PATTERN.test(apiKey);

const base64UrlToUint8Array = (input: string): Uint8Array => {
  const padded = input.replace(/-/g, '+').replace(/_/g, '/');
  const padding = '='.repeat((4 - (padded.length % 4)) % 4);
  const base64 = `${padded}${padding}`;
  if (typeof atob !== 'function') {
    throw new Error('atob unavailable');
  }
  const binary = atob(base64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i += 1) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
};

const base64UrlToJson = <T>(input: string): T | null => {
  try {
    const bytes = base64UrlToUint8Array(input);
    const json = new TextDecoder().decode(bytes);
    return JSON.parse(json) as T;
  } catch {
    return null;
  }
};

const verifyJwtLocally = async (
  token: string
): Promise<{ ok: boolean; expMs?: number } | null> => {
  const secret = process.env.JWT_SECRET_KEY;
  const secondarySecret = process.env.JWT_SECONDARY_SECRET;
  const algorithm = (process.env.JWT_ALGORITHM || 'HS256').toUpperCase();
  const hashByAlg: Record<string, string> = {
    HS256: 'SHA-256',
    HS384: 'SHA-384',
    HS512: 'SHA-512',
  };
  const hash = hashByAlg[algorithm];
  const subtle = globalThis.crypto?.subtle;

  if (!secret || !hash || !subtle || typeof atob !== 'function') return null;

  const parts = token.split('.');
  if (parts.length !== 3) return { ok: false };

  const [headerSegment, payloadSegment, signatureSegment] = parts;
  const header = base64UrlToJson<{ alg?: string }>(headerSegment);
  if (!header) return { ok: false };
  if (!header.alg || header.alg.toUpperCase() !== algorithm) return { ok: false };

  const data = new TextEncoder().encode(`${headerSegment}.${payloadSegment}`);
  const signature = base64UrlToUint8Array(signatureSegment);
  const secrets = [secret, secondarySecret].filter((value): value is string => !!value);
  let signatureValid = false;

  for (const candidate of secrets) {
    const key = await subtle.importKey(
      'raw',
      new TextEncoder().encode(candidate),
      { name: 'HMAC', hash: { name: hash } },
      false,
      ['verify']
    );
    if (await subtle.verify('HMAC', key, signature, data)) {
      signatureValid = true;
      break;
    }
  }

  if (!signatureValid) return { ok: false };

  const payload = base64UrlToJson<{ exp?: number; nbf?: number }>(payloadSegment);
  if (!payload) return { ok: false };

  const nowSec = Math.floor(Date.now() / 1000);
  if (typeof payload.exp === 'number' && nowSec >= payload.exp) return { ok: false };
  if (typeof payload.nbf === 'number' && nowSec < payload.nbf) return { ok: false };
  if (typeof payload.exp !== 'number') return null;

  return { ok: true, expMs: payload.exp * 1000 };
};

const verifyTokenWithApi = async (token: string, kind: AuthTokenKind): Promise<boolean> => {
  const headers = new Headers();
  if (kind === 'apiKey') {
    headers.set('X-API-KEY', token);
  } else {
    headers.set('Authorization', `Bearer ${token}`);
  }

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 2000);

  try {
    const response = await fetch(buildApiUrl('/users/me'), {
      method: 'GET',
      headers,
      cache: 'no-store',
      signal: controller.signal,
    });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeoutId);
  }
};

const verifyAuthToken = async (token: string, kind: AuthTokenKind): Promise<boolean> => {
  const cacheKey = await buildAuthCacheKey(kind, token);
  const cached = cacheKey ? getCachedAuth(cacheKey) : null;
  if (cached !== null) return cached;

  let ok = false;
  let ttlMs = AUTH_CACHE_TTL_MS;

  if (kind === 'jwt') {
    const localResult = await verifyJwtLocally(token);
    if (localResult) {
      ok = localResult.ok;
      if (ok && typeof localResult.expMs === 'number') {
        ttlMs = Math.min(
          AUTH_CACHE_TTL_MS,
          Math.max(0, localResult.expMs - Date.now() - 1000)
        );
      }
    } else {
      ok = await verifyTokenWithApi(token, kind);
    }
  } else {
    ok = await verifyTokenWithApi(token, kind);
  }

  if (cacheKey) {
    setCachedAuth(cacheKey, ok, ok ? ttlMs : AUTH_NEGATIVE_CACHE_TTL_MS);
  }
  return ok;
};

const validateBearerToken = async (token: string): Promise<boolean> =>
  verifyAuthToken(token, 'jwt');

const validateApiKey = async (apiKey: string): Promise<boolean> => {
  const normalized = apiKey.trim();
  if (!normalized || !isValidApiKeyFormat(normalized)) return false;
  return verifyAuthToken(normalized, 'apiKey');
};

const hasAuthCookie = async (request: NextRequest): Promise<boolean> => {
  for (const name of AUTH_COOKIE_NAMES) {
    const cookie = request.cookies.get(name);
    const rawValue = cookie?.value ? safeDecodeCookieValue(cookie.value) : '';
    const token = normalizeToken(rawValue);
    if (!token) continue;

    const kind: AuthTokenKind = name === 'access_token' ? 'jwt' : 'apiKey';
    if (await verifyAuthToken(token, kind)) {
      return true;
    }
  }
  return false;
};

const hasAuthHeader = async (request: NextRequest): Promise<boolean> => {
  const authorization = request.headers.get('authorization');
  if (authorization) {
    const token = parseBearerHeader(authorization);
    if (token && (await validateBearerToken(token))) {
      return true;
    }
  }
  const apiKey = request.headers.get('x-api-key');
  if (apiKey && (await validateApiKey(apiKey))) {
    return true;
  }
  return false;
};

const hasAuthSession = async (request: NextRequest): Promise<boolean> => {
  if (await hasAuthCookie(request)) {
    return true;
  }
  return await hasAuthHeader(request);
};

export async function middleware(request: NextRequest) {
  if (await hasAuthSession(request)) {
    return NextResponse.next();
  }

  const loginUrl = request.nextUrl.clone();
  loginUrl.pathname = '/login';
  loginUrl.searchParams.set(
    'redirectTo',
    `${request.nextUrl.pathname}${request.nextUrl.search}`
  );
  return NextResponse.redirect(loginUrl);
}

export const config = {
  matcher: ['/((?!login(?:/|$)|api(?:/|$)|_next|.*\\..*).*)'],
};
