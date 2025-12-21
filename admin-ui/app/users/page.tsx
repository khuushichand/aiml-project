'use client';

import { useEffect, useState, Suspense } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { Eye, Key, Search } from 'lucide-react';
import { api } from '@/lib/api-client';
import { User } from '@/types';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportUsers, ExportFormat } from '@/lib/export';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { useUrlState, useUrlPagination } from '@/lib/use-url-state';
import Link from 'next/link';

function UsersPageContent() {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // URL state for search
  const [searchQuery, setSearchQuery] = useUrlState<string>('q', { defaultValue: '' });

  // URL state for pagination
  const { page: currentPage, pageSize, setPage: setCurrentPage, setPageSize, resetPagination } = useUrlPagination();

  useEffect(() => {
    loadUsers();
  }, []);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (error: unknown) {
      console.error('Failed to load users:', error);
      setError(error instanceof Error && error.message ? error.message : 'Failed to load users');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

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

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h1 className="text-3xl font-bold">Users</h1>
                <p className="text-muted-foreground">Manage system users and their access</p>
              </div>
              <ExportMenu
                onExport={handleExport}
                disabled={filteredUsers.length === 0}
              />
            </div>

            {error && (
              <Alert variant="destructive" className="mb-6">
                <AlertDescription>{error}</AlertDescription>
              </Alert>
            )}

            {/* Search */}
            <Card className="mb-6">
              <CardContent className="pt-6">
                <div className="relative max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search by username, email, or role..."
                    value={searchQuery || ''}
                    onChange={(e) => handleSearchChange(e.target.value)}
                    className="pl-10"
                  />
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
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={5} columns={8} />
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
                          return (
                            <TableRow key={user.id}>
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
    </ProtectedRoute>
  );
}

// Wrap with Suspense for useSearchParams
export default function UsersPage() {
  return (
    <Suspense fallback={
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <Skeleton className="h-8 w-32 mb-2" />
              <Skeleton className="h-4 w-64" />
            </div>
            <TableSkeleton rows={5} columns={8} />
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    }>
      <UsersPageContent />
    </Suspense>
  );
}
