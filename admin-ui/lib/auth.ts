'use client';

import { buildApiUrl } from './api-config';

// In-memory storage for single-user API key to avoid clear-text persistence
let inMemoryApiKey: string | null = null;

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

/**
 * Check if we're in single-user mode (X-API-KEY auth)
 */
export function isSingleUserMode(): boolean {
  if (typeof window === 'undefined') return false;
  return !!inMemoryApiKey;
}

/**
 * Get X-API-KEY for single-user mode
 */
export function getApiKey(): string | null {
  if (typeof window === 'undefined') return null;
  return inMemoryApiKey;
}

/**
 * Set X-API-KEY for single-user mode
 */
export function setApiKey(key: string): void {
  if (typeof window !== 'undefined') {
    inMemoryApiKey = key;
  }
}

/**
 * Get JWT token from localStorage
 */
export function getJWTToken(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('access_token');
}

/**
 * Login with username/email and password (multi-user JWT mode)
 * tldw_server uses OAuth2 form-urlencoded login
 */
export async function loginWithPassword(
  username: string,
  password: string
): Promise<LoginResponse | null> {
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
      const data: LoginResponse = await response.json();
      // Store JWT token
      localStorage.setItem('access_token', data.access_token);

      // Fetch user info
      await fetchAndStoreUser(data.access_token);

      return data;
    }

    return null;
  } catch (error) {
    console.error('Login failed:', error);
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
    localStorage.removeItem('access_token');
    localStorage.removeItem('x_api_key');
    if (typeof sessionStorage !== 'undefined') {
      sessionStorage.removeItem('x_api_key');
    }
  }
}
