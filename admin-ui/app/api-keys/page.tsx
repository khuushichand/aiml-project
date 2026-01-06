'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { TableSkeleton } from '@/components/ui/skeleton';
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { Key, Search, ExternalLink, BookmarkPlus, BookmarkX } from 'lucide-react';
import { api } from '@/lib/api-client';
import { User } from '@/types';
import Link from 'next/link';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useUrlPagination, useUrlState } from '@/lib/use-url-state';

interface UserWithKeyCount extends User {
  api_key_count?: number;
}

type SavedKeyView = {
  id: string;
  name: string;
  query: string;
};

const SAVED_VIEWS_STORAGE_KEY = 'admin_api_keys_saved_views';

export default function ApiKeysPage() {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();
  const { selectedOrg } = useOrgContext();
  const [users, setUsers] = useState<UserWithKeyCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });
  const [savedViews, setSavedViews] = useState<SavedKeyView[]>([]);
  const activeViewId = useMemo(() => {
    const match = savedViews.find((view) => view.query === (searchQuery || ''));
    return match ? match.id : '';
  }, [savedViews, searchQuery]);
  const [showSaveViewDialog, setShowSaveViewDialog] = useState(false);
  const [saveViewName, setSaveViewName] = useState('');
  const [saveViewError, setSaveViewError] = useState('');
  const {
    page: currentPage,
    pageSize,
    setPage: setCurrentPage,
    setPageSize,
    resetPagination,
  } = useUrlPagination();

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const stored = window.localStorage.getItem(SAVED_VIEWS_STORAGE_KEY);
      if (!stored) return;
      const parsed = JSON.parse(stored);
      if (Array.isArray(parsed)) {
        setSavedViews(parsed as SavedKeyView[]);
      }
    } catch (err) {
      console.warn('Failed to load saved API key views:', err);
    }
  }, []);

  const persistSavedViews = useCallback((views: SavedKeyView[]) => {
    setSavedViews(views);
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(SAVED_VIEWS_STORAGE_KEY, JSON.stringify(views));
    } catch (err) {
      console.warn('Failed to persist API key saved views:', err);
    }
  }, []);

  const loadUsers = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const params: Record<string, string> = {};
      if (selectedOrg) {
        params.org_id = String(selectedOrg.id);
      }
      if (searchQuery) {
        params.search = searchQuery;
      }
      const data = await api.getUsers(Object.keys(params).length ? params : undefined);
      setUsers(data);
    } catch (err: unknown) {
      console.error('Failed to load users:', err);
      const message = err instanceof Error && err.message ? err.message : 'Failed to load users';
      setError(message);
      showError('Load users failed', message);
      setUsers([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery, selectedOrg, showError]);

  useEffect(() => {
    loadUsers();
  }, [loadUsers]);

  // Pagination calculations
  const totalItems = users.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedUsers = users.slice(startIndex, startIndex + pageSize);

  const handleSearchChange = (value: string) => {
    setSearchQuery(value || undefined);
    resetPagination();
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
    const newView: SavedKeyView = {
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

  return (
    <PermissionGuard variant="route" requireAuth>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <h1 className="text-3xl font-bold">API Keys</h1>
              <p className="text-muted-foreground">
                Manage API keys for all users in the system
              </p>
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
                  <Key className="h-8 w-8 text-primary mt-1" />
                  <div>
                    <h3 className="font-semibold">API Key Management</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      Select a user below to manage their API keys. Each user can have multiple
                      API keys with different scopes and expiration dates.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Search */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="relative max-w-md w-full">
                    <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input
                      placeholder="Search users by name or email..."
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
                          <Label htmlFor="saved-keys-view-name">View name</Label>
                          <Input
                            id="saved-keys-view-name"
                            value={saveViewName}
                            onChange={(event) => setSaveViewName(event.target.value)}
                            placeholder="e.g., Active admins"
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

            {/* Users Table */}
            <Card>
              <CardHeader>
                <CardTitle>Users</CardTitle>
                <CardDescription>
                  {totalItems} user{totalItems !== 1 ? 's' : ''} found - Select a user to manage their API keys
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={5} columns={5} />
                  </div>
                ) : users.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    {searchQuery ? 'No users match your search' : 'No users found'}
                  </div>
                ) : (
                  <>
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>User</TableHead>
                          <TableHead>Email</TableHead>
                          <TableHead>Role</TableHead>
                          <TableHead>Status</TableHead>
                          <TableHead className="text-right">Actions</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {paginatedUsers.map((user) => (
                          <TableRow key={user.id}>
                            <TableCell className="font-medium">{user.username}</TableCell>
                            <TableCell>{user.email}</TableCell>
                            <TableCell>
                              <Badge variant="outline">{user.role}</Badge>
                            </TableCell>
                            <TableCell>
                              <Badge variant={user.is_active ? 'default' : 'secondary'}>
                                {user.is_active ? 'Active' : 'Inactive'}
                              </Badge>
                            </TableCell>
                            <TableCell className="text-right">
                              <Link href={`/users/${user.id}/api-keys`}>
                                <Button variant="outline" size="sm">
                                  <Key className="mr-2 h-4 w-4" />
                                  Manage Keys
                                  <ExternalLink className="ml-2 h-3 w-3" />
                                </Button>
                              </Link>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>

                    <Pagination
                      currentPage={currentPage}
                      totalPages={totalPages}
                      totalItems={totalItems}
                      pageSize={pageSize}
                      onPageChange={setCurrentPage}
                      onPageSizeChange={(size) => {
                        setPageSize(size);
                        resetPagination();
                      }}
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
