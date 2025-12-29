'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { TableSkeleton } from '@/components/ui/skeleton';
import { RefreshCw, Wallet } from 'lucide-react';
import { api } from '@/lib/api-client';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useUrlMultiState } from '@/lib/use-url-state';

type BudgetAlertThresholds = {
  global?: number[];
  per_metric?: Record<string, number[]>;
};

type BudgetEnforcementMode = {
  global?: 'none' | 'soft' | 'hard';
  per_metric?: Record<string, 'none' | 'soft' | 'hard'>;
};

type BudgetSettings = {
  budget_day_usd?: number | null;
  budget_month_usd?: number | null;
  budget_day_tokens?: number | null;
  budget_month_tokens?: number | null;
  alert_thresholds?: BudgetAlertThresholds | null;
  enforcement_mode?: BudgetEnforcementMode | null;
};

type OrgBudgetItem = {
  org_id: number;
  org_name: string;
  org_slug?: string | null;
  plan_name: string;
  plan_display_name: string;
  budgets: BudgetSettings;
  updated_at?: string | null;
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === 'object' && value !== null;

const isNumberArray = (value: unknown): value is number[] =>
  Array.isArray(value) && value.every((item) => typeof item === 'number');

const parseAlertThresholds = (value: unknown): BudgetAlertThresholds | null | undefined => {
  if (value === null) return null;
  if (!isRecord(value)) return undefined;

  const global = isNumberArray(value.global) ? value.global : undefined;
  let perMetric: Record<string, number[]> | undefined;
  if (isRecord(value.per_metric)) {
    const entries = Object.entries(value.per_metric).reduce<Record<string, number[]>>((acc, [key, entry]) => {
      if (isNumberArray(entry)) {
        acc[key] = entry;
      }
      return acc;
    }, {});
    if (Object.keys(entries).length > 0) {
      perMetric = entries;
    }
  }

  if (!global && !perMetric) return undefined;
  return {
    ...(global ? { global } : {}),
    ...(perMetric ? { per_metric: perMetric } : {}),
  };
};

const isEnforcementModeValue = (value: unknown): value is 'none' | 'soft' | 'hard' =>
  value === 'none' || value === 'soft' || value === 'hard';

const parseEnforcementMode = (value: unknown): BudgetEnforcementMode | null | undefined => {
  if (value === null) return null;
  if (!isRecord(value)) return undefined;

  const global = isEnforcementModeValue(value.global) ? value.global : undefined;
  let perMetric: Record<string, 'none' | 'soft' | 'hard'> | undefined;
  if (isRecord(value.per_metric)) {
    const entries = Object.entries(value.per_metric).reduce<Record<string, 'none' | 'soft' | 'hard'>>(
      (acc, [key, entry]) => {
        if (isEnforcementModeValue(entry)) {
          acc[key] = entry;
        }
        return acc;
      },
      {},
    );
    if (Object.keys(entries).length > 0) {
      perMetric = entries;
    }
  }

  if (!global && !perMetric) return undefined;
  return {
    ...(global ? { global } : {}),
    ...(perMetric ? { per_metric: perMetric } : {}),
  };
};

const parseBudgetSettings = (value: unknown): BudgetSettings => {
  if (!isRecord(value)) return {};

  return {
    budget_day_usd: typeof value.budget_day_usd === 'number' || value.budget_day_usd === null
      ? value.budget_day_usd
      : undefined,
    budget_month_usd: typeof value.budget_month_usd === 'number' || value.budget_month_usd === null
      ? value.budget_month_usd
      : undefined,
    budget_day_tokens: typeof value.budget_day_tokens === 'number' || value.budget_day_tokens === null
      ? value.budget_day_tokens
      : undefined,
    budget_month_tokens: typeof value.budget_month_tokens === 'number' || value.budget_month_tokens === null
      ? value.budget_month_tokens
      : undefined,
    alert_thresholds: parseAlertThresholds(value.alert_thresholds),
    enforcement_mode: parseEnforcementMode(value.enforcement_mode),
  };
};

const parseOrgBudgetItems = (value: unknown): OrgBudgetItem[] => {
  if (!Array.isArray(value)) return [];

  return value.reduce<OrgBudgetItem[]>((acc, item) => {
    if (!isRecord(item)) return acc;

    const orgId = item.org_id;
    const orgName = item.org_name;
    const planName = item.plan_name;
    const planDisplayName = item.plan_display_name;

    if (
      typeof orgId !== 'number'
      || typeof orgName !== 'string'
      || typeof planName !== 'string'
      || typeof planDisplayName !== 'string'
    ) {
      return acc;
    }

    const orgSlug = typeof item.org_slug === 'string' || item.org_slug === null ? item.org_slug : undefined;
    const updatedAt = typeof item.updated_at === 'string' || item.updated_at === null ? item.updated_at : undefined;
    const budgets = parseBudgetSettings(item.budgets);

    acc.push({
      org_id: orgId,
      org_name: orgName,
      org_slug: orgSlug,
      plan_name: planName,
      plan_display_name: planDisplayName,
      budgets,
      updated_at: updatedAt,
    });

    return acc;
  }, []);
};

const formatCurrency = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  return `$${value.toFixed(2)}`;
};

const formatTokens = (value?: number | null) => {
  if (value === null || value === undefined) return '—';
  return value.toLocaleString();
};

const formatDate = (value?: string | null) => {
  if (!value) return '—';
  return new Date(value).toLocaleString('en-US', {
    dateStyle: 'medium',
    timeStyle: 'short',
  });
};

const formatPercentList = (values: number[]) =>
  values.map((value) => `${value}%`).join(', ');

const formatThresholds = (thresholds?: BudgetAlertThresholds | null) => {
  if (!thresholds) return '—';
  const parts: string[] = [];
  if (thresholds.global && thresholds.global.length > 0) {
    parts.push(`global: ${formatPercentList(thresholds.global)}`);
  }
  const perMetricKeys = thresholds.per_metric ? Object.keys(thresholds.per_metric) : [];
  if (perMetricKeys.length > 0) {
    parts.push(`per metric: ${perMetricKeys.join(', ')}`);
  }
  return parts.length > 0 ? parts.join(' | ') : '—';
};

const formatEnforcement = (mode?: BudgetEnforcementMode | null) => {
  if (!mode) return '—';
  const parts: string[] = [];
  if (mode.global) {
    parts.push(`global: ${mode.global}`);
  }
  const perMetricKeys = mode.per_metric ? Object.keys(mode.per_metric) : [];
  if (perMetricKeys.length > 0) {
    parts.push(`per metric: ${perMetricKeys.length}`);
  }
  return parts.length > 0 ? parts.join(' | ') : '—';
};

const renderBudgetCaps = (item: OrgBudgetItem) => {
  const settings = item.budgets || {};
  const hasAny = [
    settings.budget_day_usd,
    settings.budget_month_usd,
    settings.budget_day_tokens,
    settings.budget_month_tokens,
  ].some((value) => value !== null && value !== undefined);
  if (!hasAny) {
    return <span className="text-muted-foreground text-sm">No caps set</span>;
  }
  return (
    <div className="space-y-1 text-xs">
      <div className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">Daily USD</span>
        <span className="font-mono">{formatCurrency(settings.budget_day_usd)}</span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">Monthly USD</span>
        <span className="font-mono">{formatCurrency(settings.budget_month_usd)}</span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">Daily tokens</span>
        <span className="font-mono">{formatTokens(settings.budget_day_tokens)}</span>
      </div>
      <div className="flex items-center justify-between gap-3">
        <span className="text-muted-foreground">Monthly tokens</span>
        <span className="font-mono">{formatTokens(settings.budget_month_tokens)}</span>
      </div>
    </div>
  );
};

export default function BudgetsPage() {
  const { selectedOrg } = useOrgContext();
  const defaultPage = 1;
  const defaultPageSize = 20;
  const [{ page: rawPage, pageSize: rawPageSize }, setPaginationValues] = useUrlMultiState({
    page: defaultPage,
    pageSize: defaultPageSize,
  });
  const setPaginationValuesRef = useRef(setPaginationValues);
  useEffect(() => {
    setPaginationValuesRef.current = setPaginationValues;
  }, [setPaginationValues]);
  const page = Number.isFinite(rawPage) && rawPage > 0 ? rawPage : defaultPage;
  const pageSize = Number.isFinite(rawPageSize) && rawPageSize > 0 ? rawPageSize : defaultPageSize;
  const setPage = useCallback((nextPage: number) => {
    setPaginationValues({ page: nextPage });
  }, [setPaginationValues]);
  const [budgets, setBudgets] = useState<OrgBudgetItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const budgetParams = useMemo(() => {
    const params: Record<string, string> = {
      page: String(page),
      limit: String(pageSize),
    };
    if (selectedOrg) {
      params.org_id = String(selectedOrg.id);
    }
    return params;
  }, [page, pageSize, selectedOrg]);

  const loadBudgets = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const data = await api.getBudgets(budgetParams);
      if (isRecord(data)) {
        const items = parseOrgBudgetItems(data.items);
        setBudgets(items);
        const totalValue = typeof data.total === 'number' ? data.total : items.length;
        setTotal(totalValue);
      } else {
        setBudgets([]);
        setTotal(0);
      }
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to load budgets';
      setError(message);
      setBudgets([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [budgetParams]);

  useEffect(() => {
    void loadBudgets();
  }, [loadBudgets]);

  useEffect(() => {
    setPaginationValuesRef.current({ page: defaultPage });
  }, [selectedOrg, defaultPage]);

  const totalItems = total || budgets.length;
  const totalPages = Math.max(1, Math.ceil(totalItems / pageSize));

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
        <div className="p-4 lg:p-8">
          <div className="mb-8 flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <h1 className="text-3xl font-bold">Budgets</h1>
              <p className="text-muted-foreground">
                Review per-organization caps, alert thresholds, and enforcement settings.
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Read-only</Badge>
              <Button variant="outline" onClick={loadBudgets} disabled={loading}>
                <RefreshCw className={`mr-2 h-4 w-4 ${loading ? 'animate-spin' : ''}`} />
                Refresh
              </Button>
            </div>
          </div>

          {error && (
            <Alert variant="destructive" className="mb-6">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}

          <Card className="mb-6">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Wallet className="h-5 w-5" />
                Budget overview
              </CardTitle>
              <CardDescription>
                Budget updates are disabled in Stage 5.1. Use the Usage page for spend analytics.
              </CardDescription>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Organization budgets</CardTitle>
              <CardDescription>
                {totalItems} record{totalItems !== 1 ? 's' : ''} found
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-4" data-testid="table-skeleton">
                  <TableSkeleton rows={5} columns={6} />
                </div>
              ) : budgets.length === 0 ? (
                <div className="text-muted-foreground">No budgets found for the selected scope.</div>
              ) : (
                <>
                  <div className="overflow-x-auto">
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Organization</TableHead>
                          <TableHead>Plan</TableHead>
                          <TableHead>Budget caps</TableHead>
                          <TableHead>Alert thresholds</TableHead>
                          <TableHead>Enforcement</TableHead>
                          <TableHead>Updated</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {budgets.map((item) => (
                          <TableRow key={item.org_id}>
                            <TableCell>
                              <div className="space-y-1">
                                <div className="font-medium">{item.org_name}</div>
                                {item.org_slug ? (
                                  <div className="text-xs text-muted-foreground">{item.org_slug}</div>
                                ) : null}
                                <div className="text-xs text-muted-foreground">ID {item.org_id}</div>
                              </div>
                            </TableCell>
                            <TableCell>
                              <div className="space-y-1">
                                <div className="font-medium">{item.plan_display_name}</div>
                                <div className="text-xs text-muted-foreground">{item.plan_name}</div>
                              </div>
                            </TableCell>
                            <TableCell>{renderBudgetCaps(item)}</TableCell>
                            <TableCell className="text-sm">{formatThresholds(item.budgets?.alert_thresholds)}</TableCell>
                            <TableCell className="text-sm">{formatEnforcement(item.budgets?.enforcement_mode)}</TableCell>
                            <TableCell className="text-sm">{formatDate(item.updated_at)}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  </div>

                  <Pagination
                    currentPage={page}
                    totalPages={totalPages}
                    totalItems={totalItems}
                    pageSize={pageSize}
                    onPageChange={setPage}
                    onPageSizeChange={(size) => {
                      setPaginationValues({ pageSize: size, page: defaultPage });
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
