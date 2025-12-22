'use client';

import { useEffect, useRef, useState } from 'react';
import { useParams, useRouter } from 'next/navigation';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { ArrowLeft, Plus, Copy } from 'lucide-react';
import { api } from '@/lib/api-client';
import { ApiKeyCreateForm } from '@/components/users/ApiKeyCreateForm';
import { ApiKeysTable } from '@/components/users/ApiKeysTable';
import { useUserApiKeys } from '@/lib/use-user-api-keys';

export default function UserApiKeysPage() {
  const params = useParams();
  const router = useRouter();
  const confirm = useConfirm();
  const userId = params.id as string;

  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [showCreateForm, setShowCreateForm] = useState(false);
  const [newKeyValue, setNewKeyValue] = useState<string | null>(null);
  const successTimerRef = useRef<number | null>(null);
  const isMountedRef = useRef(true);

  const [formData, setFormData] = useState({
    name: '',
    scope: 'read',
    expires_days: 90,
  });

  const { user, apiKeys, loading, reload } = useUserApiKeys(userId, { onError: setError });

  useEffect(() => {
    return () => {
      isMountedRef.current = false;
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
        successTimerRef.current = null;
      }
    };
  }, []);

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

      // The API returns the full key value only on creation
      if (result.key) {
        setNewKeyValue(result.key);
      }

      setSuccess('API key created successfully');
      setShowCreateForm(false);
      setFormData({ name: '', scope: 'read', expires_days: 90 });
      void reload();
    } catch (err: unknown) {
      console.error('Failed to create API key:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to create API key');
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
      if (result.key) {
        setNewKeyValue(result.key);
      }
      setSuccess('API key rotated successfully');
      void reload();
    } catch (err: unknown) {
      console.error('Failed to rotate API key:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to rotate API key');
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
      void reload();
    } catch (err: unknown) {
      console.error('Failed to revoke API key:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to revoke API key');
    }
  };

  const copyToClipboard = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      if (!isMountedRef.current) {
        return;
      }
      setError('');
      setSuccess('Copied to clipboard!');
      if (successTimerRef.current !== null) {
        window.clearTimeout(successTimerRef.current);
      }
      successTimerRef.current = window.setTimeout(() => {
        if (!isMountedRef.current) {
          return;
        }
        setSuccess('');
        successTimerRef.current = null;
      }, 2000);
    } catch (err: unknown) {
      console.error('Failed to copy to clipboard:', err);
      if (!isMountedRef.current) {
        return;
      }
      setError('Failed to copy to clipboard. Please copy manually or check browser permissions.');
    }
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
                      Save this API key now - it won&apos;t be shown again!
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
              <ApiKeyCreateForm
                formData={formData}
                onFormDataChange={setFormData}
                onSubmit={handleCreate}
                onCancel={() => setShowCreateForm(false)}
              />
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
                <ApiKeysTable
                  apiKeys={apiKeys}
                  onRotate={handleRotate}
                  onRevoke={handleRevoke}
                />
              </CardContent>
            </Card>
          </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
