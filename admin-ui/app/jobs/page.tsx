'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { RefreshCw, Briefcase, Filter, AlertTriangle, Eye, RotateCcw, XCircle, Repeat } from 'lucide-react';
import { api, ApiError } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';

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

interface JobDetail extends JobItem {
  payload?: unknown;
  result?: unknown;
  archived?: boolean;
  error_message?: string | null;
  last_error?: string | null;
  progress_percent?: number | null;
  progress_message?: string | null;
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

const formatJobDateTime = (value?: string | null) =>
  formatDateTime(value, { fallback: '—' });

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

const clampLimit = (value: string) => {
  if (!value.trim()) return '';
  const parsed = Number(value);
  if (Number.isNaN(parsed)) return '';
  const clamped = Math.min(500, Math.max(1, Math.floor(parsed)));
  return String(clamped);
};

export default function JobsPage() {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();
  const [jobs, setJobs] = useState<JobItem[]>([]);
  const [stats, setStats] = useState<QueueStats[]>([]);
  const [staleGroups, setStaleGroups] = useState<StaleGroup[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [routesUnavailable, setRoutesUnavailable] = useState(false);
  const [selectedJob, setSelectedJob] = useState<JobItem | null>(null);
  const [jobDetail, setJobDetail] = useState<JobDetail | null>(null);
  const [jobDetailLoading, setJobDetailLoading] = useState(false);
  const [jobDetailError, setJobDetailError] = useState('');

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
    const normalizedLimit = clampLimit(filters.limit);
    if (normalizedLimit) params.limit = normalizedLimit;
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

    setLoading(false);
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

  const handleOpenDetail = async (job: JobItem) => {
    setSelectedJob(job);
    setJobDetail(null);
    setJobDetailError('');
    setJobDetailLoading(true);
    try {
      const detail = await api.getJobDetail(job.id, { domain: job.domain });
      setJobDetail(detail as JobDetail);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load job detail';
      setJobDetailError(message);
      setJobDetail(null);
    } finally {
      setJobDetailLoading(false);
    }
  };

  const handleCloseDetail = () => {
    setSelectedJob(null);
    setJobDetail(null);
    setJobDetailError('');
    setJobDetailLoading(false);
  };

  const handleCancelJob = async (job: JobItem) => {
    const confirmed = await confirm({
      title: 'Cancel job',
      message: `Cancel job ${job.id}? This stops any processing immediately.`,
      confirmText: 'Cancel job',
      variant: 'danger',
      icon: 'warning',
    });
    if (!confirmed) return;

    try {
      await api.cancelJobs({ domain: job.domain, job_id: job.id, dry_run: false });
      success('Job cancelled', `Job ${job.id} has been cancelled.`);
      handleCloseDetail();
      void loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to cancel job';
      showError('Cancel failed', message);
    }
  };

  const handleRetryJob = async (job: JobItem) => {
    const confirmed = await confirm({
      title: 'Retry job',
      message: `Retry job ${job.id}? The job will re-enter the queue immediately.`,
      confirmText: 'Retry job',
      variant: 'default',
    });
    if (!confirmed) return;

    try {
      await api.retryJobsNow({ domain: job.domain, job_id: job.id, only_failed: true, dry_run: false });
      success('Job retried', `Job ${job.id} has been re-queued.`);
      handleCloseDetail();
      void loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to retry job';
      showError('Retry failed', message);
    }
  };

  const handleRequeueJob = async (job: JobItem) => {
    const confirmed = await confirm({
      title: 'Requeue job',
      message: `Requeue job ${job.id}? The job will move out of quarantine.`,
      confirmText: 'Requeue job',
      variant: 'default',
    });
    if (!confirmed) return;

    try {
      await api.requeueQuarantinedJobs({ domain: job.domain, job_id: job.id, dry_run: false });
      success('Job requeued', `Job ${job.id} moved back to queued.`);
      handleCloseDetail();
      void loadData();
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to requeue job';
      showError('Requeue failed', message);
    }
  };

  const formatJson = (value: unknown) => {
    if (value === undefined || value === null) {
      return '—';
    }
    try {
      return JSON.stringify(value, null, 2);
    } catch {
      return String(value);
    }
  };

  return (
    <PermissionGuard variant="route" requireAuth>
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
                    onBlur={(event) => {
                      const next = clampLimit(event.target.value);
                      setFilters((prev) => ({ ...prev, limit: next }));
                    }}
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
                <>
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
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {jobs.map((job) => {
                        const normalizedStatus = job.status.toLowerCase();
                        const canCancel = normalizedStatus === 'queued' || normalizedStatus === 'processing';
                        const canRetry = normalizedStatus === 'failed';
                        const canRequeue = normalizedStatus === 'quarantined';

                        return (
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
                            <TableCell>{formatJobDateTime(job.created_at)}</TableCell>
                            <TableCell>{formatJobDateTime(job.started_at)}</TableCell>
                            <TableCell>{formatJobDateTime(job.completed_at)}</TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-2">
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleOpenDetail(job)}
                                >
                                  <Eye className="mr-2 h-4 w-4" />
                                  View
                                </Button>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={() => handleRetryJob(job)}
                                  disabled={!canRetry}
                                  title={canRetry ? 'Retry job' : 'Retry available for failed jobs'}
                                >
                                  <RotateCcw className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={() => handleRequeueJob(job)}
                                  disabled={!canRequeue}
                                  title={canRequeue ? 'Requeue job' : 'Requeue available for quarantined jobs'}
                                >
                                  <Repeat className="h-4 w-4" />
                                </Button>
                                <Button
                                  variant="outline"
                                  size="icon"
                                  onClick={() => handleCancelJob(job)}
                                  disabled={!canCancel}
                                  title={canCancel ? 'Cancel job' : 'Cancel available for queued or processing jobs'}
                                >
                                  <XCircle className="h-4 w-4" />
                                </Button>
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                </>
              )}
            </CardContent>
          </Card>

          <Dialog open={!!selectedJob} onOpenChange={(open) => !open && handleCloseDetail()}>
            <DialogContent className="max-w-4xl">
              <DialogHeader>
                <DialogTitle>Job {selectedJob?.id}</DialogTitle>
                <DialogDescription>
                  {jobDetail?.archived ? 'Archived job details' : 'Job details and payload'}
                </DialogDescription>
              </DialogHeader>
              {jobDetailLoading && (
                <div className="text-sm text-muted-foreground">Loading job details…</div>
              )}
              {jobDetailError && (
                <Alert variant="destructive">
                  <AlertDescription>{jobDetailError}</AlertDescription>
                </Alert>
              )}
              {jobDetail && (
                <div className="space-y-4">
                  <div className="grid gap-4 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label>ID</Label>
                      <div className="text-sm font-mono">{jobDetail.id}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Status</Label>
                      <Badge className={statusBadge(jobDetail.status)}>{jobDetail.status}</Badge>
                    </div>
                    <div className="space-y-1">
                      <Label>Domain</Label>
                      <div className="text-sm">{jobDetail.domain}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Queue</Label>
                      <div className="text-sm">{jobDetail.queue}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Job type</Label>
                      <div className="text-sm">{jobDetail.job_type}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Retries</Label>
                      <div className="text-sm">
                        {jobDetail.retry_count ?? 0}/{jobDetail.max_retries ?? 0}
                      </div>
                    </div>
                    <div className="space-y-1">
                      <Label>Created</Label>
                      <div className="text-sm">{formatJobDateTime(jobDetail.created_at)}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Started</Label>
                      <div className="text-sm">{formatJobDateTime(jobDetail.started_at)}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Completed</Label>
                      <div className="text-sm">{formatJobDateTime(jobDetail.completed_at)}</div>
                    </div>
                    <div className="space-y-1">
                      <Label>Archived</Label>
                      <div className="text-sm">{jobDetail.archived ? 'Yes' : 'No'}</div>
                    </div>
                  </div>

                  {jobDetail.error_message && (
                    <Alert variant="destructive">
                      <AlertDescription>{jobDetail.error_message}</AlertDescription>
                    </Alert>
                  )}

                  <div className="space-y-2">
                    <Label>Payload</Label>
                    <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">
                      {formatJson(jobDetail.payload)}
                    </pre>
                  </div>
                  <div className="space-y-2">
                    <Label>Result</Label>
                    <pre className="max-h-64 overflow-auto rounded-md bg-muted p-3 text-xs">
                      {formatJson(jobDetail.result)}
                    </pre>
                  </div>
                </div>
              )}
            </DialogContent>
          </Dialog>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
