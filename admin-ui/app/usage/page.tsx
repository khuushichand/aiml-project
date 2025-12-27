'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { RefreshCw, BarChart3, Calendar, Download } from 'lucide-react';
import { api } from '@/lib/api-client';
import { getAuthHeaders } from '@/lib/auth';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useToast } from '@/components/ui/toast';

interface UsageDailyRow {
  user_id: number;
  day: string;
  requests: number;
  errors: number;
  bytes_total: number;
  bytes_in_total?: number | null;
  latency_avg_ms?: number | null;
}

interface UsageTopRow {
  user_id: number;
  requests: number;
  errors: number;
  bytes_total: number;
  bytes_in_total?: number | null;
  latency_avg_ms?: number | null;
}

interface LlmSummaryRow {
  group_value: string;
  requests: number;
  errors: number;
  input_tokens: number;
  output_tokens: number;
  total_tokens: number;
  total_cost_usd: number;
  latency_avg_ms?: number | null;
}

interface LlmTopSpenderRow {
  user_id: number;
  total_cost_usd: number;
  requests: number;
}

type ExportKey = 'daily' | 'top' | 'llm';

const API_HOST = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const API_URL = `${API_HOST.replace(/\/$/, '')}/api/${API_VERSION}`;

const toDateInput = (date: Date) => date.toISOString().slice(0, 10);

const defaultEnd = () => toDateInput(new Date());
const defaultStart = () => {
  const date = new Date();
  date.setDate(date.getDate() - 7);
  return toDateInput(date);
};

const formatBytes = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  const units = ['B', 'KB', 'MB', 'GB', 'TB'];
  let size = value;
  let idx = 0;
  while (size >= 1024 && idx < units.length - 1) {
    size /= 1024;
    idx += 1;
  }
  return `${size.toFixed(1)} ${units[idx]}`;
};

const formatLatency = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  return `${value.toFixed(1)} ms`;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const getErrorMessage = (reason: unknown, fallback: string) => {
  if (reason instanceof Error && reason.message) return reason.message;
  if (typeof reason === 'string' && reason.trim().length > 0) return reason;
  if (isRecord(reason) && typeof reason.message === 'string' && reason.message.trim().length > 0) {
    return reason.message;
  }
  return fallback;
};

const getFilenameFromDisposition = (disposition: string | null): string | null => {
  if (!disposition) return null;
  const match = disposition.match(/filename="?([^"]+)"?/i);
  return match ? match[1] : null;
};

const downloadCsv = async (
  endpoint: string,
  params: Record<string, string>,
  fallbackFilename: string
) => {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(`${API_URL}${endpoint}${query ? `?${query}` : ''}`, {
    headers: getAuthHeaders(),
    credentials: 'include',
  });
  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || 'Failed to download CSV');
  }
  const blob = await response.blob();
  const filename = getFilenameFromDisposition(response.headers.get('content-disposition')) || fallbackFilename;
  const url = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(url);
};

export default function UsagePage() {
  const { selectedOrg } = useOrgContext();
  const { success, error: showError } = useToast();
  const [usageDaily, setUsageDaily] = useState<UsageDailyRow[]>([]);
  const [usageTop, setUsageTop] = useState<UsageTopRow[]>([]);
  const [llmSummary, setLlmSummary] = useState<LlmSummaryRow[]>([]);
  const [llmTop, setLlmTop] = useState<LlmTopSpenderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [exporting, setExporting] = useState<Record<ExportKey, boolean>>({
    daily: false,
    top: false,
    llm: false,
  });

  const [startDate, setStartDate] = useState(defaultStart());
  const [endDate, setEndDate] = useState(defaultEnd());
  const [topMetric, setTopMetric] = useState('requests');
  const [groupBy, setGroupBy] = useState('provider');
  const dateSuffix = `${startDate || 'all'}_${endDate || 'all'}`;

  const toIsoStart = (value: string) => (value ? `${value}T00:00:00Z` : undefined);
  const toIsoEnd = (value: string) => (value ? `${value}T23:59:59Z` : undefined);

  const usageParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (startDate) params.start = startDate;
    if (endDate) params.end = endDate;
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    return params;
  }, [startDate, endDate, selectedOrg]);

  const llmParams = useMemo(() => {
    const params: Record<string, string> = { group_by: groupBy };
    if (startDate) params.start = toIsoStart(startDate) as string;
    if (endDate) params.end = toIsoEnd(endDate) as string;
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    return params;
  }, [startDate, endDate, groupBy, selectedOrg]);

  const llmExportParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (startDate) params.start = toIsoStart(startDate) as string;
    if (endDate) params.end = toIsoEnd(endDate) as string;
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    return params;
  }, [startDate, endDate, selectedOrg]);

  const handleExport = useCallback(async (
    key: ExportKey,
    endpoint: string,
    params: Record<string, string>,
    fallbackFilename: string
  ) => {
    setExporting((prev) => ({ ...prev, [key]: true }));
    try {
      await downloadCsv(endpoint, params, fallbackFilename);
      success('Export ready', 'CSV download started.');
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to export CSV';
      showError('Export failed', message);
    } finally {
      setExporting((prev) => ({ ...prev, [key]: false }));
    }
  }, [success, showError]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setErrors({});

      const topSpenderParams: Record<string, string> = { limit: '10' };
      if (llmParams.start) topSpenderParams.start = llmParams.start;
      if (llmParams.end) topSpenderParams.end = llmParams.end;
      if (selectedOrg) topSpenderParams.org_id = String(selectedOrg.id);

      const [dailyResult, topResult, summaryResult, topSpendersResult] = await Promise.allSettled([
        api.getUsageDaily({ ...usageParams, limit: '50' }),
        api.getUsageTop({ ...usageParams, metric: topMetric, limit: '10' }),
        api.getLlmUsageSummary(llmParams),
        api.getLlmTopSpenders(topSpenderParams),
      ]);

      const nextErrors: Record<string, string> = {};

      if (dailyResult.status === 'fulfilled' && isRecord(dailyResult.value)) {
        const items = dailyResult.value.items;
        setUsageDaily(Array.isArray(items) ? (items as UsageDailyRow[]) : []);
      } else {
        setUsageDaily([]);
        const reason = dailyResult.status === 'rejected' ? dailyResult.reason : null;
        nextErrors.daily = getErrorMessage(reason, 'Failed to load daily usage');
      }

      if (topResult.status === 'fulfilled' && isRecord(topResult.value)) {
        const items = topResult.value.items;
        setUsageTop(Array.isArray(items) ? (items as UsageTopRow[]) : []);
      } else {
        setUsageTop([]);
        const reason = topResult.status === 'rejected' ? topResult.reason : null;
        nextErrors.top = getErrorMessage(reason, 'Failed to load top users');
      }

      if (summaryResult.status === 'fulfilled' && isRecord(summaryResult.value)) {
        const items = summaryResult.value.items;
        setLlmSummary(Array.isArray(items) ? (items as LlmSummaryRow[]) : []);
      } else {
        setLlmSummary([]);
        const reason = summaryResult.status === 'rejected' ? summaryResult.reason : null;
        nextErrors.summary = getErrorMessage(reason, 'Failed to load LLM usage summary');
      }

      if (topSpendersResult.status === 'fulfilled' && isRecord(topSpendersResult.value)) {
        const items = topSpendersResult.value.items;
        setLlmTop(Array.isArray(items) ? (items as LlmTopSpenderRow[]) : []);
      } else {
        setLlmTop([]);
        const reason = topSpendersResult.status === 'rejected' ? topSpendersResult.reason : null;
        nextErrors.topSpenders = getErrorMessage(reason, 'Failed to load top spenders');
      }

      setErrors(nextErrors);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load usage data';
      setError(message);
      setUsageDaily([]);
      setUsageTop([]);
      setLlmSummary([]);
      setLlmTop([]);
      setErrors({
        daily: 'Failed to load daily usage',
        top: 'Failed to load top users',
        summary: 'Failed to load LLM usage summary',
        topSpenders: 'Failed to load top spenders',
      });
    } finally {
      setLoading(false);
    }
  }, [usageParams, topMetric, llmParams, selectedOrg]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold">Usage Analytics</h1>
              <p className="text-muted-foreground">Track API consumption and LLM costs.</p>
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

          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Calendar className="h-5 w-5" />
                Date range
              </CardTitle>
              <CardDescription>Filter usage across API and LLM metrics.</CardDescription>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
                <div className="space-y-2">
                  <Label htmlFor="usage-start">Start date</Label>
                  <Input
                    id="usage-start"
                    type="date"
                    value={startDate}
                    onChange={(event) => setStartDate(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="usage-end">End date</Label>
                  <Input
                    id="usage-end"
                    type="date"
                    value={endDate}
                    onChange={(event) => setEndDate(event.target.value)}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="usage-metric">Top metric</Label>
                  <Select
                    id="usage-metric"
                    value={topMetric}
                    onChange={(event) => setTopMetric(event.target.value)}
                  >
                    <option value="requests">Requests</option>
                    <option value="bytes_total">Bytes out</option>
                    <option value="bytes_in_total">Bytes in</option>
                    <option value="errors">Errors</option>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="usage-group">LLM group by</Label>
                  <Select
                    id="usage-group"
                    value={groupBy}
                    onChange={(event) => setGroupBy(event.target.value)}
                  >
                    <option value="user">User</option>
                    <option value="provider">Provider</option>
                    <option value="model">Model</option>
                    <option value="operation">Operation</option>
                    <option value="day">Day</option>
                  </Select>
                </div>
              </div>
              <div className="mt-4">
                <Button onClick={loadData} disabled={loading}>
                  Apply filters
                </Button>
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="api" className="space-y-6">
            <TabsList>
              <TabsTrigger value="api">API Usage</TabsTrigger>
              <TabsTrigger value="llm">LLM Usage</TabsTrigger>
            </TabsList>

            <TabsContent value="api" className="space-y-6">
              <Card>
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <CardTitle className="flex items-center gap-2">
                      <BarChart3 className="h-5 w-5" />
                      Daily usage
                    </CardTitle>
                    <CardDescription>Requests, errors, and bandwidth by day.</CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport(
                      'daily',
                      '/admin/usage/daily/export.csv',
                      { ...usageParams, limit: '1000' },
                      `usage_daily_${dateSuffix}.csv`
                    )}
                    disabled={loading || exporting.daily}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading usage…</div>
                  ) : errors.daily ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.daily}</AlertDescription>
                    </Alert>
                  ) : usageDaily.length === 0 ? (
                    <div className="text-muted-foreground">No usage data for this range.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Day</TableHead>
                          <TableHead>User</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Errors</TableHead>
                          <TableHead className="text-right">Bytes out</TableHead>
                          <TableHead className="text-right">Bytes in</TableHead>
                          <TableHead className="text-right">Avg latency</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {usageDaily.map((row) => (
                          <TableRow key={`${row.user_id}-${row.day}`}>
                            <TableCell>{row.day}</TableCell>
                            <TableCell>{row.user_id}</TableCell>
                            <TableCell className="text-right">{row.requests}</TableCell>
                            <TableCell className="text-right">{row.errors}</TableCell>
                            <TableCell className="text-right">{formatBytes(row.bytes_total)}</TableCell>
                            <TableCell className="text-right">{formatBytes(row.bytes_in_total ?? undefined)}</TableCell>
                            <TableCell className="text-right">{formatLatency(row.latency_avg_ms)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <CardTitle>Top users</CardTitle>
                    <CardDescription>Top consumers for the selected metric.</CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport(
                      'top',
                      '/admin/usage/top/export.csv',
                      { ...usageParams, metric: topMetric, limit: '100' },
                      `usage_top_${topMetric}_${dateSuffix}.csv`
                    )}
                    disabled={loading || exporting.top}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading top users…</div>
                  ) : errors.top ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.top}</AlertDescription>
                    </Alert>
                  ) : usageTop.length === 0 ? (
                    <div className="text-muted-foreground">No top-user data for this range.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>User</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Errors</TableHead>
                          <TableHead className="text-right">Bytes out</TableHead>
                          <TableHead className="text-right">Bytes in</TableHead>
                          <TableHead className="text-right">Avg latency</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {usageTop.map((row) => (
                          <TableRow key={row.user_id}>
                            <TableCell>{row.user_id}</TableCell>
                            <TableCell className="text-right">{row.requests}</TableCell>
                            <TableCell className="text-right">{row.errors}</TableCell>
                            <TableCell className="text-right">{formatBytes(row.bytes_total)}</TableCell>
                            <TableCell className="text-right">{formatBytes(row.bytes_in_total ?? undefined)}</TableCell>
                            <TableCell className="text-right">{formatLatency(row.latency_avg_ms)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="llm" className="space-y-6">
              <Card>
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <CardTitle>LLM usage summary</CardTitle>
                    <CardDescription>Grouped usage for the selected dimension.</CardDescription>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => handleExport(
                      'llm',
                      '/admin/llm-usage/export.csv',
                      { ...llmExportParams, limit: '1000' },
                      `llm_usage_${dateSuffix}.csv`
                    )}
                    disabled={loading || exporting.llm}
                  >
                    <Download className="mr-2 h-4 w-4" />
                    Export CSV
                  </Button>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading LLM summary…</div>
                  ) : errors.summary ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.summary}</AlertDescription>
                    </Alert>
                  ) : llmSummary.length === 0 ? (
                    <div className="text-muted-foreground">No LLM usage data for this range.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Group</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Errors</TableHead>
                          <TableHead className="text-right">Input tokens</TableHead>
                          <TableHead className="text-right">Output tokens</TableHead>
                          <TableHead className="text-right">Total tokens</TableHead>
                          <TableHead className="text-right">Cost (USD)</TableHead>
                          <TableHead className="text-right">Avg latency</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {llmSummary.map((row) => (
                          <TableRow key={row.group_value}>
                            <TableCell>{row.group_value}</TableCell>
                            <TableCell className="text-right">{row.requests}</TableCell>
                            <TableCell className="text-right">{row.errors}</TableCell>
                            <TableCell className="text-right">{row.input_tokens}</TableCell>
                            <TableCell className="text-right">{row.output_tokens}</TableCell>
                            <TableCell className="text-right">{row.total_tokens}</TableCell>
                            <TableCell className="text-right">${row.total_cost_usd.toFixed(4)}</TableCell>
                            <TableCell className="text-right">{formatLatency(row.latency_avg_ms)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Top spenders</CardTitle>
                  <CardDescription>Users with the highest LLM costs.</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading top spenders…</div>
                  ) : errors.topSpenders ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.topSpenders}</AlertDescription>
                    </Alert>
                  ) : llmTop.length === 0 ? (
                    <div className="text-muted-foreground">No spend data for this range.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>User</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Total cost (USD)</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {llmTop.map((row) => (
                          <TableRow key={row.user_id}>
                            <TableCell>{row.user_id}</TableCell>
                            <TableCell className="text-right">{row.requests}</TableCell>
                            <TableCell className="text-right">
                              <Badge variant="outline">${row.total_cost_usd.toFixed(4)}</Badge>
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>
        </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
