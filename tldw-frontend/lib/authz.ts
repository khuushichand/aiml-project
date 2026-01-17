/**
 * Utility functions for authZ checks consumed across the WebUI.
 */

import type { AuthUser } from '@/types/common';

/** Parse common truthy env/string values into boolean. */
export function toBool(val: unknown, fallback = false): boolean {
  if (val === undefined || val === null) return !!fallback;
  const s = String(val).trim().toLowerCase();
  if (s === '') return !!fallback;
  return s === '1' || s === 'true' || s === 'yes' || s === 'y' || s === 'on';
}

/** Normalize a possibly singular-or-array value into a lowercase string array. */
export function normalizeStringArray(input: unknown): string[] {
  const arr = Array.isArray(input) ? input : (input != null ? [input] : []);
  return arr
    .map((v) => (v != null ? String(v) : ''))
    .filter((s) => s.length > 0)
    .map((s) => s.toLowerCase());
}

/** Determine whether a user has administrative privileges. */
export function isAdmin(user: AuthUser | null | undefined): boolean {
  try {
    if (!user) return false;
    if (user.is_admin === true) return true;
    if (user.isAdmin === true) return true;

    const roleVal = user.role != null ? String(user.role).toLowerCase() : '';
    if (roleVal === 'admin') return true;

    const rolesArr = normalizeStringArray(user.roles);
    if (rolesArr.includes('admin')) return true;

    const perms = normalizeStringArray(user.permissions);
    if (perms.includes('admin')) return true;

    const scopes = normalizeStringArray(user.scopes);
    if (scopes.includes('admin')) return true;

    return false;
  } catch {
    return false;
  }
}
