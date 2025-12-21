'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { ArrowLeft, Key, Save, Building2, Users } from 'lucide-react';
import { api } from '@/lib/api-client';
import { User } from '@/types';
import Link from 'next/link';

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = params.id as string;

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');

  const [formData, setFormData] = useState({
    username: '',
    email: '',
    role: '',
    is_active: true,
    storage_quota_mb: 0,
  });

  useEffect(() => {
    loadUser();
  }, [userId]);

  const loadUser = async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getUser(userId);
      setUser(data);
      setFormData({
        username: data.username || '',
        email: data.email || '',
        role: data.role || '',
        is_active: data.is_active ?? true,
        storage_quota_mb: data.storage_quota_mb || 0,
      });
    } catch (err: any) {
      console.error('Failed to load user:', err);
      setError(err.message || 'Failed to load user');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      await api.updateUser(userId, formData);
      setSuccess('User updated successfully');
      loadUser();
    } catch (err: any) {
      console.error('Failed to update user:', err);
      setError(err.message || 'Failed to update user');
    } finally {
      setSaving(false);
    }
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return 'Never';
    return new Date(dateStr).toLocaleString();
  };

  const formatStorage = (usedMb: number, quotaMb: number) => {
    const percentage = quotaMb > 0 ? (usedMb / quotaMb) * 100 : 0;
    return {
      used: usedMb.toFixed(1),
      quota: quotaMb,
      percentage: Math.min(percentage, 100).toFixed(1),
    };
  };

  if (loading) {
    return (
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="text-center text-muted-foreground py-8">Loading user...</div>
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    );
  }

  if (!user) {
    return (
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <Alert variant="destructive">
              <AlertDescription>User not found</AlertDescription>
            </Alert>
            <Button onClick={() => router.push('/users')} className="mt-4">
              <ArrowLeft className="mr-2 h-4 w-4" />
              Back to Users
            </Button>
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    );
  }

  const storage = formatStorage(user.storage_used_mb || 0, user.storage_quota_mb || 0);

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => router.push('/users')}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <h1 className="text-3xl font-bold">{user.username}</h1>
                  <p className="text-muted-foreground">{user.email}</p>
                </div>
                <Badge variant={user.is_active ? 'default' : 'destructive'}>
                  {user.is_active ? 'Active' : 'Inactive'}
                </Badge>
                <Badge variant="outline">{user.role}</Badge>
              </div>
              <div className="flex gap-2">
                <Link href={`/users/${userId}/api-keys`}>
                  <Button variant="outline">
                    <Key className="mr-2 h-4 w-4" />
                    API Keys
                  </Button>
                </Link>
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

            <div className="grid gap-6 lg:grid-cols-2">
              {/* User Info Card */}
              <Card>
                <CardHeader>
                  <CardTitle>User Information</CardTitle>
                  <CardDescription>View and edit user details</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <div className="space-y-2">
                      <Label>User ID</Label>
                      <Input value={user.id} disabled />
                    </div>
                    <div className="space-y-2">
                      <Label>UUID</Label>
                      <Input value={user.uuid} disabled className="font-mono text-xs" />
                    </div>
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="username">Username</Label>
                    <Input
                      id="username"
                      value={formData.username}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="role">Role</Label>
                    <select
                      id="role"
                      value={formData.role}
                      onChange={(e) => setFormData({ ...formData, role: e.target.value })}
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="member">Member</option>
                      <option value="admin">Admin</option>
                      <option value="super_admin">Super Admin</option>
                    </select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={formData.is_active}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="h-4 w-4 rounded border-primary"
                    />
                    <Label htmlFor="is_active">Active</Label>
                  </div>

                  <Button onClick={handleSave} disabled={saving}>
                    <Save className="mr-2 h-4 w-4" />
                    {saving ? 'Saving...' : 'Save Changes'}
                  </Button>
                </CardContent>
              </Card>

              {/* Storage & Activity Card */}
              <Card>
                <CardHeader>
                  <CardTitle>Storage & Activity</CardTitle>
                  <CardDescription>Usage statistics and timestamps</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {/* Storage Usage */}
                  <div className="space-y-2">
                    <Label>Storage Usage</Label>
                    <div className="space-y-2">
                      <div className="flex justify-between text-sm">
                        <span>{storage.used} MB used</span>
                        <span>{storage.quota} MB quota</span>
                      </div>
                      <div className="w-full bg-gray-200 rounded-full h-3">
                        <div
                          className={`h-3 rounded-full transition-all ${
                            parseFloat(storage.percentage) > 90 ? 'bg-red-500' :
                            parseFloat(storage.percentage) > 70 ? 'bg-yellow-500' :
                            'bg-green-500'
                          }`}
                          style={{ width: `${storage.percentage}%` }}
                        />
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {storage.percentage}% of quota used
                      </p>
                    </div>

                    <div className="pt-2">
                      <Label htmlFor="storage_quota">Storage Quota (MB)</Label>
                      <Input
                        id="storage_quota"
                        type="number"
                        value={formData.storage_quota_mb}
                        onChange={(e) => setFormData({ ...formData, storage_quota_mb: parseInt(e.target.value) || 0 })}
                        className="mt-1"
                      />
                    </div>
                  </div>

                  {/* Timestamps */}
                  <div className="space-y-3 pt-4 border-t">
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Created</span>
                      <span className="text-sm">{formatDate(user.created_at)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Updated</span>
                      <span className="text-sm">{formatDate(user.updated_at)}</span>
                    </div>
                    <div className="flex justify-between">
                      <span className="text-sm text-muted-foreground">Last Login</span>
                      <span className="text-sm">{formatDate(user.last_login)}</span>
                    </div>
                  </div>

                  {/* Verification Status */}
                  <div className="pt-4 border-t">
                    <div className="flex items-center justify-between">
                      <span className="text-sm text-muted-foreground">Email Verified</span>
                      <Badge variant={user.is_verified ? 'default' : 'secondary'}>
                        {user.is_verified ? 'Verified' : 'Not Verified'}
                      </Badge>
                    </div>
                  </div>
                </CardContent>
              </Card>

              {/* Quick Actions */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Quick Actions</CardTitle>
                </CardHeader>
                <CardContent>
                  <div className="flex flex-wrap gap-4">
                    <Link href={`/users/${userId}/api-keys`}>
                      <Button variant="outline">
                        <Key className="mr-2 h-4 w-4" />
                        Manage API Keys
                      </Button>
                    </Link>
                    <Button variant="outline" disabled>
                      <Building2 className="mr-2 h-4 w-4" />
                      View Organizations
                    </Button>
                    <Button variant="outline" disabled>
                      <Users className="mr-2 h-4 w-4" />
                      View Teams
                    </Button>
                  </div>
                </CardContent>
              </Card>
            </div>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
