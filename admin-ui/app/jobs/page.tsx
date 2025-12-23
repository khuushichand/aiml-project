'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, Briefcase, Filter, AlertTriangle } from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';

interface JobItem {
  id: number;
  uuid?: string | null;
  domain: string;
  queue: string;
  job_type: string;
  status: string;
  priority?: number | null;
  retry_count?: number | null;
  max_retries?: number | null;
  available_at?: string | null;
  created_at?: string | null;
  acquired_at?: string | null;
  started_at?: string | null;
  leased_until?: string | null;
  completed_at?: string | null;
}

interface QueueStats {
  domain: string;
  queue: string;
  job_type: string;
  queued: number;
  scheduled: number;
  processing: number;
  quarantined: number;
}

interface StaleGroup {
  domain: string;
  queue: string;
  count: number;
}

const formatDateTime = (value?: string | null) => {
  if (!value) return '—';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return '—';
  return date.toLocaleString();
};

const statusBadge = (status: string) => {
  const normalized = status.toLowerCase();
  if (normalized === 'completed') return 'bg-green-500';
  if (normalized === 'processing') return 'bg-blue-500';
  if (normalized === 'queued' || normalized === 'scheduled') return 'bg-yellow-500';
  if (normalized === 'failed' || normalized === 'cancelled' || normalized === 'quarantined') {
    return 'bg-red-500';
  }
  return 'bg-muted text-muted-foreground';
};

export default function JobsPage() {
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [stats, setStats] = useState<QueueStats[]>([]);
  const [staleGroups, setStaleGroups] = useState<StaleGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [routesUnavailable, setRoutesUnavailable] = useState(false);

  const [filters, setFilters] = useState({
    domain: '',
    queue: '',
    status: '',
    job_type: '',
    limit: '100',
  });

  const statsParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (filters.domain) params.domain = filters.domain;
    if (filters.queue) params.queue = filters.queue;
    if (filters.job_type) params.job_type = filters.job_type;
    return params;
  }, [filters.domain, filters.queue, filters.job_type]);

  const listParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (filters.domain) params.domain = filters.domain;
    if (filters.queue) params.queue = filters.queue;
    if (filters.status) params.status = filters.status;
    if (filters.job_type) params.job_type = filters.job_type;
    if (filters.limit) params.limit = filters.limit;
    return params;
  }, [filters.domain, filters.queue, filters.status, filters.job_type, filters.limit]);

  const isNotFoundError = (err: unknown): boolean => {
    if (err instanceof ApiError) {
      return err.status === 404;
    }
    if (typeof err === 'object' && err !== null && 'status' in err) {
      return (err as { status?: number }).status === 404;
    }
    if (err instanceof Error) {
      return /not found|404/i.test(err.message);
    }
    return false;
  };

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setRoutesUnavailable(false);

      const [statsResult, jobsResult, staleResult] = await Promise.allSettled([
        api.getJobsStats(statsParams),
        api.getJobs(listParams),
        api.getJobsStale(statsParams),
      ]);

      const sawNotFound = [statsResult, jobsResult, staleResult].some(
        (result) => result.status === 'rejected' && isNotFoundError(result.reason)
      );
      setRoutesUnavailable(sawNotFound);

      if (statsResult.status === 'fulfilled') {
        setStats(Array.isArray(statsResult.value) ? statsResult.value : []);
      } else {
        setStats([]);
      }

      if (jobsResult.status === 'fulfilled') {
        setJobs(Array.isArray(jobsResult.value) ? jobsResult.value : []);
      } else {
        setJobs([]);
      }

      if (staleResult.status === 'fulfilled') {
        setStaleGroups(Array.isArray(staleResult.value) ? staleResult.value : []);
      } else {
        setStaleGroups([]);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load jobs';
      setError(message);
      setJobs([]);
      setStats([]);
      setStaleGroups([]);
    } finally {
      setLoading(false);
    }
  }, [listParams, statsParams]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  const handleReset = () => {
    setFilters({
      domain: '',
      queue: '',
      status: '',
      job_type: '',
      limit: '100',
    });
  };

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold">Jobs</h1>
              <p className="text-muted-foreground">Inspect queues, job health, and recent activity</p>
            </div>
            <Button variant="outline" onClick={loadData} disabled={loading}>
              <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          {routesUnavailable && (
            <Alert className="mb-6 border-yellow-200 bg-yellow-50">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                Jobs admin endpoints are disabled or unavailable. Enable the <span className="font-medium">jobs</span>{' '}
                route in server settings and restart the API to load queue data.
              </AlertDescription>
            </Alert>
          )}

          {staleGroups.length > 0 && (
            <Alert className="mb-6 bg-yellow-50 border-yellow-200">
              <AlertTriangle className="h-4 w-4 text-yellow-600" />
              <AlertDescription className="text-yellow-800">
                {staleGroups.length} stale processing group{staleGroups.length !== 1 ? 's' : ''} detected. Review queues for
                hung jobs.
              </AlertDescription>
            </Alert>
          )}

          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Filter className="h-5 w-5" />
                Filters
              </CardTitle>
              <CardDescription>Limit jobs by domain, queue, status, or type.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
                <div className="space-y-2">
                  <Label htmlFor="jobs-domain">Domain</Label>
                  <Input
                    id="jobs-domain"
                    value={filters.domain}
                    onChange={(event) => setFilters((prev) => ({ ...prev, domain: event.target.value }))}
                    placeholder="e.g. chatbooks"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="jobs-queue">Queue</Label>
                  <Input
                    id="jobs-queue"
                    value={filters.queue}
                    onChange={(event) => setFilters((prev) => ({ ...prev, queue: event.target.value }))}
                    placeholder="default"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="jobs-status">Status</Label>
                  <Select
                    id="jobs-status"
                    value={filters.status}
                    onChange={(event) => setFilters((prev) => ({ ...prev, status: event.target.value }))}
                  >
                    <option value="">All</option>
                    <option value="queued">Queued</option>
                    <option value="scheduled">Scheduled</option>
                    <option value="processing">Processing</option>
                    <option value="completed">Completed</option>
                    <option value="failed">Failed</option>
                    <option value="cancelled">Cancelled</option>
                    <option value="quarantined">Quarantined</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="jobs-type">Job type</Label>
                  <Input
                    id="jobs-type"
                    value={filters.job_type}
                    onChange={(event) => setFilters((prev) => ({ ...prev, job_type: event.target.value }))}
                    placeholder="export"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="jobs-limit">Limit</Label>
                  <Input
                    id="jobs-limit"
                    type="number"
                    min={1}
                    max={500}
                    value={filters.limit}
                    onChange={(event) => setFilters((prev) => ({ ...prev, limit: event.target.value }))}
                  />
                </div>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">
                <Button onClick={loadData} disabled={loading}>
                  Apply filters
                </Button>
                <Button variant="outline" onClick={handleReset} disabled={loading}>
                  Reset
                </Button>
              </div>
            </CardContent>
          </Card>

          <div className="grid gap-6 lg:grid-cols-3 mb-6">
            <Card className="lg:col-span-2">
              <CardHeader>
                <CardTitle className="flex items-center gap-2">
                  <Briefcase className="h-5 w-5" />
                  Queue Stats
                </CardTitle>
                <CardDescription>Current queue snapshot by domain/queue/type.</CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-muted-foreground">Loading stats…</div>
                ) : stats.length === 0 ? (
                  <div className="text-muted-foreground">No queue stats available.</div>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Domain</TableHead>
                        <TableHead>Queue</TableHead>
                        <TableHead>Job type</TableHead>
                        <TableHead className="text-right">Queued</TableHead>
                        <TableHead className="text-right">Scheduled</TableHead>
                        <TableHead className="text-right">Processing</TableHead>
                        <TableHead className="text-right">Quarantined</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {stats.map((row) => (
                        <TableRow key={`${row.domain}-${row.queue}-${row.job_type}`}>
                          <TableCell>{row.domain}</TableCell>
                          <TableCell>{row.queue}</TableCell>
                          <TableCell>{row.job_type}</TableCell>
                          <TableCell className="text-right">{row.queued}</TableCell>
                          <TableCell className="text-right">{row.scheduled}</TableCell>
                          <TableCell className="text-right">{row.processing}</TableCell>
                          <TableCell className="text-right">{row.quarantined}</TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Stale processing</CardTitle>
                <CardDescription>Queues with expired leases.</CardDescription>
              </CardHeader>
              <CardContent>
                {loading ? (
                  <div className="text-muted-foreground">Loading stale jobs…</div>
                ) : staleGroups.length === 0 ? (
                  <div className="text-muted-foreground">No stale jobs detected.</div>
                ) : (
                  <div className="space-y-3">
                    {staleGroups.map((group) => (
                      <div key={`${group.domain}-${group.queue}`} className="rounded-lg border p-3">
                        <div className="flex items-center justify-between">
                          <div>
                            <p className="text-sm font-medium">{group.domain}</p>
                            <p className="text-xs text-muted-foreground">Queue {group.queue}</p>
                          </div>
                          <Badge variant="destructive">{group.count} stale</Badge>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Recent jobs</CardTitle>
              <CardDescription>Latest jobs in the selected scope.</CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="text-muted-foreground">Loading jobs…</div>
              ) : jobs.length === 0 ? (
                <div className="text-muted-foreground">No jobs found.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>ID</TableHead>
                      <TableHead>Domain</TableHead>
                      <TableHead>Queue</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Retries</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Started</TableHead>
                      <TableHead>Completed</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {jobs.map((job) => (
                      <TableRow key={job.id}>
                        <TableCell className="font-medium">{job.id}</TableCell>
                        <TableCell>{job.domain}</TableCell>
                        <TableCell>{job.queue}</TableCell>
                        <TableCell>{job.job_type}</TableCell>
                        <TableCell>
                          <Badge className={statusBadge(job.status)}>{job.status}</Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          {job.retry_count ?? 0}/{job.max_retries ?? 0}
                        </TableCell>
                        <TableCell>{formatDateTime(job.created_at)}</TableCell>
                        <TableCell>{formatDateTime(job.started_at)}</TableCell>
                        <TableCell>{formatDateTime(job.completed_at)}</TableCell>
                      </TableRow>
                    ))}
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
