'use client';

import { useCallback, useEffect, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { EmptyState } from '@/components/ui/empty-state';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog';
import { usePrivilegedActionDialog } from '@/components/ui/privileged-action-dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import type { WebhookItem } from '@/types/webhooks';
import { Copy, Plus, RefreshCw, Trash2, Webhook } from 'lucide-react';

const AVAILABLE_EVENTS = [
  'user.created',
  'user.deleted',
  'incident.created',
  'incident.updated',
  'incident.resolved',
] as const;

function WebhooksPageContent() {
  const promptPrivileged = usePrivilegedActionDialog();
  const { success, error: showError } = useToast();

  const [webhooks, setWebhooks] = useState<WebhookItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Create dialog state
  const [showCreateDialog, setShowCreateDialog] = useState(false);
  const [createUrl, setCreateUrl] = useState('');
  const [createEvents, setCreateEvents] = useState<string[]>([]);
  const [creating, setCreating] = useState(false);

  // Secret display state (shown once after creation)
  const [showSecretDialog, setShowSecretDialog] = useState(false);
  const [createdSecret, setCreatedSecret] = useState('');
  const [secretCopied, setSecretCopied] = useState(false);

  const fetchWebhooks = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const response = await api.getWebhooks();
      setWebhooks(response.items ?? []);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load webhooks';
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchWebhooks();
  }, [fetchWebhooks]);

  const handleCreate = async () => {
    if (!createUrl.trim()) return;
    if (createEvents.length === 0) return;
    setCreating(true);
    try {
      const result = await api.createWebhook({
        url: createUrl.trim(),
        events: createEvents,
        enabled: true,
      });
      success('Webhook created');
      setShowCreateDialog(false);
      setCreateUrl('');
      setCreateEvents([]);
      // Show the secret once
      setCreatedSecret(result.secret);
      setSecretCopied(false);
      setShowSecretDialog(true);
      await fetchWebhooks();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to create webhook';
      showError(message);
    } finally {
      setCreating(false);
    }
  };

  const handleToggleEnabled = async (webhook: WebhookItem) => {
    try {
      await api.updateWebhook(webhook.id, { enabled: !webhook.enabled });
      success(webhook.enabled ? 'Webhook disabled' : 'Webhook enabled');
      await fetchWebhooks();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to update webhook';
      showError(message);
    }
  };

  const handleDelete = async (webhook: WebhookItem) => {
    const result = await promptPrivileged({
      title: 'Delete Webhook',
      message: `Delete the webhook for ${webhook.url}? This cannot be undone.`,
      confirmText: 'Delete Webhook',
    });
    if (!result) return;
    try {
      await api.deleteWebhook(webhook.id);
      success('Webhook deleted');
      await fetchWebhooks();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete webhook';
      showError(message);
    }
  };

  const handleCopySecret = async () => {
    try {
      await navigator.clipboard.writeText(createdSecret);
      setSecretCopied(true);
    } catch {
      // Fallback: select input text
    }
  };

  const toggleCreateEvent = (event: string) => {
    setCreateEvents((prev) =>
      prev.includes(event) ? prev.filter((e) => e !== event) : [...prev, event]
    );
  };

  return (
    <ResponsiveLayout>
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div>
              <CardTitle>Webhooks</CardTitle>
              <CardDescription>
                Configure outgoing webhooks for event notifications
              </CardDescription>
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={fetchWebhooks} disabled={loading}>
                <RefreshCw className={`h-4 w-4 mr-1 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
              <Button size="sm" onClick={() => setShowCreateDialog(true)}>
                <Plus className="h-4 w-4 mr-1" />
                Add Webhook
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent>
          {error && (
            <Alert variant="destructive" className="mb-4">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {!loading && webhooks.length === 0 && !error && (
            <EmptyState
              icon={Webhook}
              title="No webhooks configured"
              description="Add a webhook to receive event notifications at your URL."
            />
          )}

          {webhooks.length > 0 && (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>URL</TableHead>
                  <TableHead>Events</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Created</TableHead>
                  <TableHead className="text-right">Actions</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {webhooks.map((webhook) => (
                  <TableRow key={webhook.id}>
                    <TableCell className="font-mono text-sm max-w-[300px] truncate">
                      {webhook.url}
                    </TableCell>
                    <TableCell>
                      <div className="flex flex-wrap gap-1">
                        {webhook.events.map((event) => (
                          <Badge key={event} variant="secondary" className="text-xs">
                            {event}
                          </Badge>
                        ))}
                      </div>
                    </TableCell>
                    <TableCell>
                      <Badge variant={webhook.enabled ? 'default' : 'outline'}>
                        {webhook.enabled ? 'Enabled' : 'Disabled'}
                      </Badge>
                    </TableCell>
                    <TableCell className="text-sm text-muted-foreground">
                      {formatDateTime(webhook.created_at, { fallback: '\u2014' })}
                    </TableCell>
                    <TableCell className="text-right">
                      <div className="flex justify-end gap-1">
                        <Button
                          variant="outline"
                          size="sm"
                          onClick={() => handleToggleEnabled(webhook)}
                        >
                          {webhook.enabled ? 'Disable' : 'Enable'}
                        </Button>
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(webhook)}
                        >
                          <Trash2 className="h-4 w-4 text-destructive" />
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

      {/* Create Webhook Dialog */}
      <Dialog open={showCreateDialog} onOpenChange={setShowCreateDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add Webhook</DialogTitle>
            <DialogDescription>
              Configure a URL to receive event notifications. A signing secret will be generated automatically.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="webhook-url">Endpoint URL</Label>
              <Input
                id="webhook-url"
                type="url"
                placeholder="https://example.com/webhook"
                value={createUrl}
                onChange={(e) => setCreateUrl(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label>Events</Label>
              <div className="space-y-2">
                {AVAILABLE_EVENTS.map((event) => (
                  <label key={event} className="flex items-center gap-2 text-sm">
                    <Checkbox
                      checked={createEvents.includes(event)}
                      onCheckedChange={() => toggleCreateEvent(event)}
                    />
                    {event}
                  </label>
                ))}
              </div>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setShowCreateDialog(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleCreate}
              disabled={creating || !createUrl.trim() || createEvents.length === 0}
            >
              {creating ? 'Creating...' : 'Create Webhook'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Secret Display Dialog (shown once) */}
      <Dialog open={showSecretDialog} onOpenChange={setShowSecretDialog}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Webhook Secret</DialogTitle>
            <DialogDescription>
              Copy your webhook signing secret now. It will not be shown again.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="flex items-center gap-2">
              <Input
                readOnly
                value={createdSecret}
                className="font-mono text-sm"
                data-testid="webhook-secret-value"
              />
              <Button variant="outline" size="sm" onClick={handleCopySecret}>
                <Copy className="h-4 w-4" />
              </Button>
            </div>
            {secretCopied && (
              <p className="text-sm text-green-600">Copied to clipboard</p>
            )}
            <Alert>
              <AlertDescription>
                Use this secret to verify webhook signatures using HMAC-SHA256.
              </AlertDescription>
            </Alert>
          </div>
          <DialogFooter>
            <Button onClick={() => setShowSecretDialog(false)}>
              Done
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </ResponsiveLayout>
  );
}

export default function WebhooksPage() {
  return (
    <PermissionGuard role={['admin', 'super_admin', 'owner']}>
      <WebhooksPageContent />
    </PermissionGuard>
  );
}
