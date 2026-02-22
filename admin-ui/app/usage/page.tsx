'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
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
import { buildApiUrl } from '@/lib/api-config';
import { buildAuthHeaders } from '@/lib/http';
import { formatBytes, formatDateTime, formatLatency } from '@/lib/format';
import { buildUsageCostForecast, normalizeDailyCostPoints, type DailyCostPoint, type UsageCostForecast } from '@/lib/usage-forecast';
import {
  parseEndpointUsageMetrics,
  parseMediaTypeStorageBreakdown,
  parseUserStorageMetrics,
  type EndpointUsageMetricsRow,
  type MediaTypeStorageBreakdownRow,
} from '@/lib/usage-insights';
import { normalizeRateLimitEventsPayload, parseRateLimitEventsFromMetricsText, type RateLimitEvent } from '@/lib/rate-limit-events';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useToast } from '@/components/ui/toast';
import Link from 'next/link';

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
type LlmGroupBy = 'user' | 'provider' | 'model' | 'operation' | 'day' | 'organization';
const VALID_LLM_GROUP_BY = new Set<LlmGroupBy>(['user', 'provider', 'model', 'operation', 'day', 'organization']);
type EndpointSortKey = 'endpoint' | 'method' | 'requests' | 'avgLatency' | 'errorRate' | 'p95';
type SortDirection = 'asc' | 'desc';
type RateLimitEventsSource = 'endpoint' | 'metrics_text' | 'unavailable';

type OrgCostAttributionRow = {
  orgId: number | null;
  orgName: string;
  requests: number;
  inputTokens: number;
  outputTokens: number;
  totalTokens: number;
  totalCostUsd: number;
  percentOfTotal: number;
  latencyAvgMs: number | null;
};

type StorageUserRow = {
  userId: number;
  username: string;
  email: string;
  storageUsedMb: number;
  storageQuotaMb: number | null;
};

const toDateInput = (date: Date) => date.toISOString().slice(0, 10);

const defaultEnd = () => toDateInput(new Date());
const defaultStart = () => {
  const date = new Date();
  date.setDate(date.getDate() - 7);
  return toDateInput(date);
};

const formatBytesDisplay = (value?: number | null) =>
  formatBytes(value, { fallback: '—' });

const formatLatencyDisplay = (value?: number | null) =>
  formatLatency(value, { fallback: '—' });

const formatPercentDisplay = (value?: number | null) => (
  value === null || value === undefined || !Number.isFinite(value)
    ? '—'
    : `${value.toFixed(2)}%`
);

const formatStorageMbDisplay = (value?: number | null) => (
  value === null || value === undefined || !Number.isFinite(value)
    ? '—'
    : `${value.toFixed(2)} MB`
);

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

const ORG_ATTRIBUTION_USER_LIMIT = 100;
const STORAGE_USERS_PAGE_LIMIT = 200;
const TOP_THROTTLED_LIMIT = 3;

const normalizeOrganizations = (value: unknown): Array<{ id: number; name: string }> => {
  if (Array.isArray(value)) {
    return value
      .filter((entry): entry is { id: number; name: string } =>
        isRecord(entry) && typeof entry.id === 'number' && typeof entry.name === 'string')
      .map((entry) => ({ id: entry.id, name: entry.name }));
  }
  if (!isRecord(value)) return [];
  const items = Array.isArray(value.items)
    ? value.items
    : (Array.isArray(value.orgs) ? value.orgs : []);
  return items
    .filter((entry): entry is { id: number; name: string } =>
      isRecord(entry) && typeof entry.id === 'number' && typeof entry.name === 'string')
    .map((entry) => ({ id: entry.id, name: entry.name }));
};

const normalizeOrgMembershipIds = (value: unknown): number[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry) => (isRecord(entry) && typeof entry.org_id === 'number' ? entry.org_id : null))
    .filter((orgId): orgId is number => typeof orgId === 'number');
};

const normalizeStorageUsers = (value: unknown): StorageUserRow[] => {
  if (!isRecord(value) || !Array.isArray(value.items)) return [];

  return value.items
    .map((entry) => {
      if (!isRecord(entry)) return null;
      const userId = Number(entry.id);
      if (!Number.isFinite(userId)) return null;
      const used = Number(entry.storage_used_mb);
      const quota = Number(entry.storage_quota_mb);
      const username = typeof entry.username === 'string' ? entry.username : `User ${userId}`;
      const email = typeof entry.email === 'string' ? entry.email : '';
      return {
        userId,
        username,
        email,
        storageUsedMb: Number.isFinite(used) ? Math.max(0, used) : 0,
        storageQuotaMb: Number.isFinite(quota) ? Math.max(0, quota) : null,
      };
    })
    .filter((row): row is StorageUserRow => row !== null);
};

const extractMonthlyBudgetUsd = (value: unknown, selectedOrgId?: number): number | null => {
  const items = Array.isArray(value)
    ? value
    : (isRecord(value) && Array.isArray(value.items) ? value.items : []);
  if (!Array.isArray(items)) return null;

  if (selectedOrgId) {
    const row = items.find((entry) => isRecord(entry) && Number(entry.org_id) === selectedOrgId);
    const budgetValue = isRecord(row) && isRecord(row.budgets)
      ? Number(row.budgets.budget_month_usd)
      : Number.NaN;
    return Number.isFinite(budgetValue) && budgetValue > 0 ? budgetValue : null;
  }

  const total = items.reduce((sum, entry) => {
    if (!isRecord(entry) || !isRecord(entry.budgets)) return sum;
    const candidate = Number(entry.budgets.budget_month_usd);
    return Number.isFinite(candidate) && candidate > 0 ? sum + candidate : sum;
  }, 0);
  return total > 0 ? total : null;
};

const buildOrgAttributionRows = async (rows: LlmSummaryRow[]): Promise<OrgCostAttributionRow[]> => {
  const userRows = rows
    .filter((row) => /^\d+$/.test(String(row.group_value)))
    .slice(0, ORG_ATTRIBUTION_USER_LIMIT);
  if (userRows.length === 0) return [];

  const organizationsResponse = await api.getOrganizations({ limit: '500' });
  const organizations = normalizeOrganizations(organizationsResponse);
  const orgNameById = new Map(organizations.map((org) => [org.id, org.name]));

  const membershipResults = await Promise.allSettled(
    userRows.map(async (row) => {
      const userId = Number(row.group_value);
      const memberships = await api.getUserOrgMemberships(String(userId));
      return {
        row,
        orgIds: normalizeOrgMembershipIds(memberships),
      };
    })
  );

  const aggregates = new Map<string, OrgCostAttributionRow>();
  let totalCost = 0;

  membershipResults.forEach((result) => {
    if (result.status !== 'fulfilled') return;
    const { row, orgIds } = result.value;
    const primaryOrgId = orgIds.length > 0 ? orgIds[0] : null;
    const orgName = primaryOrgId !== null
      ? (orgNameById.get(primaryOrgId) ?? `Org ${primaryOrgId}`)
      : 'Unassigned';
    const key = primaryOrgId !== null ? String(primaryOrgId) : 'unassigned';
    const existing = aggregates.get(key) ?? {
      orgId: primaryOrgId,
      orgName,
      requests: 0,
      inputTokens: 0,
      outputTokens: 0,
      totalTokens: 0,
      totalCostUsd: 0,
      percentOfTotal: 0,
      latencyAvgMs: 0,
    };

    const nextRequests = existing.requests + row.requests;
    const weightedLatency = (
      (existing.latencyAvgMs ?? 0) * existing.requests
      + (Number(row.latency_avg_ms ?? 0) * row.requests)
    ) / Math.max(1, nextRequests);

    existing.requests = nextRequests;
    existing.inputTokens += row.input_tokens;
    existing.outputTokens += row.output_tokens;
    existing.totalTokens += row.total_tokens;
    existing.totalCostUsd += row.total_cost_usd;
    existing.latencyAvgMs = Number.isFinite(weightedLatency) ? weightedLatency : null;
    aggregates.set(key, existing);
    totalCost += row.total_cost_usd;
  });

  return [...aggregates.values()]
    .map((row) => ({
      ...row,
      percentOfTotal: totalCost > 0 ? (row.totalCostUsd / totalCost) * 100 : 0,
    }))
    .sort((a, b) => b.totalCostUsd - a.totalCostUsd);
};

const downloadCsv = async (
  endpoint: string,
  params: Record<string, string>,
  fallbackFilename: string
) => {
  const query = new URLSearchParams(params).toString();
  const response = await fetch(buildApiUrl(`${endpoint}${query ? `?${query}` : ''}`), {
    headers: buildAuthHeaders('GET'),
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
  const [orgAttribution, setOrgAttribution] = useState<OrgCostAttributionRow[]>([]);
  const [dailyCostTrend, setDailyCostTrend] = useState<DailyCostPoint[]>([]);
  const [endpointUsage, setEndpointUsage] = useState<EndpointUsageMetricsRow[]>([]);
  const [endpointSortKey, setEndpointSortKey] = useState<EndpointSortKey>('requests');
  const [endpointSortDirection, setEndpointSortDirection] = useState<SortDirection>('desc');
  const [endpointMethodFilter, setEndpointMethodFilter] = useState('ALL');
  const [storageUsers, setStorageUsers] = useState<StorageUserRow[]>([]);
  const [mediaTypeBreakdown, setMediaTypeBreakdown] = useState<MediaTypeStorageBreakdownRow[]>([]);
  const [rateLimitEvents, setRateLimitEvents] = useState<RateLimitEvent[]>([]);
  const [rateLimitEventsSource, setRateLimitEventsSource] = useState<RateLimitEventsSource>('unavailable');
  const [forecast, setForecast] = useState<UsageCostForecast | null>(null);
  const [monthlyBudgetUsd, setMonthlyBudgetUsd] = useState<number | null>(null);
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
  const [groupBy, setGroupBy] = useState<LlmGroupBy>('provider');
  const [providerFilter, setProviderFilter] = useState('');
  const dateSuffix = `${startDate || 'all'}_${endDate || 'all'}`;
  const summaryGroupBy: Exclude<LlmGroupBy, 'organization'> = groupBy === 'organization' ? 'user' : groupBy;

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
    const params: Record<string, string> = { group_by: summaryGroupBy };
    const isoStart = toIsoStart(startDate);
    const isoEnd = toIsoEnd(endDate);
    if (isoStart) params.start = isoStart;
    if (isoEnd) params.end = isoEnd;
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    if (providerFilter) params.provider = providerFilter;
    return params;
  }, [startDate, endDate, summaryGroupBy, selectedOrg, providerFilter]);

  const dayTrendParams = useMemo(() => {
    const params: Record<string, string> = { group_by: 'day' };
    const isoStart = toIsoStart(startDate);
    const isoEnd = toIsoEnd(endDate);
    if (isoStart) params.start = isoStart;
    if (isoEnd) params.end = isoEnd;
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    if (providerFilter) params.provider = providerFilter;
    return params;
  }, [startDate, endDate, selectedOrg, providerFilter]);

  const orgAttributionParams = useMemo(() => {
    const params: Record<string, string> = { group_by: 'user' };
    const isoStart = toIsoStart(startDate);
    const isoEnd = toIsoEnd(endDate);
    if (isoStart) params.start = isoStart;
    if (isoEnd) params.end = isoEnd;
    if (selectedOrg) params.org_id = String(selectedOrg.id);
    return params;
  }, [startDate, endDate, selectedOrg]);

  const llmExportParams = useMemo(() => {
    const params: Record<string, string> = {};
    const isoStart = toIsoStart(startDate);
    const isoEnd = toIsoEnd(endDate);
    if (isoStart) params.start = isoStart;
    if (isoEnd) params.end = isoEnd;
    if (selectedOrg?.id) params.org_id = String(selectedOrg.id);
    return params;
  }, [startDate, endDate, selectedOrg]);

  const filteredLlmSummary = useMemo(() => {
    if (!providerFilter || summaryGroupBy !== 'provider') return llmSummary;
    return llmSummary.filter((row) => row.group_value?.toLowerCase() === providerFilter);
  }, [summaryGroupBy, llmSummary, providerFilter]);

  const organizationSummaryRows = useMemo<LlmSummaryRow[]>(() => {
    return orgAttribution.map((row) => ({
      group_value: row.orgName,
      requests: row.requests,
      errors: 0,
      input_tokens: row.inputTokens,
      output_tokens: row.outputTokens,
      total_tokens: row.totalTokens,
      total_cost_usd: row.totalCostUsd,
      latency_avg_ms: row.latencyAvgMs,
    }));
  }, [orgAttribution]);

  const summaryRows = groupBy === 'organization' ? organizationSummaryRows : filteredLlmSummary;
  const orgIdByName = useMemo(() => {
    return new Map(orgAttribution.map((row) => [row.orgName, row.orgId]));
  }, [orgAttribution]);
  const endpointMethodOptions = useMemo(() => {
    const methods = new Set<string>();
    endpointUsage.forEach((row) => methods.add(row.method));
    return ['ALL', ...[...methods].sort()];
  }, [endpointUsage]);

  const endpointRows = useMemo(() => {
    const directionFactor = endpointSortDirection === 'asc' ? 1 : -1;
    const filteredRows = endpointMethodFilter === 'ALL'
      ? endpointUsage
      : endpointUsage.filter((row) => row.method === endpointMethodFilter);

    return [...filteredRows].sort((a, b) => {
      switch (endpointSortKey) {
        case 'endpoint':
          return a.endpoint.localeCompare(b.endpoint) * directionFactor;
        case 'method':
          return a.method.localeCompare(b.method) * directionFactor;
        case 'avgLatency':
          return ((a.avgLatencyMs ?? -1) - (b.avgLatencyMs ?? -1)) * directionFactor;
        case 'errorRate':
          return ((a.errorRatePct ?? -1) - (b.errorRatePct ?? -1)) * directionFactor;
        case 'p95':
          return ((a.p95LatencyMs ?? -1) - (b.p95LatencyMs ?? -1)) * directionFactor;
        case 'requests':
        default:
          return (a.requestCount - b.requestCount) * directionFactor;
      }
    });
  }, [endpointMethodFilter, endpointSortDirection, endpointSortKey, endpointUsage]);

  const topStorageUsers = useMemo(() => {
    return [...storageUsers]
      .sort((a, b) => b.storageUsedMb - a.storageUsedMb)
      .slice(0, 10);
  }, [storageUsers]);

  const maxStorageUserMb = useMemo(() => {
    const maxValue = topStorageUsers.reduce((current, row) => Math.max(current, row.storageUsedMb), 0);
    return maxValue > 0 ? maxValue : 1;
  }, [topStorageUsers]);

  const maxMediaTypeBytes = useMemo(() => {
    const maxValue = mediaTypeBreakdown.reduce((current, row) => Math.max(current, row.bytesTotal), 0);
    return maxValue > 0 ? maxValue : 1;
  }, [mediaTypeBreakdown]);

  const topThrottledKeys = useMemo(() => {
    return new Set(
      rateLimitEvents
        .slice(0, TOP_THROTTLED_LIMIT)
        .map((event) => `${event.actor}|${event.policy}|${event.resourceType ?? ''}|${event.reason ?? ''}`)
    );
  }, [rateLimitEvents]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    const params = new URLSearchParams(window.location.search);
    const queryGroupBy = params.get('group_by');
    const nextGroupBy = queryGroupBy && VALID_LLM_GROUP_BY.has(queryGroupBy as LlmGroupBy)
      ? (queryGroupBy as LlmGroupBy)
      : 'provider';
    const nextProviderFilter = (params.get('provider') ?? '').trim().toLowerCase();
    setGroupBy(nextGroupBy);
    setProviderFilter(nextProviderFilter);
  }, []);

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

  const handleEndpointSort = useCallback((key: EndpointSortKey) => {
    if (endpointSortKey === key) {
      setEndpointSortDirection((prev) => (prev === 'asc' ? 'desc' : 'asc'));
      return;
    }
    setEndpointSortKey(key);
    setEndpointSortDirection('desc');
  }, [endpointSortKey]);

  const getEndpointSortIndicator = useCallback((key: EndpointSortKey) => {
    if (endpointSortKey !== key) return '↕';
    return endpointSortDirection === 'asc' ? '↑' : '↓';
  }, [endpointSortDirection, endpointSortKey]);

  const fetchStorageUsers = useCallback(async (): Promise<StorageUserRow[]> => {
    const rows: StorageUserRow[] = [];
    let page = 1;
    let totalPages = 1;

    while (page <= totalPages) {
      const payload = await api.getUsersPage({
        page: String(page),
        limit: String(STORAGE_USERS_PAGE_LIMIT),
      });
      rows.push(...normalizeStorageUsers(payload));

      if (isRecord(payload) && Number.isFinite(Number(payload.pages))) {
        totalPages = Math.max(1, Number(payload.pages));
      }

      if (rows.length === 0) break;
      if (page >= totalPages) break;
      page += 1;
    }

    return rows;
  }, []);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      setErrors({});

      const topSpenderParams: Record<string, string> = { limit: '10' };
      if (llmParams.start) topSpenderParams.start = llmParams.start;
      if (llmParams.end) topSpenderParams.end = llmParams.end;
      if (selectedOrg) topSpenderParams.org_id = String(selectedOrg.id);

      const [
        dailyResult,
        topResult,
        summaryResult,
        topSpendersResult,
        dayTrendResult,
        orgAttributionResult,
        budgetsResult,
        metricsTextResult,
        storageUsersResult,
        rateLimitEventsResult,
      ] = await Promise.allSettled([
        api.getUsageDaily({ ...usageParams, limit: '50' }),
        api.getUsageTop({ ...usageParams, metric: topMetric, limit: '10' }),
        api.getLlmUsageSummary(llmParams),
        api.getLlmTopSpenders(topSpenderParams),
        api.getLlmUsageSummary(dayTrendParams),
        api.getLlmUsageSummary(orgAttributionParams),
        api.getBudgets(selectedOrg ? { org_id: String(selectedOrg.id), limit: '200' } : { limit: '200' }),
        api.getMetricsText(),
        fetchStorageUsers(),
        api.getRateLimitEvents({ hours: '24' }),
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

      let budgetCapUsd: number | null = null;
      if (budgetsResult.status === 'fulfilled') {
        budgetCapUsd = extractMonthlyBudgetUsd(budgetsResult.value, selectedOrg?.id);
      }
      setMonthlyBudgetUsd(budgetCapUsd);

      if (dayTrendResult.status === 'fulfilled' && isRecord(dayTrendResult.value)) {
        const items = dayTrendResult.value.items;
        const rows = Array.isArray(items) ? (items as LlmSummaryRow[]) : [];
        const points = normalizeDailyCostPoints(rows);
        setDailyCostTrend(points);
        setForecast(buildUsageCostForecast(points, budgetCapUsd));
      } else {
        setDailyCostTrend([]);
        setForecast(null);
        const reason = dayTrendResult.status === 'rejected' ? dayTrendResult.reason : null;
        nextErrors.forecast = getErrorMessage(reason, 'Failed to load forecast data');
      }

      if (orgAttributionResult.status === 'fulfilled' && isRecord(orgAttributionResult.value)) {
        const items = orgAttributionResult.value.items;
        const rows = Array.isArray(items) ? (items as LlmSummaryRow[]) : [];
        try {
          const attributionRows = await buildOrgAttributionRows(rows);
          setOrgAttribution(attributionRows);
        } catch (orgError: unknown) {
          setOrgAttribution([]);
          nextErrors.orgAttribution = getErrorMessage(orgError, 'Failed to build organization attribution');
        }
      } else {
        setOrgAttribution([]);
        const reason = orgAttributionResult.status === 'rejected' ? orgAttributionResult.reason : null;
        nextErrors.orgAttribution = getErrorMessage(reason, 'Failed to load organization attribution');
      }

      const metricsText = metricsTextResult.status === 'fulfilled' && typeof metricsTextResult.value === 'string'
        ? metricsTextResult.value
        : '';
      if (metricsText) {
        setEndpointUsage(parseEndpointUsageMetrics(metricsText));
        setMediaTypeBreakdown(parseMediaTypeStorageBreakdown(metricsText));
      } else {
        setEndpointUsage([]);
        setMediaTypeBreakdown([]);
        const reason = metricsTextResult.status === 'rejected'
          ? metricsTextResult.reason
          : new Error('Metrics text response was not in the expected format');
        nextErrors.endpoints = getErrorMessage(reason, 'Failed to load endpoint metrics');
        nextErrors.storage = getErrorMessage(reason, 'Failed to load storage breakdown metrics');
      }

      if (storageUsersResult.status === 'fulfilled') {
        const users = storageUsersResult.value;
        if (users.length > 0) {
          setStorageUsers(users);
        } else if (metricsText) {
          const metricRows = parseUserStorageMetrics(metricsText);
          setStorageUsers(metricRows.map((row) => ({
            userId: Number(row.userId) || 0,
            username: `User ${row.userId}`,
            email: '',
            storageUsedMb: row.usedMb,
            storageQuotaMb: row.quotaMb,
          })));
        } else {
          setStorageUsers([]);
        }
      } else if (metricsText) {
        const metricRows = parseUserStorageMetrics(metricsText);
        setStorageUsers(metricRows.map((row) => ({
          userId: Number(row.userId) || 0,
          username: `User ${row.userId}`,
          email: '',
          storageUsedMb: row.usedMb,
          storageQuotaMb: row.quotaMb,
        })));
      } else {
        setStorageUsers([]);
        const reason = storageUsersResult.reason;
        nextErrors.storage = getErrorMessage(reason, 'Failed to load top storage users');
      }

      if (rateLimitEventsResult.status === 'fulfilled') {
        setRateLimitEvents(normalizeRateLimitEventsPayload(rateLimitEventsResult.value));
        setRateLimitEventsSource('endpoint');
      } else if (metricsText) {
        setRateLimitEvents(parseRateLimitEventsFromMetricsText(metricsText));
        setRateLimitEventsSource('metrics_text');
      } else {
        setRateLimitEvents([]);
        setRateLimitEventsSource('unavailable');
        const reason = rateLimitEventsResult.reason;
        nextErrors.rateLimits = getErrorMessage(reason, 'Failed to load rate limit events');
      }

      setErrors(nextErrors);
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to load usage data';
      setError(message);
      setUsageDaily([]);
      setUsageTop([]);
      setLlmSummary([]);
      setLlmTop([]);
      setOrgAttribution([]);
      setDailyCostTrend([]);
      setForecast(null);
      setMonthlyBudgetUsd(null);
      setEndpointUsage([]);
      setStorageUsers([]);
      setMediaTypeBreakdown([]);
      setRateLimitEvents([]);
      setRateLimitEventsSource('unavailable');
      setErrors({
        daily: 'Failed to load daily usage',
        top: 'Failed to load top users',
        summary: 'Failed to load LLM usage summary',
        topSpenders: 'Failed to load top spenders',
        forecast: 'Failed to load forecast data',
        orgAttribution: 'Failed to load organization attribution',
        endpoints: 'Failed to load endpoint metrics',
        storage: 'Failed to load storage breakdown',
        rateLimits: 'Failed to load rate limit events',
      });
    } finally {
      setLoading(false);
    }
  }, [dayTrendParams, fetchStorageUsers, llmParams, orgAttributionParams, selectedOrg, topMetric, usageParams]);

  useEffect(() => {
    void loadData();
  }, [loadData]);

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold">Usage Analytics</h1>
              <p className="text-muted-foreground">Track API consumption and LLM costs.</p>
            </div>
            <Button variant="outline" onClick={() => { void loadData(); }} loading={loading} loadingText="Refreshing...">
              <RefreshCw className="mr-2 h-4 w-4" />
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
                    onChange={(event) => setGroupBy(event.target.value as LlmGroupBy)}
                  >
                    <option value="user">User</option>
                    <option value="provider">Provider</option>
                    <option value="model">Model</option>
                    <option value="operation">Operation</option>
                    <option value="day">Day</option>
                    <option value="organization">Organization</option>
                  </Select>
                </div>
              </div>
              <div className="mt-4 flex flex-wrap items-center gap-2">
                <Button onClick={() => { void loadData(); }} loading={loading} loadingText="Applying...">
                  Apply filters
                </Button>
                {providerFilter ? (
                  <>
                    <Badge variant="secondary">Provider filter: {providerFilter}</Badge>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setProviderFilter('')}
                    >
                      Clear provider filter
                    </Button>
                  </>
                ) : null}
              </div>
            </CardContent>
          </Card>

          <Tabs defaultValue="api" className="space-y-6">
            <TabsList>
              <TabsTrigger value="api">API Usage</TabsTrigger>
              <TabsTrigger value="endpoints">Endpoints</TabsTrigger>
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
                            <TableCell className="text-right">{formatBytesDisplay(row.bytes_total)}</TableCell>
                            <TableCell className="text-right">{formatBytesDisplay(row.bytes_in_total ?? undefined)}</TableCell>
                            <TableCell className="text-right">{formatLatencyDisplay(row.latency_avg_ms)}</TableCell>
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
                            <TableCell className="text-right">{formatBytesDisplay(row.bytes_total)}</TableCell>
                            <TableCell className="text-right">{formatBytesDisplay(row.bytes_in_total ?? undefined)}</TableCell>
                            <TableCell className="text-right">{formatLatencyDisplay(row.latency_avg_ms)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="endpoints" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Endpoint usage</CardTitle>
                  <CardDescription>
                    Per-endpoint HTTP request, latency, and error metrics from Prometheus text metrics.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading endpoint metrics…</div>
                  ) : errors.endpoints ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.endpoints}</AlertDescription>
                    </Alert>
                  ) : endpointRows.length === 0 ? (
                    <div className="text-muted-foreground">No endpoint metrics available for the current source.</div>
                  ) : (
                    <>
                      <div className="mb-4 flex flex-wrap items-end gap-4">
                        <div className="space-y-2">
                          <Label htmlFor="endpoint-method-filter">Method filter</Label>
                          <Select
                            id="endpoint-method-filter"
                            value={endpointMethodFilter}
                            onChange={(event) => setEndpointMethodFilter(event.target.value)}
                          >
                            {endpointMethodOptions.map((option) => (
                              <option key={option} value={option}>{option}</option>
                            ))}
                          </Select>
                        </div>
                        <Badge variant="outline">Rows: {endpointRows.length}</Badge>
                      </div>
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>
                              <button type="button" className="inline-flex items-center gap-1" onClick={() => handleEndpointSort('endpoint')}>
                                Endpoint {getEndpointSortIndicator('endpoint')}
                              </button>
                            </TableHead>
                            <TableHead>
                              <button type="button" className="inline-flex items-center gap-1" onClick={() => handleEndpointSort('method')}>
                                Method {getEndpointSortIndicator('method')}
                              </button>
                            </TableHead>
                            <TableHead className="text-right">
                              <button type="button" className="inline-flex items-center gap-1" onClick={() => handleEndpointSort('requests')}>
                                Requests {getEndpointSortIndicator('requests')}
                              </button>
                            </TableHead>
                            <TableHead className="text-right">
                              <button type="button" className="inline-flex items-center gap-1" onClick={() => handleEndpointSort('avgLatency')}>
                                Avg latency {getEndpointSortIndicator('avgLatency')}
                              </button>
                            </TableHead>
                            <TableHead className="text-right">
                              <button type="button" className="inline-flex items-center gap-1" onClick={() => handleEndpointSort('errorRate')}>
                                Error rate {getEndpointSortIndicator('errorRate')}
                              </button>
                            </TableHead>
                            <TableHead className="text-right">
                              <button type="button" className="inline-flex items-center gap-1" onClick={() => handleEndpointSort('p95')}>
                                p95 latency {getEndpointSortIndicator('p95')}
                              </button>
                            </TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {endpointRows.map((row) => (
                            <TableRow key={`${row.method}-${row.endpoint}`}>
                              <TableCell className="max-w-[320px] truncate font-mono text-xs">{row.endpoint}</TableCell>
                              <TableCell>
                                <Badge variant="outline">{row.method}</Badge>
                              </TableCell>
                              <TableCell className="text-right">{row.requestCount}</TableCell>
                              <TableCell className="text-right">{formatLatencyDisplay(row.avgLatencyMs)}</TableCell>
                              <TableCell className="text-right">{formatPercentDisplay(row.errorRatePct)}</TableCell>
                              <TableCell className="text-right">{formatLatencyDisplay(row.p95LatencyMs)}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Storage breakdown</CardTitle>
                  <CardDescription>
                    Top storage consumers by user and upload volume by media type.
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                  {loading ? (
                    <div className="text-muted-foreground">Loading storage breakdown…</div>
                  ) : errors.storage ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.storage}</AlertDescription>
                    </Alert>
                  ) : (
                    <div className="grid gap-6 lg:grid-cols-2">
                      <div className="space-y-3">
                        <h3 className="text-sm font-semibold">Top storage consumers</h3>
                        {topStorageUsers.length === 0 ? (
                          <div className="text-sm text-muted-foreground">No per-user storage data available.</div>
                        ) : (
                          topStorageUsers.map((row) => (
                            <div key={row.userId} className="space-y-1">
                              <div className="flex items-center justify-between text-sm">
                                <span className="truncate">{row.username}</span>
                                <span className="text-muted-foreground">{formatStorageMbDisplay(row.storageUsedMb)}</span>
                              </div>
                              <div className="h-2 rounded bg-muted">
                                <div
                                  className="h-2 rounded bg-primary"
                                  style={{ width: `${Math.min((row.storageUsedMb / maxStorageUserMb) * 100, 100)}%` }}
                                />
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                      <div className="space-y-3">
                        <h3 className="text-sm font-semibold">Media type upload volume</h3>
                        {mediaTypeBreakdown.length === 0 ? (
                          <div className="text-sm text-muted-foreground">No media-type storage data available.</div>
                        ) : (
                          mediaTypeBreakdown.map((row) => (
                            <div key={row.mediaType} className="space-y-1">
                              <div className="flex items-center justify-between text-sm">
                                <span className="truncate capitalize">{row.mediaType}</span>
                                <span className="text-muted-foreground">{formatBytesDisplay(row.bytesTotal)}</span>
                              </div>
                              <div className="h-2 rounded bg-muted">
                                <div
                                  className="h-2 rounded bg-primary"
                                  style={{ width: `${Math.min((row.bytesTotal / maxMediaTypeBytes) * 100, 100)}%` }}
                                />
                              </div>
                            </div>
                          ))
                        )}
                      </div>
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <CardTitle>Rate limit monitoring</CardTitle>
                    <CardDescription>
                      Rejection counts and recent throttle activity by actor and policy.
                    </CardDescription>
                  </div>
                  <Badge variant={rateLimitEventsSource === 'endpoint' ? 'default' : 'secondary'}>
                    Source: {rateLimitEventsSource}
                  </Badge>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading rate limit events…</div>
                  ) : errors.rateLimits ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.rateLimits}</AlertDescription>
                    </Alert>
                  ) : rateLimitEvents.length === 0 ? (
                    <div className="text-muted-foreground">No rate limit rejections found in current data sources.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Actor</TableHead>
                          <TableHead>Policy</TableHead>
                          <TableHead className="text-right">Rejections (24h)</TableHead>
                          <TableHead className="text-right">Rejections (7d)</TableHead>
                          <TableHead className="text-right">Last rejection</TableHead>
                          <TableHead className="text-right">Status</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {rateLimitEvents.map((event) => {
                          const rowKey = `${event.actor}|${event.policy}|${event.resourceType ?? ''}|${event.reason ?? ''}`;
                          const isTopThrottled = topThrottledKeys.has(rowKey);
                          return (
                            <TableRow key={rowKey} className={isTopThrottled ? 'bg-red-50/40 dark:bg-red-950/20' : undefined}>
                              <TableCell>{event.actor}</TableCell>
                              <TableCell>
                                <div className="flex flex-col gap-1">
                                  <span>{event.policy}</span>
                                  {event.resourceType ? (
                                    <span className="text-xs text-muted-foreground">resource: {event.resourceType}</span>
                                  ) : null}
                                </div>
                              </TableCell>
                              <TableCell className="text-right tabular-nums">{event.rejections24h}</TableCell>
                              <TableCell className="text-right tabular-nums">{event.rejections7d}</TableCell>
                              <TableCell className="text-right">{formatDateTime(event.lastRejectedAt, { fallback: '—' })}</TableCell>
                              <TableCell className="text-right">
                                {isTopThrottled ? <Badge variant="destructive">Top throttled</Badge> : <Badge variant="outline">Normal</Badge>}
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="llm" className="space-y-6">
              <Card>
                <CardHeader>
                  <CardTitle>Cost forecast</CardTitle>
                  <CardDescription>
                    Linear-regression projection for the next 7, 30, and 90 days.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading forecast…</div>
                  ) : errors.forecast ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.forecast}</AlertDescription>
                    </Alert>
                  ) : !forecast || dailyCostTrend.length === 0 ? (
                    <div className="text-muted-foreground">Not enough daily cost data to forecast.</div>
                  ) : (
                    <div className="space-y-4">
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>Horizon</TableHead>
                            <TableHead className="text-right">Low estimate</TableHead>
                            <TableHead className="text-right">Expected</TableHead>
                            <TableHead className="text-right">High estimate</TableHead>
                            <TableHead className="text-right">Confidence</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {forecast.bands.map((band) => (
                            <TableRow key={band.horizonDays}>
                              <TableCell>{band.horizonDays} days</TableCell>
                              <TableCell className="text-right">${band.lowEstimateUsd.toFixed(2)}</TableCell>
                              <TableCell className="text-right font-medium">${band.expectedCostUsd.toFixed(2)}</TableCell>
                              <TableCell className="text-right">${band.highEstimateUsd.toFixed(2)}</TableCell>
                              <TableCell className="text-right">
                                <Badge variant={band.confidence === 'high' ? 'default' : band.confidence === 'medium' ? 'secondary' : 'outline'}>
                                  {band.confidence}
                                </Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                      <div className="flex flex-wrap items-center gap-2 text-sm">
                        <Badge variant="outline">Monthly run rate: ${forecast.monthlyRunRateUsd.toFixed(2)}</Badge>
                        <Badge variant="outline">Trend slope/day: ${forecast.slopePerDayUsd.toFixed(4)}</Badge>
                        <Badge variant="outline">R²: {forecast.rSquared.toFixed(3)}</Badge>
                        {monthlyBudgetUsd ? (
                          <Badge variant="secondary">Monthly budget: ${monthlyBudgetUsd.toFixed(2)}</Badge>
                        ) : null}
                      </div>
                      {forecast.budgetExceededByDate ? (
                        <Alert variant="destructive">
                          <AlertDescription>
                            At this rate, monthly budget will be exceeded by <strong>{forecast.budgetExceededByDate}</strong>.
                          </AlertDescription>
                        </Alert>
                      ) : monthlyBudgetUsd ? (
                        <Alert>
                          <AlertDescription>
                            Forecast remains within the current monthly budget cap.
                          </AlertDescription>
                        </Alert>
                      ) : null}
                    </div>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                  <div className="space-y-1">
                    <CardTitle>LLM usage summary</CardTitle>
                    <CardDescription>
                      Grouped usage for the selected dimension.
                    </CardDescription>
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
                  ) : summaryRows.length === 0 ? (
                    <div className="text-muted-foreground">No LLM usage data for this range.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{groupBy === 'organization' ? 'Organization' : 'Group'}</TableHead>
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
                        {summaryRows.map((row) => {
                          const orgId = groupBy === 'organization' ? (orgIdByName.get(row.group_value) ?? null) : null;
                          return (
                          <TableRow key={row.group_value}>
                            <TableCell>
                              {groupBy === 'organization' && orgId ? (
                                <Link href={`/organizations/${orgId}`} className="text-primary underline">
                                  {row.group_value}
                                </Link>
                              ) : (
                                row.group_value
                              )}
                            </TableCell>
                            <TableCell className="text-right">{row.requests}</TableCell>
                            <TableCell className="text-right">{row.errors}</TableCell>
                            <TableCell className="text-right">{row.input_tokens}</TableCell>
                            <TableCell className="text-right">{row.output_tokens}</TableCell>
                            <TableCell className="text-right">{row.total_tokens}</TableCell>
                            <TableCell className="text-right">${row.total_cost_usd.toFixed(4)}</TableCell>
                            <TableCell className="text-right">{formatLatencyDisplay(row.latency_avg_ms)}</TableCell>
                          </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>Per-organization cost attribution</CardTitle>
                  <CardDescription>
                    Requests, tokens, and cost contribution by organization.
                  </CardDescription>
                </CardHeader>
                <CardContent>
                  {loading ? (
                    <div className="text-muted-foreground">Loading organization attribution…</div>
                  ) : errors.orgAttribution ? (
                    <Alert variant="destructive" className="mb-4">
                      <AlertDescription>{errors.orgAttribution}</AlertDescription>
                    </Alert>
                  ) : orgAttribution.length === 0 ? (
                    <div className="text-muted-foreground">No organization attribution data for this range.</div>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Organization</TableHead>
                          <TableHead className="text-right">Requests</TableHead>
                          <TableHead className="text-right">Total tokens</TableHead>
                          <TableHead className="text-right">Cost (USD)</TableHead>
                          <TableHead className="text-right">% of total</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {orgAttribution.map((row) => (
                          <TableRow key={`${row.orgId ?? 'unassigned'}-${row.orgName}`}>
                            <TableCell>
                              {row.orgId ? (
                                <Link href={`/organizations/${row.orgId}`} className="text-primary underline">
                                  {row.orgName}
                                </Link>
                              ) : (
                                row.orgName
                              )}
                            </TableCell>
                            <TableCell className="text-right">{row.requests}</TableCell>
                            <TableCell className="text-right">{row.totalTokens}</TableCell>
                            <TableCell className="text-right">${row.totalCostUsd.toFixed(4)}</TableCell>
                            <TableCell className="text-right">{row.percentOfTotal.toFixed(2)}%</TableCell>
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
    </PermissionGuard>
  );
}
