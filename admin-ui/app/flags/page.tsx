'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Badge } from '@/components/ui/badge';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import { RefreshCw, Trash2 } from 'lucide-react';

type MaintenanceState = {
  enabled: boolean;
  message?: string | null;
  allowlist_user_ids?: number[];
  allowlist_emails?: string[];
  updated_at?: string | null;
  updated_by?: string | null;
};

type FeatureFlagItem = {
  id?: number | string | null;
  key: string;
  scope: 'global' | 'org' | 'user';
  enabled: boolean;
  description?: string | null;
  org_id?: number | null;
  user_id?: number | null;
  updated_at?: string | null;
  updated_by?: string | null;
  history?: {
    timestamp: string;
    enabled: boolean;
    actor?: string | null;
    note?: string | null;
  }[];
};

type FlagsResponse = {
  items?: FeatureFlagItem[];
};

const FLAG_SCOPES = ['global', 'org', 'user'] as const;

type ParsedList<T> = {
  values: T[];
  invalid: string[];
};

const EMAIL_REGEX = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

const formatInvalidValues = (values: string[]) => {
  const sample = values.slice(0, 5).join(', ');
  return values.length > 5 ? `${sample} (+${values.length - 5} more)` : sample;
};

const parsePositiveInt = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return null;
  const parsed = Number(trimmed);
  if (!Number.isInteger(parsed) || parsed <= 0) return null;
  return parsed;
};

const parsePositiveIntList = (value: string): ParsedList<number> => {
  const values: number[] = [];
  const invalid: string[] = [];

  value.split(',').forEach((item) => {
    const trimmed = item.trim();
    if (!trimmed) return;
    const parsed = Number(trimmed);
    if (Number.isInteger(parsed) && parsed > 0) {
      values.push(parsed);
    } else {
      invalid.push(trimmed);
    }
  });

  return { values, invalid };
};

const parseEmailList = (value: string): ParsedList<string> => {
  const values: string[] = [];
  const invalid: string[] = [];

  value.split(',').forEach((item) => {
    const trimmed = item.trim();
    if (!trimmed) return;
    if (EMAIL_REGEX.test(trimmed)) {
      values.push(trimmed);
    } else {
      invalid.push(trimmed);
    }
  });

  return { values, invalid };
};

const formatDate = (value?: string | null) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

export default function FlagsPage() {
  const confirm = useConfirm();
  const { success, error: showError, warning } = useToast();

  const [maintenance, setMaintenance] = useState<MaintenanceState | null>(null);
  const [maintenanceEnabled, setMaintenanceEnabled] = useState(false);
  const [maintenanceMessage, setMaintenanceMessage] = useState('');
  const [maintenanceAllowUserIds, setMaintenanceAllowUserIds] = useState('');
  const [maintenanceAllowEmails, setMaintenanceAllowEmails] = useState('');
  const [maintenanceLoading, setMaintenanceLoading] = useState(true);
  const [maintenanceSaving, setMaintenanceSaving] = useState(false);

  const [flags, setFlags] = useState<FeatureFlagItem[]>([]);
  const [flagError, setFlagError] = useState('');
  const [flagLoading, setFlagLoading] = useState(true);
  const [flagScopeFilter, setFlagScopeFilter] = useState('');
  const [flagOrgFilter, setFlagOrgFilter] = useState('');
  const [flagUserFilter, setFlagUserFilter] = useState('');

  const [flagKey, setFlagKey] = useState('');
  const [flagScope, setFlagScope] = useState<'global' | 'org' | 'user'>('global');
  const [flagEnabled, setFlagEnabled] = useState(true);
  const [flagDescription, setFlagDescription] = useState('');
  const [flagOrgId, setFlagOrgId] = useState('');
  const [flagUserId, setFlagUserId] = useState('');
  const [flagNote, setFlagNote] = useState('');
  const [flagSaving, setFlagSaving] = useState(false);

  const flagParams = useMemo(() => {
    const params: Record<string, string> = {};
    if (flagScopeFilter) params.scope = flagScopeFilter;
    if (flagOrgFilter) params.org_id = flagOrgFilter;
    if (flagUserFilter) params.user_id = flagUserFilter;
    return params;
  }, [flagOrgFilter, flagScopeFilter, flagUserFilter]);

  const loadMaintenance = useCallback(async (signal?: AbortSignal) => {
    try {
      setMaintenanceLoading(true);
      const data = (await api.getMaintenanceMode({ signal })) as MaintenanceState;
      setMaintenance(data);
      setMaintenanceEnabled(Boolean(data?.enabled));
      setMaintenanceMessage(data?.message || '');
      setMaintenanceAllowUserIds((data?.allowlist_user_ids || []).join(', '));
      setMaintenanceAllowEmails((data?.allowlist_emails || []).join(', '));
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      const message = err instanceof Error && err.message ? err.message : 'Failed to load maintenance mode';
      showError(message);
    } finally {
      setMaintenanceLoading(false);
    }
  }, [showError]);

  const loadFlags = useCallback(async (signal?: AbortSignal) => {
    try {
      setFlagLoading(true);
      setFlagError('');
      const data = (await api.getFeatureFlags(flagParams, { signal })) as FlagsResponse;
      const items = Array.isArray(data.items) ? data.items : [];
      setFlags(items);
    } catch (err: unknown) {
      if (err instanceof Error && err.name === 'AbortError') return;
      const message = err instanceof Error && err.message ? err.message : 'Failed to load feature flags';
      setFlagError(message);
      setFlags([]);
    } finally {
      setFlagLoading(false);
    }
  }, [flagParams]);

  useEffect(() => {
    const controller = new AbortController();
    void loadMaintenance(controller.signal);
    return () => controller.abort();
  }, [loadMaintenance]);

  useEffect(() => {
    const controller = new AbortController();
    void loadFlags(controller.signal);
    return () => controller.abort();
  }, [loadFlags]);

  const handleRefresh = useCallback(() => {
    void Promise.allSettled([loadMaintenance(), loadFlags()]);
  }, [loadFlags, loadMaintenance]);

  const handleSaveMaintenance = async () => {
    if (!maintenance) return;
    const changed = maintenanceEnabled !== maintenance.enabled;
    if (changed) {
      const confirmed = await confirm({
        title: maintenanceEnabled ? 'Enable maintenance mode?' : 'Disable maintenance mode?',
        description: maintenanceEnabled
          ? 'This will block non-allowlisted users.'
          : 'Service traffic will resume for all users.',
        confirmText: maintenanceEnabled ? 'Enable' : 'Disable',
        variant: 'destructive',
      });
      if (!confirmed) return;
    }
    try {
      setMaintenanceSaving(true);
      const allowlistUserIds = parsePositiveIntList(maintenanceAllowUserIds);
      const allowlistEmails = parseEmailList(maintenanceAllowEmails);
      if (allowlistUserIds.invalid.length > 0) {
        warning(
          'Some allowlist user IDs were ignored',
          `Invalid values: ${formatInvalidValues(allowlistUserIds.invalid)}`
        );
      }
      if (allowlistEmails.invalid.length > 0) {
        warning(
          'Some allowlist emails were ignored',
          `Invalid values: ${formatInvalidValues(allowlistEmails.invalid)}`
        );
      }
      const payload = {
        enabled: maintenanceEnabled,
        message: maintenanceMessage,
        allowlist_user_ids: allowlistUserIds.values,
        allowlist_emails: allowlistEmails.values,
      };
      const updated = await api.updateMaintenanceMode(payload);
      const updatedState = updated as MaintenanceState;
      setMaintenance(updatedState);
      setMaintenanceEnabled(Boolean(updatedState.enabled));
      setMaintenanceMessage(updatedState.message || '');
      setMaintenanceAllowUserIds((updatedState.allowlist_user_ids || []).join(', '));
      setMaintenanceAllowEmails((updatedState.allowlist_emails || []).join(', '));
      success('Maintenance mode updated');
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to update maintenance mode';
      showError(message);
    } finally {
      setMaintenanceSaving(false);
    }
  };

  const handleUpsertFlag = async () => {
    const key = flagKey.trim();
    if (!key) {
      showError('Flag key is required');
      return;
    }
    if (flagScope === 'org' && !flagOrgId.trim()) {
      showError('Org ID is required for org-scoped flags');
      return;
    }
    if (flagScope === 'user' && !flagUserId.trim()) {
      showError('User ID is required for user-scoped flags');
      return;
    }
    const parsedOrgId = flagOrgId.trim() ? parsePositiveInt(flagOrgId) : undefined;
    const parsedUserId = flagUserId.trim() ? parsePositiveInt(flagUserId) : undefined;
    if (flagScope === 'org' && !parsedOrgId) {
      showError('Org ID must be a positive integer');
      return;
    }
    if (flagScope === 'user' && !parsedUserId) {
      showError('User ID must be a positive integer');
      return;
    }
    try {
      setFlagSaving(true);
      await api.upsertFeatureFlag(key, {
        scope: flagScope,
        enabled: flagEnabled,
        description: flagDescription,
        org_id: flagScope === 'org' ? parsedOrgId : undefined,
        user_id: flagScope === 'user' ? parsedUserId : undefined,
        note: flagNote,
      });
      success('Feature flag saved');
      setFlagKey('');
      setFlagDescription('');
      setFlagOrgId('');
      setFlagUserId('');
      setFlagNote('');
      await loadFlags();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to save feature flag';
      showError(message);
    } finally {
      setFlagSaving(false);
    }
  };

  const handleDeleteFlag = async (flag: FeatureFlagItem) => {
    const confirmed = await confirm({
      title: `Delete flag ${flag.key}?`,
      description: 'This removes the flag override for the selected scope.',
      confirmText: 'Delete',
      variant: 'destructive',
    });
    if (!confirmed) return;
    try {
      const params: Record<string, string> = { scope: flag.scope };
      if (flag.org_id !== null && flag.org_id !== undefined) {
        params.org_id = String(flag.org_id);
      }
      if (flag.user_id !== null && flag.user_id !== undefined) {
        params.user_id = String(flag.user_id);
      }
      await api.deleteFeatureFlag(flag.key, params);
      success('Feature flag deleted');
      await loadFlags();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to delete feature flag';
      showError(message);
    }
  };

  const isRefreshing = maintenanceLoading || flagLoading;

  return (
    <ProtectedRoute>
      <ResponsiveLayout>
        <div className="flex flex-col gap-6 p-6">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-bold">Flags & Maintenance</h1>
              <p className="text-muted-foreground">Control runtime switches and maintenance mode.</p>
            </div>
            <Button variant="outline" onClick={handleRefresh} disabled={isRefreshing}>
              <RefreshCw className={`mr-2 h-4 w-4 ${isRefreshing ? 'animate-spin' : ''}`} />
              Refresh
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Maintenance Mode</CardTitle>
              <CardDescription>Block non-allowlisted users with a custom message.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4 md:grid-cols-2">
              <div className="flex items-center gap-2">
                <Checkbox
                  checked={maintenanceEnabled}
                  onCheckedChange={(checked) => setMaintenanceEnabled(Boolean(checked))}
                  id="maintenance-enabled"
                />
                <Label htmlFor="maintenance-enabled">Enabled</Label>
                {maintenance?.updated_at && (
                  <Badge variant="outline" className="ml-2">
                    Updated {formatDate(maintenance.updated_at)}
                  </Badge>
                )}
              </div>
              <div className="space-y-1 md:col-span-2">
                <Label htmlFor="maintenance-message">Message</Label>
                <Input
                  id="maintenance-message"
                  placeholder="Maintenance in progress"
                  value={maintenanceMessage}
                  onChange={(e) => setMaintenanceMessage(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="maintenance-users">Allowlist User IDs</Label>
                <Input
                  id="maintenance-users"
                  placeholder="1, 2, 3"
                  value={maintenanceAllowUserIds}
                  onChange={(e) => setMaintenanceAllowUserIds(e.target.value)}
                />
              </div>
              <div className="space-y-1">
                <Label htmlFor="maintenance-emails">Allowlist Emails</Label>
                <Input
                  id="maintenance-emails"
                  placeholder="admin@example.com"
                  value={maintenanceAllowEmails}
                  onChange={(e) => setMaintenanceAllowEmails(e.target.value)}
                />
              </div>
              <div>
                <Button
                  onClick={handleSaveMaintenance}
                  disabled={maintenanceSaving || maintenanceLoading || !maintenance}
                >
                  {maintenanceSaving ? 'Saving...' : 'Save Maintenance'}
                </Button>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Feature Flags</CardTitle>
              <CardDescription>Manage feature overrides by scope.</CardDescription>
            </CardHeader>
            <CardContent className="grid gap-4">
              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-1">
                  <Label htmlFor="flag-scope-filter">Scope</Label>
                  <Select
                    id="flag-scope-filter"
                    value={flagScopeFilter}
                    onChange={(e) => setFlagScopeFilter(e.target.value)}
                  >
                    <option value="">All</option>
                    {FLAG_SCOPES.map((scope) => (
                      <option key={scope} value={scope}>
                        {scope}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="flag-org-filter">Org ID</Label>
                  <Input
                    id="flag-org-filter"
                    placeholder="optional"
                    value={flagOrgFilter}
                    onChange={(e) => setFlagOrgFilter(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="flag-user-filter">User ID</Label>
                  <Input
                    id="flag-user-filter"
                    placeholder="optional"
                    value={flagUserFilter}
                    onChange={(e) => setFlagUserFilter(e.target.value)}
                  />
                </div>
              </div>

              {flagError && (
                <Alert variant="destructive">
                  <AlertDescription>{flagError}</AlertDescription>
                </Alert>
              )}

              <div className="grid gap-4 md:grid-cols-3">
                <div className="space-y-1">
                  <Label htmlFor="flag-key">Flag Key</Label>
                  <Input
                    id="flag-key"
                    placeholder="claims.monitoring"
                    value={flagKey}
                    onChange={(e) => setFlagKey(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="flag-scope">Scope</Label>
                  <Select
                    id="flag-scope"
                    value={flagScope}
                    onChange={(e) => setFlagScope(e.target.value as typeof flagScope)}
                  >
                    {FLAG_SCOPES.map((scope) => (
                      <option key={scope} value={scope}>
                        {scope}
                      </option>
                    ))}
                  </Select>
                </div>
                <div className="flex items-center gap-2 pt-6">
                  <Checkbox
                    checked={flagEnabled}
                    onCheckedChange={(checked) => setFlagEnabled(Boolean(checked))}
                    id="flag-enabled"
                  />
                  <Label htmlFor="flag-enabled">Enabled</Label>
                </div>
                <div className="space-y-1">
                  <Label htmlFor="flag-org">Org ID (org scope)</Label>
                  <Input
                    id="flag-org"
                    placeholder="optional"
                    value={flagOrgId}
                    onChange={(e) => setFlagOrgId(e.target.value)}
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="flag-user">User ID (user scope)</Label>
                  <Input
                    id="flag-user"
                    placeholder="optional"
                    value={flagUserId}
                    onChange={(e) => setFlagUserId(e.target.value)}
                  />
                </div>
                <div className="space-y-1 md:col-span-3">
                  <Label htmlFor="flag-description">Description</Label>
                  <Input
                    id="flag-description"
                    placeholder="optional"
                    value={flagDescription}
                    onChange={(e) => setFlagDescription(e.target.value)}
                  />
                </div>
                <div className="space-y-1 md:col-span-3">
                  <Label htmlFor="flag-note">Change Note</Label>
                  <Input
                    id="flag-note"
                    placeholder="optional"
                    value={flagNote}
                    onChange={(e) => setFlagNote(e.target.value)}
                  />
                </div>
                <div>
                  <Button onClick={handleUpsertFlag} disabled={flagSaving}>
                    {flagSaving ? 'Saving...' : 'Save Flag'}
                  </Button>
                </div>
              </div>

              {flagLoading ? (
                <div className="py-8 text-center text-muted-foreground">Loading flags...</div>
              ) : flags.length === 0 ? (
                <div className="py-8 text-center text-muted-foreground">No flags found.</div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Key</TableHead>
                      <TableHead>Scope</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Target</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead>History</TableHead>
                      <TableHead></TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {flags.map((flag, index) => {
                      const hasStableFields =
                        Boolean(flag.key) ||
                        Boolean(flag.scope) ||
                        flag.org_id !== undefined ||
                        flag.user_id !== undefined;
                      const rowKey =
                        flag.id !== null && flag.id !== undefined
                          ? `flag-${flag.id}`
                          : hasStableFields
                            ? JSON.stringify([
                                flag.key,
                                flag.scope,
                                flag.org_id ?? 'NULL',
                                flag.user_id ?? 'NULL',
                              ])
                            : `flag-index-${index}`;
                      return (
                        <TableRow key={rowKey}>
                          <TableCell className="font-medium">{flag.key}</TableCell>
                          <TableCell>{flag.scope}</TableCell>
                          <TableCell>
                            <Badge variant={flag.enabled ? 'default' : 'outline'}>
                              {flag.enabled ? 'Enabled' : 'Disabled'}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            {flag.scope === 'global'
                              ? 'Global'
                              : flag.scope === 'org'
                                ? `Org ${flag.org_id}`
                                : `User ${flag.user_id}`}
                          </TableCell>
                          <TableCell>{formatDate(flag.updated_at)}</TableCell>
                          <TableCell>
                            <details className="text-xs text-muted-foreground">
                              <summary className="cursor-pointer">
                                {flag.history?.length || 0} changes
                              </summary>
                              <div className="mt-2 space-y-2">
                                {(flag.history || []).map((entry, entryIndex) => (
                                  <div key={`${flag.key}-history-${entryIndex}`}>
                                    <div className="font-medium text-foreground">
                                      {entry.enabled ? 'Enabled' : 'Disabled'}
                                    </div>
                                    <div>
                                      {formatDate(entry.timestamp)}{' '}
                                      {entry.actor ? `· ${entry.actor}` : ''}
                                    </div>
                                    {entry.note ? <div>Note: {entry.note}</div> : null}
                                  </div>
                                ))}
                              </div>
                            </details>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDeleteFlag(flag)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })}
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
