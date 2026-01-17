'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { PermissionGuard } from '@/components/PermissionGuard';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import type { AuditLog } from '@/types';
import { KeyRound, RefreshCw } from 'lucide-react';

type MetricSample = {
  name: string;
  labels: Record<string, string>;
  value: number;
};

type ResolutionSummary = {
  source: string;
  count: number;
  share: string;
};

const SOURCE_LABELS: Record<string, string> = {
  user: 'User',
  team: 'Team',
  org: 'Org',
  server_default: 'Server',
  none: 'None',
};

const unescapeLabelValue = (s: string): string => {
  let result = '';
  for (let i = 0; i < s.length; i++) {
    const ch = s[i];
    if (ch === '\\' && i + 1 < s.length) {
      const next = s[i + 1];
      if (next === '\\') {
        result += '\\';
        i++;
      } else if (next === '"') {
        result += '"';
        i++;
      } else if (next === 'n') {
        result += '\n';
        i++;
      } else {
        // Unknown escape, keep as-is
        result += ch + next;
        i++;
      }
    } else {
      result += ch;
    }
  }
  return result;
};

const parsePrometheusText = (text: string): MetricSample[] => {
  const samples: MetricSample[] = [];
  const lineRegex = /^([a-zA-Z_:][a-zA-Z0-9_:]*)(\{([^}]*)\})?\s+([-+]?\d+(?:\.\d+)?(?:[eE][-+]?\d+)?)$/;
  const labelRegex = /(\w+)\s*=\s*"((?:\\.|[^"\\])*)"/g;
  text.split('\n').forEach((raw) => {
    const line = raw.trim();
    if (!line || line.startsWith('#')) return;
    const match = lineRegex.exec(line);
    if (!match) return;
    const [, name, , labelBlob, valueRaw] = match;
    const labels: Record<string, string> = {};
    if (labelBlob) {
      let labelMatch: RegExpExecArray | null;
      while ((labelMatch = labelRegex.exec(labelBlob))) {
        const key = labelMatch[1];
        const value = unescapeLabelValue(labelMatch[2]);
        labels[key] = value;
      }
    }
    const value = Number(valueRaw);
    if (!Number.isNaN(value)) {
      samples.push({ name, labels, value });
    }
  });
  return samples;
};

const sumValues = (values: number[]) => values.reduce((acc, val) => acc + val, 0);

const formatCount = (value: number | null) => {
  if (value === null) return '—';
  if (value < 1000) return `${value}`;
  if (value < 1000000) return `${(value / 1000).toFixed(1)}k`;
  return `${(value / 1000000).toFixed(1)}m`;
};

export default function ByokDashboardPage() {
  const { selectedOrg } = useOrgContext();
  const { error: showError } = useToast();
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [resolutionBySource, setResolutionBySource] = useState<Record<string, number>>({});
  const [resolutionByProvider, setResolutionByProvider] = useState<Record<string, number>>({});
  const [missingByProvider, setMissingByProvider] = useState<Record<string, number>>({});
  const [missingByOperation, setMissingByOperation] = useState<Record<string, number>>({});
  const [auditEntries, setAuditEntries] = useState<AuditLog[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);

  const loadMetrics = useCallback(async () => {
    setMetricsLoading(true);
    setMetricsError(null);
    try {
      const raw = await api.getMetricsText();
      const samples = parsePrometheusText(raw);
      const resolutionSamples = samples.filter((sample) => sample.name === 'byok_resolution_total');
      const missingSamples = samples.filter((sample) => sample.name === 'byok_missing_credentials_total');

      const sourceTotals: Record<string, number> = {};
      const providerTotals: Record<string, number> = {};
      resolutionSamples.forEach((sample) => {
        const source = sample.labels.source || 'unknown';
        const provider = sample.labels.provider || 'unknown';
        sourceTotals[source] = (sourceTotals[source] || 0) + sample.value;
        providerTotals[provider] = (providerTotals[provider] || 0) + sample.value;
      });

      const missingProviderTotals: Record<string, number> = {};
      const missingOperationTotals: Record<string, number> = {};
      missingSamples.forEach((sample) => {
        const provider = sample.labels.provider || 'unknown';
        const operation = sample.labels.operation || 'unknown';
        missingProviderTotals[provider] = (missingProviderTotals[provider] || 0) + sample.value;
        missingOperationTotals[operation] = (missingOperationTotals[operation] || 0) + sample.value;
      });

      setResolutionBySource(sourceTotals);
      setResolutionByProvider(providerTotals);
      setMissingByProvider(missingProviderTotals);
      setMissingByOperation(missingOperationTotals);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load metrics.';
      setMetricsError(message);
      showError('Metrics error', message);
    } finally {
      setMetricsLoading(false);
    }
  }, [showError]);

  const loadAudit = useCallback(async () => {
    setAuditLoading(true);
    setAuditError(null);
    try {
      const params: Record<string, string> = { limit: '200', offset: '0' };
      if (selectedOrg?.id) params.org_id = String(selectedOrg.id);
      const { entries } = await api.getAuditLogs(params);
      const byokEntries = (entries || []).filter((entry) => {
        const haystack = [
          entry.action,
          entry.resource,
          JSON.stringify(entry.details || {}),
        ]
          .join(' ')
          .toLowerCase();
        return (
          haystack.includes('byok')
          || haystack.includes('provider_secret')
          || haystack.includes('user_provider')
          || haystack.includes('org_provider')
          || haystack.includes('shared_key')
        );
      });
      setAuditEntries(byokEntries.slice(0, 12));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to load audit activity.';
      setAuditError(message);
    } finally {
      setAuditLoading(false);
    }
  }, [selectedOrg?.id]);

  useEffect(() => {
    loadMetrics();
    loadAudit();
  }, [loadMetrics, loadAudit]);

  const summaryCards = useMemo(() => {
    const byokTotal = sumValues(
      Object.entries(resolutionBySource)
        .filter(([source]) => ['user', 'team', 'org'].includes(source))
        .map(([, value]) => value)
    );
    const missingTotal = sumValues(Object.values(missingByProvider));
    const providersWithByok = Object.keys(resolutionByProvider).length || null;
    const topProvider = Object.entries(resolutionByProvider)
      .sort((a, b) => b[1] - a[1])[0]?.[0];

    return [
      { title: 'BYOK Requests', value: formatCount(byokTotal), detail: 'Resolved via user/team/org keys' },
      { title: 'Missing Credentials', value: formatCount(missingTotal), detail: 'Missing key events' },
      { title: 'Providers Used', value: providersWithByok ? String(providersWithByok) : '—', detail: 'Providers with BYOK traffic' },
      { title: 'Top Provider', value: topProvider || '—', detail: 'Highest BYOK volume' },
    ];
  }, [resolutionByProvider, resolutionBySource, missingByProvider]);

  const resolutionMix: ResolutionSummary[] = useMemo(() => {
    const total = sumValues(Object.values(resolutionBySource));
    const sources = Object.keys(resolutionBySource);
    const fallbackSources = ['user', 'team', 'org', 'server_default'];
    const list = (sources.length ? sources : fallbackSources).map((source) => {
      const count = resolutionBySource[source] || 0;
      const share = total > 0 ? `${Math.round((count / total) * 100)}%` : '—';
      return {
        source,
        count,
        share,
      };
    });
    return list;
  }, [resolutionBySource]);

  const missingTopProviders = useMemo(() => {
    return Object.entries(missingByProvider)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
  }, [missingByProvider]);

  const missingTopOperations = useMemo(() => {
    return Object.entries(missingByOperation)
      .sort((a, b) => b[1] - a[1])
      .slice(0, 5);
  }, [missingByOperation]);

  return (
    <PermissionGuard variant="route" requireAuth role="admin">
      <ResponsiveLayout>
        <div className="space-y-6 p-4 lg:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <div className="flex items-center gap-2">
                <KeyRound className="h-5 w-5 text-primary" />
                <h1 className="text-2xl font-semibold">BYOK Dashboards</h1>
              </div>
              <p className="text-sm text-muted-foreground">
                Placeholder telemetry views for BYOK adoption, resolution mix, and key activity.
              </p>
              {selectedOrg && (
                <div className="mt-1 text-xs text-muted-foreground">
                  Active scope: {selectedOrg.name}
                </div>
              )}
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <Badge variant="outline">Metrics</Badge>
              <Button variant="outline" size="sm" onClick={loadMetrics} disabled={metricsLoading}>
                <RefreshCw className="mr-2 h-4 w-4" />
                {metricsLoading ? 'Refreshing…' : 'Refresh metrics'}
              </Button>
            </div>
          </div>

          <Alert>
            <AlertDescription>
              {metricsError
                ? `Metrics unavailable: ${metricsError}`
                : 'Metrics are sourced from /api/v1/metrics/text and audit logs where available.'}
            </AlertDescription>
          </Alert>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {summaryCards.map((card) => (
              <Card key={card.title}>
                <CardHeader className="pb-2">
                  <CardTitle className="text-base">{card.title}</CardTitle>
                  <CardDescription>{card.detail}</CardDescription>
                </CardHeader>
                <CardContent>
                  <div className="text-3xl font-semibold">{card.value}</div>
                </CardContent>
              </Card>
            ))}
          </div>

          <div className="grid gap-4 lg:grid-cols-3">
            <Card>
              <CardHeader>
                <CardTitle className="text-base">Resolution Mix</CardTitle>
                <CardDescription>Share of requests by credential source.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2">
                {resolutionMix.map((row) => (
                  <div key={row.source} className="flex items-center justify-between rounded-md border px-3 py-2 text-sm">
                    <div>
                      <div className="font-medium">{SOURCE_LABELS[row.source] || row.source}</div>
                      <div className="text-xs text-muted-foreground">{formatCount(row.count)} requests</div>
                    </div>
                    <div className="text-xs font-semibold text-muted-foreground">{row.share}</div>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Missing Credentials</CardTitle>
                <CardDescription>Top providers with missing key events.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                {missingTopProviders.length === 0 && (
                  <div className="rounded-md border px-3 py-2 text-sm text-muted-foreground">
                    No missing credential events yet.
                  </div>
                )}
                {missingTopProviders.map(([provider, count]) => (
                  <div key={provider} className="flex items-center justify-between rounded-md border px-3 py-2">
                    <span>{provider}</span>
                    <span>{formatCount(count)}</span>
                  </div>
                ))}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle className="text-base">Key Validation</CardTitle>
                <CardDescription>Recent validation results and errors.</CardDescription>
              </CardHeader>
              <CardContent className="space-y-2 text-sm text-muted-foreground">
                {missingTopOperations.length === 0 ? (
                  <div className="rounded-md border px-3 py-2">No validation events yet.</div>
                ) : (
                  missingTopOperations.map(([operation, count]) => (
                    <div key={operation} className="flex items-center justify-between rounded-md border px-3 py-2">
                      <span>{operation}</span>
                      <span>{formatCount(count)}</span>
                    </div>
                  ))
                )}
                <Button variant="secondary" size="sm" disabled>
                  Validation sweep coming soon
                </Button>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Key Activity (Placeholder)</CardTitle>
              <CardDescription>Audit events matching BYOK-related actions (when emitted).</CardDescription>
            </CardHeader>
            <CardContent>
              {auditError && (
                <div className="mb-3 rounded-md border border-red-200 bg-red-50 px-3 py-2 text-sm text-red-700">
                  {auditError}
                </div>
              )}
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>When</TableHead>
                    <TableHead>Actor</TableHead>
                    <TableHead>Action</TableHead>
                    <TableHead>Scope</TableHead>
                    <TableHead>Provider</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {auditLoading && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground">
                        Loading audit activity…
                      </TableCell>
                    </TableRow>
                  )}
                  {!auditLoading && auditEntries.length === 0 && (
                    <TableRow>
                      <TableCell colSpan={5} className="text-muted-foreground">
                        No BYOK audit events found yet.
                      </TableCell>
                    </TableRow>
                  )}
                  {auditEntries.map((entry) => {
                    const details = entry.details || {};
                    const provider = typeof details.provider === 'string' ? details.provider : '—';
                    const scope =
                      typeof details.scope_type === 'string'
                        ? details.scope_type
                        : typeof details.scope === 'string'
                          ? details.scope
                          : '—';
                    return (
                      <TableRow key={entry.id}>
                        <TableCell className="text-muted-foreground">{entry.timestamp || '—'}</TableCell>
                        <TableCell>{entry.username || entry.user_id || '—'}</TableCell>
                        <TableCell>{entry.action || '—'}</TableCell>
                        <TableCell>{scope}</TableCell>
                        <TableCell>{provider}</TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </PermissionGuard>
  );
}
