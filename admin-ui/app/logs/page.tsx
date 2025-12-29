'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { api } from '@/lib/api-client';
import { useUrlPagination } from '@/lib/use-url-state';
import { RefreshCw } from 'lucide-react';

type SystemLogEntry = {
  timestamp?: string | null;
  level?: string | null;
  message?: string | null;
  logger?: string | null;
  module?: string | null;
  function?: string | null;
  line?: number | null;
  request_id?: string | null;
  org_id?: number | null;
  user_id?: number | null;
};

const LOG_LEVELS = ['', 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'];

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const toIsoIfSet = (value: string) => {
  if (!value) return '';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString();
};

export default function LogsPage() {
  const { page, pageSize, setPage, setPageSize, resetPagination } = useUrlPagination();
  const [logs, setLogs] = useState<SystemLogEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [start, setStart] = useState('');
  const [end, setEnd] = useState('');
  const [level, setLevel] = useState('');
  const [service, setService] = useState('');
  const [query, setQuery] = useState('');
  const [orgId, setOrgId] = useState('');
  const [userId, setUserId] = useState('');

  const params = useMemo(() => {
    const offset = Math.max(0, (page - 1) * pageSize);
    const payload: Record<string, string> = {
      limit: String(pageSize),
      offset: String(offset),
    };
    const isoStart = toIsoIfSet(start);
    const isoEnd = toIsoIfSet(end);
    if (isoStart) payload.start = isoStart;
    if (isoEnd) payload.end = isoEnd;
    if (level) payload.level = level;
    if (service) payload.service = service;
    if (query) payload.query = query;
    if (orgId) payload.org_id = orgId;
    if (userId) payload.user_id = userId;
    return payload;
  }, [end, level, orgId, page, pageSize, query, service, start, userId]);

  const loadLogs = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getSystemLogs(params);
      if (data && typeof data === 'object') {
        const items = Array.isArray((data as { items?: unknown }).items)
          ? ((data as { items: SystemLogEntry[] }).items)
          : [];
        setLogs(items);
        setTotal(Number((data as { total?: number }).total || items.length));
      } else {
        setLogs([]);
        setTotal(0);
      }
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to load logs';
      setError(message);
      setLogs([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [params]);

  useEffect(() => {
    void loadLogs();
  }, [loadLogs]);

  const totalPages = Math.max(1, Math.ceil(total / pageSize));

  const handleFilterChange = () => {
    resetPagination();
  };

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
        <div className="flex flex-col gap-6 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">System Logs</h1>
              <p className="text-muted-foreground">Query recent logs captured in memory.</p>
            </div>
            <Button variant="outline" onClick={loadLogs} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Filters</CardTitle>
              <CardDescription>Restrict logs by time range, level, or metadata.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-3">
              <div className="space-y-1">
                <Label htmlFor="start">Start</Label>
                <Input
                  id="start"
                  type="datetime-local"
                  value={start}
                  onChange={(e) => {
                    setStart(e.target.value);
                    handleFilterChange();
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="end">End</Label>
                <Input
                  id="end"
                  type="datetime-local"
                  value={end}
                  onChange={(e) => {
                    setEnd(e.target.value);
                    handleFilterChange();
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="level">Level</Label>
                <Select
                  id="level"
                  value={level}
                  onChange={(e) => {
                    setLevel(e.target.value);
                    handleFilterChange();
                  }}
                >
                  {LOG_LEVELS.map((item) => (
                    <option key={item || 'all'} value={item}>
                      {item || 'All'}
                    </option>
                  ))}
                </Select>
              </div>
              <div className="space-y-1">
                <Label htmlFor="service">Service</Label>
                <Input
                  id="service"
                  placeholder="logger or module"
                  value={service}
                  onChange={(e) => {
                    setService(e.target.value);
                    handleFilterChange();
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="query">Search</Label>
                <Input
                  id="query"
                  placeholder="message contains..."
                  value={query}
                  onChange={(e) => {
                    setQuery(e.target.value);
                    handleFilterChange();
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="orgId">Org ID</Label>
                <Input
                  id="orgId"
                  placeholder="optional"
                  value={orgId}
                  onChange={(e) => {
                    setOrgId(e.target.value);
                    handleFilterChange();
                  }}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="userId">User ID</Label>
                <Input
                  id="userId"
                  placeholder="optional"
                  value={userId}
                  onChange={(e) => {
                    setUserId(e.target.value);
                    handleFilterChange();
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

          <Card>
            <CardHeader>
              <CardTitle>Entries</CardTitle>
              <CardDescription>Newest entries appear first.</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-12 text-center text-muted-foreground">Loading logs...</div>
              ) : logs.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground">No logs match the filters.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Level</TableHead>
                      <TableHead>Message</TableHead>
                      <TableHead>Logger</TableHead>
                      <TableHead>Org/User</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {logs.map((entry, idx) => (
                      <TableRow key={`${entry.timestamp || 'log'}-${idx}`}>
                        <TableCell className="whitespace-nowrap">
                          {formatDateTime(entry.timestamp)}
                        </TableCell>
                        <TableCell>
                          <Badge variant="outline">{entry.level || '—'}</Badge>
                        </TableCell>
                        <TableCell className="max-w-[420px] truncate">
                          {entry.message || '—'}
                        </TableCell>
                        <TableCell className="max-w-[240px] truncate">
                          {entry.logger || entry.module || '—'}
                        </TableCell>
                        <TableCell>
                          {entry.org_id ? `Org ${entry.org_id}` : '—'}{' '}
                          {entry.user_id ? `• User ${entry.user_id}` : ''}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

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
    </ProtectedRoute>
  );
}
