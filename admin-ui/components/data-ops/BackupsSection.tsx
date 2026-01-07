'use client';

import { useCallback, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Pagination } from '@/components/ui/pagination';
import { useToast } from '@/components/ui/toast';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { api } from '@/lib/api-client';
import { formatBytes, formatDateTime } from '@/lib/format';
import { useUrlPagination } from '@/lib/use-url-state';
import { usePagedResource, type LoadOptions } from '@/lib/use-paged-resource';
import type { BackupItem } from '@/types';
import { Database } from 'lucide-react';
import { Field } from '@/components/data-ops/Field';

type BackupsSectionProps = {
  refreshSignal: number;
};

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

const formatBackupDate = (value?: string | null) => formatDateTime(value, {
  fallback: '—',
  options: {
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit',
    hour12: false,
  },
});

export const BackupsSection = ({ refreshSignal }: BackupsSectionProps) => {
  const { page, pageSize, setPage, setPageSize, resetPagination } = useUrlPagination();
  const { success, error: showError } = useToast();
  const confirm = useConfirm();

  const [listDataset, setListDataset] = useState('');
  const [listUserId, setListUserId] = useState('');

  const [createDataset, setCreateDataset] = useState('media');
  const [createUserId, setCreateUserId] = useState('');
  const [backupType, setBackupType] = useState('full');
  const [maxBackups, setMaxBackups] = useState('');
  const [creatingBackup, setCreatingBackup] = useState(false);
  const [restoreBusyId, setRestoreBusyId] = useState<string | null>(null);

  const backupParams = useMemo(() => {
    const params: Record<string, string> = {
      limit: String(pageSize),
      offset: String(Math.max(0, (page - 1) * pageSize)),
    };
    if (listDataset) params.dataset = listDataset;
    if (listUserId) params.user_id = listUserId;
    return params;
  }, [listDataset, listUserId, page, pageSize]);

  const loadBackups = useCallback(({ signal }: LoadOptions = {}) =>
    api.getBackups(backupParams, signal ? { signal } : undefined), [backupParams]);

  const {
    items: backups,
    total: backupTotal,
    loading: backupLoading,
    error: backupError,
    reload,
  } = usePagedResource<BackupItem>({
    load: loadBackups,
    deps: [refreshSignal],
    defaultError: 'Failed to load backups',
  });

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
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed <= 0) {
        showError('Invalid user id', 'User id must be a positive integer.');
        return;
      }
      payload.user_id = parsed;
    }
    if (maxBackups.trim()) {
      const parsed = Number(maxBackups);
      if (!Number.isFinite(parsed) || !Number.isInteger(parsed) || parsed <= 0) {
        showError('Invalid max backups', 'Max backups must be a positive integer.');
        return;
      }
      payload.max_backups = parsed;
    }

    try {
      setCreatingBackup(true);
      await api.createBackup(payload);
      success('Backup created', 'Snapshot created successfully.');
      await reload();
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
      await reload();
    } catch (err: unknown) {
      const message = err instanceof Error && err.message ? err.message : 'Failed to restore backup';
      showError('Restore failed', message);
    } finally {
      setRestoreBusyId(null);
    }
  };

  const totalPages = Math.max(1, Math.ceil(backupTotal / pageSize));

  return (
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
            <Button variant="outline" onClick={reload} disabled={backupLoading}>
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
                  <TableCell>{formatBytes(backup.size_bytes, { fallback: '—' })}</TableCell>
                  <TableCell>{formatBackupDate(backup.created_at)}</TableCell>
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
  );
};
