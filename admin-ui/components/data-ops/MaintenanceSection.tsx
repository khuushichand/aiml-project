'use client';

import { useCallback, useEffect, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { useConfirm } from '@/components/ui/confirm-dialog';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
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

type MaintenanceSectionProps = {
  refreshSignal: number;
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
  const [notesSettings, setNotesSettings] = useState<NotesTitleSettings | null>(null);
  const [notesLoading, setNotesLoading] = useState(false);
  const [notesSaving, setNotesSaving] = useState(false);
  const [editAutoTitles, setEditAutoTitles] = useState(false);
  const [editMaxTitleLength, setEditMaxTitleLength] = useState('');

  // Maintenance Operations
  const [ftsMaintRunning, setFtsMaintRunning] = useState(false);
  const [cryptoRotating, setCryptoRotating] = useState(false);

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
    loadCleanupSettings();
    loadNotesSettings();
  }, [loadCleanupSettings, loadNotesSettings, refreshSignal]);

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
      setCleanupSettings({
        ...cleanupSettings,
        auto_cleanup_enabled: editAutoCleanup,
        retention_days: retentionDays,
      });
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
      setNotesSettings({
        ...notesSettings,
        auto_generate_titles: editAutoTitles,
        max_title_length: maxLength,
      });
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

  const handleRotateCrypto = async () => {
    const confirmed = await confirm({
      title: 'Rotate Encryption Keys',
      message: 'This will rotate the encryption keys used for job data. All existing encrypted data will be re-encrypted. This operation cannot be undone.',
      confirmText: 'Rotate Keys',
      variant: 'danger',
    });
    if (!confirmed) return;

    try {
      setCryptoRotating(true);
      await api.rotateJobCrypto();
      success('Keys rotated', 'Encryption keys have been rotated successfully');
    } catch (err: unknown) {
      const message = err instanceof Error ? err.message : 'Key rotation failed';
      showError('Rotation failed', message);
    } finally {
      setCryptoRotating(false);
    }
  };

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
                    <Label>Auto Cleanup</Label>
                    <p className="text-xs text-muted-foreground">Automatically delete old data</p>
                  </div>
                  <input
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
                <Button onClick={handleSaveCleanupSettings} disabled={cleanupSaving}>
                  {cleanupSaving ? 'Saving...' : 'Save Settings'}
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
                    <Label>Auto-generate Titles</Label>
                    <p className="text-xs text-muted-foreground">Generate titles from content</p>
                  </div>
                  <input
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
                <Button onClick={handleSaveNotesSettings} disabled={notesSaving}>
                  {notesSaving ? 'Saving...' : 'Save Settings'}
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
              >
                <RefreshCw className={`mr-2 h-4 w-4 ${ftsMaintRunning ? 'animate-spin' : ''}`} />
                {ftsMaintRunning ? 'Running...' : 'Run Maintenance'}
              </Button>
            </div>

            <div className="p-4 border rounded-lg space-y-3">
              <div className="flex items-center gap-2">
                <Key className="h-5 w-5" />
                <span className="font-medium">Encryption Key Rotation</span>
                <Badge variant="destructive">Caution</Badge>
              </div>
              <p className="text-sm text-muted-foreground">
                Rotate encryption keys used for job data. Re-encrypts all existing data.
              </p>
              <Button
                variant="outline"
                onClick={handleRotateCrypto}
                disabled={cryptoRotating}
                className="text-red-500 hover:text-red-600"
              >
                <Key className={`mr-2 h-4 w-4 ${cryptoRotating ? 'animate-pulse' : ''}`} />
                {cryptoRotating ? 'Rotating...' : 'Rotate Keys'}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
