'use client';

import { useCallback, useDeferredValue, useEffect, useMemo, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import { useUrlPagination } from '@/lib/use-url-state';
import { usePagedResource } from '@/lib/use-paged-resource';
import type { IncidentItem } from '@/types/incidents';
import { RefreshCw, Trash2 } from 'lucide-react';

const STATUSES = ['open', 'investigating', 'mitigating', 'resolved'] as const;
const SEVERITIES = ['low', 'medium', 'high', 'critical'] as const;

const formatIncidentDate = (value?: string | null) =>
  formatDateTime(value, { fallback: '—' });

export default function IncidentsPage() {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();
  const { page, pageSize, setPage, setPageSize, resetPagination } = useUrlPagination();

  const [statusFilter, setStatusFilter] = useState('');
  const [severityFilter, setSeverityFilter] = useState('');
  const [tagFilterInput, setTagFilterInput] = useState('');
  const deferredTagFilter = useDeferredValue(tagFilterInput);

  const [title, setTitle] = useState('');
  const [status, setStatus] = useState<typeof STATUSES[number]>('open');
  const [severity, setSeverity] = useState<typeof SEVERITIES[number]>('medium');
  const [summary, setSummary] = useState('');
  const [tags, setTags] = useState('');
  const [creating, setCreating] = useState(false);

  const [updateNotes, setUpdateNotes] = useState<Record<string, string>>({});
  const [updatingIncidents, setUpdatingIncidents] = useState<Set<string>>(new Set());

  const params = useMemo(() => {
    const offset = Math.max(0, (page - 1) * pageSize);
    const payload: Record<string, string> = {
      limit: String(pageSize),
      offset: String(offset),
    };
    if (statusFilter) payload.status = statusFilter;
    if (severityFilter) payload.severity = severityFilter;
    if (deferredTagFilter) payload.tag = deferredTagFilter;
    return payload;
  }, [deferredTagFilter, page, pageSize, severityFilter, statusFilter]);

  const loadIncidents = useCallback(({ signal }: { signal?: AbortSignal } = {}) =>
    api.getIncidents(params, signal ? { signal } : undefined), [params]);

  const {
    items: incidents,
    total,
    loading,
    error,
    reload,
  } = usePagedResource<IncidentItem>({
    load: loadIncidents,
    defaultError: 'Failed to load incidents',
  });

  useEffect(() => {
    resetPagination();
  }, [deferredTagFilter, resetPagination]);

  const setIncidentUpdating = useCallback((incidentId: string, isUpdating: boolean) => {
    setUpdatingIncidents((prev) => {
      const next = new Set(prev);
      if (isUpdating) {
        next.add(incidentId);
      } else {
        next.delete(incidentId);
      }
      return next;
    });
  }, []);

  const handleCreateIncident = async () => {
    if (!title.trim()) {
      showError('Incident title is required');
      return;
    }
    try {
      setCreating(true);
      await api.createIncident({
        title,
        status,
        severity,
        summary,
        tags: tags ? tags.split(',').map((item) => item.trim()).filter(Boolean) : [],
      });
      success('Incident created');
      setTitle('');
      setSummary('');
      setTags('');
      resetPagination();
      await reload();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to create incident';
      showError(message);
    } finally {
      setCreating(false);
    }
  };

  const handleStatusChange = async (incidentId: string, nextStatus: IncidentItem['status']) => {
    try {
      setIncidentUpdating(incidentId, true);
      await api.updateIncident(incidentId, {
        status: nextStatus,
        update_message: `Status changed to ${nextStatus}`,
      });
      await reload();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to update status';
      showError(message);
    } finally {
      setIncidentUpdating(incidentId, false);
    }
  };

  const handleSeverityChange = async (incidentId: string, nextSeverity: IncidentItem['severity']) => {
    try {
      setIncidentUpdating(incidentId, true);
      await api.updateIncident(incidentId, {
        severity: nextSeverity,
        update_message: `Severity set to ${nextSeverity}`,
      });
      await reload();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to update severity';
      showError(message);
    } finally {
      setIncidentUpdating(incidentId, false);
    }
  };

  const handleAddUpdate = async (incidentId: string) => {
    const note = (updateNotes[incidentId] || '').trim();
    if (!note) {
      showError('Update message is required');
      return;
    }
    try {
      setIncidentUpdating(incidentId, true);
      await api.addIncidentEvent(incidentId, { message: note });
      setUpdateNotes((prev) => ({ ...prev, [incidentId]: '' }));
      await reload();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to add update';
      showError(message);
    } finally {
      setIncidentUpdating(incidentId, false);
    }
  };

  const handleDeleteIncident = async (incidentId: string) => {
    const confirmed = await confirm({
      title: 'Delete incident?',
      description: 'This removes the incident from the timeline.',
      confirmText: 'Delete',
      variant: 'destructive',
    });
    if (!confirmed) return;
    try {
      setIncidentUpdating(incidentId, true);
      await api.deleteIncident(incidentId);
      success('Incident deleted');
      await reload();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to delete incident';
      showError(message);
    } finally {
      setIncidentUpdating(incidentId, false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="flex flex-col gap-6 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Incidents</h1>
              <p className="text-muted-foreground">Track operational events and updates.</p>
            </div>
            <Button
              variant="outline"
              onClick={() => {
                void reload();
              }}
              disabled={loading}
            >
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Create Incident</CardTitle>
              <CardDescription>Log a new operational event.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div className="space-y-1 md:col-span-2">
                <Label htmlFor="incident-title">Title</Label>
                <Input
                  id="incident-title"
                  placeholder="Brief incident title"
                  value={title}
                  onChange={(e) => setTitle(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="incident-status">Status</Label>
                <Select
                  id="incident-status"
                  value={status}
                  onChange={(e) => setStatus(e.target.value as IncidentItem['status'])}
                >
                  {STATUSES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="incident-severity">Severity</Label>
                <Select
                  id="incident-severity"
                  value={severity}
                  onChange={(e) => setSeverity(e.target.value as IncidentItem['severity'])}
                >
                  {SEVERITIES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label htmlFor="incident-summary">Summary</Label>
                <Input
                  id="incident-summary"
                  placeholder="What happened?"
                  value={summary}
                  onChange={(e) => setSummary(e.target.value)}
                />
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label htmlFor="incident-tags">Tags</Label>
                <Input
                  id="incident-tags"
                  placeholder="comma separated"
                  value={tags}
                  onChange={(e) => setTags(e.target.value)}
                />
              </div>
              <div>
                <Button
                  onClick={() => {
                    void handleCreateIncident();
                  }}
                  disabled={creating}
                >
                  {creating ? 'Creating...' : 'Create Incident'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Filters</CardTitle>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="filter-status">Status</Label>
                <Select
                  id="filter-status"
                  value={statusFilter}
                  onChange={(e) => {
                    setStatusFilter(e.target.value);
                    resetPagination();
                  }}
                >
                  <option value="">All</option>
                  {STATUSES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="filter-severity">Severity</Label>
                <Select
                  id="filter-severity"
                  value={severityFilter}
                  onChange={(e) => {
                    setSeverityFilter(e.target.value);
                    resetPagination();
                  }}
                >
                  <option value="">All</option>
                  {SEVERITIES.map((value) => (
                    <option key={value} value={value}>
                      {value}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="filter-tag">Tag</Label>
                <Input
                  id="filter-tag"
                  placeholder="tag"
                  value={tagFilterInput}
                  onChange={(e) => {
                    setTagFilterInput(e.target.value);
                  }}
                />
              </div>
            </CardContent>
          </Card>

          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {loading ? (
            <div className="py-10 text-center text-muted-foreground">Loading incidents...</div>
          ) : incidents.length === 0 ? (
            <div className="py-10 text-center text-muted-foreground">No incidents found.</div>
          ) : (
            <div className="grid gap-4">
              {incidents.map((incident) => {
                const isUpdating = updatingIncidents.has(incident.id);
                return (
                  <Card key={incident.id}>
                  <CardHeader className="flex flex-col gap-2 md:flex-row md:items-start md:justify-between">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {incident.title}
                        <Badge variant={incident.status === 'resolved' ? 'secondary' : 'outline'}>
                          {incident.status}
                        </Badge>
                        <Badge variant={incident.severity === 'critical' ? 'destructive' : 'outline'}>
                          {incident.severity}
                        </Badge>
                      </CardTitle>
                      <CardDescription>
                        Updated {formatIncidentDate(incident.updated_at)} · Created {formatIncidentDate(incident.created_at)}
                      </CardDescription>
                    </div>
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => {
                        void handleDeleteIncident(incident.id);
                      }}
                      aria-label={`Delete incident ${incident.id}`}
                      title={`Delete incident ${incident.id}`}
                      disabled={isUpdating}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </CardHeader>
                  <CardContent className="grid gap-4">
                    <div className="text-sm text-muted-foreground">
                      {incident.summary || 'No summary provided.'}
                    </div>
                    <div className="flex flex-wrap gap-2">
                      {(incident.tags || []).map((tag, index) => (
                        <Badge key={`${tag}-${index}`} variant="outline">
                          {tag}
                        </Badge>
                      ))}
                    </div>
                    <div className="grid gap-3 md:grid-cols-3">
                      <div className="space-y-1">
                        <Label htmlFor={`status-${incident.id}`}>Status</Label>
                        <Select
                          id={`status-${incident.id}`}
                          value={incident.status}
                          onChange={(e) => {
                            void handleStatusChange(incident.id, e.target.value as IncidentItem['status']);
                          }}
                          disabled={isUpdating}
                        >
                          {STATUSES.map((value) => (
                            <option key={value} value={value}>
                              {value}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`severity-${incident.id}`}>Severity</Label>
                        <Select
                          id={`severity-${incident.id}`}
                          value={incident.severity}
                          onChange={(e) => {
                            void handleSeverityChange(incident.id, e.target.value as IncidentItem['severity']);
                          }}
                          disabled={isUpdating}
                        >
                          {SEVERITIES.map((value) => (
                            <option key={value} value={value}>
                              {value}
                            </option>
                          ))}
                        </Select>
                      </div>
                      <div className="space-y-1">
                        <Label htmlFor={`resolved-${incident.id}`}>Resolved</Label>
                        <div id={`resolved-${incident.id}`} className="text-sm text-muted-foreground">
                          {incident.resolved_at ? formatIncidentDate(incident.resolved_at) : 'Not resolved'}
                        </div>
                      </div>
                    </div>
                    <div className="grid gap-2 md:grid-cols-[1fr_auto]">
                      <Input
                        placeholder="Add update..."
                        value={updateNotes[incident.id] || ''}
                        onChange={(e) =>
                          setUpdateNotes((prev) => ({ ...prev, [incident.id]: e.target.value }))
                        }
                        disabled={isUpdating}
                      />
                      <Button
                        onClick={() => {
                          void handleAddUpdate(incident.id);
                        }}
                        disabled={isUpdating}
                      >
                        {isUpdating ? 'Updating...' : 'Add Update'}
                      </Button>
                    </div>
                    <details className="text-sm text-muted-foreground">
                      <summary className="cursor-pointer">Timeline ({incident.timeline?.length || 0})</summary>
                      <div className="mt-2 space-y-2">
                        {(incident.timeline || []).map((event) => (
                          <div key={event.id} className="rounded-md border p-2">
                            <div className="font-medium text-foreground">{event.message}</div>
                            <div className="text-xs text-muted-foreground">
                              {formatIncidentDate(event.created_at)} {event.actor ? `· ${event.actor}` : ''}
                            </div>
                          </div>
                        ))}
                      </div>
                    </details>
                  </CardContent>
                  </Card>
                );
              })}
            </div>
          )}

          <Pagination
            currentPage={page}
            totalPages={totalPages}
            totalItems={total}
            pageSize={pageSize}
            onPageChange={setPage}
            onPageSizeChange={setPageSize}
          />
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
