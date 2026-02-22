export const DEFAULT_POST_LOGIN_REDIRECT = '/';

const containsControlCharacters = (value: string): boolean => /[\r\n\t]/.test(value);

export const sanitizeRedirectPath = (
  candidate: string | null | undefined,
  fallback: string = DEFAULT_POST_LOGIN_REDIRECT
): string => {
  if (!candidate) return fallback;
  const trimmed = candidate.trim();
  if (!trimmed) return fallback;
  if (!trimmed.startsWith('/')) return fallback;
  if (trimmed.startsWith('//')) return fallback;
  if (containsControlCharacters(trimmed)) return fallback;
  return trimmed;
};

export const getRedirectTargetFromSearch = (
  search: string,
  fallback: string = DEFAULT_POST_LOGIN_REDIRECT
): string => {
  const params = new URLSearchParams(search);
  return sanitizeRedirectPath(params.get('redirectTo'), fallback);
};

export type RouteUnauthenticatedState = 'redirect_to_login' | 'session_unavailable';

export const resolveUnauthenticatedRouteState = (
  authError: boolean
): RouteUnauthenticatedState => (authError ? 'redirect_to_login' : 'session_unavailable');
