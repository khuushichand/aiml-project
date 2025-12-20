'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { getCurrentUser, isAuthenticated as checkAuth, AdminUser } from '@/lib/auth';
import { Alert, AlertDescription } from '@/components/ui/alert';

interface ProtectedRouteProps {
  children: React.ReactNode;
  requiredRoles?: string[];
}

export default function ProtectedRoute({ children, requiredRoles }: ProtectedRouteProps) {
  const router = useRouter();
  const [isAuthed, setIsAuthed] = useState(false);
  const [hasPermission, setHasPermission] = useState(false);
  const [user, setUser] = useState<AdminUser | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    // Check if user is authenticated
    if (!checkAuth()) {
      router.push('/login');
      return;
    }

    const currentUser = getCurrentUser();
    if (!currentUser) {
      router.push('/login');
      return;
    }

    setUser(currentUser);
    setIsAuthed(true);

    // Check role-based permissions if required
    if (requiredRoles && requiredRoles.length > 0) {
      // Admin and super_admin roles have access to everything
      const hasAdminAccess = ['admin', 'super_admin', 'owner'].includes(currentUser.role);
      const hasRequiredRole = requiredRoles.includes(currentUser.role);

      if (!hasAdminAccess && !hasRequiredRole) {
        setHasPermission(false);
        setIsLoading(false);
        return;
      }
    }

    setHasPermission(true);
    setIsLoading(false);
  }, [router, requiredRoles]);

  if (isLoading) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Loading...</div>
      </div>
    );
  }

  if (!isAuthed) {
    return (
      <div className="flex h-screen items-center justify-center">
        <div className="text-muted-foreground">Redirecting to login...</div>
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
