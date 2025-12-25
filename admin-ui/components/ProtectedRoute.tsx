'use client';

import { useEffect } from 'react';
import { useRouter } from 'next/navigation';
import { getCurrentUser, isAuthenticated as checkAuth } from '@/lib/auth';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: string[];
}

// Role hierarchy for UI gating: higher roles inherit access to lower-role routes.
const ROLE_RANK: Record<string, number> = {
  owner: 3,
  super_admin: 2,
  admin: 1,
  member: 0,
  user: 0,
};

const hasRoleAccess = (currentRole: string, requiredRoles: string[]): boolean => {
  if (requiredRoles.length === 0) {
    return true;
  }

  const currentRank = ROLE_RANK[currentRole];

  return requiredRoles.some((requiredRole) => {
    if (requiredRole === currentRole) {
      return true;
    }

    const requiredRank = ROLE_RANK[requiredRole];
    if (requiredRank === undefined || currentRank === undefined) {
      return false;
    }

    return currentRank >= requiredRank;
  });
};

export default function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const router = useRouter();
  const currentUser = getCurrentUser();
  const isAuthed = checkAuth() && !!currentUser;
  const hasPermission = !!currentUser && (!requiredRoles || requiredRoles.length === 0
    || hasRoleAccess(currentUser.role, requiredRoles));

  useEffect(() => {
    if (!isAuthed) {
      router.push('/login');
    }
  }, [isAuthed, router]);

  if (!isAuthed) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!hasPermission) {
    return (
      <div className="flex h-screen items-center justify-center p-8">
        <Alert variant="destructive" className="max-w-md">
          <AlertDescription>
            You do not have permission to access this page.
            {requiredRoles && requiredRoles.length > 0 && (
              <>
                {' Required role: '}
                {requiredRoles.join(', ')}
              </>
            )}
          </AlertDescription>
        </Alert>
      </div>
    );
  }

  return <>{children}</>;
}
