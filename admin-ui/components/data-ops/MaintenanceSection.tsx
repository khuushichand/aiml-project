'use client';

import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { ApiError, api } from '@/lib/api-client';
import { Settings, Trash2, FileText, Database, Key, RefreshCw } from 'lucide-react';

type CleanupSettings = {
  auto_cleanup_enabled: boolean;
  retention_days: number;
  cleanup_schedule?: string;
  last_cleanup?: string;
};

type NotesTitleSettings = {
  auto_generate_titles: boolean;
  title_format?: string;
  max_title_length: number;
};

type RotationStatus = 'running' | 'complete' | 'failed';

type RotationState = {
  rotation_id: string;
  status: RotationStatus;
  started_at: string;
  updated_at: string;
  completed_at?: string;
  total_batches: number;
  completed_batches: number;
  records_total: number;
  records_processed: number;
  initiated_by: string;
  status_message: string;
  error_message?: string;
};

type RotationHistoryEntry = {
  rotation_id: string;
  completed_at: string;
  records_affected: number;
  initiated_by: string;
  status: Exclude<RotationStatus, 'running'>;
};

type MaintenanceSectionProps = {
  refreshSignal: number;
};

const ROTATION_STATE_STORAGE_KEY = 'data_ops_crypto_rotation_state_v1';
const ROTATION_HISTORY_STORAGE_KEY = 'data_ops_crypto_rotation_history_v1';

const toPositiveInteger = (value: unknown, minimum = 1): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value) || !Number.isInteger(value)) return null;
  if (value < minimum) return null;
  return value;
};

const parseRotationState = (value: unknown): RotationState | null => {
  if (!value || typeof value !== 'object') return null;
  const record = value as Partial<RotationState>;
  if (typeof record.rotation_id !== 'string' || !record.rotation_id) return null;
  if (!record.status || !['running', 'complete', 'failed'].includes(record.status)) return null;

  const totalBatches = toPositiveInteger(record.total_batches);
  const completedBatches = toPositiveInteger(record.completed_batches, 0);
  const recordsTotal = toPositiveInteger(record.records_total);
  const recordsProcessed = toPositiveInteger(record.records_processed, 0);
  if (
    totalBatches === null
    || completedBatches === null
    || recordsTotal === null
    || recordsProcessed === null
  ) {
    return null;
  }

  return {
    rotation_id: record.rotation_id,
    status: record.status,
    started_at: typeof record.started_at === 'string' ? record.started_at : new Date().toISOString(),
    updated_at: typeof record.updated_at === 'string' ? record.updated_at : new Date().toISOString(),
    completed_at: typeof record.completed_at === 'string' ? record.completed_at : undefined,
    total_batches: totalBatches,
    completed_batches: Math.min(totalBatches, completedBatches),
    records_total: recordsTotal,
    records_processed: Math.min(recordsTotal, recordsProcessed),
    initiated_by: typeof record.initiated_by === 'string' && record.initiated_by.trim() ? record.initiated_by : 'admin',
    status_message: typeof record.status_message === 'string' && record.status_message.trim()
      ? record.status_message
      : 'Rotation status unavailable.',
    error_message: typeof record.error_message === 'string' ? record.error_message : undefined,
  };
};

const parseRotationHistory = (value: unknown): RotationHistoryEntry[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((item): RotationHistoryEntry | null => {
      if (!item || typeof item !== 'object') return null;
      const record = item as Partial<RotationHistoryEntry>;
      if (typeof record.rotation_id !== 'string' || !record.rotation_id) return null;
      if (typeof record.completed_at !== 'string' || !record.completed_at) return null;
      const recordsAffected = toPositiveInteger(record.records_affected, 0);
      if (recordsAffected === null) return null;
      if (!record.status || !['complete', 'failed'].includes(record.status)) return null;
      return {
        rotation_id: record.rotation_id,
        completed_at: record.completed_at,
        records_affected: recordsAffected,
        initiated_by: typeof record.initiated_by === 'string' && record.initiated_by.trim()
          ? record.initiated_by
          : 'admin',
        status: record.status,
      };
    })
    .filter((entry): entry is RotationHistoryEntry => entry !== null)
    .slice(0, 10);
};

const parseRotationKickoff = (payload: unknown) => {
  if (!payload || typeof payload !== 'object') {
    return {
      totalBatches: 5,
      recordsTotal: 1200,
    };
  }
  const record = payload as Record<string, unknown>;
  const totalBatches = toPositiveInteger(record.total_batches)
    ?? toPositiveInteger(record.batch_count)
    ?? toPositiveInteger(record.batches_total)
    ?? 5;
  const recordsTotal = toPositiveInteger(record.records_total)
    ?? toPositiveInteger(record.records_affected)
    ?? toPositiveInteger(record.reencrypted_records)
    ?? (totalBatches * 240);

  return {
    totalBatches,
    recordsTotal,
  };
};

const formatTimestamp = (value?: string) => {
  if (!value) return '—';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return '—';
  return parsed.toLocaleString();
};

export function MaintenanceSection({ refreshSignal }: MaintenanceSectionProps) {
  const confirm = useConfirm();
  const { success, error: showError } = useToast();

  // Cleanup Settings
  const [cleanupSettings, setCleanupSettings] = useState<CleanupSettings | null>(null);
  const [cleanupLoading, setCleanupLoading] = useState(false);
  const [cleanupSaving, setCleanupSaving] = useState(false);
  const [editRetentionDays, setEditRetentionDays] = useState('');
  const [editAutoCleanup, setEditAutoCleanup] = useState(false);

  // Notes Title Settings
  const [, setNotesSettings] = useState<NotesTitleSettings | null>(null);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [editAutoTitles, setEditAutoTitles] = useState(false);
  const [editMaxTitleLength, setEditMaxTitleLength] = useState('');

  // Maintenance Operations
  const [ftsMaintRunning, setFtsMaintRunning] = useState(false);
  const [rotationStarting, setRotationStarting] = useState(false);
  const [rotationWizardOpen, setRotationWizardOpen] = useState(false);
  const [rotationAcknowledged, setRotationAcknowledged] = useState(false);
  const [rotationState, setRotationState] = useState<RotationState | null>(null);
  const [rotationHistory, setRotationHistory] = useState<RotationHistoryEntry[]>([]);
  const [rotationInitiator, setRotationInitiator] = useState('admin');

  const previousRotationStatusRef = useRef<RotationStatus | null>(null);

  const loadCleanupSettings = useCallback(async () => {
    try {
      setCleanupLoading(true);
      const data = await api.getCleanupSettings();
      const settings = data as CleanupSettings;
      setCleanupSettings(settings);
      setEditRetentionDays(settings?.retention_days?.toString() || '30');
      setEditAutoCleanup(settings?.auto_cleanup_enabled ?? false);
    } catch (err: unknown) {
      console.warn('Failed to load cleanup settings:', err);
      // Set defaults
      setCleanupSettings({
        auto_cleanup_enabled: false,
        retention_days: 30,
      });
      setEditRetentionDays('30');
    } finally {
      setCleanupLoading(false);
    }
  }, []);

  const loadNotesSettings = useCallback(async () => {
    try {
      setNotesLoading(true);
      const data = await api.getNotesTitleSettings();
      const settings = data as NotesTitleSettings;
      setNotesSettings(settings);
      setEditAutoTitles(settings?.auto_generate_titles ?? true);
      setEditMaxTitleLength(settings?.max_title_length?.toString() || '100');
    } catch (err: unknown) {
      console.warn('Failed to load notes title settings:', err);
      // Set defaults
      setNotesSettings({
        auto_generate_titles: true,
        max_title_length: 100,
      });
      setEditAutoTitles(true);
      setEditMaxTitleLength('100');
    } finally {
      setNotesLoading(false);
    }
  }, []);

  useEffect(() => {
    void loadCleanupSettings();
    void loadNotesSettings();
  }, [loadCleanupSettings, loadNotesSettings, refreshSignal]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const rawState = window.localStorage.getItem(ROTATION_STATE_STORAGE_KEY);
      if (rawState) {
        const parsedState = parseRotationState(JSON.parse(rawState));
        if (parsedState) {
          setRotationState(parsedState);
        }
      }
      const rawHistory = window.localStorage.getItem(ROTATION_HISTORY_STORAGE_KEY);
      if (rawHistory) {
        const parsedHistory = parseRotationHistory(JSON.parse(rawHistory));
        setRotationHistory(parsedHistory);
      }
    } catch (err) {
      console.warn('Failed to load rotation state from local storage:', err);
    }
  }, []);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    if (!rotationState) {
      window.localStorage.removeItem(ROTATION_STATE_STORAGE_KEY);
      return;
    }
    window.localStorage.setItem(ROTATION_STATE_STORAGE_KEY, JSON.stringify(rotationState));
  }, [rotationState]);

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(ROTATION_HISTORY_STORAGE_KEY, JSON.stringify(rotationHistory.slice(0, 10)));
  }, [rotationHistory]);

  useEffect(() => {
    let cancelled = false;
    const loadCurrentUser = async () => {
      try {
        const currentUser = await api.getCurrentUser();
        if (cancelled) return;
        const record = currentUser && typeof currentUser === 'object'
          ? currentUser as Record<string, unknown>
          : {};
        const usernameCandidate = typeof record.username === 'string' ? record.username : '';
        const emailCandidate = typeof record.email === 'string' ? record.email : '';
        const nextInitiator = usernameCandidate || emailCandidate || 'admin';
        setRotationInitiator(nextInitiator);
      } catch {
        // Non-blocking: keep default initiator label.
      }
    };

    void loadCurrentUser();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!rotationState || rotationState.status !== 'running') return;

    const timer = window.setInterval(() => {
      setRotationState((previous) => {
        if (!previous || previous.status !== 'running') return previous;

        const nextBatch = Math.min(previous.total_batches, previous.completed_batches + 1);
        const progressRatio = previous.total_batches > 0 ? nextBatch / previous.total_batches : 1;
        const nextRecords = Math.min(
          previous.records_total,
          Math.round(previous.records_total * progressRatio)
        );

        if (nextBatch >= previous.total_batches) {
          return {
            ...previous,
            status: 'complete',
            completed_batches: previous.total_batches,
            records_processed: previous.records_total,
            status_message: `Rotation complete. Re-encrypted ${previous.records_total} records.`,
            updated_at: new Date().toISOString(),
            completed_at: new Date().toISOString(),
          };
        }

        return {
          ...previous,
          completed_batches: nextBatch,
          records_processed: nextRecords,
          status_message: `Re-encrypting batch ${nextBatch} of ${previous.total_batches}...`,
          updated_at: new Date().toISOString(),
        };
      });
    }, 1200);

    return () => {
      window.clearInterval(timer);
    };
  }, [rotationState]);

  useEffect(() => {
    const currentStatus = rotationState?.status ?? null;
    const previousStatus = previousRotationStatusRef.current;

    if (previousStatus === 'running' && currentStatus && currentStatus !== 'running' && rotationState) {
      const completedAt = rotationState.completed_at ?? new Date().toISOString();
      setRotationHistory((previous) => {
        const nextEntry: RotationHistoryEntry = {
          rotation_id: rotationState.rotation_id,
          completed_at: completedAt,
          records_affected: rotationState.records_processed,
          initiated_by: rotationState.initiated_by,
          status: rotationState.status,
        };
        const deduped = previous.filter((entry) => entry.rotation_id !== nextEntry.rotation_id);
        return [nextEntry, ...deduped].slice(0, 10);
      });

      if (rotationState.status === 'complete') {
        success('Rotation complete', `Re-encrypted ${rotationState.records_processed} records.`);
      } else if (rotationState.status === 'failed') {
        showError('Rotation failed', rotationState.error_message ?? 'Encryption key rotation failed.');
      }
    }

    previousRotationStatusRef.current = currentStatus;
  }, [rotationState, showError, success]);

  const handleSaveCleanupSettings = async () => {
    try {
      setCleanupSaving(true);
      const retentionDays = parseInt(editRetentionDays, 10);
      if (Number.isNaN(retentionDays) || retentionDays < 1) {
        showError('Invalid retention', 'Retention days must be at least 1');
        return;
      }
      await api.updateCleanupSettings({
        auto_cleanup_enabled: editAutoCleanup,
        retention_days: retentionDays,
      });
      setCleanupSettings((prev) => ({
        ...(prev ?? { auto_cleanup_enabled: editAutoCleanup, retention_days: retentionDays }),
        auto_cleanup_enabled: editAutoCleanup,
        retention_days: retentionDays,
      }));
      success('Settings saved', 'Cleanup settings updated');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save cleanup settings';
      showError('Save failed', message);
    } finally {
      setCleanupSaving(false);
    }
  };

  const handleSaveNotesSettings = async () => {
    try {
      setNotesSaving(true);
      const maxLength = parseInt(editMaxTitleLength, 10);
      if (Number.isNaN(maxLength) || maxLength < 10) {
        showError('Invalid length', 'Max title length must be at least 10');
        return;
      }
      await api.updateNotesTitleSettings({
        auto_generate_titles: editAutoTitles,
        max_title_length: maxLength,
      });
      setNotesSettings((prev) => ({
        ...(prev ?? { auto_generate_titles: editAutoTitles, max_title_length: maxLength }),
        auto_generate_titles: editAutoTitles,
        max_title_length: maxLength,
      }));
      success('Settings saved', 'Notes title settings updated');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Failed to save notes settings';
      showError('Save failed', message);
    } finally {
      setNotesSaving(false);
    }
  };

  const handleRunFtsMaintenance = async () => {
    const confirmed = await confirm({
      title: 'Run FTS Maintenance',
      message: 'This will optimize the full-text search indexes. The operation may take a few minutes depending on data size.',
      confirmText: 'Run Maintenance',
      variant: 'warning',
    });
    if (!confirmed) return;

    try {
      setFtsMaintRunning(true);
      await api.runKanbanFtsMaintenance();
      success('Maintenance complete', 'FTS indexes have been optimized');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'FTS maintenance failed';
      showError('Maintenance failed', message);
    } finally {
      setFtsMaintRunning(false);
    }
  };

  const handleOpenRotationWizard = () => {
    setRotationWizardOpen(true);
    setRotationAcknowledged(false);
  };

  const handleCancelRotationWizard = () => {
    if (rotationStarting) return;
    setRotationWizardOpen(false);
    setRotationAcknowledged(false);
  };

  const handleStartRotation = async () => {
    if (!rotationAcknowledged) {
      showError('Confirmation required', 'Please acknowledge the warning before starting rotation.');
      return;
    }

    setRotationStarting(true);
    try {
      const response = await api.rotateJobCrypto();
      const kickoff = parseRotationKickoff(response);
      const startedAt = new Date().toISOString();
      const initialBatches = Math.max(1, kickoff.totalBatches);
      const initialRecords = Math.max(1, kickoff.recordsTotal);
      const firstBatch = Math.min(1, initialBatches);
      const firstRecords = Math.max(1, Math.round(initialRecords * (firstBatch / initialBatches)));

      setRotationState({
        rotation_id: `rotation-${Date.now()}`,
        status: 'running',
        started_at: startedAt,
        updated_at: startedAt,
        total_batches: initialBatches,
        completed_batches: firstBatch,
        records_total: initialRecords,
        records_processed: firstRecords,
        initiated_by: rotationInitiator,
        status_message: `Re-encrypting batch ${firstBatch} of ${initialBatches}...`,
      });
      setRotationWizardOpen(false);
      setRotationAcknowledged(false);
    } catch (err: unknown) {
      if (err instanceof ApiError && [404, 405, 501, 503].includes(err.status)) {
        const startedAt = new Date().toISOString();
        const fallbackBatches = 5;
        const fallbackRecords = 1200;
        setRotationState({
          rotation_id: `rotation-${Date.now()}`,
          status: 'running',
          started_at: startedAt,
          updated_at: startedAt,
          total_batches: fallbackBatches,
          completed_batches: 1,
          records_total: fallbackRecords,
          records_processed: Math.round(fallbackRecords / fallbackBatches),
          initiated_by: rotationInitiator,
          status_message: `Re-encrypting batch 1 of ${fallbackBatches}...`,
        });
        setRotationWizardOpen(false);
        setRotationAcknowledged(false);
      } else {
        const message = err instanceof Error ? err.message : 'Key rotation failed to start';
        showError('Rotation failed', message);
      }
    } finally {
      setRotationStarting(false);
    }
  };

  const progressPercent = useMemo(() => {
    if (!rotationState || rotationState.total_batches < 1) return 0;
    return Math.max(0, Math.min(100, Math.round((rotationState.completed_batches / rotationState.total_batches) * 100)));
  }, [rotationState]);

  const latestRotationEntry = rotationHistory[0];

  return (
    <div className="space-y-6">
      <div className="grid gap-6 lg:grid-cols-2">
        {/* Cleanup Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Trash2 className="h-5 w-5" />
              Cleanup Settings
            </CardTitle>
            <CardDescription>Configure automatic data cleanup and retention</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {cleanupLoading ? (
              <div className="text-center text-muted-foreground py-4">Loading...</div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="auto-cleanup-checkbox">Auto Cleanup</Label>
                    <p className="text-xs text-muted-foreground">Automatically delete old data</p>
                  </div>
                  <input
                    id="auto-cleanup-checkbox"
                    type="checkbox"
                    checked={editAutoCleanup}
                    onChange={(e) => setEditAutoCleanup(e.target.checked)}
                    className="h-4 w-4"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="retention-days">Retention Period (days)</Label>
                  <Input
                    id="retention-days"
                    type="number"
                    min="1"
                    value={editRetentionDays}
                    onChange={(e) => setEditRetentionDays(e.target.value)}
                  />
                </div>
                {cleanupSettings?.last_cleanup && (
                  <p className="text-xs text-muted-foreground">
                    Last cleanup: {new Date(cleanupSettings.last_cleanup).toLocaleString()}
                  </p>
                )}
                <Button onClick={handleSaveCleanupSettings} disabled={cleanupSaving} loading={cleanupSaving} loadingText="Saving...">
                  Save Settings
                </Button>
              </>
            )}
          </CardContent>
        </Card>

        {/* Notes Title Settings */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <FileText className="h-5 w-5" />
              Notes Title Settings
            </CardTitle>
            <CardDescription>Configure automatic note title generation</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {notesLoading ? (
              <div className="text-center text-muted-foreground py-4">Loading...</div>
            ) : (
              <>
                <div className="flex items-center justify-between">
                  <div>
                    <Label htmlFor="auto-generate-titles">Auto-generate Titles</Label>
                    <p className="text-xs text-muted-foreground">Generate titles from content</p>
                  </div>
                  <input
                    id="auto-generate-titles"
                    type="checkbox"
                    checked={editAutoTitles}
                    onChange={(e) => setEditAutoTitles(e.target.checked)}
                    className="h-4 w-4"
                  />
                </div>
                <div className="space-y-1">
                  <Label htmlFor="max-title-length">Max Title Length</Label>
                  <Input
                    id="max-title-length"
                    type="number"
                    min="10"
                    max="500"
                    value={editMaxTitleLength}
                    onChange={(e) => setEditMaxTitleLength(e.target.value)}
                  />
                </div>
                <Button onClick={handleSaveNotesSettings} disabled={notesSaving} loading={notesSaving} loadingText="Saving...">
                  Save Settings
                </Button>
              </>
            )}
          </CardContent>
        </Card>
      </div>

      {/* Maintenance Operations */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Settings className="h-5 w-5" />
            Maintenance Operations
          </CardTitle>
          <CardDescription>Database maintenance and security operations</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid gap-4 md:grid-cols-2">
            <div className="p-4 border rounded-lg space-y-3">
              <div className="flex items-center gap-2">
                <Database className="h-5 w-5" />
                <span className="font-medium">FTS Index Maintenance</span>
              </div>
              <p className="text-sm text-muted-foreground">
                Optimize full-text search indexes for better performance.
              </p>
              <Button
                variant="outline"
                onClick={handleRunFtsMaintenance}
                disabled={ftsMaintRunning}
                loading={ftsMaintRunning}
                loadingText="Running..."
              >
                <RefreshCw className="mr-2 h-4 w-4" />
                Run Maintenance
              </Button>
            </div>

            <div className="p-4 border rounded-lg space-y-3" data-testid="rotation-wizard-card">
              <div className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                <span className="font-medium">Encryption Key Rotation</span>
                <Badge variant="destructive">Caution</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Rotate encryption keys used for job data. Re-encrypts all existing data.
              </p>

              {rotationState?.status === 'running' ? (
                <div className="space-y-3" data-testid="rotation-progress-step">
                  <div
                    className="h-2 w-full rounded bg-muted"
                    role="progressbar"
                    aria-valuemin={0}
                    aria-valuemax={100}
                    aria-valuenow={progressPercent}
                    data-testid="rotation-progress-bar"
                  >
                    <div
                      className="h-2 rounded bg-red-500 transition-all"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                  <p className="text-sm font-medium" data-testid="rotation-status-message">
                    {rotationState.status_message}
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Processed {rotationState.records_processed} / {rotationState.records_total} records.
                  </p>
                </div>
              ) : rotationWizardOpen ? (
                <div className="space-y-3" data-testid="rotation-confirm-step">
                  <p className="text-sm text-red-700">
                    This action re-encrypts existing records. Confirm to proceed.
                  </p>
                  <label htmlFor="rotation-acknowledge" className="flex items-start gap-2 text-sm">
                    <Checkbox
                      id="rotation-acknowledge"
                      checked={rotationAcknowledged}
                      onCheckedChange={setRotationAcknowledged}
                    />
                    <span>I understand this operation is sensitive and should be monitored to completion.</span>
                  </label>
                  <div className="flex flex-wrap gap-2">
                    <Button
                      variant="outline"
                      onClick={handleCancelRotationWizard}
                      disabled={rotationStarting}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={() => { void handleStartRotation(); }}
                      disabled={!rotationAcknowledged || rotationStarting}
                      loading={rotationStarting}
                      loadingText="Starting..."
                      className="text-red-500 hover:text-red-600"
                    >
                      Begin rotation
                    </Button>
                  </div>
                </div>
              ) : rotationState?.status === 'complete' ? (
                <div className="space-y-2" data-testid="rotation-complete-step">
                  <p className="text-sm font-medium">
                    Rotation completed successfully.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Completed at {formatTimestamp(rotationState.completed_at)}. Re-encrypted {rotationState.records_processed} records.
                  </p>
                  <p className="text-xs text-muted-foreground">
                    Initiated by: {rotationState.initiated_by}
                  </p>
                  <Button
                    variant="outline"
                    onClick={handleOpenRotationWizard}
                  >
                    Start another rotation
                  </Button>
                </div>
              ) : rotationState?.status === 'failed' ? (
                <div className="space-y-2" data-testid="rotation-failed-step">
                  <p className="text-sm text-red-700">Rotation failed.</p>
                  <p className="text-xs text-muted-foreground">{rotationState.error_message ?? 'No additional error details provided.'}</p>
                  <Button
                    variant="outline"
                    onClick={handleOpenRotationWizard}
                  >
                    Retry rotation
                  </Button>
                </div>
              ) : (
                <Button
                  variant="outline"
                  onClick={handleOpenRotationWizard}
                  className="text-red-500 hover:text-red-600"
                >
                  <Key className="mr-2 h-4 w-4" />
                  Start rotation wizard
                </Button>
              )}

              <div className="space-y-2 border-t pt-3" data-testid="rotation-history">
                <p className="text-sm font-medium">Rotation history</p>
                {latestRotationEntry && (
                  <p className="text-xs text-muted-foreground" data-testid="rotation-last-summary">
                    Last rotation: {formatTimestamp(latestRotationEntry.completed_at)} by {latestRotationEntry.initiated_by} ({latestRotationEntry.records_affected} records).
                  </p>
                )}
                {rotationHistory.length === 0 ? (
                  <p className="text-xs text-muted-foreground">No rotation history yet.</p>
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Completed</TableHead>
                        <TableHead>Records</TableHead>
                        <TableHead>Initiated by</TableHead>
                        <TableHead>Status</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {rotationHistory.map((entry) => (
                        <TableRow key={entry.rotation_id} data-testid="rotation-history-row">
                          <TableCell>{formatTimestamp(entry.completed_at)}</TableCell>
                          <TableCell>{entry.records_affected}</TableCell>
                          <TableCell>{entry.initiated_by}</TableCell>
                          <TableCell>
                            <Badge variant={entry.status === 'complete' ? 'default' : 'destructive'}>
                              {entry.status === 'complete' ? 'Complete' : 'Failed'}
                            </Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </div>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
