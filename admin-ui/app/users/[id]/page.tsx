'use client';

import { useCallback, useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { ArrowLeft, Key, Save, Building2, Users, Shield, Monitor, RefreshCw, Trash2 } from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import { canEditFromMemberships } from '@/lib/permissions';
import { User } from '@/types';
import Link from 'next/link';

const roleOptions = [
  { value: 'member', label: 'Member' },
  { value: 'admin', label: 'Admin' },
  { value: 'super_admin', label: 'Super Admin' },
  { value: 'owner', label: 'Owner' },
] as const;

type UserRole = (typeof roleOptions)[number]['value'];

type UserFormData = {
  username: string;
  email: string;
  role: UserRole;
  is_active: boolean;
  storage_quota_mb: number;
};

const isValidRole = (role: string): role is UserRole => roleOptions.some((option) => option.value === role);
type MfaStatus = {
  enabled: boolean;
  has_secret: boolean;
  has_backup_codes: boolean;
  method?: string | null;
};

type UserSession = {
  id: number;
  ip_address?: string | null;
  user_agent?: string | null;
  created_at: string;
  last_activity?: string | null;
  expires_at?: string | null;
};

const isForbiddenError = (err: unknown): boolean => {
  if (err instanceof ApiError) {
    return err.status === 403;
  }
  if (typeof err === 'object' && err !== null && 'status' in err) {
    return (err as { status?: number }).status === 403;
  }
  if (err instanceof Error) {
    return /not authorized|forbidden|permission/i.test(err.message);
  }
  return false;
};

export default function UserDetailPage() {
  const params = useParams();
  const router = useRouter();
  const userId = Array.isArray(params.id) ? params.id[0] : params.id;
  const confirm = useConfirm();
  const { success: toastSuccess, error: showError } = useToast();

  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [isAuthorized, setIsAuthorized] = useState(true);
  const [securityLoading, setSecurityLoading] = useState(false);
  const [securityError, setSecurityError] = useState('');
  const [mfaStatus, setMfaStatus] = useState<MfaStatus | null>(null);
  const [sessions, setSessions] = useState<UserSession[]>([]);

  const [formData, setFormData] = useState<UserFormData>({
    username: '',
    email: '',
    role: 'member',
    is_active: true,
    storage_quota_mb: 0,
  });

  const loadUser = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setIsAuthorized(true);
      const data = await api.getUser(userId);
      const roleValue = data.role && isValidRole(data.role) ? data.role : 'member';
      setUser(data);
      setFormData({
        username: data.username || '',
        email: data.email || '',
        role: roleValue,
        is_active: data.is_active ?? true,
        storage_quota_mb: data.storage_quota_mb || 0,
      });

      try {
        const currentUser = await api.getCurrentUser();
        const [adminMemberships, targetMemberships] = await Promise.all([
          api.getUserOrgMemberships(currentUser.id.toString()),
          api.getUserOrgMemberships(userId),
        ]);

        const adminList = Array.isArray(adminMemberships) ? adminMemberships : [];
        const targetList = Array.isArray(targetMemberships) ? targetMemberships : [];

        if (!canEditFromMemberships(adminList, targetList)) {
          setIsAuthorized(false);
          setError('You are not authorized to edit this user.');
        }
      } catch (scopeErr: unknown) {
        if (isForbiddenError(scopeErr)) {
          setIsAuthorized(false);
          setError('You are not authorized to edit this user.');
        } else {
          console.error('Failed to verify user scope:', scopeErr);
        }
      }
    } catch (err: unknown) {
      if (isForbiddenError(err)) {
        setIsAuthorized(false);
        setError('You are not authorized to view or edit this user.');
        setUser(null);
        return;
      }
      const message =
        err instanceof Error ? err.message : typeof err === 'string' ? err : 'Failed to load user';
      console.error('Failed to load user:', message);
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [userId]);

  const loadSecurity = useCallback(async () => {
    if (!userId) return;
    try {
      setSecurityLoading(true);
      setSecurityError('');
      const [mfaResult, sessionsResult] = await Promise.allSettled([
        api.getUserMfaStatus(userId),
        api.getUserSessions(userId),
      ]);

      if (mfaResult.status === 'fulfilled') {
        setMfaStatus(mfaResult.value as MfaStatus);
      } else {
        setMfaStatus(null);
      }

      if (sessionsResult.status === 'fulfilled') {
        setSessions(Array.isArray(sessionsResult.value) ? (sessionsResult.value as UserSession[]) : []);
      } else {
        setSessions([]);
      }

      if (mfaResult.status === 'rejected' || sessionsResult.status === 'rejected') {
        setSecurityError('Failed to load security controls.');
      }
    } catch (err: unknown) {
      console.error('Failed to load security controls:', err);
      setSecurityError('Failed to load security controls.');
      setMfaStatus(null);
      setSessions([]);
    } finally {
      setSecurityLoading(false);
    }
  }, [userId]);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  useEffect(() => {
    if (user && isAuthorized) {
      void loadSecurity();
    }
  }, [user, isAuthorized, loadSecurity]);

  const handleSave = async () => {
    if (!isAuthorized) {
      setError('You are not authorized to update this user.');
      return;
    }
    try {
      setSaving(true);
      setError('');
      setSuccess('');
      await api.updateUser(userId, formData);
      setSuccess('User updated successfully');
      void loadUser();
    } catch (err: unknown) {
      if (isForbiddenError(err)) {
        setIsAuthorized(false);
        setError('You are not authorized to update this user.');
        return;
      }
      if (err instanceof Error) {
        console.error('Failed to update user:', err);
        setError(err.message);
      } else {
        console.error('Failed to update user:', err);
        setError(String(err));
      }
    } finally {
      setSaving(false);
    }
  };

  const handleDisableMfa = async () => {
    if (!mfaStatus?.enabled) return;
    const confirmed = await confirm({
      title: 'Disable MFA',
      message: `Disable MFA for ${user?.username || user?.email || 'this user'}?`,
      confirmText: 'Disable MFA',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      await api.disableUserMfa(userId);
      toastSuccess('MFA disabled', 'Multi-factor authentication has been turned off.');
      void loadSecurity();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to disable MFA';
      showError('Disable MFA failed', message);
    }
  };

  const handleRevokeSession = async (session: UserSession) => {
    const confirmed = await confirm({
      title: 'Revoke Session',
      message: 'Revoke this session? The user will be signed out on that device.',
      confirmText: 'Revoke',
      variant: 'warning',
      icon: 'warning',
    });
    if (!confirmed) return;

    try {
      await api.revokeUserSession(userId, session.id.toString());
      toastSuccess('Session revoked', 'The session has been revoked.');
      void loadSecurity();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to revoke session';
      showError('Revoke failed', message);
    }
  };

  const handleRevokeAllSessions = async () => {
    const confirmed = await confirm({
      title: 'Revoke All Sessions',
      message: 'Revoke all active sessions for this user? They will be signed out everywhere.',
      confirmText: 'Revoke all',
      variant: 'warning',
      icon: 'warning',
    });
    if (!confirmed) return;

    try {
      await api.revokeAllUserSessions(userId);
      toastSuccess('Sessions revoked', 'All sessions have been revoked.');
      void loadSecurity();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to revoke sessions';
      showError('Revoke failed', message);
    }
  };

  const formatDate = (dateStr?: string) =>
    formatDateTime(dateStr, { fallback: 'Never' });

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
      <PermissionGuard variant="route" requireAuth>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="text-center text-muted-foreground py-8">Loading user...</div>
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    );
  }

  if (!user) {
    if (!isAuthorized) {
      return (
        <PermissionGuard variant="route" requireAuth>
          <ResponsiveLayout>
            <div className="p-4 lg:p-8">
              <Alert variant="destructive">
                <AlertDescription>You are not authorized to view this user.</AlertDescription>
              </Alert>
              <Button onClick={() => router.push('/users')} className="mt-4">
                <ArrowLeft className="mr-2 h-4 w-4" />
                Back to Users
              </Button>
            </div>
          </ResponsiveLayout>
        </PermissionGuard>
      );
    }
    return (
      <PermissionGuard variant="route" requireAuth>
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
      </PermissionGuard>
    );
  }

  const storage = formatStorage(user.storage_used_mb || 0, user.storage_quota_mb || 0);

  return (
    <PermissionGuard variant="route" requireAuth>
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
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
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
                      disabled={!isAuthorized}
                      onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="email">Email</Label>
                    <Input
                      id="email"
                      type="email"
                      value={formData.email}
                      disabled={!isAuthorized}
                      onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    />
                  </div>

                  <div className="space-y-2">
                    <Label htmlFor="role">Role</Label>
                    <Select
                      id="role"
                      value={formData.role}
                      disabled={!isAuthorized}
                      onChange={(e) => {
                        const nextRole = e.target.value;
                        if (isValidRole(nextRole)) {
                          setFormData({ ...formData, role: nextRole });
                        }
                      }}
                    >
                      {roleOptions.map((option) => (
                        <option key={option.value} value={option.value}>
                          {option.label}
                        </option>
                      ))}
                    </Select>
                  </div>

                  <div className="flex items-center gap-2">
                    <input
                      type="checkbox"
                      id="is_active"
                      checked={formData.is_active}
                      disabled={!isAuthorized}
                      onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })}
                      className="h-4 w-4 rounded border-primary"
                    />
                    <Label htmlFor="is_active">Active</Label>
                  </div>

                  <Button onClick={handleSave} disabled={saving || !isAuthorized}>
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
                        min="0"
                        value={formData.storage_quota_mb}
                        disabled={!isAuthorized}
                        onChange={(e) => {
                          const val = parseInt(e.target.value, 10);
                          setFormData({
                            ...formData,
                            storage_quota_mb: Number.isNaN(val) ? formData.storage_quota_mb : val,
                          });
                        }}
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

              {/* Security Controls */}
              <Card className="lg:col-span-2">
                <CardHeader>
                  <CardTitle>Security Controls</CardTitle>
                  <CardDescription>MFA status and active sessions</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {securityError && (
                    <Alert variant="destructive">
                      <AlertDescription>{securityError}</AlertDescription>
                    </Alert>
                  )}

                  <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
                    <div className="space-y-1">
                      <div className="flex items-center gap-2">
                        <Shield className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">Multi-factor authentication</span>
                      </div>
                      <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
                        <Badge variant={mfaStatus?.enabled ? 'default' : 'secondary'}>
                          {mfaStatus?.enabled ? 'Enabled' : 'Disabled'}
                        </Badge>
                        {mfaStatus?.method && <span className="text-xs">Method: {mfaStatus.method}</span>}
                        <span className="text-xs">
                          Backup codes: {mfaStatus?.has_backup_codes ? 'Set' : 'Not set'}
                        </span>
                      </div>
                      <p className="text-xs text-muted-foreground">
                        MFA enrollment is managed by the user from their profile.
                      </p>
                    </div>
                    <Button
                      variant="outline"
                      onClick={handleDisableMfa}
                      disabled={!mfaStatus?.enabled || !isAuthorized}
                    >
                      Disable MFA
                    </Button>
                  </div>

                  <div className="space-y-3">
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <div className="flex items-center gap-2">
                        <Monitor className="h-4 w-4 text-muted-foreground" />
                        <span className="font-medium">Active sessions</span>
                        <Badge variant="outline">{sessions.length}</Badge>
                      </div>
                      <div className="flex gap-2">
                        <Button variant="outline" size="sm" onClick={loadSecurity} disabled={securityLoading}>
                          <RefreshCw className={`mr-2 h-4 w-4 ${securityLoading ? 'animate-spin' : ''}`} />
                          Refresh
                        </Button>
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={handleRevokeAllSessions}
                          disabled={!sessions.length || !isAuthorized}
                        >
                          <Trash2 className="mr-2 h-4 w-4" />
                          Revoke all
                        </Button>
                      </div>
                    </div>

                    {securityLoading ? (
                      <div className="text-sm text-muted-foreground">Loading sessions...</div>
                    ) : sessions.length === 0 ? (
                      <div className="text-sm text-muted-foreground">No active sessions found.</div>
                    ) : (
                      <div className="overflow-x-auto">
                        <Table>
                          <TableHeader>
                            <TableRow>
                              <TableHead>Session</TableHead>
                              <TableHead>IP Address</TableHead>
                              <TableHead>Last Activity</TableHead>
                              <TableHead>Expires</TableHead>
                              <TableHead className="text-right">Actions</TableHead>
                            </TableRow>
                          </TableHeader>
                          <TableBody>
                            {sessions.map((session) => (
                              <TableRow key={session.id}>
                                <TableCell>
                                  <div className="text-sm font-mono">{session.id}</div>
                                  <div className="text-xs text-muted-foreground truncate max-w-[240px]">
                                    {session.user_agent || 'Unknown device'}
                                  </div>
                                </TableCell>
                                <TableCell className="text-sm font-mono">
                                  {session.ip_address || '—'}
                                </TableCell>
                                <TableCell className="text-sm">{formatDate(session.last_activity || session.created_at)}</TableCell>
                                <TableCell className="text-sm">{formatDate(session.expires_at || '')}</TableCell>
                                <TableCell className="text-right">
                                  <Button
                                    variant="outline"
                                    size="sm"
                                    onClick={() => handleRevokeSession(session)}
                                    disabled={!isAuthorized}
                                  >
                                    Revoke
                                  </Button>
                                </TableCell>
                              </TableRow>
                            ))}
                          </TableBody>
                        </Table>
                      </div>
                    )}
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
    </PermissionGuard>
  );
}
