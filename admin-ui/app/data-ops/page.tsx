'use client';

import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import ProtectedRoute from '@/components/ProtectedRoute';
import { ResponsiveLayout } from '@/components/ResponsiveLayout';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Label } from '@/components/ui/label';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { useToast } from '@/components/ui/toast';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { api } from '@/lib/api-client';
import { useUrlPagination } from '@/lib/use-url-state';
import { useOrgContext } from '@/components/OrgContextSwitcher';
import { getAuthHeaders } from '@/lib/auth';
import type { BackupItem, RetentionPolicy } from '@/types';
import { Download, RefreshCw, Database, ShieldCheck, AlertTriangle } from 'lucide-react';

const DATASET_OPTIONS = [
  { value: 'media', label: 'Media DB' },
  { value: 'chacha', label: 'Notes/Chats DB' },
  { value: 'prompts', label: 'Prompts DB' },
  { value: 'evaluations', label: 'Evaluations DB' },
  { value: 'audit', label: 'Unified Audit DB' },
  { value: 'authnz', label: 'AuthNZ Users DB' },
];

const BACKUP_TYPES = [
  { value: 'full', label: 'Full' },
  { value: 'incremental', label: 'Incremental' },
];

const EXPORT_FORMATS = [
  { value: 'csv', label: 'CSV' },
  { value: 'json', label: 'JSON' },
];

const API_HOST = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';
const API_VERSION = process.env.NEXT_PUBLIC_API_VERSION || 'v1';
const API_URL = `${API_HOST.replace(/\/$/, '')}/api/${API_VERSION}`;

const Field = ({ id, label, children }: { id: string; label: string; children: ReactNode }) => (
  <div className="space-y-1">
    <Label htmlFor={id} className="text-xs uppercase text-muted-foreground">
      {label}
    </Label>
    {children}
  </div>
);

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

const formatDate = (value?: string | null) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString();
};

const splitDispositionParts = (value: string) => {
  const parts: string[] = [];
  let current = '';
  let inQuotes = false;
  for (let i = 0; i < value.length; i += 1) {
    const char = value[i];
    if (char === '"' && value[i - 1] !== '\\') {
      inQuotes = !inQuotes;
    }
    if (char === ';' && !inQuotes) {
      const trimmed = current.trim();
      if (trimmed) {
        parts.push(trimmed);
      }
      current = '';
      continue;
    }
    current += char;
  }
  const trimmed = current.trim();
  if (trimmed) {
    parts.push(trimmed);
  }
  return parts;
};

const unquoteHeaderValue = (value: string) => {
  if (value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1).replace(/\\(.)/g, '$1');
  }
  return value;
};

const decode5987Value = (value: string) => {
  const raw = unquoteHeaderValue(value);
  const match = raw.match(/^([^']*)'[^']*'(.*)$/);
  const encoded = match ? match[2] : raw;
  try {
    return decodeURIComponent(encoded);
  } catch {
    return encoded;
  }
};

const getFilenameFromDisposition = (disposition: string | null): string | null => {
  if (!disposition) return null;
  const parts = splitDispositionParts(disposition);
  const params: Record<string, string> = {};
  for (const part of parts.slice(1)) {
    const eqIndex = part.indexOf('=');
    if (eqIndex === -1) continue;
    const key = part.slice(0, eqIndex).trim().toLowerCase();
    if (!key) continue;
    const rawValue = part.slice(eqIndex + 1).trim();
    if (!rawValue) continue;
    params[key] = unquoteHeaderValue(rawValue);
  }
  if (params['filename*']) {
    const decoded = decode5987Value(params['filename*']);
    if (decoded) return decoded;
  }
  return params.filename || null;
};

const downloadExport = async (
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
    throw new Error(message || 'Failed to download export');
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

export default function DataOpsPage() {
  const { selectedOrg } = useOrgContext();
  const { page, pageSize, setPage, setPageSize, resetPagination } = useUrlPagination();
  const { success, error: showError } = useToast();
  const confirm = useConfirm();

  const [backups, setBackups] = useState<BackupItem[]>([]);
  const [backupTotal, setBackupTotal] = useState(0);
  const [backupLoading, setBackupLoading] = useState(true);
  const [backupError, setBackupError] = useState('');

  const [listDataset, setListDataset] = useState('');
  const [listUserId, setListUserId] = useState('');

  const [createDataset, setCreateDataset] = useState('media');
  const [createUserId, setCreateUserId] = useState('');
  const [backupType, setBackupType] = useState('full');
  const [maxBackups, setMaxBackups] = useState('');
  const [creatingBackup, setCreatingBackup] = useState(false);
  const [restoreBusyId, setRestoreBusyId] = useState<string | null>(null);

  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [policyError, setPolicyError] = useState('');
  const [policyLoading, setPolicyLoading] = useState(true);
  const [policyEdits, setPolicyEdits] = useState<Record<string, string>>({});
  const [policySaving, setPolicySaving] = useState<Record<string, boolean>>({});

  const [auditExporting, setAuditExporting] = useState(false);
  const [userExporting, setUserExporting] = useState(false);
  const [auditStart, setAuditStart] = useState('');
  const [auditEnd, setAuditEnd] = useState('');
  const [auditAction, setAuditAction] = useState('');
  const [auditUserId, setAuditUserId] = useState('');
  const [auditResource, setAuditResource] = useState('');
  const [auditFormat, setAuditFormat] = useState('csv');

  const [userSearch, setUserSearch] = useState('');
  const [userRole, setUserRole] = useState('');
  const [userStatus, setUserStatus] = useState('');
  const [userFormat, setUserFormat] = useState('csv');

  const backupParams = useMemo(() => {
    const params: Record<string, string> = {
      limit: String(pageSize),
      offset: String(Math.max(0, (page - 1) * pageSize)),
    };
    if (listDataset) params.dataset = listDataset;
    if (listUserId) params.user_id = listUserId;
    return params;
  }, [listDataset, listUserId, page, pageSize]);

  const loadBackups = useCallback(async () => {
    try {
      setBackupLoading(true);
      setBackupError('');
      const data = await api.getBackups(backupParams);
      setBackups(data.items);
      setBackupTotal(data.total);
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to load backups';
      setBackupError(message);
      setBackups([]);
      setBackupTotal(0);
    } finally {
      setBackupLoading(false);
    }
  }, [backupParams]);

  const loadPolicies = useCallback(async () => {
    try {
      setPolicyLoading(true);
      setPolicyError('');
      const data = await api.getRetentionPolicies();
      setPolicies(data.policies);
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to load retention policies';
      setPolicyError(message);
      setPolicies([]);
    } finally {
      setPolicyLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadBackups();
  }, [loadBackups]);

  useEffect(() => {
    void loadPolicies();
  }, [loadPolicies]);

  const handleBackupFilterChange = (key: 'dataset' | 'user', value: string) => {
    if (key === 'dataset') {
      setListDataset(value);
    } else {
      setListUserId(value);
    }
    resetPagination();
  };

  const handleCreateBackup = async () => {
    const payload: Record<string, unknown> = {
      dataset: createDataset,
      backup_type: backupType,
    };
    if (createUserId.trim()) {
      const parsed = Number(createUserId);
      if (!Number.isFinite(parsed)) {
        showError('Invalid user id', 'User id must be numeric.');
        return;
      }
      payload.user_id = parsed;
    }
    if (maxBackups.trim()) {
      const parsed = Number(maxBackups);
      if (!Number.isFinite(parsed)) {
        showError('Invalid max backups', 'Max backups must be numeric.');
        return;
      }
      payload.max_backups = parsed;
    }

    try {
      setCreatingBackup(true);
      await api.createBackup(payload);
      success('Backup created', 'Snapshot created successfully.');
      await loadBackups();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to create backup';
      showError('Backup failed', message);
    } finally {
      setCreatingBackup(false);
    }
  };

  const handleRestoreBackup = async (backup: BackupItem) => {
    const accepted = await confirm({
      title: 'Restore backup?',
      message: `Restore ${backup.dataset} from ${backup.id}? This overwrites the current dataset.`,
      confirmText: 'Restore',
      variant: 'danger',
      icon: 'warning',
    });
    if (!accepted) return;

    try {
      setRestoreBusyId(backup.id);
      await api.restoreBackup(backup.id, {
        dataset: backup.dataset,
        user_id: backup.user_id ?? undefined,
        confirm: true,
      });
      success('Restore complete', 'Backup restored successfully.');
      await loadBackups();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to restore backup';
      showError('Restore failed', message);
    } finally {
      setRestoreBusyId(null);
    }
  };

  const handlePolicyUpdate = async (policy: RetentionPolicy) => {
    const raw = policyEdits[policy.key] ?? '';
    if (!raw.trim()) {
      showError('Invalid value', 'Retention days cannot be empty.');
      return;
    }
    const value = Number(raw.trim());
    if (!Number.isFinite(value) || value < 1) {
      showError('Invalid value', 'Retention days must be a positive number.');
      return;
    }
    const accepted = await confirm({
      title: 'Apply retention policy change?',
      message: 'This update applies immediately and persists across restarts. Review retention windows before saving.',
      confirmText: 'Apply',
      variant: 'warning',
      icon: 'warning',
    });
    if (!accepted) return;
    setPolicySaving((prev) => ({ ...prev, [policy.key]: true }));
    try {
      await api.updateRetentionPolicy(policy.key, { days: Number(value) });
      success('Retention updated', `${policy.key} set to ${value} days.`);
      setPolicyEdits((prev) => {
        const next = { ...prev };
        delete next[policy.key];
        return next;
      });
      await loadPolicies();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to update retention policy';
      showError('Update failed', message);
    } finally {
      setPolicySaving((prev) => ({ ...prev, [policy.key]: false }));
    }
  };

  const handleAuditExport = async () => {
    try {
      setAuditExporting(true);
      const params: Record<string, string> = { format: auditFormat };
      if (auditStart) params.start = auditStart;
      if (auditEnd) params.end = auditEnd;
      if (auditAction.trim()) params.action = auditAction.trim();
      if (auditUserId.trim()) params.user_id = auditUserId.trim();
      if (auditResource.trim()) params.resource = auditResource.trim();
      if (selectedOrg) params.org_id = String(selectedOrg.id);
      const filename = `audit_log.${auditFormat}`;
      await downloadExport('/admin/audit-log/export', params, filename);
      success('Export ready', 'Audit log download started.');
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to export audit logs';
      showError('Export failed', message);
    } finally {
      setAuditExporting(false);
    }
  };

  const handleUserExport = async () => {
    try {
      setUserExporting(true);
      const params: Record<string, string> = { format: userFormat };
      if (userSearch.trim()) params.search = userSearch.trim();
      if (userRole.trim()) params.role = userRole.trim();
      if (userStatus.trim()) params.is_active = userStatus.trim();
      if (selectedOrg) params.org_id = String(selectedOrg.id);
      const filename = `users.${userFormat}`;
      await downloadExport('/admin/users/export', params, filename);
      success('Export ready', 'User export download started.');
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to export users';
      showError('Export failed', message);
    } finally {
      setUserExporting(false);
    }
  };

  const totalPages = Math.max(1, Math.ceil(backupTotal / pageSize));

  return (
    <ProtectedRoute requiredRoles={['admin', 'super_admin', 'owner']}>
      <ResponsiveLayout>
        <div className="p-6 space-y-6">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-2xl font-bold">Data Ops</h2>
              <p className="text-muted-foreground">Backups, retention, and export tools.</p>
            </div>
            <Button variant="outline" onClick={() => { loadBackups(); loadPolicies(); }}>
              <RefreshCw className="h-4 w-4 mr-2" />
              Refresh
            </Button>
          </div>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                Backups
              </CardTitle>
              <CardDescription>Create, browse, and restore backup snapshots.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-3 md:grid-cols-4">
                <Field id="backup-filter-dataset" label="Dataset filter">
                  <Select
                    id="backup-filter-dataset"
                    value={listDataset}
                    onChange={(event) => handleBackupFilterChange('dataset', event.target.value)}
                  >
                    <option value="">All datasets</option>
                    {DATASET_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field id="backup-filter-user" label="User ID filter">
                  <Input
                    id="backup-filter-user"
                    placeholder="Optional"
                    value={listUserId}
                    onChange={(event) => handleBackupFilterChange('user', event.target.value)}
                  />
                </Field>
                <div className="flex items-end">
                  <Button variant="outline" onClick={loadBackups} disabled={backupLoading}>
                    Refresh list
                  </Button>
                </div>
              </div>

              <div className="grid gap-3 md:grid-cols-5">
                <Field id="backup-create-dataset" label="Dataset">
                  <Select
                    id="backup-create-dataset"
                    value={createDataset}
                    onChange={(event) => setCreateDataset(event.target.value)}
                  >
                    {DATASET_OPTIONS.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field id="backup-create-user" label="User ID">
                  <Input
                    id="backup-create-user"
                    placeholder="Optional"
                    value={createUserId}
                    onChange={(event) => setCreateUserId(event.target.value)}
                  />
                </Field>
                <Field id="backup-create-type" label="Type">
                  <Select
                    id="backup-create-type"
                    value={backupType}
                    onChange={(event) => setBackupType(event.target.value)}
                  >
                    {BACKUP_TYPES.map((option) => (
                      <option key={option.value} value={option.value}>
                        {option.label}
                      </option>
                    ))}
                  </Select>
                </Field>
                <Field id="backup-create-max" label="Max backups">
                  <Input
                    id="backup-create-max"
                    placeholder="Optional"
                    value={maxBackups}
                    onChange={(event) => setMaxBackups(event.target.value)}
                  />
                </Field>
                <div className="flex items-end">
                  <Button onClick={handleCreateBackup} disabled={creatingBackup}>
                    {creatingBackup ? 'Creating...' : 'Create backup'}
                  </Button>
                </div>
              </div>

              {backupError && (
                <Alert variant="destructive">
                  <AlertDescription>{backupError}</AlertDescription>
                </Alert>
              )}

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>ID</TableHead>
                    <TableHead>Dataset</TableHead>
                    <TableHead>User</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Size</TableHead>
                    <TableHead>Created</TableHead>
                    <TableHead className="text-right">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {backupLoading ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-muted-foreground">
                        Loading backups...
                      </TableCell>
                    </TableRow>
                  ) : backups.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={7} className="text-muted-foreground">
                        No backups found.
                      </TableCell>
                    </TableRow>
                  ) : (
                    backups.map((backup) => (
                      <TableRow key={backup.id}>
                        <TableCell className="font-mono text-xs">{backup.id}</TableCell>
                        <TableCell>{backup.dataset}</TableCell>
                        <TableCell>{backup.user_id ?? '—'}</TableCell>
                        <TableCell>
                          <Badge variant={backup.status === 'ready' ? 'default' : 'secondary'}>
                            {backup.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{formatBytes(backup.size_bytes)}</TableCell>
                        <TableCell>{formatDate(backup.created_at)}</TableCell>
                        <TableCell className="text-right">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRestoreBackup(backup)}
                            disabled={restoreBusyId === backup.id}
                          >
                            {restoreBusyId === backup.id ? 'Restoring...' : 'Restore'}
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))
                  )}
                </TableBody>
              </Table>

              <Pagination
                currentPage={page}
                totalPages={totalPages}
                totalItems={backupTotal}
                pageSize={pageSize}
                onPageChange={setPage}
                onPageSizeChange={setPageSize}
              />
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <ShieldCheck className="h-5 w-5" />
                Retention Policies
              </CardTitle>
              <CardDescription>Adjust cleanup windows for system datasets.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {policyError && (
                <Alert variant="destructive">
                  <AlertDescription>{policyError}</AlertDescription>
                </Alert>
              )}
              <Alert className="bg-yellow-50 border-yellow-200">
                <AlertTriangle className="h-4 w-4 text-yellow-600" />
                <AlertDescription className="text-yellow-800">
                  Retention policy changes apply immediately and persist across restarts. Lower values can delete data
                  sooner than expected, so review carefully before saving.
                </AlertDescription>
              </Alert>

              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Policy</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Days</TableHead>
                    <TableHead className="text-right">Action</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {policyLoading ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-muted-foreground">
                        Loading retention policies...
                      </TableCell>
                    </TableRow>
                  ) : policies.length === 0 ? (
                    <TableRow>
                      <TableCell colSpan={4} className="text-muted-foreground">
                        No retention policies found.
                      </TableCell>
                    </TableRow>
                  ) : (
                    policies.map((policy) => {
                      const draft = policyEdits[policy.key];
                      const value = draft ?? (policy.days?.toString() ?? '');
                      return (
                        <TableRow key={policy.key}>
                          <TableCell className="font-mono text-xs">{policy.key}</TableCell>
                          <TableCell>{policy.description || '—'}</TableCell>
                          <TableCell className="w-40">
                            <Input
                              value={value}
                              onChange={(event) =>
                                setPolicyEdits((prev) => ({ ...prev, [policy.key]: event.target.value }))
                              }
                            />
                          </TableCell>
                          <TableCell className="text-right">
                            <Button
                              size="sm"
                              onClick={() => handlePolicyUpdate(policy)}
                              disabled={policySaving[policy.key]}
                            >
                              {policySaving[policy.key] ? 'Saving...' : 'Save'}
                            </Button>
                          </TableCell>
                        </TableRow>
                      );
                    })
                  )}
                </TableBody>
              </Table>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Download className="h-5 w-5" />
                Exports
              </CardTitle>
              <CardDescription>Server-side exports for audit logs and users.</CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <div className="grid gap-4 md:grid-cols-2">
                <div className="space-y-3 rounded-lg border p-4">
                  <div>
                    <h4 className="font-semibold">Audit Log Export</h4>
                    <p className="text-sm text-muted-foreground">Filter and download audit events.</p>
                  </div>
                  <div className="grid gap-2 md:grid-cols-2">
                    <Field id="audit-start" label="Start (YYYY-MM-DD)">
                      <Input
                        id="audit-start"
                        type="date"
                        value={auditStart}
                        onChange={(e) => setAuditStart(e.target.value)}
                      />
                    </Field>
                    <Field id="audit-end" label="End (YYYY-MM-DD)">
                      <Input
                        id="audit-end"
                        type="date"
                        value={auditEnd}
                        onChange={(e) => setAuditEnd(e.target.value)}
                      />
                    </Field>
                    <Field id="audit-action" label="Action">
                      <Input id="audit-action" value={auditAction} onChange={(e) => setAuditAction(e.target.value)} />
                    </Field>
                    <Field id="audit-user" label="User ID">
                      <Input id="audit-user" value={auditUserId} onChange={(e) => setAuditUserId(e.target.value)} />
                    </Field>
                    <Field id="audit-resource" label="Resource">
                      <Input id="audit-resource" value={auditResource} onChange={(e) => setAuditResource(e.target.value)} />
                    </Field>
                    <Field id="audit-format" label="Format">
                      <Select
                        id="audit-format"
                        value={auditFormat}
                        onChange={(event) => setAuditFormat(event.target.value)}
                      >
                        {EXPORT_FORMATS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                  <Button onClick={handleAuditExport} disabled={auditExporting}>
                    {auditExporting ? 'Exporting...' : 'Download audit logs'}
                  </Button>
                </div>

                <div className="space-y-3 rounded-lg border p-4">
                  <div>
                    <h4 className="font-semibold">User Export</h4>
                    <p className="text-sm text-muted-foreground">Download user list snapshots.</p>
                  </div>
                  <div className="grid gap-2 md:grid-cols-2">
                    <Field id="users-search" label="Search">
                      <Input id="users-search" value={userSearch} onChange={(e) => setUserSearch(e.target.value)} />
                    </Field>
                    <Field id="users-role" label="Role">
                      <Input id="users-role" value={userRole} onChange={(e) => setUserRole(e.target.value)} />
                    </Field>
                    <Field id="users-active" label="Active">
                      <Select
                        id="users-active"
                        value={userStatus}
                        onChange={(event) => setUserStatus(event.target.value)}
                      >
                        <option value="">All</option>
                        <option value="true">Active</option>
                        <option value="false">Inactive</option>
                      </Select>
                    </Field>
                    <Field id="users-format" label="Format">
                      <Select
                        id="users-format"
                        value={userFormat}
                        onChange={(event) => setUserFormat(event.target.value)}
                      >
                        {EXPORT_FORMATS.map((option) => (
                          <option key={option.value} value={option.value}>
                            {option.label}
                          </option>
                        ))}
                      </Select>
                    </Field>
                  </div>
                  <Button onClick={handleUserExport} disabled={userExporting}>
                    {userExporting ? 'Exporting...' : 'Download users'}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </ResponsiveLayout>
    </ProtectedRoute>
  );
}
