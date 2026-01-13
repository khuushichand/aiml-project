import { useCallback, useEffect, useMemo, useState } from 'react';
import Link from 'next/link';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { ConfirmDialog } from '@/components/ui/ConfirmDialog';
import { Input } from '@/components/ui/Input';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient, buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useIsAdmin } from '@/hooks/useIsAdmin';

type BackupDataset = 'media' | 'chacha' | 'prompts' | 'evaluations' | 'audit' | 'authnz';

interface BackupItem {
  id: string;
  dataset: BackupDataset;
  user_id?: number | null;
  status: string;
  size_bytes: number;
  created_at: string;
}

interface BackupListResponse {
  items: BackupItem[];
  total: number;
  limit: number;
  offset: number;
}

interface BackupCreateResponse {
  item: BackupItem;
}

interface RetentionPolicy {
  key: string;
  days?: number | null;
  description?: string | null;
}

interface RetentionPoliciesResponse {
  policies: RetentionPolicy[];
}

const BACKUP_DATASETS: { value: BackupDataset; label: string; perUser: boolean }[] = [
  { value: 'media', label: 'Media DB (media)', perUser: true },
  { value: 'chacha', label: 'ChaChaNotes (chacha)', perUser: true },
  { value: 'prompts', label: 'Prompts DB (prompts)', perUser: true },
  { value: 'evaluations', label: 'Evaluations DB (evaluations)', perUser: true },
  { value: 'audit', label: 'Unified Audit DB (audit)', perUser: true },
  { value: 'authnz', label: 'AuthNZ Users (authnz)', perUser: false },
];

const PER_USER_DATASETS = new Set(BACKUP_DATASETS.filter((d) => d.perUser).map((d) => d.value));

const formatBytes = (value: number) => {
  if (!Number.isFinite(value)) return '-';
  if (value < 1024) return `${value} B`;
  const units = ['KB', 'MB', 'GB', 'TB'];
  let size = value / 1024;
  let unitIndex = 0;
  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }
  return `${size.toFixed(size < 10 ? 1 : 0)} ${units[unitIndex]}`;
};

const parseOptionalInt = (value: string) => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  if (!Number.isFinite(parsed)) return undefined;
  return Math.trunc(parsed);
};

const getFilenameFromDisposition = (header: string | null) => {
  if (!header) return null;
  const match = /filename=\"([^\"]+)\"/i.exec(header);
  if (match?.[1]) return match[1];
  const fallback = /filename=([^;]+)/i.exec(header);
  if (fallback?.[1]) return fallback[1].trim();
  return null;
};

export default function AdminDataOpsPage() {
  const { show } = useToast();
  const isAdmin = useIsAdmin();
  const base = getApiBaseUrl();

  const [listDataset, setListDataset] = useState<string>('authnz');
  const [listUserId, setListUserId] = useState<string>('');
  const [listLimit, setListLimit] = useState<string>('100');
  const [listOffset, setListOffset] = useState<string>('0');
  const [backupItems, setBackupItems] = useState<BackupItem[]>([]);
  const [backupTotal, setBackupTotal] = useState<number>(0);
  const [backupsLoading, setBackupsLoading] = useState(false);

  const [createDataset, setCreateDataset] = useState<BackupDataset>('media');
  const [createUserId, setCreateUserId] = useState<string>('');
  const [backupType, setBackupType] = useState<'full' | 'incremental'>('full');
  const [maxBackups, setMaxBackups] = useState<string>('');
  const [createBusy, setCreateBusy] = useState(false);

  const [policies, setPolicies] = useState<RetentionPolicy[]>([]);
  const [policyDrafts, setPolicyDrafts] = useState<Record<string, string>>({});
  const [policyBusy, setPolicyBusy] = useState<string | null>(null);

  const [confirmRestore, setConfirmRestore] = useState<BackupItem | null>(null);
  const [confirmRetention, setConfirmRetention] = useState<{ key: string; days: number } | null>(null);
  const [exportBusy, setExportBusy] = useState<string | null>(null);

  const [auditDays, setAuditDays] = useState<string>('30');
  const [auditLimit, setAuditLimit] = useState<string>('10000');
  const [auditFormat, setAuditFormat] = useState<'csv' | 'json'>('csv');
  const [usersLimit, setUsersLimit] = useState<string>('10000');
  const [usersFormat, setUsersFormat] = useState<'csv' | 'json'>('csv');

  const listRequiresUser = useMemo(() => PER_USER_DATASETS.has(listDataset as BackupDataset), [listDataset]);
  const createRequiresUser = useMemo(() => PER_USER_DATASETS.has(createDataset), [createDataset]);

  const resolveUrl = (path: string, params?: Record<string, string | number | undefined>) => {
    const normalizedBase = base.endsWith('/') ? base : `${base}/`;
    const normalizedPath = path.startsWith('/') ? path.slice(1) : path;
    const url = new URL(normalizedPath, normalizedBase);
    if (params) {
      Object.entries(params).forEach(([key, value]) => {
        if (value === undefined || value === null || value === '') return;
        url.searchParams.set(key, String(value));
      });
    }
    return url.toString();
  };

  const fetchBackups = useCallback(async () => {
    if (listRequiresUser && !listUserId.trim()) {
      show({ title: 'User ID required', description: 'Provide a user id for per-user datasets.', variant: 'warning' });
      return;
    }
    setBackupsLoading(true);
    try {
      const params: Record<string, unknown> = {};
      if (listDataset && listDataset !== 'all') params.dataset = listDataset;
      const userIdNum = parseOptionalInt(listUserId);
      if (userIdNum) params.user_id = userIdNum;
      const limitNum = parseOptionalInt(listLimit);
      const offsetNum = parseOptionalInt(listOffset);
      if (limitNum) params.limit = limitNum;
      if (offsetNum !== undefined) params.offset = Math.max(0, offsetNum);

      const data = await apiClient.get<BackupListResponse>('/admin/backups', { params });
      setBackupItems(Array.isArray(data?.items) ? data.items : []);
      setBackupTotal(Number.isFinite(data?.total) ? data.total : 0);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setBackupItems([]);
      setBackupTotal(0);
      show({ title: 'Failed to load backups', description: message, variant: 'danger' });
    } finally {
      setBackupsLoading(false);
    }
  }, [listDataset, listLimit, listOffset, listRequiresUser, listUserId, show]);

  const fetchRetentionPolicies = useCallback(async () => {
    setPolicyBusy('loading');
    try {
      const data = await apiClient.get<RetentionPoliciesResponse>('/admin/retention-policies');
      const nextPolicies = Array.isArray(data?.policies) ? data.policies : [];
      setPolicies(nextPolicies);
      const drafts: Record<string, string> = {};
      nextPolicies.forEach((policy) => {
        drafts[policy.key] = policy.days !== undefined && policy.days !== null ? String(policy.days) : '';
      });
      setPolicyDrafts(drafts);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Failed to load retention policies', description: message, variant: 'danger' });
      setPolicies([]);
    } finally {
      setPolicyBusy(null);
    }
  }, [show]);

  useEffect(() => {
    if (!isAdmin) return;
    void fetchRetentionPolicies();
    void fetchBackups();
  }, [fetchBackups, fetchRetentionPolicies, isAdmin]);

  const handleCreateBackup = async () => {
    if (createRequiresUser && !createUserId.trim()) {
      show({ title: 'User ID required', description: 'Provide a user id for per-user datasets.', variant: 'warning' });
      return;
    }
    const userIdNum = parseOptionalInt(createUserId);
    if (createRequiresUser && (!userIdNum || userIdNum <= 0)) {
      show({ title: 'Invalid user id', description: 'Enter a positive integer user id.', variant: 'warning' });
      return;
    }
    const maxBackupsNum = parseOptionalInt(maxBackups);
    setCreateBusy(true);
    try {
      const payload: Record<string, unknown> = {
        dataset: createDataset,
        backup_type: backupType,
      };
      if (userIdNum) payload.user_id = userIdNum;
      if (maxBackupsNum) payload.max_backups = maxBackupsNum;

      const data = await apiClient.post<BackupCreateResponse>('/admin/backups', payload);
      if (data?.item) {
        show({ title: 'Backup created', description: data.item.id, variant: 'success' });
        void fetchBackups();
      }
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Backup failed', description: message, variant: 'danger' });
    } finally {
      setCreateBusy(false);
    }
  };

  const handleRestoreBackup = async (item: BackupItem) => {
    setConfirmRestore(item);
  };

  const confirmRestoreBackup = async () => {
    if (!confirmRestore) return;
    const item = confirmRestore;
    setConfirmRestore(null);
    try {
      const payload: Record<string, unknown> = {
        dataset: item.dataset,
        confirm: true,
      };
      if (item.user_id) payload.user_id = item.user_id;
      await apiClient.post(`/admin/backups/${encodeURIComponent(item.id)}/restore`, payload);
      show({ title: 'Backup restored', description: item.id, variant: 'success' });
      void fetchBackups();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Restore failed', description: message, variant: 'danger' });
    }
  };

  const handleRetentionUpdate = (policy: RetentionPolicy) => {
    const draft = policyDrafts[policy.key] ?? '';
    const days = parseOptionalInt(draft);
    if (!days || days <= 0) {
      show({ title: 'Invalid retention value', description: 'Enter a positive number of days.', variant: 'warning' });
      return;
    }
    setConfirmRetention({ key: policy.key, days });
  };

  const confirmRetentionUpdate = async () => {
    if (!confirmRetention) return;
    const { key, days } = confirmRetention;
    setConfirmRetention(null);
    setPolicyBusy(key);
    try {
      const updated = await apiClient.put<RetentionPolicy>(`/admin/retention-policies/${encodeURIComponent(key)}`, { days });
      setPolicies((prev) => prev.map((policy) => (policy.key === key ? updated : policy)));
      setPolicyDrafts((prev) => ({ ...prev, [key]: String(updated.days ?? days) }));
      show({ title: 'Retention updated', description: `${key} -> ${days} days`, variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Retention update failed', description: message, variant: 'danger' });
    } finally {
      setPolicyBusy(null);
    }
  };

  const downloadExport = async (label: string, path: string, params: Record<string, string | number | undefined>, fallbackName: string) => {
    setExportBusy(label);
    try {
      const url = resolveUrl(path, params);
      const resp = await fetch(url, { headers: buildAuthHeaders('GET') });
      if (!resp.ok) {
        const text = await resp.text();
        throw new Error(text || `${resp.status} ${resp.statusText}`);
      }
      const blob = await resp.blob();
      const filename = getFilenameFromDisposition(resp.headers.get('Content-Disposition')) || fallbackName;
      const link = document.createElement('a');
      const blobUrl = URL.createObjectURL(blob);
      link.href = blobUrl;
      link.download = filename;
      document.body.appendChild(link);
      link.click();
      link.remove();
      URL.revokeObjectURL(blobUrl);
      show({ title: 'Export ready', description: filename, variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Export failed', description: message, variant: 'danger' });
    } finally {
      setExportBusy(null);
    }
  };

  if (!isAdmin) {
    return (
      <Layout>
        <div className="mx-auto max-w-3xl">
          <h1 className="mb-4 text-2xl font-bold text-gray-900">Admin Data Ops</h1>
          <div className="rounded-md border bg-white p-4 text-sm text-gray-700">Admin access required.</div>
        </div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <div>
            <h1 className="text-2xl font-semibold text-gray-800">Admin Data Ops</h1>
            <p className="mt-1 text-sm text-gray-600">Backups, retention policies, and admin exports.</p>
          </div>
          <Link href="/admin" className="text-sm text-blue-600 hover:underline">
            Back to Admin
          </Link>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-md border bg-white p-4">
            <div className="mb-2 text-lg font-semibold text-gray-800">Create Backup</div>
            <p className="mb-4 text-sm text-gray-600">Create a backup snapshot for a dataset.</p>
            <div className="space-y-3">
              <label className="block text-sm text-gray-700">
                Dataset
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                  value={createDataset}
                  onChange={(e) => setCreateDataset(e.target.value as BackupDataset)}
                >
                  {BACKUP_DATASETS.map((dataset) => (
                    <option key={dataset.value} value={dataset.value}>{dataset.label}</option>
                  ))}
                </select>
              </label>
              <Input
                label="User ID"
                value={createUserId}
                onChange={(e) => setCreateUserId(e.target.value.replace(/[^0-9]/g, ''))}
                placeholder={createRequiresUser ? 'Required for per-user datasets' : 'Optional for authnz'}
                inputMode="numeric"
              />
              <div className="flex flex-wrap items-center gap-3">
                <label className="flex flex-col text-sm text-gray-700">
                  Backup Type
                  <select
                    className="mt-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                    value={backupType}
                    onChange={(e) => setBackupType(e.target.value as 'full' | 'incremental')}
                  >
                    <option value="full">full</option>
                    <option value="incremental">incremental</option>
                  </select>
                </label>
                <Input
                  label="Max Backups"
                  value={maxBackups}
                  onChange={(e) => setMaxBackups(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="Optional"
                  inputMode="numeric"
                />
              </div>
              <Button onClick={handleCreateBackup} disabled={createBusy}>
                {createBusy ? 'Creating…' : 'Create Backup'}
              </Button>
              {createRequiresUser && (
                <div className="text-xs text-gray-500">User ID is required for per-user datasets.</div>
              )}
            </div>
          </div>

          <div className="rounded-md border bg-white p-4">
            <div className="mb-2 text-lg font-semibold text-gray-800">Backups</div>
            <p className="mb-4 text-sm text-gray-600">List and restore backups for a dataset.</p>
            <div className="space-y-3">
              <label className="block text-sm text-gray-700">
                Dataset
                <select
                  className="mt-1 w-full rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                  value={listDataset}
                  onChange={(e) => setListDataset(e.target.value)}
                >
                  <option value="all">All datasets</option>
                  {BACKUP_DATASETS.map((dataset) => (
                    <option key={dataset.value} value={dataset.value}>{dataset.label}</option>
                  ))}
                </select>
              </label>
              <div className="grid gap-2 md:grid-cols-2">
                <Input
                  label="User ID"
                  value={listUserId}
                  onChange={(e) => setListUserId(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder={listRequiresUser ? 'Required for per-user datasets' : 'Optional'}
                  inputMode="numeric"
                />
                <Input
                  label="Limit"
                  value={listLimit}
                  onChange={(e) => setListLimit(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="100"
                  inputMode="numeric"
                />
                <Input
                  label="Offset"
                  value={listOffset}
                  onChange={(e) => setListOffset(e.target.value.replace(/[^0-9]/g, ''))}
                  placeholder="0"
                  inputMode="numeric"
                />
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <Button variant="secondary" onClick={fetchBackups} disabled={backupsLoading}>
                  {backupsLoading ? 'Loading…' : 'Load Backups'}
                </Button>
                <span className="text-xs text-gray-500">Total: {backupTotal}</span>
              </div>
              {listRequiresUser && (
                <div className="text-xs text-gray-500">User ID is required for per-user datasets.</div>
              )}
              <div className="max-h-64 overflow-auto rounded-md border border-gray-200">
                {backupItems.length === 0 ? (
                  <div className="p-3 text-sm text-gray-500">No backups found.</div>
                ) : (
                  <table className="min-w-full divide-y divide-gray-200 text-sm">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-3 py-2 text-left font-medium text-gray-700">ID</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700">Dataset</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700">User</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700">Size</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700">Created</th>
                        <th className="px-3 py-2 text-left font-medium text-gray-700">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-gray-100">
                      {backupItems.map((item) => (
                        <tr key={item.id} className="bg-white">
                          <td className="px-3 py-2 text-gray-900">{item.id}</td>
                          <td className="px-3 py-2 text-gray-700">{item.dataset}</td>
                          <td className="px-3 py-2 text-gray-500">{item.user_id ?? '-'}</td>
                          <td className="px-3 py-2 text-gray-500">{formatBytes(item.size_bytes)}</td>
                          <td className="px-3 py-2 text-gray-500">{item.created_at ? new Date(item.created_at).toLocaleString() : '-'}</td>
                          <td className="px-3 py-2">
                            <Button variant="danger" size="xs" onClick={() => handleRestoreBackup(item)}>
                              Restore
                            </Button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
              </div>
            </div>
          </div>
        </div>

        <div className="rounded-md border bg-white p-4">
          <div className="mb-2 text-lg font-semibold text-gray-800">Retention Policies</div>
          <p className="mb-4 text-sm text-gray-600">Update retention windows (days). Changes persist across restarts.</p>
          {policies.length === 0 ? (
            <div className="text-sm text-gray-500">No policies loaded.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200 text-sm">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-medium text-gray-700">Key</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-700">Description</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-700">Days</th>
                    <th className="px-3 py-2 text-left font-medium text-gray-700">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-gray-100">
                  {policies.map((policy) => (
                    <tr key={policy.key} className="bg-white">
                      <td className="px-3 py-2 text-gray-900">{policy.key}</td>
                      <td className="px-3 py-2 text-gray-600">{policy.description || '-'}</td>
                      <td className="px-3 py-2 text-gray-600">
                        <input
                          className="w-24 rounded-md border border-gray-300 px-2 py-1 text-sm"
                          value={policyDrafts[policy.key] ?? ''}
                          onChange={(e) => setPolicyDrafts((prev) => ({ ...prev, [policy.key]: e.target.value.replace(/[^0-9]/g, '') }))}
                          inputMode="numeric"
                        />
                      </td>
                      <td className="px-3 py-2">
                        <Button
                          variant="secondary"
                          size="xs"
                          onClick={() => handleRetentionUpdate(policy)}
                          disabled={policyBusy !== null}
                        >
                          Update
                        </Button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <div className="rounded-md border bg-white p-4">
            <div className="mb-2 text-lg font-semibold text-gray-800">Audit Log Export</div>
            <p className="mb-4 text-sm text-gray-600">Export audit logs as CSV or JSON.</p>
            <div className="grid gap-2 md:grid-cols-2">
              <Input
                label="Days"
                value={auditDays}
                onChange={(e) => setAuditDays(e.target.value.replace(/[^0-9]/g, ''))}
                inputMode="numeric"
              />
              <Input
                label="Limit"
                value={auditLimit}
                onChange={(e) => setAuditLimit(e.target.value.replace(/[^0-9]/g, ''))}
                inputMode="numeric"
              />
              <label className="flex flex-col text-sm text-gray-700">
                Format
                <select
                  className="mt-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                  value={auditFormat}
                  onChange={(e) => setAuditFormat(e.target.value as 'csv' | 'json')}
                >
                  <option value="csv">csv</option>
                  <option value="json">json</option>
                </select>
              </label>
            </div>
            <div className="mt-3">
              <Button
                variant="secondary"
                onClick={() => downloadExport(
                  'audit-export',
                  '/admin/audit-log/export',
                  {
                    days: parseOptionalInt(auditDays) ?? 30,
                    limit: parseOptionalInt(auditLimit) ?? 10000,
                    format: auditFormat,
                  },
                  `audit_log.${auditFormat}`,
                )}
                disabled={exportBusy !== null}
              >
                {exportBusy === 'audit-export' ? 'Preparing…' : 'Download Audit Export'}
              </Button>
            </div>
          </div>

          <div className="rounded-md border bg-white p-4">
            <div className="mb-2 text-lg font-semibold text-gray-800">Users Export</div>
            <p className="mb-4 text-sm text-gray-600">Export users as CSV or JSON.</p>
            <div className="grid gap-2 md:grid-cols-2">
              <Input
                label="Limit"
                value={usersLimit}
                onChange={(e) => setUsersLimit(e.target.value.replace(/[^0-9]/g, ''))}
                inputMode="numeric"
              />
              <label className="flex flex-col text-sm text-gray-700">
                Format
                <select
                  className="mt-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                  value={usersFormat}
                  onChange={(e) => setUsersFormat(e.target.value as 'csv' | 'json')}
                >
                  <option value="csv">csv</option>
                  <option value="json">json</option>
                </select>
              </label>
            </div>
            <div className="mt-3">
              <Button
                variant="secondary"
                onClick={() => downloadExport(
                  'users-export',
                  '/admin/users/export',
                  {
                    limit: parseOptionalInt(usersLimit) ?? 10000,
                    format: usersFormat,
                  },
                  `users.${usersFormat}`,
                )}
                disabled={exportBusy !== null}
              >
                {exportBusy === 'users-export' ? 'Preparing…' : 'Download Users Export'}
              </Button>
            </div>
          </div>
        </div>
      </div>

      <ConfirmDialog
        open={confirmRestore !== null}
        title="Restore backup?"
        message={confirmRestore ? `Restore ${confirmRestore.id}? This will overwrite the current dataset.` : ''}
        confirmText="Restore backup"
        cancelText="Cancel"
        destructive
        onConfirm={confirmRestoreBackup}
        onCancel={() => setConfirmRestore(null)}
      />

      <ConfirmDialog
        open={confirmRetention !== null}
        title="Update retention policy?"
        message={confirmRetention ? `Update ${confirmRetention.key} to ${confirmRetention.days} days?` : ''}
        confirmText="Apply change"
        cancelText="Cancel"
        destructive
        onConfirm={confirmRetentionUpdate}
        onCancel={() => setConfirmRetention(null)}
      />
    </Layout>
  );
}
