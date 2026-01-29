'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select } from '@/components/ui/select';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { KeyRound, RefreshCw, Plus, Trash2, Send, Server, X } from 'lucide-react';
import { AccessibleIconButton } from '@/components/ui/accessible-icon-button';

type SharedProviderKey = {
  scope_type: 'org' | 'team';
  scope_id: number;
  provider: string;
  key_hint?: string;
  last_used_at?: string;
};

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

const PROVIDER_OPTIONS = [
  'openai',
  'anthropic',
  'cohere',
  'deepseek',
  'google',
  'groq',
  'huggingface',
  'mistral',
  'openrouter',
  'qwen',
  'moonshot',
  'zai',
] as const;

export default function ByokDashboardPage() {
  const { selectedOrg } = useOrgContext();
  const confirm = useConfirm();
  const { success: toastSuccess, error: showError } = useToast();
  const [metricsLoading, setMetricsLoading] = useState(false);
  const [metricsError, setMetricsError] = useState<string | null>(null);
  const [resolutionBySource, setResolutionBySource] = useState<Record<string, number>>({});
  const [resolutionByProvider, setResolutionByProvider] = useState<Record<string, number>>({});
  const [missingByProvider, setMissingByProvider] = useState<Record<string, number>>({});
  const [missingByOperation, setMissingByOperation] = useState<Record<string, number>>({});
  const [auditEntries, setAuditEntries] = useState<AuditLog[]>([]);
  const [auditError, setAuditError] = useState<string | null>(null);
  const [auditLoading, setAuditLoading] = useState(false);

  // Shared Provider Keys
  const [sharedKeys, setSharedKeys] = useState<SharedProviderKey[]>([]);
  const [sharedKeysLoading, setSharedKeysLoading] = useState(false);
  const [sharedKeysError, setSharedKeysError] = useState<string | null>(null);
  const [showAddKey, setShowAddKey] = useState(false);
  const [newKeyProvider, setNewKeyProvider] = useState('openai');
  const [newKeyValue, setNewKeyValue] = useState('');
  const [addingKey, setAddingKey] = useState(false);
  const [testingKey, setTestingKey] = useState<string | null>(null);
  const [deletingKey, setDeletingKey] = useState<string | null>(null);
  const sharedKeysRequestIdRef = useRef(0);

  const resetAddKeyForm = useCallback(() => {
    setShowAddKey(false);
    setNewKeyValue('');
  }, []);

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

  const loadSharedKeys = useCallback(async () => {
    const requestId = sharedKeysRequestIdRef.current + 1;
    sharedKeysRequestIdRef.current = requestId;
    setSharedKeysLoading(true);
    setSharedKeysError(null);
    setSharedKeys([]);
    try {
      const orgId = selectedOrg?.id;
      // Filter by selected org if one is selected
      const params = orgId
        ? { scope_type: 'org', scope_id: orgId }
        : undefined;
      const data = await api.getSharedProviderKeys(params);
      if (sharedKeysRequestIdRef.current !== requestId) return;
      const result = data as { keys?: SharedProviderKey[]; items?: SharedProviderKey[] };
      setSharedKeys(
        Array.isArray(result.keys) ? result.keys :
        Array.isArray(result.items) ? result.items :
        Array.isArray(result) ? result as SharedProviderKey[] : []
      );
    } catch (err) {
      if (sharedKeysRequestIdRef.current !== requestId) return;
      const message = err instanceof Error ? err.message : 'Failed to load shared keys.';
      setSharedKeysError(message);
    } finally {
      if (sharedKeysRequestIdRef.current === requestId) {
        setSharedKeysLoading(false);
      }
    }
  }, [selectedOrg?.id]);

  const handleAddSharedKey = async () => {
    if (!newKeyValue.trim()) {
      showError('API key required', 'Please enter the API key value.');
      return;
    }

    if (!selectedOrg?.id) {
      showError('Organization required', 'Please select an organization to add a shared key.');
      return;
    }

    try {
      setAddingKey(true);
      await api.createSharedProviderKey({
        scope_type: 'org',
        scope_id: selectedOrg.id,
        provider: newKeyProvider,
        api_key: newKeyValue.trim(),
      });
      toastSuccess('Key added', `Shared key for ${newKeyProvider} has been added.`);
      setShowAddKey(false);
      setNewKeyProvider('openai');
      setNewKeyValue('');
      void loadSharedKeys();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to add shared key.';
      showError('Add failed', message);
    } finally {
      setAddingKey(false);
    }
  };

  const handleDeleteSharedKey = async (key: SharedProviderKey) => {
    const keyId = `${key.scope_type}:${key.scope_id}:${key.provider}`;
    const confirmed = await confirm({
      title: 'Delete Shared Key',
      message: `Delete the shared key for "${key.provider}"? Users and orgs will fall back to their own keys.`,
      confirmText: 'Delete',
      variant: 'danger',
      icon: 'delete',
    });
    if (!confirmed) return;

    try {
      setDeletingKey(keyId);
      await api.deleteSharedProviderKey(key.scope_type, key.scope_id, key.provider);
      toastSuccess('Key deleted', `Shared key for ${key.provider} has been removed.`);
      void loadSharedKeys();
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Failed to delete shared key.';
      showError('Delete failed', message);
    } finally {
      setDeletingKey(null);
    }
  };

  const handleTestSharedKey = async (key: SharedProviderKey) => {
    const keyId = `${key.scope_type}:${key.scope_id}:${key.provider}`;
    try {
      setTestingKey(keyId);
      await api.testSharedProviderKey({
        scope_type: key.scope_type,
        scope_id: key.scope_id,
        provider: key.provider,
      });
      toastSuccess('Test passed', `Shared key for ${key.provider} is valid.`);
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Key test failed.';
      showError('Test failed', message);
    } finally {
      setTestingKey(null);
    }
  };

  useEffect(() => {
    loadMetrics();
    loadAudit();
    loadSharedKeys();
  }, [loadMetrics, loadAudit, loadSharedKeys]);

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

          {/* Shared Provider Keys (Organization-Level) */}
          <Card>
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="flex items-center gap-2 text-base">
                    <Server className="h-5 w-5" />
                    Organization Provider Keys
                  </CardTitle>
                  <CardDescription>
                    Shared API keys for the selected organization. Users in the org can use these when they don&apos;t have their own keys.
                    <br />
                    <span className="text-xs">Resolution order: User → Organization</span>
                  </CardDescription>
                </div>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAddKey(true)}
                  disabled={showAddKey || !selectedOrg?.id}
                  title={!selectedOrg?.id ? 'Select an organization first' : undefined}
                >
                  <Plus className="mr-2 h-4 w-4" />
                  Add Key
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              {sharedKeysError && (
                <Alert variant="destructive">
                  <AlertDescription>{sharedKeysError}</AlertDescription>
                </Alert>
              )}

              {/* Add Key Form */}
              {showAddKey && (
                <div className="p-4 border rounded-lg space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="font-medium">Add Organization Provider Key</span>
                    <AccessibleIconButton
                      icon={X}
                      label="Close form"
                      variant="ghost"
                      onClick={resetAddKeyForm}
                    />
                  </div>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <div className="space-y-1">
                      <Label htmlFor="key-provider">Provider</Label>
                      <Select
                        id="key-provider"
                        value={newKeyProvider}
                        onChange={(e) => setNewKeyProvider(e.target.value)}
                      >
                        {PROVIDER_OPTIONS.map((provider) => (
                          <option key={provider} value={provider}>
                            {provider.charAt(0).toUpperCase() + provider.slice(1)}
                          </option>
                        ))}
                      </Select>
                    </div>
                    <div className="space-y-1">
                      <Label htmlFor="key-value">API Key</Label>
                      <Input
                        id="key-value"
                        type="password"
                        placeholder="sk-..."
                        value={newKeyValue}
                        onChange={(e) => setNewKeyValue(e.target.value)}
                      />
                    </div>
                  </div>
                  <div className="flex gap-2">
                    <Button onClick={handleAddSharedKey} disabled={addingKey || !newKeyValue.trim()}>
                      {addingKey ? 'Adding...' : 'Add Key'}
                    </Button>
                    <Button variant="outline" onClick={resetAddKeyForm}>
                      Cancel
                    </Button>
                  </div>
                </div>
              )}

              {/* Keys List */}
              {sharedKeysLoading ? (
                <div className="text-center text-muted-foreground py-4">Loading organization keys...</div>
              ) : sharedKeys.length === 0 ? (
                <div className="text-center text-muted-foreground py-8 border rounded-lg">
                  No organization-level provider keys configured.
                  <br />
                  <span className="text-xs">Users must provide their own keys or select an organization.</span>
                </div>
              ) : (
                <div className="space-y-2">
                  {sharedKeys.map((key) => {
                    const keyId = `${key.scope_type}:${key.scope_id}:${key.provider}`;
                    return (
                    <div
                      key={keyId}
                      className="flex items-center justify-between p-3 rounded-lg border bg-background"
                    >
                      <div className="flex items-center gap-3">
                        <KeyRound className="h-4 w-4 text-muted-foreground" />
                        <div>
                          <div className="font-medium capitalize">{key.provider}</div>
                          <div className="text-xs text-muted-foreground">
                            {key.key_hint ? `Key: ${key.key_hint}` : `${key.scope_type} key`}
                            {key.last_used_at && ` • Last used: ${new Date(key.last_used_at).toLocaleDateString()}`}
                          </div>
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <Badge variant="secondary" className="capitalize">{key.scope_type}</Badge>
                        <AccessibleIconButton
                          icon={Send}
                          label="Test key"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleTestSharedKey(key)}
                          disabled={testingKey === keyId}
                          iconClassName={testingKey === keyId ? 'animate-pulse' : ''}
                        />
                        <AccessibleIconButton
                          icon={Trash2}
                          label="Delete key"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDeleteSharedKey(key)}
                          disabled={deletingKey === keyId}
                          iconClassName="text-red-500"
                        />
                      </div>
                    </div>
                  );
                  })}
                </div>
              )}
            </CardContent>
          </Card>

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
