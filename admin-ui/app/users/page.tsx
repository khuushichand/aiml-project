'use client';

import { useCallback, useEffect, useMemo, useState, Suspense } from 'react';
import { useForm, FormProvider } from 'react-hook-form';
import { z } from 'zod';
import { zodResolver } from '@hookform/resolvers/zod';
import { PermissionGuard, usePermissions } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Checkbox } from '@/components/ui/checkbox';
import { Form, FormCheckbox, FormInput, FormSelect } from '@/components/ui/form';
import { Eye, Key, Search, Plus, Trash2, UserCheck, UserX, BookmarkPlus, BookmarkX } from 'lucide-react';
import { api } from '@/lib/api-client';
import { User } from '@/types';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportUsers, ExportFormat } from '@/lib/export';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { useUrlState, useUrlPagination } from '@/lib/use-url-state';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import Link from 'next/link';

type SavedUserView = {
  id: string;
  name: string;
  query: string;
};

const SAVED_VIEWS_STORAGE_KEY = 'admin_users_saved_views';

const createUserSchema = z.object({
  username: z.string().min(1, 'Username is required'),
  email: z.string().email('Enter a valid email address'),
  password: z.string().min(10, 'Password must be at least 10 characters'),
  role: z.enum(['user', 'admin', 'service']),
  is_active: z.boolean(),
  is_verified: z.boolean(),
});

type CreateUserFormData = z.infer<typeof createUserSchema>;

function UsersPageContent() {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();
  const { selectedOrg } = useOrgContext();
  const { user: currentUser } = usePermissions();
  const currentUserId = currentUser?.id;
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [bulkBusy, setBulkBusy] = useState(false);
  const [selectedUserIds, setSelectedUserIds] = useState<Set<number>>(new Set());
  const [showCreateUserDialog, setShowCreateUserDialog] = useState(false);
  const [createUserError, setCreateUserError] = useState('');
  const [creatingUser, setCreatingUser] = useState(false);
  const [savedViews, setSavedViews] = useState<SavedUserView[]>([]);
  const [showSaveViewDialog, setShowSaveViewDialog] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');
  const [saveViewError, setSaveViewError] = useState('');
  const createUserForm = useForm<CreateUserFormData>({
    resolver: zodResolver(createUserSchema),
    defaultValues: {
      username: '',
      email: '',
      password: '',
      role: 'user',
      is_active: true,
      is_verified: true,
    },
  });

  // URL state for search
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });
  const activeViewId = useMemo(() => {
    const match = savedViews.find((view) => view.query === (searchQuery || ''));
    return match ? match.id : '';
  }, [savedViews, searchQuery]);

  // URL state for pagination
  const { page: currentPage, pageSize, setPage: setCurrentPage, setPageSize, resetPagination } = useUrlPagination();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = window.localStorage.getItem(SAVED_VIEWS_STORAGE_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        setSavedViews(parsed as SavedUserView[]);
      }
    } catch (err) {
      console.warn('Failed to load saved user views:', err);
    }
  }, []);

  useEffect(() => {
    if (!showCreateUserDialog) {
      createUserForm.reset();
      setCreateUserError('');
    }
  }, [createUserForm, showCreateUserDialog]);

  const persistSavedViews = useCallback((views: SavedUserView[]) => {
    setSavedViews(views);
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(SAVED_VIEWS_STORAGE_KEY, JSON.stringify(views));
    } catch (err) {
      console.warn('Failed to persist saved user views:', err);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, string> = { limit: '200' };
      if (selectedOrg) params.org_id = String(selectedOrg.id);
      if (searchQuery) params.search = searchQuery;
      const data = await api.getUsers(params);
      setUsers(data);
    } catch (error: unknown) {
      console.error('Failed to load users:', error);
      setError(error instanceof Error && error.message ? error.message : 'Failed to load users');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedOrg]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  useEffect(() => {
    setSelectedUserIds((prev) => {
      if (prev.size === 0) return prev;
      const available = new Set(users.map((user) => user.id));
      const next = new Set<number>();
      prev.forEach((id) => {
        if (available.has(id) && id !== currentUserId) {
          next.add(id);
        }
      });
      return next;
    });
  }, [currentUserId, users]);

  const filteredUsers = users.filter((user) => {
    if (!searchQuery) return true;
    const query = (searchQuery || '').toLowerCase();
    return (
      user.username?.toLowerCase().includes(query) ||
      user.email?.toLowerCase().includes(query) ||
      user.role?.toLowerCase().includes(query)
    );
  });

  // Pagination calculations
  const totalItems = filteredUsers.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedUsers = filteredUsers.slice(startIndex, startIndex + pageSize);
  const selectableUsers = currentUserId
    ? paginatedUsers.filter((user) => user.id !== currentUserId)
    : paginatedUsers;
  const allVisibleSelected = selectableUsers.length > 0
    && selectableUsers.every((user) => selectedUserIds.has(user.id));
  const selectedCount = selectedUserIds.size;

  const handlePageChange = (page: number) => {
    setCurrentPage(page);
  };

  const handlePageSizeChange = (size: number) => {
    setPageSize(size);
    resetPagination();
  };

  const handleSearchChange = (value: string) => {
    setSearchQuery(value || undefined);
    resetPagination();
  };

  const handleToggleSelectUser = (userId: number, checked: boolean) => {
    if (currentUserId && userId === currentUserId) return;
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        next.add(userId);
      } else {
        next.delete(userId);
      }
      return next;
    });
  };

  const handleToggleSelectAllVisible = (checked: boolean) => {
    setSelectedUserIds((prev) => {
      const next = new Set(prev);
      if (checked) {
        paginatedUsers.forEach((user) => {
          if (currentUserId && user.id === currentUserId) return;
          next.add(user.id);
        });
      } else {
        paginatedUsers.forEach((user) => {
          if (currentUserId && user.id === currentUserId) return;
          next.delete(user.id);
        });
      }
      return next;
    });
  };

  const handleClearSelection = () => {
    setSelectedUserIds(new Set());
  };

  const handleBulkToggleActive = async (nextState: boolean) => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0) return;
    const confirmed = await confirm({
      title: nextState ? 'Activate selected users' : 'Deactivate selected users',
      message: `${nextState ? 'Activate' : 'Deactivate'} ${ids.length} selected user${ids.length !== 1 ? 's' : ''}?`,
      confirmText: nextState ? 'Activate' : 'Deactivate',
      variant: nextState ? 'default' : 'warning',
      icon: nextState ? 'check' : 'warning',
    });
    if (!confirmed) return;

    try {
      setBulkBusy(true);
      const results = await Promise.allSettled(
        ids.map((id) => api.updateUser(id.toString(), { is_active: nextState }))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      if (failures > 0) {
        showError(
          'Bulk update incomplete',
          `${ids.length - failures} updated, ${failures} failed.`
        );
      } else {
        success(
          'Users updated',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} ${nextState ? 'activated' : 'deactivated'}.`
        );
      }
      handleClearSelection();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update users';
      showError('Bulk update failed', message);
    } finally {
      setBulkBusy(false);
    }
  };

  const handleBulkDelete = async () => {
    const ids = Array.from(selectedUserIds);
    if (ids.length === 0) return;
    if (currentUser && ids.includes(currentUser.id)) {
      showError('Cannot delete yourself', 'Remove your account from the selection to continue.');
      return;
    }
    const confirmed = await confirm({
      title: 'Delete selected users',
      message: `Delete ${ids.length} selected user${ids.length !== 1 ? 's' : ''}? This cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      setBulkBusy(true);
      const results = await Promise.allSettled(
        ids.map((id) => api.deleteUser(id.toString()))
      );
      const failures = results.filter((result) => result.status === 'rejected').length;
      if (failures > 0) {
        showError(
          'Bulk delete incomplete',
          `${ids.length - failures} deleted, ${failures} failed.`
        );
      } else {
        success(
          'Users deleted',
          `${ids.length} user${ids.length !== 1 ? 's' : ''} removed.`
        );
      }
      handleClearSelection();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete users';
      showError('Bulk delete failed', message);
    } finally {
      setBulkBusy(false);
    }
  };

  const getRoleBadgeVariant = (role: string) => {
    switch (role) {
      case 'admin':
      case 'super_admin':
      case 'owner':
        return 'default';
      default:
        return 'secondary';
    }
  };

  const formatStorageUsage = (usedMb: number, quotaMb: number) => {
    const percentage = quotaMb > 0 ? (usedMb / quotaMb) * 100 : 0;
    return {
      text: `${usedMb.toFixed(1)} / ${quotaMb} MB`,
      percentage: Math.min(percentage, 100),
    };
  };

  const handleExport = (format: ExportFormat) => {
    exportUsers(filteredUsers, format);
  };

  const handleApplySavedView = (viewId: string) => {
    if (!viewId) {
      setSearchQuery(undefined);
      resetPagination();
      return;
    }
    const view = savedViews.find((item) => item.id === viewId);
    if (!view) return;
    setSearchQuery(view.query || undefined);
    resetPagination();
  };

  const handleSaveView = () => {
    const name = saveViewName.trim();
    if (!name) {
      setSaveViewError('Provide a name for this view.');
      return;
    }
    const query = searchQuery || '';
    const newView: SavedUserView = {
      id: `${Date.now()}`,
      name,
      query,
    };
    persistSavedViews([newView, ...savedViews]);
    setSaveViewName('');
    setSaveViewError('');
    setShowSaveViewDialog(false);
    success('Saved view', `${name} has been added.`);
  };

  const handleDeleteView = async () => {
    if (!activeViewId) return;
    const view = savedViews.find((item) => item.id === activeViewId);
    if (!view) return;
    const confirmed = await confirm({
      title: 'Delete saved view',
      message: `Delete "${view.name}"?`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;
    const next = savedViews.filter((item) => item.id !== activeViewId);
    persistSavedViews(next);
    success('Saved view removed', `"${view.name}" deleted.`);
  };

  const handleCreateUserSubmit = createUserForm.handleSubmit(async (data) => {
    setCreateUserError('');
    try {
      setCreatingUser(true);
      await api.createUser({
        username: data.username,
        email: data.email,
        password: data.password,
        role: data.role,
        is_active: data.is_active,
        is_verified: data.is_verified,
      });
      success('User created', `${data.username} added.`);
      setShowCreateUserDialog(false);
      createUserForm.reset();
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to create user';
      setCreateUserError(message);
      showError('Create user failed', message);
    } finally {
      setCreatingUser(false);
    }
  });

  const handleToggleActive = async (user: User) => {
    const nextState = !user.is_active;
    const confirmed = await confirm({
      title: nextState ? 'Activate User' : 'Deactivate User',
      message: `${nextState ? 'Activate' : 'Deactivate'} ${user.username || user.email}?`,
      confirmText: nextState ? 'Activate' : 'Deactivate',
      variant: nextState ? 'default' : 'warning',
      icon: nextState ? 'check' : 'warning',
    });
    if (!confirmed) return;

    try {
      await api.updateUser(user.id.toString(), { is_active: nextState });
      success('User updated', `${user.username || user.email} ${nextState ? 'activated' : 'deactivated'}.`);
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to update user';
      showError('Update failed', message);
    }
  };

  const handleDeleteUser = async (user: User) => {
    if (currentUser && user.id === currentUser.id) {
      showError('Cannot delete yourself', 'You cannot delete your own account.');
      return;
    }
    const confirmed = await confirm({
      title: 'Delete User',
      message: `Delete ${user.username || user.email}? This cannot be undone.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      await api.deleteUser(user.id.toString());
      success('User deleted', `${user.username || user.email} removed.`);
      void loadUsers();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to delete user';
      showError('Delete failed', message);
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold">Users</h1>
                <p className="text-muted-foreground">Manage system users and their access</p>
              </div>
              <div className="flex flex-wrap gap-2">
                <ExportMenu
                  onExport={handleExport}
                  disabled={filteredUsers.length === 0}
                />
                <Dialog open={showCreateUserDialog} onOpenChange={setShowCreateUserDialog}>
                  <DialogTrigger asChild>
                    <Button>
                      <Plus className="mr-2 h-4 w-4" />
                      Create User
                    </Button>
                  </DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Create user</DialogTitle>
                      <DialogDescription>Create a user with a temporary password.</DialogDescription>
                    </DialogHeader>
                    {createUserError && (
                      <Alert variant="destructive">
                        <AlertDescription>{createUserError}</AlertDescription>
                      </Alert>
                    )}
                    <FormProvider {...createUserForm}>
                      <Form onSubmit={handleCreateUserSubmit}>
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <FormInput<CreateUserFormData>
                            name="username"
                            label="Username"
                            required
                          />
                          <FormInput<CreateUserFormData>
                            name="email"
                            label="Email"
                            type="email"
                            required
                          />
                        </div>
                        <FormInput<CreateUserFormData>
                          name="password"
                          label="Password"
                          type="password"
                          description="Minimum 10 characters."
                          required
                        />
                        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                          <FormSelect<CreateUserFormData>
                            name="role"
                            label="Role"
                            options={[
                              { value: 'user', label: 'User' },
                              { value: 'admin', label: 'Admin' },
                              { value: 'service', label: 'Service' },
                            ]}
                          />
                          <div className="space-y-2">
                            <Label className="block">Status</Label>
                            <div className="space-y-2">
                              <FormCheckbox<CreateUserFormData>
                                name="is_active"
                                label="Active"
                              />
                              <FormCheckbox<CreateUserFormData>
                                name="is_verified"
                                label="Verified"
                              />
                            </div>
                          </div>
                        </div>
                        <DialogFooter className="gap-2 sm:gap-0">
                          <Button
                            type="button"
                            variant="outline"
                            onClick={() => setShowCreateUserDialog(false)}
                            disabled={creatingUser}
                          >
                            Cancel
                          </Button>
                          <Button type="submit" disabled={creatingUser}>
                            {creatingUser ? 'Creating...' : 'Create user'}
                          </Button>
                        </DialogFooter>
                      </Form>
                    </FormProvider>
                  </DialogContent>
                </Dialog>
              </div>
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Search */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="relative max-w-md w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search by username, email, or role..."
                      value={searchQuery || ''}
                      onChange={(e) => handleSearchChange(e.target.value)}
                      className="pl-10"
                    />
                  </div>
                  <div className="flex flex-wrap items-center gap-2">
                    <Select
                      value={activeViewId}
                      onChange={(event) => handleApplySavedView(event.target.value)}
                      className="min-w-[200px]"
                      disabled={savedViews.length === 0}
                    >
                      <option value="">Saved views</option>
                      {savedViews.map((view) => (
                        <option key={view.id} value={view.id}>
                          {view.name}
                        </option>
                      ))}
                    </Select>
                    <Dialog open={showSaveViewDialog} onOpenChange={(open) => {
                      setShowSaveViewDialog(open);
                      if (!open) {
                        setSaveViewError('');
                        setSaveViewName('');
                      }
                    }}>
                      <DialogTrigger asChild>
                        <Button variant="outline">
                          <BookmarkPlus className="mr-2 h-4 w-4" />
                          Save view
                        </Button>
                      </DialogTrigger>
                      <DialogContent>
                        <DialogHeader>
                          <DialogTitle>Save view</DialogTitle>
                          <DialogDescription>Store the current search for quick reuse.</DialogDescription>
                        </DialogHeader>
                        {saveViewError && (
                          <Alert variant="destructive">
                            <AlertDescription>{saveViewError}</AlertDescription>
                          </Alert>
                        )}
                        <div className="space-y-2">
                          <Label htmlFor="saved-view-name">View name</Label>
                          <Input
                            id="saved-view-name"
                            value={saveViewName}
                            onChange={(event) => setSaveViewName(event.target.value)}
                            placeholder="e.g., Inactive admins"
                          />
                          <p className="text-xs text-muted-foreground">
                            Current search: {searchQuery || 'All users'}
                          </p>
                        </div>
                        <DialogFooter>
                          <Button variant="outline" onClick={() => setShowSaveViewDialog(false)}>
                            Cancel
                          </Button>
                          <Button onClick={handleSaveView}>
                            Save view
                          </Button>
                        </DialogFooter>
                      </DialogContent>
                    </Dialog>
                    <Button
                      variant="outline"
                      onClick={handleDeleteView}
                      disabled={!activeViewId}
                    >
                      <BookmarkX className="mr-2 h-4 w-4" />
                      Delete view
                    </Button>
                  </div>
                </div>
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Users List</CardTitle>
                <CardDescription>
                  {totalItems} user{totalItems !== 1 ? 's' : ''} found
                </CardDescription>
              </CardHeader>
              <CardContent>
                {selectedCount > 0 && (
                  <div className="mb-4 flex flex-col gap-3 rounded-md border bg-muted/20 p-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">{selectedCount} selected</Badge>
                      <span className="text-sm text-muted-foreground">
                        Bulk actions apply to selected users.
                      </span>
                    </div>
                    <div className="flex flex-wrap gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkToggleActive(true)}
                        disabled={bulkBusy}
                      >
                        <UserCheck className="mr-2 h-4 w-4" />
                        Activate
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleBulkToggleActive(false)}
                        disabled={bulkBusy}
                      >
                        <UserX className="mr-2 h-4 w-4" />
                        Deactivate
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={handleBulkDelete}
                        disabled={bulkBusy}
                      >
                        <Trash2 className="mr-2 h-4 w-4 text-destructive" />
                        Delete
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={handleClearSelection}
                        disabled={bulkBusy}
                      >
                        Clear selection
                      </Button>
                    </div>
                  </div>
                )}
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={5} columns={9} />
                  </div>
                ) : filteredUsers.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    {searchQuery ? 'No users match your search' : 'No users found'}
                  </div>
                ) : (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead className="w-10">
                            <Checkbox
                              checked={allVisibleSelected}
                              onCheckedChange={handleToggleSelectAllVisible}
                              aria-label="Select all visible users"
                            />
                          </TableHead>
                          <TableHead>ID</TableHead>
                          <TableHead>Username</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead>Storage</TableHead>
                          <TableHead>Last Login</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedUsers.map((user) => {
                          const storage = formatStorageUsage(
                            user.storage_used_mb || 0,
                            user.storage_quota_mb || 0
                          );
                          const isCurrentUser = currentUserId === user.id;
                          return (
                            <TableRow key={user.id}>
                              <TableCell>
                                <Checkbox
                                  checked={selectedUserIds.has(user.id)}
                                  onCheckedChange={(checked) => handleToggleSelectUser(user.id, checked)}
                                  aria-label={`Select user ${user.username || user.email || user.id}`}
                                  disabled={isCurrentUser}
                                />
                              </TableCell>
                              <TableCell className="font-mono text-sm">{user.id}</TableCell>
                              <TableCell className="font-medium">{user.username}</TableCell>
                              <TableCell>{user.email}</TableCell>
                              <TableCell>
                                <Badge variant={getRoleBadgeVariant(user.role)}>
                                  {user.role}
                                </Badge>
                              </TableCell>
                              <TableCell>
                                <Badge variant={user.is_active ? 'default' : 'destructive'}>
                                  {user.is_active ? 'Active' : 'Inactive'}
                                </Badge>
                                {user.is_verified && (
                                  <Badge variant="outline" className="ml-1">
                                    Verified
                                  </Badge>
                                )}
                              </TableCell>
                              <TableCell>
                                <div className="space-y-1">
                                  <div className="text-xs">{storage.text}</div>
                                  <div className="w-20 bg-gray-200 rounded-full h-1.5">
                                    <div
                                      className={`h-1.5 rounded-full ${
                                        storage.percentage > 90 ? 'bg-red-500' :
                                        storage.percentage > 70 ? 'bg-yellow-500' :
                                        'bg-green-500'
                                      }`}
                                      style={{ width: `${storage.percentage}%` }}
                                    />
                                  </div>
                                </div>
                              </TableCell>
                              <TableCell className="text-muted-foreground text-sm">
                                {user.last_login
                                  ? new Date(user.last_login).toLocaleDateString()
                                  : 'Never'}
                              </TableCell>
                              <TableCell className="text-right">
                                <div className="flex justify-end gap-1">
                                  <Link href={`/users/${user.id}`}>
                                    <Button variant="ghost" size="sm" title="View details">
                                      <Eye className="h-4 w-4" />
                                    </Button>
                                  </Link>
                                  <Link href={`/users/${user.id}/api-keys`}>
                                    <Button variant="ghost" size="sm" title="Manage API keys">
                                      <Key className="h-4 w-4" />
                                    </Button>
                                  </Link>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    title={user.is_active ? 'Deactivate user' : 'Activate user'}
                                    onClick={() => handleToggleActive(user)}
                                  >
                                    {user.is_active ? (
                                      <UserX className="h-4 w-4" />
                                    ) : (
                                      <UserCheck className="h-4 w-4" />
                                    )}
                                  </Button>
                                  <Button
                                    variant="ghost"
                                    size="sm"
                                    title={isCurrentUser ? 'Cannot delete yourself' : 'Delete user'}
                                    onClick={() => handleDeleteUser(user)}
                                    disabled={isCurrentUser}
                                  >
                                    <Trash2 className="h-4 w-4 text-destructive" />
                                  </Button>
                                </div>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>

                    <Pagination
                      currentPage={currentPage}
                      totalPages={totalPages}
                      totalItems={totalItems}
                      pageSize={pageSize}
                      onPageChange={handlePageChange}
                      onPageSizeChange={handlePageSizeChange}
                    />
                  </>
                )}
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}

// Wrap with Suspense for useSearchParams
export default function UsersPage() {
  return (
    <Suspense fallback={
      <PermissionGuard variant="route" requireAuth role="admin">
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <Skeleton className="h-8 w-32 mb-2" />
              <Skeleton className="h-4 w-64" />
            </div>
            <TableSkeleton rows={5} columns={9} />
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    }>
      <UsersPageContent />
    </Suspense>
  );
}
