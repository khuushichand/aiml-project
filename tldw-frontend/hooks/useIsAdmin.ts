import { useAuth } from '@/hooks/useAuth';
import { isAdmin } from '@/lib/authz';

/**
 * useIsAdmin - returns true when the current user is considered an admin.
 * Centralizes the logic so components remain consistent.
 */
export function useIsAdmin(): boolean {
  const { user } = useAuth();
  return isAdmin(user);
}
