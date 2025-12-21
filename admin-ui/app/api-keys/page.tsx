'use client';

import { useEffect, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { Key, Search, ExternalLink } from 'lucide-react';
import { api } from '@/lib/api-client';
import { User } from '@/types';
import Link from 'next/link';

interface UserWithKeyCount extends User {
  api_key_count?: number;
}

export default function ApiKeysPage() {
  const [users, setUsers] = useState<UserWithKeyCount[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [searchQuery, setSearchQuery] = useState('');

  // Pagination
  const [currentPage, setCurrentPage] = useState(1);
  const [pageSize, setPageSize] = useState(20);

  useEffect(() => {
    loadUsers();
  }, []);

  // Reset to first page when search changes
  useEffect(() => {
    setCurrentPage(1);
  }, [searchQuery]);

  const loadUsers = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err: unknown) {
      console.error('Failed to load users:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to load users');
      setUsers([]);
    } finally {
      setLoading(false);
    }
  };

  const filteredUsers = users.filter((user) => {
    if (!searchQuery) return true;
    const query = searchQuery.toLowerCase();
    return (
      user.username?.toLowerCase().includes(query) ||
      user.email?.toLowerCase().includes(query)
    );
  });

  // Pagination calculations
  const totalItems = filteredUsers.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedUsers = filteredUsers.slice(startIndex, startIndex + pageSize);

  return (
    <ProtectedRoute>
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
                <div className="relative max-w-md">
                  <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                  <Input
                    placeholder="Search users by name or email..."
                    value={searchQuery}
                    onChange={(e) => setSearchQuery(e.target.value)}
                    className="pl-10"
                  />
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
                  <div className="text-center text-muted-foreground py-8">Loading...</div>
                ) : filteredUsers.length === 0 ? (
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
                        setCurrentPage(1);
                      }}
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
