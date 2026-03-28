'use client';

import { Suspense, useState, useCallback, useMemo } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { Pagination } from '@/components/ui/pagination';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { usePagedResource } from '@/lib/use-paged-resource';
import { useUrlPagination } from '@/lib/use-url-state';
import api from '@/lib/api-client';
import type {
  AdminWebhook,
  AdminWebhookDeliveryLogEntry,
  AdminWebhookDeliveryLogResponse,
} from '@/types';
import { PlugZap, Plus, Trash2, TestTube, Eye, CheckCircle2, XCircle, Loader2 } from 'lucide-react';

// ---------------------------------------------------------------------------
// Webhook Form Dialog
// ---------------------------------------------------------------------------

function WebhookFormDialog({
  webhook,
  open,
  onOpenChange,
  onSaved,
}: {
  webhook?: AdminWebhook;
  open: boolean;
  onOpenChange: (open: boolean) => void;
  onSaved: () => void;
}) {
  const isEdit = !!webhook;
  const { success, error: showError } = useToast();
  const [saving, setSaving] = useState(false);
  const [url, setUrl] = useState(webhook?.url ?? '');
  const [description, setDescription] = useState(webhook?.description ?? '');
  const [eventTypes, setEventTypes] = useState(webhook?.event_types?.join(', ') ?? '*');
  const [retryCount, setRetryCount] = useState(String(webhook?.retry_count ?? 3));
  const [timeoutSec, setTimeoutSec] = useState(String(webhook?.timeout_seconds ?? 10));

  const handleSubmit = async () => {
    if (!url.trim()) return;
    setSaving(true);
    try {
      const events = eventTypes.split(',').map((s) => s.trim()).filter(Boolean);
      if (isEdit && webhook) {
        await api.updateWebhook(webhook.id, {
          url: url.trim(),
          description: description.trim(),
          event_types: events,
          retry_count: Number(retryCount),
          timeout_seconds: Number(timeoutSec),
        });
        success('Webhook updated');
      } else {
        await api.createWebhook({
          url: url.trim(),
          description: description.trim(),
          event_types: events,
          retry_count: Number(retryCount),
          timeout_seconds: Number(timeoutSec),
        });
        success('Webhook created');
      }
      onOpenChange(false);
      onSaved();
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Failed to save webhook');
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{isEdit ? 'Edit Webhook' : 'Register Webhook'}</DialogTitle>
          <DialogDescription>
            {isEdit ? 'Update webhook configuration.' : 'Register a new endpoint to receive event notifications.'}
          </DialogDescription>
        </DialogHeader>
        <div className="grid gap-4 py-4">
          <div className="grid gap-2">
            <Label htmlFor="wh-url">URL</Label>
            <Input id="wh-url" placeholder="https://example.com/webhook" value={url} onChange={(e) => setUrl(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="wh-desc">Description</Label>
            <Input id="wh-desc" placeholder="Optional description" value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid gap-2">
            <Label htmlFor="wh-events">Event Types (comma-separated, * for all)</Label>
            <Input id="wh-events" placeholder="*, incident.created, alert.fired" value={eventTypes} onChange={(e) => setEventTypes(e.target.value)} />
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="grid gap-2">
              <Label htmlFor="wh-retry">Retry Count</Label>
              <Input id="wh-retry" type="number" min={0} max={10} value={retryCount} onChange={(e) => setRetryCount(e.target.value)} />
            </div>
            <div className="grid gap-2">
              <Label htmlFor="wh-timeout">Timeout (seconds)</Label>
              <Input id="wh-timeout" type="number" min={1} max={60} value={timeoutSec} onChange={(e) => setTimeoutSec(e.target.value)} />
            </div>
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button onClick={handleSubmit} disabled={saving || !url.trim()}>
            {saving ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : null}
            {isEdit ? 'Update' : 'Create'}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

// ---------------------------------------------------------------------------
// Delivery Log Panel
// ---------------------------------------------------------------------------

function DeliveryLogPanel({ webhookId }: { webhookId: number }) {
  const [dlPage, setDlPage] = useState(1);
  const dlPageSize = 20;
  const offset = (dlPage - 1) * dlPageSize;

  const loadDeliveries = useCallback(
    ({ signal }: { signal?: AbortSignal } = {}) =>
      api.getWebhookDeliveries(webhookId, { limit: String(dlPageSize), offset: String(offset) }),
    [webhookId, dlPageSize, offset],
  );

  const { items: deliveries, total, loading } = usePagedResource<AdminWebhookDeliveryLogEntry>({
    load: loadDeliveries,
    defaultError: 'Failed to load deliveries',
  });

  const dlTotalPages = Math.max(1, Math.ceil(total / dlPageSize));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Delivery Log</CardTitle>
        <CardDescription>{total} deliveries</CardDescription>
      </CardHeader>
      <CardContent>
        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
          </div>
        ) : deliveries.length === 0 ? (
          <p className="text-sm text-muted-foreground py-4 text-center">No deliveries yet.</p>
        ) : (
          <>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Event</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead>Latency</TableHead>
                  <TableHead>Retries</TableHead>
                  <TableHead>Error</TableHead>
                  <TableHead>Time</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {deliveries.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-mono text-xs">{d.event_type}</TableCell>
                    <TableCell>
                      {d.status_code != null ? (
                        <span className={d.status_code >= 200 && d.status_code < 300 ? 'text-green-600' : 'text-red-600'}>
                          {d.status_code}
                        </span>
                      ) : (
                        <span className="text-muted-foreground">-</span>
                      )}
                    </TableCell>
                    <TableCell>{d.latency_ms != null ? `${d.latency_ms}ms` : '-'}</TableCell>
                    <TableCell>{d.retry_attempt}</TableCell>
                    <TableCell className="max-w-[200px] truncate text-xs text-red-600">
                      {d.error_message || '-'}
                    </TableCell>
                    <TableCell className="text-xs text-muted-foreground">
                      {d.created_at ? new Date(d.created_at).toLocaleString() : '-'}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
            {dlTotalPages > 1 && (
              <div className="mt-4">
                <Pagination currentPage={dlPage} totalPages={dlTotalPages} totalItems={total} pageSize={dlPageSize} onPageChange={setDlPage} />
              </div>
            )}
          </>
        )}
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

function WebhooksPageContent() {
  const { page, pageSize, setPage } = useUrlPagination();
  const offset = (page - 1) * pageSize;
  const { success, error: showError } = useToast();
  const confirm = useConfirm();

  const [createOpen, setCreateOpen] = useState(false);
  const [editWebhook, setEditWebhook] = useState<AdminWebhook | undefined>();
  const [editOpen, setEditOpen] = useState(false);
  const [selectedWebhookId, setSelectedWebhookId] = useState<number | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);

  const params = useMemo(() => ({
    limit: String(pageSize),
    offset: String(offset),
  }), [pageSize, offset]);

  const loadWebhooks = useCallback(
    ({ signal }: { signal?: AbortSignal } = {}) =>
      api.getWebhooks(params, signal ? { signal } : undefined),
    [params],
  );

  const {
    items: webhooks,
    total,
    loading,
    reload,
  } = usePagedResource<AdminWebhook>({
    load: loadWebhooks,
    defaultError: 'Failed to load webhooks',
  });

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleDelete = async (wh: AdminWebhook) => {
    const confirmed = await confirm({
      title: 'Delete webhook?',
      message: `This will permanently remove the webhook to ${wh.url} and all its delivery logs.`,
      confirmText: 'Delete',
      cancelText: 'Cancel',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;
    try {
      await api.deleteWebhook(wh.id);
      success('Webhook deleted');
      reload();
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Failed to delete webhook');
    }
  };

  const handleTest = async (wh: AdminWebhook) => {
    setTestingId(wh.id);
    try {
      const result = await api.testWebhook(wh.id);
      if (result.success) {
        success(`Test ping succeeded (${result.status_code}, ${result.latency_ms}ms)`);
      } else {
        showError(`Test ping failed: ${result.error || 'Unknown error'}`);
      }
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Failed to test webhook');
    } finally {
      setTestingId(null);
    }
  };

  const handleToggleActive = async (wh: AdminWebhook) => {
    try {
      await api.updateWebhook(wh.id, { active: !wh.active });
      success(wh.active ? 'Webhook disabled' : 'Webhook enabled');
      reload();
    } catch (err: unknown) {
      showError(err instanceof Error ? err.message : 'Failed to update webhook');
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          {/* Header */}
          <div className="mb-8 flex items-center justify-between">
            <div className="flex items-center gap-3">
              <PlugZap className="h-8 w-8" />
              <h1 className="text-3xl font-bold">Webhooks</h1>
            </div>
            <Button onClick={() => setCreateOpen(true)}>
              <Plus className="mr-2 h-4 w-4" /> Register Webhook
            </Button>
          </div>

          {/* Summary cards */}
          <div className="grid gap-4 md:grid-cols-3 mb-6">
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold">{total}</div>
                <p className="text-sm text-muted-foreground">Total Webhooks</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold text-green-600">
                  {webhooks.filter((w) => w.active).length}
                </div>
                <p className="text-sm text-muted-foreground">Active</p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-6">
                <div className="text-2xl font-bold text-muted-foreground">
                  {webhooks.filter((w) => !w.active).length}
                </div>
                <p className="text-sm text-muted-foreground">Disabled</p>
              </CardContent>
            </Card>
          </div>

          {/* Webhooks list */}
          <Card className="mb-6">
            <CardHeader>
              <CardTitle>Registered Webhooks</CardTitle>
              <CardDescription>{total} webhook{total !== 1 ? 's' : ''} configured</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="flex items-center justify-center py-8">
                  <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                </div>
              ) : webhooks.length === 0 ? (
                <div className="text-center py-8">
                  <PlugZap className="mx-auto h-12 w-12 text-muted-foreground mb-4" />
                  <p className="text-muted-foreground">No webhooks registered yet.</p>
                  <Button className="mt-4" onClick={() => setCreateOpen(true)}>
                    <Plus className="mr-2 h-4 w-4" /> Register your first webhook
                  </Button>
                </div>
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>URL</TableHead>
                        <TableHead>Events</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Retries</TableHead>
                        <TableHead>Description</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {webhooks.map((wh) => (
                        <TableRow key={wh.id}>
                          <TableCell className="font-mono text-xs max-w-[300px] truncate">
                            {wh.url}
                          </TableCell>
                          <TableCell className="text-xs">
                            {wh.event_types.join(', ')}
                          </TableCell>
                          <TableCell>
                            <button
                              onClick={() => handleToggleActive(wh)}
                              className="inline-flex items-center gap-1 text-xs cursor-pointer hover:opacity-80"
                            >
                              {wh.active ? (
                                <><CheckCircle2 className="h-4 w-4 text-green-600" /> Active</>
                              ) : (
                                <><XCircle className="h-4 w-4 text-muted-foreground" /> Disabled</>
                              )}
                            </button>
                          </TableCell>
                          <TableCell>{wh.retry_count}</TableCell>
                          <TableCell className="text-xs text-muted-foreground max-w-[200px] truncate">
                            {wh.description || '-'}
                          </TableCell>
                          <TableCell className="text-right">
                            <div className="flex items-center justify-end gap-1">
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => setSelectedWebhookId(selectedWebhookId === wh.id ? null : wh.id)}
                                title="View deliveries"
                              >
                                <Eye className="h-4 w-4" />
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleTest(wh)}
                                disabled={testingId === wh.id}
                                title="Send test ping"
                              >
                                {testingId === wh.id ? (
                                  <Loader2 className="h-4 w-4 animate-spin" />
                                ) : (
                                  <TestTube className="h-4 w-4" />
                                )}
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => {
                                  setEditWebhook(wh);
                                  setEditOpen(true);
                                }}
                                title="Edit"
                              >
                                Edit
                              </Button>
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDelete(wh)}
                                title="Delete"
                              >
                                <Trash2 className="h-4 w-4 text-red-500" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                  {totalPages > 1 && (
                    <div className="mt-4">
                      <Pagination currentPage={page} totalPages={totalPages} totalItems={total} pageSize={pageSize} onPageChange={setPage} />
                    </div>
                  )}
                </>
              )}
            </CardContent>
          </Card>

          {/* Delivery log for selected webhook */}
          {selectedWebhookId !== null && (
            <DeliveryLogPanel webhookId={selectedWebhookId} />
          )}

          {/* Create dialog */}
          <WebhookFormDialog
            open={createOpen}
            onOpenChange={setCreateOpen}
            onSaved={reload}
          />

          {/* Edit dialog */}
          {editWebhook && (
            <WebhookFormDialog
              webhook={editWebhook}
              open={editOpen}
              onOpenChange={(open) => {
                setEditOpen(open);
                if (!open) setEditWebhook(undefined);
              }}
              onSaved={reload}
            />
          )}
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}

export default function WebhooksPage() {
  return (
    <Suspense fallback={<div className="flex items-center justify-center h-screen"><Loader2 className="h-8 w-8 animate-spin" /></div>}>
      <WebhooksPageContent />
    </Suspense>
  );
}
