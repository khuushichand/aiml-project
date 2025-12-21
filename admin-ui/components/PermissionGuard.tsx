'use client';

import { createContext, useContext, useEffect, useState, ReactNode } from 'react';
import { api } from '@/lib/api-client';
import { User, Permission } from '@/types';

interface PermissionContextType {
  user: User | null;
  permissions: string[];
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
  const [roles, setRoles] = useState<string[]>([]);
  const [loading, setLoading] = useState(true);

  const loadUserPermissions = async () => {
    try {
      setLoading(true);
      const userData = await api.getCurrentUser();
      setUser(userData);

      // Extract role
      const userRoles = userData.role ? [userData.role] : [];
      setRoles(userRoles);

      // For now, derive permissions from role
      // In a full implementation, you'd fetch actual permissions from the server
      const derivedPermissions: string[] = [];

      if (userRoles.includes('super_admin') || userRoles.includes('owner')) {
        derivedPermissions.push('*'); // Wildcard for all permissions
      } else if (userRoles.includes('admin')) {
        derivedPermissions.push(
          'read:users', 'write:users',
          'read:orgs', 'write:orgs',
          'read:teams', 'write:teams',
          'read:api_keys', 'write:api_keys',
          'read:audit', 'read:config'
        );
      } else if (userRoles.includes('member')) {
        derivedPermissions.push('read:users', 'read:orgs', 'read:teams');
      }

      setPermissions(derivedPermissions);
    } catch (error) {
      console.error('Failed to load user permissions:', error);
      setUser(null);
      setPermissions([]);
      setRoles([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadUserPermissions();
  }, []);

  const hasPermission = (permission: string | string[]): boolean => {
    if (permissions.includes('*')) return true;

    const perms = Array.isArray(permission) ? permission : [permission];
    return perms.some((p) => permissions.includes(p));
  };

  const hasRole = (role: string | string[]): boolean => {
    const checkRoles = Array.isArray(role) ? role : [role];
    return checkRoles.some((r) => roles.includes(r));
  };

  const hasAnyPermission = (perms: string[]): boolean => {
    if (permissions.includes('*')) return true;
    return perms.some((p) => permissions.includes(p));
  };

  const hasAllPermissions = (perms: string[]): boolean => {
    if (permissions.includes('*')) return true;
    return perms.every((p) => permissions.includes(p));
  };

  const isAdmin = (): boolean => {
    return hasRole(['admin', 'super_admin', 'owner']);
  };

  const isSuperAdmin = (): boolean => {
    return hasRole(['super_admin', 'owner']);
  };

  return (
    <PermissionContext.Provider
      value={{
        user,
        permissions,
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
}

export function PermissionGuard({
  children,
  permission,
  permissions: requiredPermissions,
  requireAll = false,
  role,
  fallback = null,
  showLoading = false,
}: PermissionGuardProps) {
  const { hasPermission, hasAnyPermission, hasAllPermissions, hasRole, loading } = usePermissions();

  if (loading && showLoading) {
    return <div className="animate-pulse bg-muted h-8 rounded" />;
  }

  if (loading) {
    return null;
  }

  // Check role first if specified
  if (role && !hasRole(role)) {
    return <>{fallback}</>;
  }

  // Check single permission
  if (permission && !hasPermission(permission)) {
    return <>{fallback}</>;
  }

  // Check multiple permissions
  if (requiredPermissions && requiredPermissions.length > 0) {
    const hasAccess = requireAll
      ? hasAllPermissions(requiredPermissions)
      : hasAnyPermission(requiredPermissions);

    if (!hasAccess) {
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
      if (options.redirectTo && typeof window !== 'undefined') {
        window.location.href = options.redirectTo;
        return null;
      }

      return (
        <div className="flex flex-col items-center justify-center min-h-screen">
          <h1 className="text-2xl font-bold mb-4">Access Denied</h1>
          <p className="text-muted-foreground">
            You don't have permission to access this page.
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
    <PermissionGuard role={['admin', 'super_admin', 'owner']} fallback={fallback}>
      {children}
    </PermissionGuard>
  );
}

// Utility component for super-admin-only content
export function SuperAdminOnly({ children, fallback = null }: AdminOnlyProps) {
  return (
    <PermissionGuard role={['super_admin', 'owner']} fallback={fallback}>
      {children}
    </PermissionGuard>
  );
}

export default PermissionGuard;
