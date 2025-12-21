'use client';

import { useEffect, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { ArrowLeft, Plus, RotateCw, Trash2, Copy, Eye, EyeOff, Clock } from 'lucide-react';
import { api } from '@/lib/api-client';
import { ApiKey, User } from '@/types';

export default function UserApiKeysPage() {
  const params = useParams();
  const router = useRouter();
  const confirm = useConfirm();
  const userId = params.id as string;

  const [user, setUser] = useState<User | null>(null);
  const [apiKeys, setApiKeys] = useState<ApiKey[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [revealedKeys, setRevealedKeys] = useState<Set<string>>(new Set());
  const [newKeyValue, setNewKeyValue] = useState<string | null>(null);

  const [formData, setFormData] = useState({
    name: '',
    scope: 'read',
    expires_days: 90,
  });

  useEffect(() => {
    loadData();
  }, [userId]);

  const loadData = async () => {
    try {
      setLoading(true);
      setError('');
      const [userData, keysData] = await Promise.all([
        api.getUser(userId),
        api.getUserApiKeys(userId),
      ]);
      setUser(userData);
      setApiKeys(Array.isArray(keysData) ? keysData : []);
    } catch (err: any) {
      console.error('Failed to load data:', err);
      setError(err.message || 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    try {
      setError('');
      setSuccess('');
      const result = await api.createApiKey(userId, {
        name: formData.name,
        scope: formData.scope,
        expires_in_days: formData.expires_days,
      });

      // The API might return the full key value only on creation
      if (result.key || result.api_key) {
        setNewKeyValue(result.key || result.api_key);
      }

      setSuccess('API key created successfully');
      setShowCreateForm(false);
      setFormData({ name: '', scope: 'read', expires_days: 90 });
      loadData();
    } catch (err: any) {
      console.error('Failed to create API key:', err);
      setError(err.message || 'Failed to create API key');
    }
  };

  const handleRotate = async (keyId: string) => {
    const confirmed = await confirm({
      title: 'Rotate API Key',
      message: 'Are you sure you want to rotate this key? The old key will stop working immediately.',
      confirmText: 'Rotate',
      variant: 'warning',
      icon: 'rotate',
    });
    if (!confirmed) return;

    try {
      setError('');
      setSuccess('');
      const result = await api.rotateApiKey(userId, keyId);
      if (result.key || result.api_key) {
        setNewKeyValue(result.key || result.api_key);
      }
      setSuccess('API key rotated successfully');
      loadData();
    } catch (err: any) {
      console.error('Failed to rotate API key:', err);
      setError(err.message || 'Failed to rotate API key');
    }
  };

  const handleRevoke = async (keyId: string, keyName: string) => {
    const confirmed = await confirm({
      title: 'Revoke API Key',
      message: `Are you sure you want to revoke "${keyName || keyId}"? This action cannot be undone.`,
      confirmText: 'Revoke',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      setError('');
      setSuccess('');
      await api.revokeApiKey(userId, keyId);
      setSuccess('API key revoked successfully');
      loadData();
    } catch (err: any) {
      console.error('Failed to revoke API key:', err);
      setError(err.message || 'Failed to revoke API key');
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setSuccess('Copied to clipboard!');
      setTimeout(() => setSuccess(''), 2000);
    } catch (err) {
      setError('Failed to copy to clipboard');
    }
  };

  const toggleKeyVisibility = (keyId: string) => {
    setRevealedKeys((prev) => {
      const newSet = new Set(prev);
      if (newSet.has(keyId)) {
        newSet.delete(keyId);
      } else {
        newSet.add(keyId);
      }
      return newSet;
    });
  };

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '-';
    return new Date(dateStr).toLocaleDateString();
  };

  const isExpired = (expiresAt?: string) => {
    if (!expiresAt) return false;
    return new Date(expiresAt) < new Date();
  };

  const isRevoked = (revokedAt?: string) => {
    return !!revokedAt;
  };

  const getKeyStatus = (key: ApiKey) => {
    if (isRevoked(key.revoked_at)) return { label: 'Revoked', variant: 'destructive' as const };
    if (isExpired(key.expires_at)) return { label: 'Expired', variant: 'secondary' as const };
    return { label: 'Active', variant: 'default' as const };
  };

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

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            {/* Header */}
            <div className="mb-8 flex items-center justify-between">
              <div className="flex items-center gap-4">
                <Button variant="ghost" onClick={() => router.push(`/users/${userId}`)}>
                  <ArrowLeft className="h-4 w-4" />
                </Button>
                <div>
                  <h1 className="text-3xl font-bold">API Keys</h1>
                  <p className="text-muted-foreground">
                    Manage API keys for {user?.username || 'user'}
                  </p>
                </div>
              </div>
              <Button onClick={() => setShowCreateForm(!showCreateForm)}>
                <Plus className="mr-2 h-4 w-4" />
                Create API Key
              </Button>
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

            {/* New Key Display */}
            {newKeyValue && (
              <Alert className="mb-6 bg-yellow-50 border-yellow-200">
                <AlertDescription>
                  <div className="space-y-2">
                    <p className="font-semibold text-yellow-800">
                      Save this API key now - it won't be shown again!
                    </p>
                    <div className="flex items-center gap-2">
                      <code className="flex-1 bg-yellow-100 p-2 rounded font-mono text-sm break-all">
                        {newKeyValue}
                      </code>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => copyToClipboard(newKeyValue)}
                      >
                        <Copy className="h-4 w-4" />
                      </Button>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setNewKeyValue(null)}
                      className="text-yellow-700"
                    >
                      Dismiss
                    </Button>
                  </div>
                </AlertDescription>
              </Alert>
            )}

            {/* Create Form */}
            {showCreateForm && (
              <Card className="mb-6">
                <CardHeader>
                  <CardTitle>Create API Key</CardTitle>
                  <CardDescription>Generate a new API key for this user</CardDescription>
                </CardHeader>
                <CardContent>
                  <form onSubmit={handleCreate} className="space-y-4">
                    <div className="grid grid-cols-3 gap-4">
                      <div className="space-y-2">
                        <Label htmlFor="name">Key Name</Label>
                        <Input
                          id="name"
                          placeholder="e.g., Production API"
                          value={formData.name}
                          onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                          required
                        />
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="scope">Scope</Label>
                        <select
                          id="scope"
                          value={formData.scope}
                          onChange={(e) => setFormData({ ...formData, scope: e.target.value })}
                          className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                        >
                          <option value="read">Read Only</option>
                          <option value="write">Read & Write</option>
                          <option value="admin">Admin</option>
                        </select>
                      </div>

                      <div className="space-y-2">
                        <Label htmlFor="expires">Expires In (days)</Label>
                        <Input
                          id="expires"
                          type="number"
                          min="1"
                          max="365"
                          value={formData.expires_days}
                          onChange={(e) => setFormData({ ...formData, expires_days: parseInt(e.target.value) || 90 })}
                        />
                      </div>
                    </div>

                    <div className="flex gap-2">
                      <Button type="submit">Create Key</Button>
                      <Button type="button" variant="outline" onClick={() => setShowCreateForm(false)}>
                        Cancel
                      </Button>
                    </div>
                  </form>
                </CardContent>
              </Card>
            )}

            {/* API Keys Table */}
            <Card>
              <CardHeader>
                <CardTitle>API Keys</CardTitle>
                <CardDescription>
                  {apiKeys.length} key{apiKeys.length !== 1 ? 's' : ''} total
                </CardDescription>
              </CardHeader>
              <CardContent>
                {apiKeys.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    No API keys found. Create one to get started.
                  </div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Name</TableHead>
                        <TableHead>Key Prefix</TableHead>
                        <TableHead>Scope</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Expires</TableHead>
                        <TableHead>Last Used</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {apiKeys.map((key) => {
                        const status = getKeyStatus(key);
                        const isActive = status.label === 'Active';

                        return (
                          <TableRow key={key.id} className={!isActive ? 'opacity-60' : ''}>
                            <TableCell className="font-medium">{key.name || '-'}</TableCell>
                            <TableCell>
                              <code className="bg-muted px-2 py-1 rounded text-sm">
                                {key.key_prefix}...
                              </code>
                            </TableCell>
                            <TableCell>
                              <Badge variant="outline">{key.scope}</Badge>
                            </TableCell>
                            <TableCell>
                              <Badge variant={status.variant}>{status.label}</Badge>
                            </TableCell>
                            <TableCell className="text-sm">{formatDate(key.created_at)}</TableCell>
                            <TableCell className="text-sm">
                              {key.expires_at ? (
                                <span className={isExpired(key.expires_at) ? 'text-red-500' : ''}>
                                  {formatDate(key.expires_at)}
                                </span>
                              ) : (
                                'Never'
                              )}
                            </TableCell>
                            <TableCell className="text-sm text-muted-foreground">
                              {formatDate(key.last_used_at)}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1">
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRotate(key.id)}
                                  disabled={!isActive}
                                  title="Rotate key"
                                >
                                  <RotateCw className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="ghost"
                                  size="sm"
                                  onClick={() => handleRevoke(key.id, key.name || '')}
                                  disabled={!isActive}
                                  title="Revoke key"
                                >
                                  <Trash2 className="h-4 w-4 text-red-500" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
