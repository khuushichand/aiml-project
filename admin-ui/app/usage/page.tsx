'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { RefreshCw } from 'lucide-react';

import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { formatLatency } from '@/lib/format';
import {
  getRouterAnalyticsMeta,
  getRouterAnalyticsQuota,
  getRouterAnalyticsStatus,
  getRouterAnalyticsStatusBreakdowns,
} from '@/lib/router-analytics-client';
import type {
  RouterAnalyticsBreakdownRow,
  RouterAnalyticsBreakdownsResponse,
  RouterAnalyticsMetaResponse,
  RouterAnalyticsQuotaMetric,
  RouterAnalyticsQuotaResponse,
  RouterAnalyticsRange,
  RouterAnalyticsStatusResponse,
} from '@/lib/router-analytics-types';

type UsageTab = 'status' | 'quota' | 'providers' | 'access' | 'network' | 'models' | 'conversations' | 'log';

type UsageTabConfig = {
  value: UsageTab;
  label: string;
  implemented: boolean;
};

const TABS: UsageTabConfig[] = [
  { value: 'status', label: 'Status', implemented: true },
  { value: 'quota', label: 'Quota', implemented: true },
  { value: 'providers', label: 'Providers', implemented: false },
  { value: 'access', label: 'Access', implemented: false },
  { value: 'network', label: 'Network', implemented: false },
  { value: 'models', label: 'Models', implemented: false },
  { value: 'conversations', label: 'Conversations', implemented: false },
  { value: 'log', label: 'Log', implemented: false },
];

const RANGE_OPTIONS: RouterAnalyticsRange[] = ['realtime', '1h', '8h', '24h', '7d', '30d'];

type TimelineBucket = {
  ts: string;
  requests: number;
  totalTokens: number;
  topModel: string;
};

const normalizeErrorMessage = (error: unknown): string => {
  if (error instanceof Error && error.message.trim()) return error.message;
  if (typeof error === 'string' && error.trim()) return error;
  return 'Failed to load router analytics usage data.';
};

const formatNumber = (value?: number | null): string => {
  if (value === undefined || value === null || Number.isNaN(value)) return '—';
  return Number(value).toLocaleString();
};

const formatTokensPerSecond = (value?: number | null): string => {
  if (value === undefined || value === null || Number.isNaN(value)) return '—';
  return value.toFixed(2);
};

const formatPercent = (value?: number | null): string => {
  if (value === undefined || value === null || Number.isNaN(value)) return '—';
  return `${value.toFixed(1)}%`;
};

const formatQuotaMetric = (metric?: RouterAnalyticsQuotaMetric | null): string => {
  if (!metric) return '—';
  return `${formatNumber(metric.used)} / ${formatNumber(metric.limit)} (${formatPercent(metric.utilization_pct)})`;
};

const formatBucketTime = (value: string): string => {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
};

function BreakdownCard({ title, rows, keyLabel }: { title: string; rows: RouterAnalyticsBreakdownRow[]; keyLabel: string }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-lg">{title}</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{keyLabel}</TableHead>
              <TableHead className="text-right">Requests</TableHead>
              <TableHead className="text-right">PP</TableHead>
              <TableHead className="text-right">TG</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.length === 0 ? (
              <TableRow>
                <TableCell colSpan={4} className="text-center text-muted-foreground">
                  No data
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => (
                <TableRow key={`${title}-${row.key}`}>
                  <TableCell className="font-medium">{row.label || row.key}</TableCell>
                  <TableCell className="text-right">{formatNumber(row.requests)}</TableCell>
                  <TableCell className="text-right">{formatNumber(row.prompt_tokens)}</TableCell>
                  <TableCell className="text-right">{formatNumber(row.total_tokens)}</TableCell>
                </TableRow>
              ))
            )}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

export default function UsagePage() {
  const [activeTab, setActiveTab] = useState<UsageTab>('status');
  const [range, setRange] = useState<RouterAnalyticsRange>('8h');
  const [provider, setProvider] = useState('');
  const [model, setModel] = useState('');
  const [tokenName, setTokenName] = useState('');

  const [statusPayload, setStatusPayload] = useState<RouterAnalyticsStatusResponse | null>(null);
  const [breakdownsPayload, setBreakdownsPayload] = useState<RouterAnalyticsBreakdownsResponse | null>(null);
  const [quotaPayload, setQuotaPayload] = useState<RouterAnalyticsQuotaResponse | null>(null);
  const [metaPayload, setMetaPayload] = useState<RouterAnalyticsMetaResponse | null>(null);

  const [statusLoading, setStatusLoading] = useState<boolean>(true);
  const [statusError, setStatusError] = useState<string>('');
  const [quotaLoading, setQuotaLoading] = useState<boolean>(false);
  const [quotaError, setQuotaError] = useState<string>('');
  const [refreshTick, setRefreshTick] = useState<number>(0);

  const selectedTokenValue = tokenName && tokenName !== '__all__' ? tokenName : '';

  const selectedTokenId = useMemo<number | undefined>(() => {
    if (!metaPayload || !selectedTokenValue) return undefined;
    const index = metaPayload.tokens.findIndex((entry) => entry.value === selectedTokenValue);
    if (index < 0) return undefined;
    return index + 1;
  }, [metaPayload, selectedTokenValue]);

  const statusQuery = useMemo(
    () => ({
      range,
      provider: provider || undefined,
      model: model || undefined,
      tokenId: selectedTokenId,
    }),
    [range, provider, model, selectedTokenId]
  );

  const loadStatusData = useCallback(async () => {
    setStatusLoading(true);
    setStatusError('');
    try {
      const [statusResponse, breakdownsResponse, metaResponse] = await Promise.all([
        getRouterAnalyticsStatus(statusQuery),
        getRouterAnalyticsStatusBreakdowns(statusQuery),
        getRouterAnalyticsMeta(),
      ]);
      setStatusPayload(statusResponse);
      setBreakdownsPayload(breakdownsResponse);
      setMetaPayload(metaResponse);
    } catch (loadError) {
      setStatusError(normalizeErrorMessage(loadError));
    } finally {
      setStatusLoading(false);
    }
  }, [statusQuery]);

  const loadQuotaData = useCallback(async () => {
    setQuotaLoading(true);
    setQuotaError('');
    try {
      const [quotaResponse, metaResponse] = await Promise.all([
        getRouterAnalyticsQuota(statusQuery),
        getRouterAnalyticsMeta(),
      ]);
      setQuotaPayload(quotaResponse);
      setMetaPayload(metaResponse);
    } catch (loadError) {
      setQuotaError(normalizeErrorMessage(loadError));
    } finally {
      setQuotaLoading(false);
    }
  }, [statusQuery]);

  useEffect(() => {
    if (activeTab === 'status') {
      void loadStatusData();
      return;
    }
    if (activeTab === 'quota') {
      void loadQuotaData();
    }
  }, [activeTab, loadStatusData, loadQuotaData, refreshTick]);

  const timelineBuckets = useMemo<TimelineBucket[]>(() => {
    if (!statusPayload?.series?.length) return [];

    const map = new Map<string, { requests: number; totalTokens: number; models: Map<string, number> }>();

    statusPayload.series.forEach((point) => {
      const ts = point.ts;
      const modelKey = point.model && point.model.trim().length > 0 ? point.model : 'unknown';
      const existing = map.get(ts) ?? { requests: 0, totalTokens: 0, models: new Map<string, number>() };
      existing.requests += Number(point.requests || 0);
      existing.totalTokens += Number(point.total_tokens || 0);
      existing.models.set(modelKey, (existing.models.get(modelKey) || 0) + Number(point.total_tokens || 0));
      map.set(ts, existing);
    });

    return [...map.entries()]
      .sort((a, b) => new Date(a[0]).getTime() - new Date(b[0]).getTime())
      .map(([ts, value]) => {
        let topModel = 'unknown';
        let topValue = -1;
        value.models.forEach((tokenCount, modelName) => {
          if (tokenCount > topValue) {
            topModel = modelName;
            topValue = tokenCount;
          }
        });

        return {
          ts,
          requests: value.requests,
          totalTokens: value.totalTokens,
          topModel,
        };
      });
  }, [statusPayload]);

  const maxTimelineTokens = useMemo(() => {
    if (!timelineBuckets.length) return 0;
    return Math.max(...timelineBuckets.map((bucket) => bucket.totalTokens));
  }, [timelineBuckets]);

  const currentTabLabel = useMemo(() => {
    return TABS.find((tab) => tab.value === activeTab)?.label || 'Tab';
  }, [activeTab]);

  return (
    <PermissionGuard requiredRole="admin" fallbackToDashboard>
      <ResponsiveLayout title="Usage" subtitle="Router analytics status dashboard">
        <div className="space-y-6" data-testid="usage-router-analytics-page">
          <div className="rounded-lg border bg-card p-4">
            <div className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
              <div>
                <h1 className="text-2xl font-semibold">Usage Stats</h1>
                <p className="text-sm text-muted-foreground">
                  Router analytics overview for status operations.
                </p>
              </div>

              <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-5">
                <div className="space-y-1">
                  <Label htmlFor="usage-time-range">Time Range</Label>
                  <Select
                    id="usage-time-range"
                    aria-label="Time Range"
                    value={range}
                    onChange={(event) => setRange(event.target.value as RouterAnalyticsRange)}
                  >
                    {RANGE_OPTIONS.map((option) => (
                      <option key={option} value={option}>
                        {option}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="usage-provider-filter">Provider</Label>
                  <Select
                    id="usage-provider-filter"
                    aria-label="Provider"
                    value={provider || '__all__'}
                    onChange={(event) => setProvider(event.target.value === '__all__' ? '' : event.target.value)}
                  >
                    <option value="__all__">All providers</option>
                    {(metaPayload?.providers || []).map((entry) => (
                      <option key={entry.value} value={entry.value}>
                        {entry.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="usage-model-filter">Model</Label>
                  <Select
                    id="usage-model-filter"
                    aria-label="Model"
                    value={model || '__all__'}
                    onChange={(event) => setModel(event.target.value === '__all__' ? '' : event.target.value)}
                  >
                    <option value="__all__">All models</option>
                    {(metaPayload?.models || []).map((entry) => (
                      <option key={entry.value} value={entry.value}>
                        {entry.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="usage-token-filter">Token</Label>
                  <Select
                    id="usage-token-filter"
                    aria-label="Token"
                    value={tokenName || '__all__'}
                    onChange={(event) => setTokenName(event.target.value === '__all__' ? '' : event.target.value)}
                  >
                    <option value="__all__">All tokens</option>
                    {(metaPayload?.tokens || []).map((entry) => (
                      <option key={entry.value} value={entry.value}>
                        {entry.label}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex items-end">
                  <Button
                    type="button"
                    variant="outline"
                    className="w-full"
                    onClick={() => setRefreshTick((value) => value + 1)}
                  >
                    <RefreshCw className="mr-2 h-4 w-4" />
                    Refresh
                  </Button>
                </div>
              </div>
            </div>
          </div>

          <Tabs value={activeTab} onValueChange={(value) => setActiveTab(value as UsageTab)}>
            <TabsList className="h-auto w-full justify-start overflow-x-auto rounded-md border bg-muted/40 p-1">
              {TABS.map((tab) => (
                <TabsTrigger key={tab.value} value={tab.value} className="relative min-w-fit px-3 py-2">
                  {tab.label}
                  {!tab.implemented && (
                    <Badge variant="secondary" className="ml-2 text-[10px]">
                      Soon
                    </Badge>
                  )}
                </TabsTrigger>
              ))}
            </TabsList>

            <TabsContent value="status" className="space-y-4">
              {statusError && (
                <Alert variant="destructive">
                  <AlertDescription>{statusError}</AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Requests</CardDescription>
                    <CardTitle>{formatNumber(statusPayload?.kpis.requests)}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Prompt / Generated</CardDescription>
                    <CardTitle>
                      {formatNumber(statusPayload?.kpis.prompt_tokens)} / {formatNumber(statusPayload?.kpis.generated_tokens)}
                    </CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Avg latency ms</CardDescription>
                    <CardTitle>{formatLatency(statusPayload?.kpis.avg_latency_ms, { fallback: '—', precision: 1 })}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Avg gen tok/s</CardDescription>
                    <CardTitle>{formatTokensPerSecond(statusPayload?.kpis.avg_gen_toks_per_s)}</CardTitle>
                  </CardHeader>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Usage by model (tokens / bucket)</CardTitle>
                  <CardDescription>
                    Providers available: {statusPayload?.providers_available ?? 0} • Online: {statusPayload?.providers_online ?? 0}
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {statusLoading ? (
                    <p className="text-sm text-muted-foreground">Loading status timeline...</p>
                  ) : timelineBuckets.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No usage data in this window.</p>
                  ) : (
                    <div className="space-y-3">
                      {timelineBuckets.map((bucket) => {
                        const widthPercent = maxTimelineTokens > 0
                          ? Math.max(6, Math.round((bucket.totalTokens / maxTimelineTokens) * 100))
                          : 0;
                        return (
                          <div key={bucket.ts} className="space-y-1">
                            <div className="flex items-center justify-between text-xs text-muted-foreground">
                              <span>{formatBucketTime(bucket.ts)}</span>
                              <span>{bucket.topModel}</span>
                            </div>
                            <div className="h-2 rounded bg-muted">
                              <div className="h-2 rounded bg-blue-500" style={{ width: `${widthPercent}%` }} />
                            </div>
                            <div className="text-xs text-muted-foreground">
                              {formatNumber(bucket.totalTokens)} tokens • {formatNumber(bucket.requests)} requests
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </CardContent>
              </Card>

              <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                <BreakdownCard title="Providers" rows={breakdownsPayload?.providers || []} keyLabel="Provider" />
                <BreakdownCard title="Models" rows={breakdownsPayload?.models || []} keyLabel="Model" />
                <BreakdownCard title="Token Names" rows={breakdownsPayload?.token_names || []} keyLabel="Token Name" />
                <BreakdownCard title="Remote IPs" rows={breakdownsPayload?.remote_ips || []} keyLabel="Remote IP" />
                <BreakdownCard title="User Agents" rows={breakdownsPayload?.user_agents || []} keyLabel="User-Agent" />
              </div>
            </TabsContent>

            <TabsContent value="quota" className="space-y-4">
              {quotaError && (
                <Alert variant="destructive">
                  <AlertDescription>{quotaError}</AlertDescription>
                </Alert>
              )}

              <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Keys tracked</CardDescription>
                    <CardTitle>{formatNumber(quotaPayload?.summary.keys_total)}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Keys over budget</CardDescription>
                    <CardTitle>{formatNumber(quotaPayload?.summary.keys_over_budget)}</CardTitle>
                  </CardHeader>
                </Card>
                <Card>
                  <CardHeader className="pb-2">
                    <CardDescription>Budgeted keys</CardDescription>
                    <CardTitle>{formatNumber(quotaPayload?.summary.budgeted_keys)}</CardTitle>
                  </CardHeader>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle>Quota utilization</CardTitle>
                  <CardDescription>Day and 30-day budget usage for active keys in the selected filter window.</CardDescription>
                </CardHeader>
                <CardContent>
                  {quotaLoading ? (
                    <p className="text-sm text-muted-foreground">Loading quota data...</p>
                  ) : (quotaPayload?.items.length || 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">No quota-linked key usage in this window.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Token</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Tokens</TableHead>
                          <TableHead className="text-right">Cost USD</TableHead>
                          <TableHead className="text-right">Day Tokens</TableHead>
                          <TableHead className="text-right">30d Tokens</TableHead>
                          <TableHead className="text-right">Day USD</TableHead>
                          <TableHead className="text-right">30d USD</TableHead>
                          <TableHead className="text-right">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {(quotaPayload?.items || []).map((row) => (
                          <TableRow key={`quota-${row.key_id}`}>
                            <TableCell className="font-medium">{row.token_name}</TableCell>
                            <TableCell className="text-right">{formatNumber(row.requests)}</TableCell>
                            <TableCell className="text-right">{formatNumber(row.total_tokens)}</TableCell>
                            <TableCell className="text-right">{formatNumber(row.total_cost_usd)}</TableCell>
                            <TableCell className="text-right">{formatQuotaMetric(row.day_tokens)}</TableCell>
                            <TableCell className="text-right">{formatQuotaMetric(row.month_tokens)}</TableCell>
                            <TableCell className="text-right">{formatQuotaMetric(row.day_usd)}</TableCell>
                            <TableCell className="text-right">{formatQuotaMetric(row.month_usd)}</TableCell>
                            <TableCell className="text-right">
                              {row.over_budget ? (
                                <Badge variant="destructive">Exceeded</Badge>
                              ) : (
                                <Badge variant="secondary">OK</Badge>
                              )}
                            </TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            {TABS.filter((tab) => !tab.implemented).map((tab) => (
              <TabsContent key={tab.value} value={tab.value}>
                <Card>
                  <CardHeader>
                    <CardTitle>{tab.label}</CardTitle>
                    <CardDescription>{tab.label} tab is coming soon.</CardDescription>
                  </CardHeader>
                  <CardContent>
                    <p className="text-sm text-muted-foreground">
                      {currentTabLabel} will be delivered as part of the router analytics staged rollout.
                    </p>
                  </CardContent>
                </Card>
              </TabsContent>
            ))}
          </Tabs>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
