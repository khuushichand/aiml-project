'use client';

import { buildApiUrl } from './api-config';

// In-memory storage for single-user API key (not persisted to web storage).
let inMemoryApiKey: string | null = null;
const AUTH_CHANGE_EVENT = 'tldw-admin-auth-change';

const clearApiKeyStorage = (): void => {
  inMemoryApiKey = null;
};

const clearJwtStorage = (): void => {
  if (typeof localStorage !== 'undefined') {
    localStorage.removeItem('access_token');
  }
};

const emitAuthChange = () => {
  if (typeof window === 'undefined') return;
  window.dispatchEvent(new Event(AUTH_CHANGE_EVENT));
};

export const subscribeAuthChange = (handler: () => void): (() => void) => {
  if (typeof window === 'undefined') return () => {};
  window.addEventListener(AUTH_CHANGE_EVENT, handler);
  return () => window.removeEventListener(AUTH_CHANGE_EVENT, handler);
};

export interface AdminUser {
  id: number;
  uuid: string;
  username: string;
  email: string;
  role: string;
  is_active: boolean;
  is_verified: boolean;
  storage_quota_mb: number;
  storage_used_mb: number;
  created_at: string;
  updated_at: string;
  last_login?: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
}

export interface AuthenticatedLoginResult {
  status: 'authenticated';
  accessToken: string;
  tokenType: string;
}

export interface MfaRequiredLoginResult {
  status: 'mfa_required';
  sessionToken: string;
  expiresIn: number;
  message: string;
}

export type PasswordLoginResult = AuthenticatedLoginResult | MfaRequiredLoginResult;

type LoginSuccessPayload = {
  access_token?: string;
  token_type?: string;
  session_token?: string;
  mfa_required?: boolean;
  expires_in?: number;
  message?: string;
};

const isMfaChallengePayload = (
  value: LoginSuccessPayload
): value is Required<Pick<LoginSuccessPayload, 'session_token' | 'expires_in' | 'message'>> & {
  mfa_required: true;
} =>
  value.mfa_required === true
  && typeof value.session_token === 'string'
  && typeof value.expires_in === 'number'
  && typeof value.message === 'string';

const isTokenPayload = (
  value: LoginSuccessPayload
): value is Required<Pick<LoginSuccessPayload, 'access_token' | 'token_type'>> =>
  typeof value.access_token === 'string'
  && typeof value.token_type === 'string';

const finalizePasswordLogin = async (
  accessToken: string,
  tokenType: string
): Promise<AuthenticatedLoginResult> => {
  clearApiKeyStorage();
  localStorage.setItem('access_token', accessToken);
  emitAuthChange();
  await fetchAndStoreUser(accessToken);
  return {
    status: 'authenticated',
    accessToken,
    tokenType,
  };
};

/**
 * Check if we're in single-user mode (X-API-KEY auth)
 */
export function isSingleUserMode(): boolean {
  if (typeof window === 'undefined') return false;
  return !!getApiKey();
}

/**
 * Get X-API-KEY for single-user mode
 */
export function getApiKey(): string | null {
  if (typeof window === 'undefined') return null;
  if (inMemoryApiKey) return inMemoryApiKey;
  return null;
}

/**
 * Set X-API-KEY for single-user mode
 */
export function setApiKey(key: string): void {
  if (typeof window !== 'undefined') {
    inMemoryApiKey = key;
    emitAuthChange();
  }
}

/**
 * Get JWT token from localStorage
 */
export function getJWTToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

export function hasStoredAuth(): boolean {
  if (typeof window === 'undefined') return false;
  return !!getJWTToken() || !!getApiKey();
}

/**
 * Login with username/email and password (multi-user JWT mode)
 * tldw_server uses OAuth2 form-urlencoded login
 */
export async function loginWithPassword(
  username: string,
  password: string
): Promise<PasswordLoginResult | null> {
  try {
    // tldw_server expects OAuth2 form-urlencoded body
    const formData = new URLSearchParams();
    formData.append('username', username);
    formData.append('password', password);

    const response = await fetch(buildApiUrl('/auth/login'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
      },
      body: formData.toString(),
    });

    if (response.ok) {
      const data = await response.json() as LoginSuccessPayload;
      if (isMfaChallengePayload(data)) {
        return {
          status: 'mfa_required',
          sessionToken: data.session_token,
          expiresIn: data.expires_in,
          message: data.message,
        };
      }
      if (isTokenPayload(data)) {
        return await finalizePasswordLogin(data.access_token, data.token_type);
      }
    }

    return null;
  } catch (error) {
    console.error('Login failed:', error);
    return null;
  }
}

export async function completeMfaLogin(
  sessionToken: string,
  mfaToken: string
): Promise<AuthenticatedLoginResult | null> {
  try {
    const response = await fetch(buildApiUrl('/auth/mfa/login'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        session_token: sessionToken,
        mfa_token: mfaToken,
      }),
    });

    if (!response.ok) {
      return null;
    }

    const data = await response.json() as LoginSuccessPayload;
    if (!isTokenPayload(data)) {
      return null;
    }

    return await finalizePasswordLogin(data.access_token, data.token_type);
  } catch (error) {
    console.error('MFA login failed:', error);
    return null;
  }
}

/**
 * Login with API key (single-user mode)
 */
export async function loginWithApiKey(apiKey: string): Promise<boolean> {
  try {
    // Validate the API key by calling a protected endpoint
    const response = await fetch(buildApiUrl('/users/me'), {
      method: 'GET',
      headers: {
        'X-API-KEY': apiKey,
      },
    });

    if (response.ok) {
      const user = await response.json();
      // Auth mode exclusivity: API key login clears JWT auth state.
      clearJwtStorage();
      setApiKey(apiKey);
      localStorage.setItem('user', JSON.stringify(user));
      return true;
    }

    return false;
  } catch (error) {
    console.error('API key validation failed:', error);
    return false;
  }
}

/**
 * Fetch and store current user info
 */
async function fetchAndStoreUser(token: string): Promise<AdminUser | null> {
  try {
    const response = await fetch(buildApiUrl('/users/me'), {
      headers: {
        'Authorization': `Bearer ${token}`,
      },
    });

    if (response.ok) {
      const user: AdminUser = await response.json();
      localStorage.setItem('user', JSON.stringify(user));
      return user;
    }
    return null;
  } catch (error) {
    console.error('Failed to fetch user:', error);
    return null;
  }
}

/**
 * Logout - clear all stored credentials
 */
export async function logout(): Promise<void> {
  try {
    const token = getJWTToken();
    if (token) {
      // Try to invalidate token on server (optional - tldw_server may not have this endpoint)
      await fetch(buildApiUrl('/auth/logout'), {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
        },
      }).catch(() => {
        // Ignore errors - server might not have logout endpoint
      });
    }
  } finally {
    // Always clear local storage
    localStorage.removeItem('user');
    clearJwtStorage();
    clearApiKeyStorage();
    emitAuthChange();
  }
}
