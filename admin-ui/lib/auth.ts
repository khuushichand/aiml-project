'use client';

// API configuration - supports tldw_server API
const API_HOST = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const API_URL = `${API_HOST.replace(/\/$/, '')}/api/${API_VERSION}`;

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
  const storedApiKey = localStorage.getItem('x_api_key');
  return !!storedApiKey;
}

/**
 * Get X-API-KEY for single-user mode
 */
export function getApiKey(): string | null {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem('x_api_key') || null;
}

/**
 * Set X-API-KEY for single-user mode
 */
export function setApiKey(key: string): void {
  if (typeof window !== 'undefined') {
    localStorage.setItem('x_api_key', key);
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

    const response = await fetch(`${API_URL}/auth/login`, {
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
    const response = await fetch(`${API_URL}/users/me`, {
      method: 'GET',
      headers: {
        'X-API-KEY': apiKey,
      },
    });

    if (response.ok) {
      const user = await response.json();
      localStorage.setItem('x_api_key', apiKey);
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
    const response = await fetch(`${API_URL}/users/me`, {
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
      await fetch(`${API_URL}/auth/logout`, {
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
  }
}

/**
 * Get current user from localStorage
 */
export function getCurrentUser(): AdminUser | null {
  if (typeof window === 'undefined') return null;
  const user = localStorage.getItem('user');
  return user ? JSON.parse(user) : null;
}

/**
 * Check if user is authenticated (either JWT or API key)
 */
export function isAuthenticated(): boolean {
  return !!(getJWTToken() || getApiKey());
}

/**
 * Check if current user has admin role
 */
export function isAdmin(): boolean {
  const user = getCurrentUser();
  return user?.role === 'admin' || user?.role === 'owner' || user?.role === 'super_admin';
}

/**
 * Check if current user is owner/super_admin
 */
export function isOwner(): boolean {
  const user = getCurrentUser();
  return user?.role === 'owner' || user?.role === 'super_admin';
}

/**
 * Get auth headers for API requests
 */
export function getAuthHeaders(): Record<string, string> {
  const headers: Record<string, string> = {};

  const token = getJWTToken();
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const apiKey = getApiKey();
  if (apiKey) {
    headers['X-API-KEY'] = apiKey;
  }

  return headers;
}
