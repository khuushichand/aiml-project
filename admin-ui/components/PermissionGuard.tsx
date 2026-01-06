'use client';

import { createContext, useCallback, useContext, useEffect, useState, ReactNode } from 'react';
import { useRouter } from 'next/navigation';
import { api } from '@/lib/api-client';
import { User } from '@/types';
import { hasRoleAccess, isAdminRole, isSuperAdminRole } from '@/lib/roles';
import { Alert, AlertDescription } from '@/components/ui/alert';

// UI gating only; backend must enforce authorization and never trust client permissions.
interface PermissionContextType {
  user: User | null;
  permissions: string[];
  permissionHints: string[];
  roles: string[];
  loading: boolean;
  hasPermission: (permission: string | string[]) => boolean;
  hasRole: (role: string | string[]) => boolean;
  hasAnyPermission: (permissions: string[]) => boolean;
  hasAllPermissions: (permissions: string[]) => boolean;
  isAdmin: () => boolean;
  isSuperAdmin: () => boolean;
  refresh: () => Promise<void>;
}

const PermissionContext = createContext<PermissionContextType>({
  user: null,
  permissions: [],
  permissionHints: [],
  roles: [],
  loading: true,
  hasPermission: () => false,
  hasRole: () => false,
  hasAnyPermission: () => false,
  hasAllPermissions: () => false,
  isAdmin: () => false,
  isSuperAdmin: () => false,
  refresh: async () => {},
});

export function usePermissions() {
  return useContext(PermissionContext);
}

interface PermissionProviderProps {
  children: ReactNode;
}

export function PermissionProvider({ children }: PermissionProviderProps) {
  const [user, setUser] = useState<User | null>(null);
  const [permissions, setPermissions] = useState<string[]>([]);
  const [permissionHints, setPermissionHints] = useState<string[]>([]);
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const loadUserPermissions = useCallback(async () => {
    try {
      setLoading(true);
      const userData = await api.getCurrentUser();
      setUser(userData);

      // UI-only role hints. Backend authorization must enforce real permissions.
      const userRole = userData.role || '';
      const userRoles = userRole ? [userRole] : [];
      setRoles(userRoles);

      const derivedPermissions: string[] = [];

      if (isSuperAdminRole(userRole)) {
        derivedPermissions.push('*'); // Wildcard for all permissions
      } else if (userRole === 'admin') {
        derivedPermissions.push(
          'read:users', 'write:users',
          'read:orgs', 'write:orgs',
          'read:teams', 'write:teams',
          'read:api_keys', 'write:api_keys',
          'read:audit', 'read:config'
        );
      } else if (userRole === 'member') {
        derivedPermissions.push('read:users', 'read:orgs', 'read:teams');
      }

      setPermissionHints(derivedPermissions);

      // NOTE: UI gating only. Backend must enforce authorization.
      try {
        const effective = await api.getUserEffectivePermissions(userData.id.toString());
        const serverPermissions = Array.isArray(effective?.permissions) ? effective.permissions : [];
        setPermissions(serverPermissions);
      } catch (error) {
        console.error('Failed to load server permissions:', error);
        setPermissions([]);
      }
    } catch (error) {
      console.error('Failed to load user permissions:', error);
      setUser(null);
      setPermissions([]);
      setPermissionHints([]);
      setRoles([]);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUserPermissions();
  }, [loadUserPermissions]);

  const hasPermission = (permission: string | string[]): boolean => {
    if (permissions.includes('*')) return true;

    const perms = Array.isArray(permission) ? permission : [permission];
    return perms.some((p) => permissions.includes(p));
  };

  const hasRole = (role: string | string[]): boolean => {
    const currentRole = roles[0];
    const requiredRoles = Array.isArray(role) ? role : [role];
    return hasRoleAccess(currentRole, requiredRoles);
  };

  const hasAnyPermission = (perms: string[]): boolean => {
    if (permissions.includes('*')) return true;
    return perms.some((p) => permissions.includes(p));
  };

  const hasAllPermissions = (perms: string[]): boolean => {
    if (permissions.includes('*')) return true;
    return perms.every((p) => permissions.includes(p));
  };

  const isAdmin = (): boolean => isAdminRole(roles[0]);

  const isSuperAdmin = (): boolean => isSuperAdminRole(roles[0]);

  return (
    <PermissionContext.Provider
      value={{
        user,
        permissions,
        permissionHints,
        roles,
        loading,
        hasPermission,
        hasRole,
        hasAnyPermission,
        hasAllPermissions,
        isAdmin,
        isSuperAdmin,
        refresh: loadUserPermissions,
      }}
    >
      {children}
    </PermissionContext.Provider>
  );
}

// Component to conditionally render based on permissions
interface PermissionGuardProps {
  children: ReactNode;
  permission?: string | string[];
  permissions?: string[];
  requireAll?: boolean;
  role?: string | string[];
  fallback?: ReactNode;
  showLoading?: boolean;
  requireAuth?: boolean;
  redirectTo?: string;
  variant?: 'inline' | 'route';
}

export function PermissionGuard({
  children,
  permission,
  permissions: requiredPermissions,
  requireAll = false,
  role,
  fallback = null,
  showLoading = false,
  requireAuth = false,
  redirectTo = '/login',
  variant = 'inline',
}: PermissionGuardProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions, hasRole, loading, user } = usePermissions();
  const router = useRouter();

  useEffect(() => {
    if (!loading && requireAuth && !user && redirectTo) {
      router.push(redirectTo);
    }
  }, [loading, requireAuth, user, redirectTo, router]);

  const renderRouteLoading = () => (
    <div className="flex h-screen items-center justify-center">
      <div className="text-muted-foreground">Loading...</div>
    </div>
  );

  const renderRouteDenied = () => (
    <div className="flex h-screen items-center justify-center p-8">
      <Alert variant="destructive" className="max-w-md">
        <AlertDescription>
          You do not have permission to access this page.
        </AlertDescription>
      </Alert>
    </div>
  );

  if (loading) {
    if (variant === 'route') {
      return renderRouteLoading();
    }
    if (showLoading) {
      return <div className="animate-pulse bg-muted h-8 rounded" />;
    }
    return null;
  }

  if (requireAuth && !user) {
    if (variant === 'route') {
      return renderRouteLoading();
    }
    return <>{fallback}</>;
  }

  // Check role first if specified
  if (role && !hasRole(role)) {
    if (variant === 'route') {
      return renderRouteDenied();
    }
    return <>{fallback}</>;
  }

  // Check single permission
  if (permission && !hasPermission(permission)) {
    if (variant === 'route') {
      return renderRouteDenied();
    }
    return <>{fallback}</>;
  }

  // Check multiple permissions
  if (requiredPermissions && requiredPermissions.length > 0) {
    const hasAccess = requireAll
      ? hasAllPermissions(requiredPermissions)
      : hasAnyPermission(requiredPermissions);

    if (!hasAccess) {
      if (variant === 'route') {
        return renderRouteDenied();
      }
      return <>{fallback}</>;
    }
  }

  return <>{children}</>;
}

// Higher-order component for protecting entire pages
interface WithPermissionOptions {
  permission?: string | string[];
  role?: string | string[];
  redirectTo?: string;
}

export function withPermission<P extends object>(
  WrappedComponent: React.ComponentType<P>,
  options: WithPermissionOptions
) {
  return function PermissionProtectedComponent(props: P) {
    const router = useRouter();
    const { hasPermission, hasRole, loading } = usePermissions();
    const [mounted, setMounted] = useState(false);

    useEffect(() => {
      setMounted(true);
    }, []);

    if (!mounted || loading) {
      return (
        <div className="flex items-center justify-center min-h-screen">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary" />
        </div>
      );
    }

    const hasAccess =
      (!options.permission || hasPermission(options.permission)) &&
      (!options.role || hasRole(options.role));

    if (!hasAccess) {
      if (options.redirectTo) {
        router.push(options.redirectTo);
        return null;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-screen">
          <h1 className="text-2xl font-bold mb-4">Access Denied</h1>
          <p className="text-muted-foreground">
            You don&apos;t have permission to access this page.
          </p>
        </div>
      );
    }

    return <WrappedComponent {...props} />;
  };
}

// Utility component for admin-only content
interface AdminOnlyProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function AdminOnly({ children, fallback = null }: AdminOnlyProps) {
  return (
    <PermissionGuard role="admin" fallback={fallback}>
      {children}
    </PermissionGuard>
  );
}

// Utility component for super-admin-only content
export function SuperAdminOnly({ children, fallback = null }: AdminOnlyProps) {
  return (
    <PermissionGuard role="super_admin" fallback={fallback}>
      {children}
    </PermissionGuard>
  );
}

export default PermissionGuard;
