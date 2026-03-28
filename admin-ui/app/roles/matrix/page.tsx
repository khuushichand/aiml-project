'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/navigation';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { ArrowLeft, RefreshCw, Shield, Save, X } from 'lucide-react';
import { api } from '@/lib/api-client';
import { TableSkeleton } from '@/components/ui/skeleton';
import { Role, Permission } from '@/types';

type RolePermissionMap = Record<number, Set<number>>;

export default function PermissionMatrixPage() {
  const router = useRouter();
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [rolePermissions, setRolePermissions] = useState<RolePermissionMap>({});
  const [pendingChanges, setPendingChanges] = useState<Record<string, boolean>>({});
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const loadData = useCallback(async () => {
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
          } catch (err: unknown) {
            console.warn(`Failed to load permissions for role ${role.id}`, err);
            permMap[role.id] = new Set();
          }
        })
      );

      setRolePermissions(permMap);
      setPendingChanges({});
    } catch (err: unknown) {
      console.error('Failed to load data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load roles and permissions');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  useEffect(() => {
    if (!success) return;
    const timer = setTimeout(() => setSuccess(''), 2500);
    return () => clearTimeout(timer);
  }, [success]);

  const getCellKey = (roleId: number, permissionId: number): string => `${roleId}:${permissionId}`;

  const baseHasPermission = (roleId: number, permissionId: number): boolean => {
    return rolePermissions[roleId]?.has(permissionId) || false;
  };

  const hasPermission = (roleId: number, permissionId: number): boolean => {
    const key = getCellKey(roleId, permissionId);
    if (key in pendingChanges) {
      return pendingChanges[key];
    }
    return baseHasPermission(roleId, permissionId);
  };

  const pendingChangeCount = useMemo(() => Object.keys(pendingChanges).length, [pendingChanges]);

  const isDirtyCell = (roleId: number, permissionId: number): boolean => {
    return getCellKey(roleId, permissionId) in pendingChanges;
  };

  const togglePermission = (role: Role, permissionId: number) => {
    if (role.is_system || saving) return;

    const roleId = role.id;
    const key = getCellKey(roleId, permissionId);
    const baseline = baseHasPermission(roleId, permissionId);
    const nextValue = !hasPermission(roleId, permissionId);

    setPendingChanges((prev) => {
      if (nextValue === baseline) {
        if (!(key in prev)) return prev;
        const next = { ...prev };
        delete next[key];
        return next;
      }
      return {
        ...prev,
        [key]: nextValue,
      };
    });
  };

  const handleDiscardChanges = () => {
    if (pendingChangeCount === 0) return;
    setPendingChanges({});
    setSuccess('Unsaved changes discarded.');
  };

  const handleSaveChanges = async () => {
    const entries = Object.entries(pendingChanges);
    if (entries.length === 0) return;

    try {
      setSaving(true);
      setError('');

      for (const [cellKey, shouldHavePermission] of entries) {
        const [roleIdPart, permissionIdPart] = cellKey.split(':');
        const roleId = Number(roleIdPart);
        const permissionId = Number(permissionIdPart);
        if (!Number.isFinite(roleId) || !Number.isFinite(permissionId)) {
          continue;
        }
        const currentlyHasPermission = baseHasPermission(roleId, permissionId);
        if (shouldHavePermission === currentlyHasPermission) {
          continue;
        }
        if (shouldHavePermission) {
          await api.assignPermissionToRole(String(roleId), String(permissionId));
        } else {
          await api.removePermissionFromRole(String(roleId), String(permissionId));
        }
      }

      setRolePermissions((prev) => {
        const next: RolePermissionMap = {};
        Object.entries(prev).forEach(([roleId, permissionSet]) => {
          next[Number(roleId)] = new Set(permissionSet);
        });

        entries.forEach(([cellKey, shouldHavePermission]) => {
          const [roleIdPart, permissionIdPart] = cellKey.split(':');
          const roleId = Number(roleIdPart);
          const permissionId = Number(permissionIdPart);
          if (!Number.isFinite(roleId) || !Number.isFinite(permissionId)) {
            return;
          }
          if (!next[roleId]) {
            next[roleId] = new Set();
          }
          if (shouldHavePermission) {
            next[roleId].add(permissionId);
          } else {
            next[roleId].delete(permissionId);
          }
        });

        return next;
      });

      setPendingChanges({});
      setSuccess(`Saved ${entries.length} permission change${entries.length === 1 ? '' : 's'}.`);
    } catch (err: unknown) {
      console.error('Failed to save matrix changes:', err);
      setError(err instanceof Error ? err.message : 'Failed to save matrix changes');
    } finally {
      setSaving(false);
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
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
                    Multi-edit role-permission assignments with batch save
                  </p>
                </div>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => router.push('/roles/compare')}
                >
                  Compare Roles
                </Button>
                {pendingChangeCount > 0 && (
                  <Button
                    variant="outline"
                    onClick={handleDiscardChanges}
                    disabled={saving}
                  >
                    <X className="mr-2 h-4 w-4" />
                    Discard ({pendingChangeCount})
                  </Button>
                )}
                {pendingChangeCount > 0 && (
                  <Button
                    onClick={handleSaveChanges}
                    disabled={saving}
                    loading={saving}
                    loadingText="Saving..."
                  >
                    <Save className="mr-2 h-4 w-4" />
                    Save Changes
                  </Button>
                )}
                <Button
                  variant="outline"
                  onClick={loadData}
                  disabled={loading || saving}
                  loading={loading}
                  loadingText="Refreshing..."
                >
                  <RefreshCw className="mr-2 h-4 w-4" />
                  Refresh
                </Button>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="mb-6 bg-green-50 border-green-200 dark:bg-green-900/20 dark:border-green-800">
                <AlertDescription className="text-green-800 dark:text-green-200">
                  {success}
                </AlertDescription>
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
                      Toggle cells to stage permission grants/removals, then save all changes in one batch.
                      Unsaved cells are highlighted. System roles remain read-only.
                    </p>
                    {pendingChangeCount > 0 && (
                      <p className="text-sm text-amber-700 dark:text-amber-300 mt-2 font-medium">
                        {pendingChangeCount} unsaved change{pendingChangeCount === 1 ? '' : 's'}.
                      </p>
                    )}
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
                  <TableSkeleton rows={5} columns={5} />
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
                              <td
                                key={`${role.id}-${perm.id}`}
                                className={`p-3 text-center border-b ${
                                  isDirtyCell(role.id, perm.id)
                                    ? 'bg-amber-50 dark:bg-amber-900/20'
                                    : ''
                                }`}
                              >
                                <Checkbox
                                  checked={hasPermission(role.id, perm.id)}
                                  onCheckedChange={() => togglePermission(role, perm.id)}
                                  aria-label={`Toggle ${perm.name} for ${role.name}`}
                                  disabled={role.is_system || saving}
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
                  <div className="flex items-center gap-2">
                    <span className="inline-block h-3 w-3 rounded-sm bg-amber-200 dark:bg-amber-700" />
                    <span className="text-muted-foreground">Unsaved matrix change</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
