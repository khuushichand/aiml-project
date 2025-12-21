'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { ArrowLeft, Shield, Lock, Save, Users, Trash2, Check, X } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Role, Permission, User } from '@/types';
import Link from 'next/link';

const MAX_DESCRIPTION_LENGTH = 500;
const USER_LIST_LIMIT = 10;

export default function RoleDetailPage() {
  const params = useParams();
  const router = useRouter();
  const confirm = useConfirm();
  const roleId = params.id as string;

  const [role, setRole] = useState<Role | null>(null);
  const [allPermissions, setAllPermissions] = useState<Permission[]>([]);
  const [rolePermissions, setRolePermissions] = useState<Set<number>>(new Set());
  const [roleUsers, setRoleUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  // Edit mode
  const [editMode, setEditMode] = useState(false);
  const [editName, setEditName] = useState('');
  const [editDescription, setEditDescription] = useState('');

  useEffect(() => {
    if (!success) {
      return;
    }
    const timer = setTimeout(() => setSuccess(''), 2000);
    return () => clearTimeout(timer);
  }, [success]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

      const [roleData, allPermsData, rolePermsData, usersData] = await Promise.allSettled([
        api.getRole(roleId),
        api.getPermissions(),
        api.getRolePermissions(roleId),
        api.getRoleUsers(roleId),
      ]);

      if (roleData.status === 'fulfilled') {
        setRole(roleData.value);
        setEditName(roleData.value.name || '');
        setEditDescription(roleData.value.description || '');
      }

      if (allPermsData.status === 'fulfilled') {
        setAllPermissions(Array.isArray(allPermsData.value) ? allPermsData.value : []);
      }

      if (rolePermsData.status === 'fulfilled') {
        const perms = Array.isArray(rolePermsData.value) ? rolePermsData.value : [];
        const permIds = new Set(perms.map((p: Permission) => p.id));
        setRolePermissions(permIds);
      }

      if (usersData.status === 'fulfilled') {
        setRoleUsers(Array.isArray(usersData.value) ? usersData.value : []);
      }
    } catch (err: unknown) {
      console.error('Failed to load role data:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to load role data');
    } finally {
      setLoading(false);
    }
  }, [roleId]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleTogglePermission = async (permissionId: number) => {
    if (role?.is_system) {
      setError('Cannot modify permissions for system roles');
      return;
    }

    const hasPermission = rolePermissions.has(permissionId);

    try {
      setError('');
      if (hasPermission) {
        await api.removePermissionFromRole(roleId, permissionId.toString());
        setRolePermissions((prev) => {
          const newSet = new Set(prev);
          newSet.delete(permissionId);
          return newSet;
        });
        setSuccess('Permission removed');
      } else {
        await api.assignPermissionToRole(roleId, permissionId.toString());
        setRolePermissions((prev) => {
          const newSet = new Set(prev);
          newSet.add(permissionId);
          return newSet;
        });
        setSuccess('Permission assigned');
      }
    } catch (err: unknown) {
      console.error('Failed to update permission:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to update permission');
    }
  };

  const handleSaveRole = async () => {
    if (!editName.trim()) {
      setError('Role name is required');
      return;
    }
    const trimmedDescription = editDescription.trim();
    if (trimmedDescription.length > MAX_DESCRIPTION_LENGTH) {
      setError(`Description must be ${MAX_DESCRIPTION_LENGTH} characters or less`);
      return;
    }

    try {
      setSaving(true);
      setError('');
      await api.updateRole(roleId, {
        name: editName.trim(),
        description: trimmedDescription || undefined,
      });
      setSuccess('Role updated successfully');
      setEditMode(false);
      loadData();
    } catch (err: unknown) {
      console.error('Failed to update role:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to update role');
    } finally {
      setSaving(false);
    }
  };

  const handleCancelEdit = () => {
    setEditName(role?.name || '');
    setEditDescription(role?.description || '');
    setEditMode(false);
  };

  const handleDeleteRole = async () => {
    const confirmed = await confirm({
      title: 'Delete Role',
      message: `Delete role "${role?.name || 'this role'}"? This cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      await api.deleteRole(roleId);
      router.push('/roles');
    } catch (err: unknown) {
      setError(err instanceof Error && err.message ? err.message : 'Failed to delete role');
    }
  };

  // Group permissions by category (based on naming convention like "read:users", "write:media")
  const groupedPermissions = allPermissions.reduce((acc, perm) => {
    const parts = perm.name.split(':');
    const category = parts.length > 1 ? parts[0] : 'general';
    if (!acc[category]) acc[category] = [];
    acc[category].push(perm);
    return acc;
  }, {} as Record<string, Permission[]>);

  if (loading) {
    return (
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="text-center text-muted-foreground py-8">Loading...</div>
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    );
  }

  if (!role) {
    return (
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <Alert variant="destructive">
              <AlertDescription>Role not found</AlertDescription>
            </Alert>
            <Button onClick={() => router.push('/roles')} className="mt-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Roles
            </Button>
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    );
  }

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
                  <div className="flex items-center gap-3">
                    <Shield className="h-8 w-8 text-primary" />
                    {editMode ? (
                      <Input
                        value={editName}
                        onChange={(e) => setEditName(e.target.value)}
                        className="text-2xl font-bold h-auto py-1"
                        placeholder="Role name"
                      />
                    ) : (
                      <h1 className="text-3xl font-bold">{role.name}</h1>
                    )}
                    {role.is_system && (
                      <Badge variant="secondary">
                        <Lock className="mr-1 h-3 w-3" />
                        System
                      </Badge>
                    )}
                  </div>
                  {editMode ? (
                    <Input
                      value={editDescription}
                      onChange={(e) => setEditDescription(e.target.value)}
                      className="mt-2 text-sm"
                      placeholder="Description (optional)"
                    />
                  ) : (
                    <p className="text-muted-foreground mt-1">
                      {role.description || 'No description'}
                    </p>
                  )}
                </div>
              </div>
              <div className="flex gap-2">
                {editMode ? (
                  <>
                    <Button variant="outline" onClick={handleCancelEdit}>
                      <X className="mr-2 h-4 w-4" />
                      Cancel
                    </Button>
                    <Button onClick={handleSaveRole} disabled={saving}>
                      <Save className="mr-2 h-4 w-4" />
                      {saving ? 'Saving...' : 'Save'}
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="outline"
                    onClick={() => setEditMode(true)}
                    disabled={role.is_system}
                  >
                    Edit Role
                  </Button>
                )}
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {success && (
              <Alert className="mb-6 bg-green-50 border-green-200">
                <AlertDescription className="text-green-800">{success}</AlertDescription>
              </Alert>
            )}

            <div className="grid gap-6 lg:grid-cols-3">
              {/* Permissions Section */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Permissions</CardTitle>
                  <CardDescription>
                    {rolePermissions.size} of {allPermissions.length} permissions assigned
                    {role.is_system && ' (read-only for system roles)'}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {allPermissions.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No permissions defined in the system.
                      <Link href="/roles" className="block mt-2 text-primary hover:underline">
                        Create permissions first
                      </Link>
                    </div>
                  ) : Object.keys(groupedPermissions).length > 1 ? (
                    // Show grouped view if there are multiple categories
                    <div className="space-y-6">
                      {Object.entries(groupedPermissions).map(([category, perms]) => (
                        <div key={category}>
                          <h4 className="text-sm font-semibold text-muted-foreground uppercase mb-3">
                            {category}
                          </h4>
                          <div className="grid gap-2">
                            {perms.map((perm) => (
                              <div
                                key={perm.id}
                                className={`flex items-center justify-between p-3 rounded-lg border ${
                                  rolePermissions.has(perm.id) ? 'bg-primary/5 border-primary/20' : 'bg-muted/30'
                                }`}
                              >
                                <div className="flex items-center gap-3">
                                  <Checkbox
                                    checked={rolePermissions.has(perm.id)}
                                    onCheckedChange={() => handleTogglePermission(perm.id)}
                                    disabled={role.is_system}
                                  />
                                  <div>
                                    <code className="text-sm font-mono">{perm.name}</code>
                                    {perm.description && (
                                      <p className="text-xs text-muted-foreground">{perm.description}</p>
                                    )}
                                  </div>
                                </div>
                                {rolePermissions.has(perm.id) && (
                                  <Check className="h-4 w-4 text-green-500" />
                                )}
                              </div>
                            ))}
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    // Show flat list if only one category
                    <div className="grid gap-2">
                      {allPermissions.map((perm) => (
                        <div
                          key={perm.id}
                          className={`flex items-center justify-between p-3 rounded-lg border ${
                            rolePermissions.has(perm.id) ? 'bg-primary/5 border-primary/20' : 'bg-muted/30'
                          }`}
                        >
                          <div className="flex items-center gap-3">
                            <Checkbox
                              checked={rolePermissions.has(perm.id)}
                              onCheckedChange={() => handleTogglePermission(perm.id)}
                              disabled={role.is_system}
                            />
                            <div>
                              <code className="text-sm font-mono">{perm.name}</code>
                              {perm.description && (
                                <p className="text-xs text-muted-foreground">{perm.description}</p>
                              )}
                            </div>
                          </div>
                          {rolePermissions.has(perm.id) && (
                            <Check className="h-4 w-4 text-green-500" />
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Users with this role */}
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <Users className="h-5 w-5" />
                    Users
                  </CardTitle>
                  <CardDescription>
                    {roleUsers.length} user{roleUsers.length !== 1 ? 's' : ''} with this role
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {roleUsers.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No users have this role assigned.
                    </div>
                  ) : (
                    <div className="space-y-2">
                      {roleUsers.slice(0, USER_LIST_LIMIT).map((user) => (
                        <Link
                          key={user.id}
                          href={`/users/${user.id}`}
                          className="flex items-center gap-3 p-2 rounded-lg hover:bg-muted transition-colors"
                        >
                          <div className="h-8 w-8 rounded-full bg-primary/10 flex items-center justify-center">
                            <span className="text-xs font-medium">
                              {user.username?.charAt(0).toUpperCase() || '?'}
                            </span>
                          </div>
                          <div className="flex-1 min-w-0">
                            <div className="font-medium truncate">{user.username}</div>
                            <div className="text-xs text-muted-foreground truncate">{user.email}</div>
                          </div>
                        </Link>
                      ))}
                      {roleUsers.length > USER_LIST_LIMIT && (
                        <p className="text-sm text-muted-foreground text-center pt-2">
                          +{roleUsers.length - USER_LIST_LIMIT} more users
                        </p>
                      )}
                    </div>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Quick Actions */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex flex-wrap gap-4">
                  <Link href="/roles/matrix">
                    <Button variant="outline">
                      View Permission Matrix
                    </Button>
                  </Link>
                  <Link href="/roles">
                    <Button variant="outline">
                      Manage All Roles
                    </Button>
                  </Link>
                  {!role.is_system && (
                    <Button
                      variant="outline"
                      className="text-red-500 hover:text-red-600"
                      onClick={handleDeleteRole}
                    >
                      <Trash2 className="mr-2 h-4 w-4" />
                      Delete Role
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
