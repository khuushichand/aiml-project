'use client';

import { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ArrowLeft, RefreshCw, Shield } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Role, Permission } from '@/types';

interface RolePermissionMap {
  [roleId: string]: Set<number>;
}

export default function PermissionMatrixPage() {
  const router = useRouter();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [rolePermissions, setRolePermissions] = useState<RolePermissionMap>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');

      // Load roles and permissions
      const [rolesData, permsData] = await Promise.all([
        api.getRoles(),
        api.getPermissions(),
      ]);

      const rolesArray = Array.isArray(rolesData) ? rolesData : [];
      const permsArray = Array.isArray(permsData) ? permsData : [];

      setRoles(rolesArray);
      setPermissions(permsArray);

      // Load permissions for each role
      const permMap: RolePermissionMap = {};
      await Promise.all(
        rolesArray.map(async (role) => {
          try {
            const rolePerms = await api.getRolePermissions(role.id.toString());
            permMap[role.id] = new Set(
              (Array.isArray(rolePerms) ? rolePerms : []).map((p: Permission) => p.id)
            );
          } catch {
            permMap[role.id] = new Set();
          }
        })
      );

      setRolePermissions(permMap);
    } catch (err: any) {
      console.error('Failed to load data:', err);
      setError(err.message || 'Failed to load roles and permissions');
    } finally {
      setLoading(false);
    }
  };

  const hasPermission = (roleId: number, permissionId: number): boolean => {
    return rolePermissions[roleId]?.has(permissionId) || false;
  };

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => router.push('/roles')}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <h1 className="text-3xl font-bold">Permission Matrix</h1>
                  <p className="text-muted-foreground">
                    Visual overview of role-permission assignments
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button variant="outline" onClick={loadData} disabled={loading}>
                  <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Info Card */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <Shield className="h-8 w-8 text-primary mt-1" />
                  <div>
                    <h3 className="font-semibold">Permission Matrix View</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      This matrix shows which permissions are assigned to each role (read-only view).
                      To modify permissions, use the individual role detail pages.
                      System roles may have restricted editing capabilities.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Matrix Table */}
            <Card>
              <CardHeader>
                <CardTitle>Role-Permission Matrix</CardTitle>
                <CardDescription>
                  {roles.length} roles x {permissions.length} permissions
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-center text-muted-foreground py-8">Loading...</div>
                ) : roles.length === 0 || permissions.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    {roles.length === 0 ? 'No roles found. ' : ''}
                    {permissions.length === 0 ? 'No permissions found. ' : ''}
                    Create some first on the Roles page.
                  </div>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full border-collapse">
                      <thead>
                        <tr>
                          <th className="text-left p-3 bg-muted font-semibold sticky left-0 z-10 border-b">
                            Permission
                          </th>
                          {roles.map((role) => (
                            <th key={role.id} className="text-center p-3 bg-muted font-semibold border-b min-w-[100px]">
                              <div>
                                <span>{role.name}</span>
                                {role.is_system && (
                                  <Badge variant="secondary" className="ml-1 text-xs">System</Badge>
                                )}
                              </div>
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {permissions.map((perm, index) => (
                          <tr key={perm.id} className={index % 2 === 0 ? 'bg-background' : 'bg-muted/30'}>
                            <td className="p-3 sticky left-0 bg-inherit border-b">
                              <div>
                                <code className="text-sm font-mono">{perm.name}</code>
                                {perm.description && (
                                  <p className="text-xs text-muted-foreground">{perm.description}</p>
                                )}
                              </div>
                            </td>
                            {roles.map((role) => (
                              <td key={`${role.id}-${perm.id}`} className="p-3 text-center border-b">
                                <Checkbox
                                  checked={hasPermission(role.id, perm.id)}
                                  disabled
                                  className="mx-auto"
                                />
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>

            {/* Legend */}
            <Card className="mt-6">
              <CardContent className="pt-6">
                <div className="flex flex-wrap gap-6 text-sm">
                  <div className="flex items-center gap-2">
                    <Checkbox checked disabled className="opacity-50" />
                    <span className="text-muted-foreground">Permission granted</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Checkbox disabled className="opacity-50" />
                    <span className="text-muted-foreground">Permission not granted</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge variant="secondary">System</Badge>
                    <span className="text-muted-foreground">System roles cannot be modified</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
