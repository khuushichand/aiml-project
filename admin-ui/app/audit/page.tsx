'use client';

import { useEffect, useState, Suspense } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { FileText, Search, RefreshCw, Filter } from 'lucide-react';
import { api } from '@/lib/api-client';
import { AuditLog } from '@/types';
import { ExportMenu } from '@/components/ui/export-menu';
import { exportAuditLogs, ExportFormat } from '@/lib/export';
import { Skeleton, TableSkeleton } from '@/components/ui/skeleton';
import { useUrlMultiState, useUrlPagination } from '@/lib/use-url-state';

function AuditPageContent() {
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [allLogs, setAllLogs] = useState<AuditLog[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // URL state for filters
  const [filters, setFilters, clearFilters] = useUrlMultiState({
    user: '',
    action: '',
    resource: '',
    start: '',
    end: '',
  });

  // URL state for pagination
  const { page: currentPage, pageSize, setPage: setCurrentPage, setPageSize, resetPagination } = useUrlPagination();

  useEffect(() => {
    loadLogs();
  }, []);

  const loadLogs = async () => {
    try {
      setLoading(true);
      setError('');

      const data = await api.getAuditLogs();
      const logsArray = Array.isArray(data) ? data : (data.items || []);
      setAllLogs(logsArray);
      setLogs(logsArray);
    } catch (err: any) {
      console.error('Failed to load audit logs:', err);
      setError(err.message || 'Failed to load audit logs');
      setAllLogs([]);
      setLogs([]);
    } finally {
      setLoading(false);
    }
  };

  // Apply filters - now filters from URL state
  const applyFilters = () => {
    let filtered = [...allLogs];

    if (filters.user) {
      filtered = filtered.filter((log) =>
        log.user_id.toString().includes(filters.user)
      );
    }

    if (filters.action) {
      filtered = filtered.filter((log) =>
        log.action.toLowerCase().includes(filters.action.toLowerCase())
      );
    }

    if (filters.resource) {
      filtered = filtered.filter((log) =>
        log.resource.toLowerCase().includes(filters.resource.toLowerCase())
      );
    }

    if (filters.start) {
      const start = new Date(filters.start);
      filtered = filtered.filter((log) => new Date(log.timestamp) >= start);
    }

    if (filters.end) {
      const end = new Date(filters.end);
      end.setHours(23, 59, 59, 999);
      filtered = filtered.filter((log) => new Date(log.timestamp) <= end);
    }

    setLogs(filtered);
    resetPagination();
  };

  const handleClearFilters = () => {
    clearFilters();
    setLogs(allLogs);
    resetPagination();
  };

  const handleExport = (format: ExportFormat) => {
    exportAuditLogs(logs, format);
  };

  // Pagination
  const totalItems = logs.length;
  const totalPages = Math.ceil(totalItems / pageSize);
  const startIndex = (currentPage - 1) * pageSize;
  const paginatedLogs = logs.slice(startIndex, startIndex + pageSize);

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
    <ProtectedRoute>
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
                <Button variant="outline" onClick={loadLogs} disabled={loading}>
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
                    <Label htmlFor="userFilter">User ID</Label>
                    <Input
                      id="userFilter"
                      placeholder="Filter by user..."
                      value={filters.user}
                      onChange={(e) => setFilters({ user: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="actionFilter">Action</Label>
                    <Input
                      id="actionFilter"
                      placeholder="e.g., create, delete..."
                      value={filters.action}
                      onChange={(e) => setFilters({ action: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="resourceFilter">Resource</Label>
                    <Input
                      id="resourceFilter"
                      placeholder="e.g., user, api_key..."
                      value={filters.resource}
                      onChange={(e) => setFilters({ resource: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="startDate">Start Date</Label>
                    <Input
                      id="startDate"
                      type="date"
                      value={filters.start}
                      onChange={(e) => setFilters({ start: e.target.value })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="endDate">End Date</Label>
                    <Input
                      id="endDate"
                      type="date"
                      value={filters.end}
                      onChange={(e) => setFilters({ end: e.target.value })}
                    />
                  </div>
                </div>
                <div className="flex gap-2 mt-4">
                  <Button onClick={applyFilters}>
                    <Search className="mr-2 h-4 w-4" />
                    Apply Filters
                  </Button>
                  <Button variant="outline" onClick={handleClearFilters}>
                    Clear Filters
                  </Button>
                </div>
              </CardContent>
            </Card>

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
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {paginatedLogs.map((log) => (
                            <TableRow key={log.id}>
                              <TableCell className="text-sm text-muted-foreground whitespace-nowrap">
                                {formatTimestamp(log.timestamp)}
                              </TableCell>
                              <TableCell className="font-mono text-sm">
                                {log.user_id}
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
    </ProtectedRoute>
  );
}

// Wrap with Suspense for useSearchParams
export default function AuditPage() {
  return (
    <Suspense fallback={
      <ProtectedRoute>
        <ResponsiveLayout>
          <div className="p-4 lg:p-8">
            <div className="mb-8">
              <Skeleton className="h-8 w-32 mb-2" />
              <Skeleton className="h-4 w-64" />
            </div>
            <TableSkeleton rows={5} columns={5} />
          </div>
        </ResponsiveLayout>
      </ProtectedRoute>
    }>
      <AuditPageContent />
    </Suspense>
  );
}
