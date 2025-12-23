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
import { RefreshCw, BarChart3, Calendar } from 'lucide-react';
import { api } from '@/lib/api-client';
import { useOrgContext } from '@/components/OrgContextSwitcher';

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

export default function UsagePage() {
  const { selectedOrg } = useOrgContext();
  const [usageDaily, setUsageDaily] = useState<UsageDailyRow[]>([]);
  const [usageTop, setUsageTop] = useState<UsageTopRow[]>([]);
  const [llmSummary, setLlmSummary] = useState<LlmSummaryRow[]>([]);
  const [llmTop, setLlmTop] = useState<LlmTopSpenderRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const [startDate, setStartDate] = useState(defaultStart());
  const [endDate, setEndDate] = useState(defaultEnd());
  const [topMetric, setTopMetric] = useState('requests');
  const [groupBy, setGroupBy] = useState('provider');

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

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');

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

      if (dailyResult.status === 'fulfilled') {
        const items = (dailyResult.value as { items?: UsageDailyRow[] } | null)?.items;
        setUsageDaily(Array.isArray(items) ? items : []);
      } else {
        setUsageDaily([]);
      }

      if (topResult.status === 'fulfilled') {
        const items = (topResult.value as { items?: UsageTopRow[] } | null)?.items;
        setUsageTop(Array.isArray(items) ? items : []);
      } else {
        setUsageTop([]);
      }

      if (summaryResult.status === 'fulfilled') {
        const items = (summaryResult.value as { items?: LlmSummaryRow[] } | null)?.items;
        setLlmSummary(Array.isArray(items) ? items : []);
      } else {
        setLlmSummary([]);
      }

      if (topSpendersResult.status === 'fulfilled') {
        const items = (topSpendersResult.value as { items?: LlmTopSpenderRow[] } | null)?.items;
        setLlmTop(Array.isArray(items) ? items : []);
      } else {
        setLlmTop([]);
      }
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load usage data';
      setError(message);
      setUsageDaily([]);
      setUsageTop([]);
      setLlmSummary([]);
      setLlmTop([]);
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
                <CardHeader>
                  <CardTitle className="flex items-center gap-2">
                    <BarChart3 className="h-5 w-5" />
                    Daily usage
                  </CardTitle>
                  <CardDescription>Requests, errors, and bandwidth by day.</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading usage…</div>
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
                <CardHeader>
                  <CardTitle>Top users</CardTitle>
                  <CardDescription>Top consumers for the selected metric.</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading top users…</div>
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
                <CardHeader>
                  <CardTitle>LLM usage summary</CardTitle>
                  <CardDescription>Grouped usage for the selected dimension.</CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading LLM summary…</div>
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
