import { describe, expect, it } from 'vitest';
import {
  DEFAULT_POST_LOGIN_REDIRECT,
  getRedirectTargetFromSearch,
  resolveUnauthenticatedRouteState,
  sanitizeRedirectPath,
} from './auth-navigation';

describe('sanitizeRedirectPath', () => {
  it('returns fallback for missing values', () => {
    expect(sanitizeRedirectPath(undefined)).toBe(DEFAULT_POST_LOGIN_REDIRECT);
    expect(sanitizeRedirectPath(null)).toBe(DEFAULT_POST_LOGIN_REDIRECT);
    expect(sanitizeRedirectPath('')).toBe(DEFAULT_POST_LOGIN_REDIRECT);
  });

  it('accepts internal absolute paths', () => {
    expect(sanitizeRedirectPath('/users')).toBe('/users');
    expect(sanitizeRedirectPath('/users/42?tab=keys')).toBe('/users/42?tab=keys');
  });

  it('rejects external and malformed redirect values', () => {
    expect(sanitizeRedirectPath('https://example.com')).toBe(DEFAULT_POST_LOGIN_REDIRECT);
    expect(sanitizeRedirectPath('//example.com')).toBe(DEFAULT_POST_LOGIN_REDIRECT);
    expect(sanitizeRedirectPath('javascript:alert(1)')).toBe(DEFAULT_POST_LOGIN_REDIRECT);
  });
});

describe('getRedirectTargetFromSearch', () => {
  it('extracts redirectTo from query string', () => {
    expect(getRedirectTargetFromSearch('?redirectTo=%2Fjobs%3Fstatus%3Dqueued')).toBe('/jobs?status=queued');
  });

  it('falls back when redirectTo is not safe', () => {
    expect(getRedirectTargetFromSearch('?redirectTo=https%3A%2F%2Fevil.example')).toBe(
      DEFAULT_POST_LOGIN_REDIRECT
    );
  });
});

describe('resolveUnauthenticatedRouteState', () => {
  it('returns redirect state for auth failures', () => {
    expect(resolveUnauthenticatedRouteState(true)).toBe('redirect_to_login');
  });

  it('returns session-unavailable state for non-auth failures', () => {
    expect(resolveUnauthenticatedRouteState(false)).toBe('session_unavailable');
  });
});
