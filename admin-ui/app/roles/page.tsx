'use client';

import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { useToast } from '@/components/ui/toast';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { Shield, Plus, Trash2, Lock, Settings } from 'lucide-react';
import { api } from '@/lib/api-client';
import { Role, Permission } from '@/types';
import Link from 'next/link';

export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([]);
  const [permissions, setPermissions] = useState<Permission[]>([]);
  const [loading, setLoading] = useState(true);
  const { success, error: showError } = useToast();
  const confirm = useConfirm();

  // Create role dialog
  const [showCreateRole, setShowCreateRole] = useState(false);
  const [newRoleName, setNewRoleName] = useState('');
  const [newRoleDescription, setNewRoleDescription] = useState('');

  // Create permission dialog
  const [showCreatePermission, setShowCreatePermission] = useState(false);
  const [newPermName, setNewPermName] = useState('');
  const [newPermDescription, setNewPermDescription] = useState('');

  useEffect(() => {
    loadData();
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [rolesData, permsData] = await Promise.all([
        api.getRoles(),
        api.getPermissions(),
      ]);
      setRoles(Array.isArray(rolesData) ? rolesData : []);
      setPermissions(Array.isArray(permsData) ? permsData : []);
    } catch (err: any) {
      console.error('Failed to load data:', err);
      showError('Failed to load data', err.message);
    } finally {
      setLoading(false);
    }
  };

  const handleCreateRole = async () => {
    if (!newRoleName.trim()) {
      showError('Validation Error', 'Role name is required');
      return;
    }

    try {
      await api.createRole({
        name: newRoleName.trim(),
        description: newRoleDescription.trim() || undefined,
      });
      success('Role Created', `Role "${newRoleName}" has been created`);
      setShowCreateRole(false);
      setNewRoleName('');
      setNewRoleDescription('');
      loadData();
    } catch (err: any) {
      console.error('Failed to create role:', err);
      showError('Failed to create role', err.message);
    }
  };

  const handleDeleteRole = async (role: Role) => {
    if (role.is_system) {
      showError('Cannot Delete', 'System roles cannot be deleted');
      return;
    }

    const confirmed = await confirm({
      title: 'Delete Role',
      message: `Are you sure you want to delete the role "${role.name}"? This action cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      await api.deleteRole(role.id.toString());
      success('Role Deleted', `Role "${role.name}" has been deleted`);
      loadData();
    } catch (err: any) {
      console.error('Failed to delete role:', err);
      showError('Failed to delete role', err.message);
    }
  };

  const handleCreatePermission = async () => {
    if (!newPermName.trim()) {
      showError('Validation Error', 'Permission name is required');
      return;
    }

    try {
      await api.createPermission({
        name: newPermName.trim(),
        description: newPermDescription.trim() || undefined,
      });
      success('Permission Created', `Permission "${newPermName}" has been created`);
      setShowCreatePermission(false);
      setNewPermName('');
      setNewPermDescription('');
      loadData();
    } catch (err: any) {
      console.error('Failed to create permission:', err);
      showError('Failed to create permission', err.message);
    }
  };

  const handleDeletePermission = async (perm: Permission) => {
    const confirmed = await confirm({
      title: 'Delete Permission',
      message: `Are you sure you want to delete the permission "${perm.name}"?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      await api.deletePermission(perm.id.toString());
      success('Permission Deleted', `Permission "${perm.name}" has been deleted`);
      loadData();
    } catch (err: any) {
      console.error('Failed to delete permission:', err);
      showError('Failed to delete permission', err.message);
    }
  };

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <h1 className="text-3xl font-bold">Roles & Permissions</h1>
              <p className="text-muted-foreground">
                Manage user roles and their associated permissions
              </p>
            </div>

            {/* Info Card */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex items-start gap-4">
                  <Shield className="h-8 w-8 text-primary mt-1" />
                  <div>
                    <h3 className="font-semibold">Role-Based Access Control (RBAC)</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Roles define what actions users can perform in the system. Each role can have
                      multiple permissions assigned to it. System roles cannot be deleted.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            <div className="grid gap-6 lg:grid-cols-2">
              {/* Roles Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Roles</CardTitle>
                    <CardDescription>
                      {roles.length} role{roles.length !== 1 ? 's' : ''} defined
                    </CardDescription>
                  </div>
                  <Dialog open={showCreateRole} onOpenChange={setShowCreateRole}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        Add Role
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Role</DialogTitle>
                        <DialogDescription>
                          Add a new role to the system. You can assign permissions after creation.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="roleName">Role Name</Label>
                          <Input
                            id="roleName"
                            placeholder="e.g., editor, viewer, moderator"
                            value={newRoleName}
                            onChange={(e) => setNewRoleName(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="roleDescription">Description (optional)</Label>
                          <Input
                            id="roleDescription"
                            placeholder="What this role is for..."
                            value={newRoleDescription}
                            onChange={(e) => setNewRoleDescription(e.target.value)}
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setShowCreateRole(false)}>Cancel</Button>
                        <Button onClick={handleCreateRole}>Create Role</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-center text-muted-foreground py-8">Loading...</div>
                  ) : roles.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No roles found. Create one to get started.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Role</TableHead>
                          <TableHead>Type</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {roles.map((role) => (
                          <TableRow key={role.id}>
                            <TableCell>
                              <div>
                                <div className="font-medium">{role.name}</div>
                                {role.description && (
                                  <div className="text-xs text-muted-foreground">{role.description}</div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell>
                              {role.is_system ? (
                                <Badge variant="secondary">
                                  <Lock className="mr-1 h-3 w-3" />
                                  System
                                </Badge>
                              ) : (
                                <Badge variant="outline">Custom</Badge>
                              )}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1">
                                <Link href={`/roles/${role.id}`}>
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    title="Manage role"
                                  >
                                    <Settings className="mr-2 h-4 w-4" />
                                    Manage
                                  </Button>
                                </Link>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleDeleteRole(role)}
                                  disabled={role.is_system}
                                  title={role.is_system ? 'Cannot delete system roles' : 'Delete role'}
                                >
                                  <Trash2 className={`h-4 w-4 ${role.is_system ? 'text-muted' : 'text-red-500'}`} />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              {/* Permissions Section */}
              <Card>
                <CardHeader className="flex flex-row items-center justify-between">
                  <div>
                    <CardTitle>Permissions</CardTitle>
                    <CardDescription>
                      {permissions.length} permission{permissions.length !== 1 ? 's' : ''} available
                    </CardDescription>
                  </div>
                  <Dialog open={showCreatePermission} onOpenChange={setShowCreatePermission}>
                    <DialogTrigger asChild>
                      <Button size="sm">
                        <Plus className="mr-2 h-4 w-4" />
                        Add Permission
                      </Button>
                    </DialogTrigger>
                    <DialogContent>
                      <DialogHeader>
                        <DialogTitle>Create New Permission</DialogTitle>
                        <DialogDescription>
                          Add a new permission that can be assigned to roles.
                        </DialogDescription>
                      </DialogHeader>
                      <div className="space-y-4 py-4">
                        <div className="space-y-2">
                          <Label htmlFor="permName">Permission Name</Label>
                          <Input
                            id="permName"
                            placeholder="e.g., read:users, write:media"
                            value={newPermName}
                            onChange={(e) => setNewPermName(e.target.value)}
                          />
                        </div>
                        <div className="space-y-2">
                          <Label htmlFor="permDescription">Description (optional)</Label>
                          <Input
                            id="permDescription"
                            placeholder="What this permission allows..."
                            value={newPermDescription}
                            onChange={(e) => setNewPermDescription(e.target.value)}
                          />
                        </div>
                      </div>
                      <DialogFooter>
                        <Button variant="outline" onClick={() => setShowCreatePermission(false)}>Cancel</Button>
                        <Button onClick={handleCreatePermission}>Create Permission</Button>
                      </DialogFooter>
                    </DialogContent>
                  </Dialog>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-center text-muted-foreground py-8">Loading...</div>
                  ) : permissions.length === 0 ? (
                    <div className="text-center text-muted-foreground py-8">
                      No permissions found. Create one to get started.
                    </div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Permission</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {permissions.map((perm) => (
                          <TableRow key={perm.id}>
                            <TableCell>
                              <div>
                                <div className="font-medium font-mono text-sm">{perm.name}</div>
                                {perm.description && (
                                  <div className="text-xs text-muted-foreground">{perm.description}</div>
                                )}
                              </div>
                            </TableCell>
                            <TableCell className="text-right">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeletePermission(perm)}
                                title="Delete permission"
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </div>

            {/* Permission Matrix Link */}
            <Card className="mt-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Settings className="h-5 w-5" />
                  Advanced Configuration
                </CardTitle>
              </CardHeader>
              <CardContent>
                <p className="text-sm text-muted-foreground mb-4">
                  For advanced role-permission mapping and bulk assignment, use the permission matrix view.
                </p>
                <Link href="/roles/matrix">
                  <Button variant="outline">
                    Open Permission Matrix
                  </Button>
                </Link>
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
