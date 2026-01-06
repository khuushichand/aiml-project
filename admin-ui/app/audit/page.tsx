'use client';

import { useCallback, useEffect, useMemo, useState, Suspense } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription, AlertTitle } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { FileText, RefreshCw, Filter, Eye, Clipboard } from 'lucide-react';
import { api } from '@/lib/api-client';
import { AuditLog } from '@/types';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportAuditLogs, ExportFormat } from '@/lib/export';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { useUrlMultiState, useUrlPagination } from '@/lib/use-url-state';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useToast } from '@/components/ui/toast';
import Link from 'next/link';

type AuditFilters = {
  user: string;
  action: string;
  resource: string;
  start: string;
  end: string;
};

const parseDateInput = (value: string) => {
  if (!value) return null;
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value)) return null;
  const date = new Date(`${value}T00:00:00`);
  return Number.isNaN(date.getTime()) ? null : date;
};

const getDateRangeError = (start: string, end: string) => {
  if (!start && !end) return '';
  const startDate = parseDateInput(start);
  const endDate = parseDateInput(end);
  if (start && !startDate) return 'Start date is invalid.';
  if (end && !endDate) return 'End date is invalid.';
  if (startDate && endDate && startDate > endDate) {
    return 'Start date must be on or before end date.';
  }
  return '';
};

const parseUserFilter = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) {
    return null;
  }
  return /^\d+$/.test(trimmed) ? trimmed : null;
};

function AuditPageContent() {
  const { selectedOrg } = useOrgContext();
  const { success, error: showError } = useToast();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [totalItems, setTotalItems] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selectedLog, setSelectedLog] = useState<AuditLog | null>(null);

  // URL state for filters
  const [filters, setFilters, clearFilters] = useUrlMultiState<AuditFilters>({
    user: '',
    action: '',
    resource: '',
    start: '',
    end: '',
  });
  const [debouncedFilters, setDebouncedFilters] = useState<AuditFilters>(filters);

  // URL state for pagination
  const { page: currentPage, pageSize, setPage: setCurrentPage, setPageSize, resetPagination } = useUrlPagination();

  useEffect(() => {
    const handle = window.setTimeout(() => {
      setDebouncedFilters((prev) => {
        if (
          prev.user === filters.user
          && prev.action === filters.action
          && prev.resource === filters.resource
          && prev.start === filters.start
          && prev.end === filters.end
        ) {
          return prev;
        }
        return filters;
      });
    }, 300);
    return () => window.clearTimeout(handle);
  }, [filters]);

  const loadLogs = useCallback(async (activeFilters: AuditFilters, page: number, size: number) => {
    try {
      setLoading(true);
      setError('');

      const rangeError = getDateRangeError(activeFilters.start, activeFilters.end);
      if (rangeError) {
        setLogs([]);
        setTotalItems(0);
        return;
      }

      const params: Record<string, string> = {
        limit: String(size),
        offset: String((page - 1) * size),
      };
      if (selectedOrg) {
        params.org_id = String(selectedOrg.id);
      }
      const userIdParam = parseUserFilter(activeFilters.user);
      if (userIdParam) {
        params.user_id = userIdParam;
      }
      const actionFilter = activeFilters.action.trim();
      if (actionFilter) {
        params.action = actionFilter;
      }
      const resourceFilter = activeFilters.resource.trim();
      if (resourceFilter) {
        params.resource = resourceFilter;
      }
      const startFilter = activeFilters.start.trim();
      if (startFilter) {
        params.start = startFilter;
      }
      const endFilter = activeFilters.end.trim();
      if (endFilter) {
        params.end = endFilter;
      }
      const data = await api.getAuditLogs(params);
      const items = Array.isArray(data) ? data : data.entries ?? [];
      setLogs(items);
      setTotalItems(Number(data.total ?? items.length ?? 0));
    } catch (err: unknown) {
      console.error('Failed to load audit logs:', err);
      setError(err instanceof Error && err.message ? err.message : 'Failed to load audit logs');
      setLogs([]);
      setTotalItems(0);
    } finally {
      setLoading(false);
    }
  }, [selectedOrg]);

  useEffect(() => {
    void loadLogs(debouncedFilters, currentPage, pageSize);
  }, [currentPage, debouncedFilters, loadLogs, pageSize]);

  const handleFilterChange = (updates: Partial<AuditFilters>) => {
    setFilters(updates);
    resetPagination();
  };

  const handleClearFilters = () => {
    clearFilters();
    resetPagination();
  };

  const dateRangeError = useMemo(() => getDateRangeError(filters.start, filters.end), [filters.end, filters.start]);

  const handleExport = (format: ExportFormat) => {
    exportAuditLogs(logs, format);
  };

  const handleCopyRaw = async () => {
    if (!selectedLog) return;
    const rawPayload = selectedLog.raw ?? {
      id: selectedLog.id,
      timestamp: selectedLog.timestamp,
      user_id: selectedLog.user_id,
      action: selectedLog.action,
      resource: selectedLog.resource,
      details: selectedLog.details,
      ip_address: selectedLog.ip_address,
      username: selectedLog.username,
    };
    try {
      if (!navigator.clipboard) {
        showError('Copy failed', 'Clipboard API not available. Ensure you are using HTTPS.');
        return;
      }
      await navigator.clipboard.writeText(JSON.stringify(rawPayload, null, 2));
      success('Copied audit event');
    } catch (err) {
      console.error('Failed to copy audit log:', err);
      showError('Copy failed', 'Unable to copy audit event details.');
    }
  };

  // Pagination
  const totalPages = Math.ceil(totalItems / pageSize);

  const formatTimestamp = (ts: string) => {
    return new Date(ts).toLocaleString();
  };

  const getActionBadgeVariant = (action: string): 'default' | 'secondary' | 'destructive' | 'outline' => {
    const lowerAction = action.toLowerCase();
    if (lowerAction.includes('delete') || lowerAction.includes('revoke')) return 'destructive';
    if (lowerAction.includes('create') || lowerAction.includes('add')) return 'default';
    if (lowerAction.includes('update') || lowerAction.includes('modify')) return 'secondary';
    return 'outline';
  };

  return (
    <PermissionGuard variant="route" requireAuth>
      <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8 flex items-center justify-between">
              <div>
                <h1 className="text-3xl font-bold">Audit Logs</h1>
                <p className="text-muted-foreground">
                  Track all system activities and user actions
                </p>
              </div>
              <div className="flex gap-2">
                <Button
                  variant="outline"
                  onClick={() => loadLogs(debouncedFilters, currentPage, pageSize)}
                  disabled={loading || Boolean(dateRangeError)}
                >
                  <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                  Refresh
                </Button>
                <ExportMenu
                  onExport={handleExport}
                  disabled={logs.length === 0}
                />
              </div>
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
                  <FileText className="h-8 w-8 text-primary mt-1" />
                  <div>
                    <h3 className="font-semibold">Audit Trail</h3>
                    <p className="text-sm text-muted-foreground mt-1">
                      View detailed records of all administrative actions, user activities, and system events.
                      Use filters to narrow down results by user, action type, or date range.
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Filters */}
            <Card className="mb-6">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Filter className="h-5 w-5" />
                  Filters
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-5 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="userFilter">User ID (exact)</Label>
                    <Input
                      id="userFilter"
                      placeholder="e.g., 42"
                      value={filters.user}
                      onChange={(e) => handleFilterChange({ user: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="actionFilter">Action (exact)</Label>
                    <Input
                      id="actionFilter"
                      placeholder="e.g., user.create"
                      value={filters.action}
                      onChange={(e) => handleFilterChange({ action: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="resourceFilter">Resource</Label>
                    <Input
                      id="resourceFilter"
                      placeholder="e.g., user, api_key..."
                      value={filters.resource}
                      onChange={(e) => handleFilterChange({ resource: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="startDate">Start Date</Label>
                    <Input
                      id="startDate"
                      type="date"
                      value={filters.start}
                      onChange={(e) => handleFilterChange({ start: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="endDate">End Date</Label>
                    <Input
                      id="endDate"
                      type="date"
                      value={filters.end}
                      onChange={(e) => handleFilterChange({ end: e.target.value })}
                    />
                  </div>
                </div>
                {dateRangeError && (
                  <Alert variant="destructive" className="mt-4">
                    <AlertTitle>Invalid date range</AlertTitle>
                    <AlertDescription>{dateRangeError}</AlertDescription>
                  </Alert>
                )}
                <div className="flex gap-2 mt-4">
                  <Button variant="outline" onClick={handleClearFilters}>
                    Clear Filters
                  </Button>
                </div>
              </CardContent>
            </Card>

            <Dialog open={!!selectedLog} onOpenChange={(open) => !open && setSelectedLog(null)}>
              <DialogContent className="max-w-3xl">
                <DialogHeader>
                  <DialogTitle>Audit Event</DialogTitle>
                  <DialogDescription>
                    {selectedLog ? `${selectedLog.action} · ${formatTimestamp(selectedLog.timestamp)}` : 'Event details'}
                  </DialogDescription>
                </DialogHeader>
                {selectedLog && (
                  <div className="space-y-4">
                    <div className="grid gap-4 sm:grid-cols-2">
                      <div className="space-y-1">
                        <Label>Event ID</Label>
                        <div className="text-sm font-mono">{selectedLog.id}</div>
                      </div>
                      <div className="space-y-1">
                        <Label>Resource</Label>
                        <div className="text-sm font-mono">{selectedLog.resource || '—'}</div>
                      </div>
                      <div className="space-y-1">
                        <Label>User</Label>
                        <div className="text-sm">
                          <div className="font-mono">{selectedLog.user_id || '—'}</div>
                          {selectedLog.username && (
                            <div className="text-xs text-muted-foreground">{selectedLog.username}</div>
                          )}
                          {selectedLog.user_id ? (
                            <Link href={`/users/${selectedLog.user_id}`} className="text-xs text-primary underline">
                              View user
                            </Link>
                          ) : null}
                        </div>
                      </div>
                      <div className="space-y-1">
                        <Label>IP Address</Label>
                        <div className="text-sm font-mono">{selectedLog.ip_address || '—'}</div>
                      </div>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>Details</Label>
                      </div>
                      {selectedLog.details ? (
                        <pre className="text-xs bg-muted p-3 rounded max-h-64 overflow-auto">
                          {JSON.stringify(selectedLog.details, null, 2)}
                        </pre>
                      ) : (
                        <div className="text-sm text-muted-foreground">No details captured.</div>
                      )}
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between">
                        <Label>Raw Event</Label>
                        <Button variant="outline" size="sm" onClick={handleCopyRaw}>
                          <Clipboard className="mr-2 h-4 w-4" />
                          Copy JSON
                        </Button>
                      </div>
                      <pre className="text-xs bg-muted p-3 rounded max-h-64 overflow-auto">
                        {JSON.stringify(
                          selectedLog.raw ?? selectedLog,
                          null,
                          2
                        )}
                      </pre>
                    </div>
                  </div>
                )}
              </DialogContent>
            </Dialog>

            {/* Logs Table */}
            <Card>
              <CardHeader>
                <CardTitle>Activity Log</CardTitle>
                <CardDescription>
                  {totalItems} record{totalItems !== 1 ? 's' : ''} found
                </CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="py-4">
                    <TableSkeleton rows={5} columns={5} />
                  </div>
                ) : logs.length === 0 ? (
                  <div className="text-center text-muted-foreground py-8">
                    No audit logs found for the selected filters.
                  </div>
                ) : (
                  <>
                    <div className="overflow-x-auto">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Timestamp</TableHead>
                            <TableHead>User</TableHead>
                            <TableHead>Action</TableHead>
                            <TableHead>Resource</TableHead>
                            <TableHead>Details</TableHead>
                            <TableHead className="text-right">Actions</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {logs.map((log) => (
                            <TableRow key={log.id}>
                              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                                {formatTimestamp(log.timestamp)}
                              </TableCell>
                              <TableCell className="font-mono text-sm">
                                <div className="flex flex-col">
                                  <span>{log.user_id}</span>
                                  {log.username && (
                                    <span className="text-xs text-muted-foreground">{log.username}</span>
                                  )}
                                </div>
                              </TableCell>
                              <TableCell>
                                <Badge variant={getActionBadgeVariant(log.action)}>
                                  {log.action}
                                </Badge>
                              </TableCell>
                              <TableCell className="font-mono text-sm">
                                {log.resource}
                              </TableCell>
                              <TableCell className="max-w-xs">
                                {log.details ? (
                                  <code className="text-xs bg-muted p-1 rounded block truncate">
                                    {JSON.stringify(log.details)}
                                  </code>
                                ) : (
                                  <span className="text-muted-foreground">-</span>
                                )}
                              </TableCell>
                              <TableCell className="text-right">
                                <Button variant="outline" size="sm" onClick={() => setSelectedLog(log)}>
                                  <Eye className="mr-2 h-4 w-4" />
                                  View
                                </Button>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </div>

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

// Wrap with Suspense for useSearchParams
export default function AuditPage() {
  return (
    <Suspense fallback={
      <PermissionGuard variant="route" requireAuth>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <Skeleton className="h-8 w-32 mb-2" />
              <Skeleton className="h-4 w-64" />
            </div>
            <TableSkeleton rows={5} columns={5} />
          </div>
        </ResponsiveLayout>
      </PermissionGuard>
    }>
      <AuditPageContent />
    </Suspense>
  );
}
