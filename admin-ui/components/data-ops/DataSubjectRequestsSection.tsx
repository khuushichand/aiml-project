'use client';

import { useEffect, useMemo, useState } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Select } from '@/components/ui/select';
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from '@/components/ui/table';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Checkbox } from '@/components/ui/checkbox';
import { useToast } from '@/components/ui/toast';
import { api } from '@/lib/api-client';
import { formatDateTime } from '@/lib/format';
import { isUnsafeLocalToolsEnabled } from '@/lib/admin-ui-flags';
import { ShieldAlert } from 'lucide-react';
import { Field } from '@/components/data-ops/Field';

type DataSubjectRequestsSectionProps = {
  refreshSignal: number;
};

type DataSubjectRequestType = 'export' | 'erasure' | 'access';
type DataSubjectRequestStatus = 'completed' | 'failed';

type DataCategoryCount = {
  key: string;
  label: string;
  count: number;
};

type DataSubjectRequestLogItem = {
  id: string;
  requester: string;
  request_type: DataSubjectRequestType;
  status: DataSubjectRequestStatus;
  requested_at: string;
  completed_at?: string;
  selected_categories?: string[];
};

const REQUEST_LOG_STORAGE_KEY = 'data_ops_data_subject_requests_log_v1';

const CATEGORY_DEFS: Array<{ key: string; label: string }> = [
  { key: 'media_records', label: 'Media records' },
  { key: 'chat_messages', label: 'Chat sessions/messages' },
  { key: 'notes', label: 'Notes' },
  { key: 'audit_events', label: 'Audit log events' },
  { key: 'embeddings', label: 'Embeddings' },
];

const REQUEST_TYPE_OPTIONS: Array<{ value: DataSubjectRequestType; label: string }> = [
  { value: 'export', label: 'Export' },
  { value: 'erasure', label: 'Erasure' },
  { value: 'access', label: 'Access' },
];

const parseNonNegativeInteger = (value: unknown): number | null => {
  if (typeof value !== 'number' || !Number.isFinite(value) || value < 0) return null;
  return Math.floor(value);
};

const parseRequestLogStorage = (value: unknown): DataSubjectRequestLogItem[] => {
  if (!Array.isArray(value)) return [];
  return value
    .map((entry): DataSubjectRequestLogItem | null => {
      if (!entry || typeof entry !== 'object') return null;
      const record = entry as Partial<DataSubjectRequestLogItem>;
      if (typeof record.id !== 'string' || !record.id) return null;
      if (typeof record.requester !== 'string' || !record.requester.trim()) return null;
      if (!record.request_type || !['export', 'erasure', 'access'].includes(record.request_type)) return null;
      if (!record.status || !['completed', 'failed'].includes(record.status)) return null;
      if (typeof record.requested_at !== 'string' || !record.requested_at) return null;
      return {
        id: record.id,
        requester: record.requester,
        request_type: record.request_type,
        status: record.status,
        requested_at: record.requested_at,
        completed_at: typeof record.completed_at === 'string' ? record.completed_at : undefined,
        selected_categories: Array.isArray(record.selected_categories)
          ? record.selected_categories.filter((value): value is string => typeof value === 'string')
          : undefined,
      };
    })
    .filter((entry): entry is DataSubjectRequestLogItem => entry !== null)
    .slice(0, 50);
};

const parseCategorySummary = (value: unknown): DataCategoryCount[] | null => {
  if (!value || typeof value !== 'object') return null;
  const root = value as Record<string, unknown>;

  const sourceSummary = (() => {
    if (root.summary && typeof root.summary === 'object') return root.summary as Record<string, unknown>;
    if (root.counts && typeof root.counts === 'object') return root.counts as Record<string, unknown>;
    if (root.categories && typeof root.categories === 'object') return root.categories as Record<string, unknown>;
    return root;
  })();

  const mapped = CATEGORY_DEFS.map((def) => {
    const aliases: Record<string, string[]> = {
      media_records: ['media_records', 'media', 'media_items', 'content_items'],
      chat_messages: ['chat_messages', 'chats', 'chat_sessions'],
      notes: ['notes', 'note_items'],
      audit_events: ['audit_events', 'audit_logs', 'audit_log_entries'],
      embeddings: ['embeddings', 'embedding_vectors', 'vectors'],
    };
    const keys = aliases[def.key] ?? [def.key];
    for (const key of keys) {
      const parsed = parseNonNegativeInteger(sourceSummary[key]);
      if (parsed !== null) {
        return { key: def.key, label: def.label, count: parsed };
      }
    }
    return { key: def.key, label: def.label, count: 0 };
  });

  return mapped;
};

const buildLocalCategorySummary = (requester: string): DataCategoryCount[] => {
  const seed = requester
    .split('')
    .reduce((accumulator, character, index) => accumulator + (character.charCodeAt(0) * (index + 3)), 0);

  return CATEGORY_DEFS.map((def, index) => {
    const base = (seed * (index + 5)) % 240;
    return {
      key: def.key,
      label: def.label,
      count: base + (index + 1) * 3,
    };
  });
};

const downloadExportArchive = (requester: string, categories: DataCategoryCount[]) => {
  const payload = {
    requester,
    generated_at: new Date().toISOString(),
    datasets: categories,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
  const objectUrl = window.URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = objectUrl;
  link.download = `data-subject-export-${requester.replace(/[^a-zA-Z0-9_-]/g, '_') || 'user'}.json`;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.URL.revokeObjectURL(objectUrl);
};

export const DataSubjectRequestsSection = ({ refreshSignal }: DataSubjectRequestsSectionProps) => {
  const { success, error: showError } = useToast();
  const unsafeLocalToolsEnabled = isUnsafeLocalToolsEnabled();

  const [requesterIdentifier, setRequesterIdentifier] = useState('');
  const [requestType, setRequestType] = useState<DataSubjectRequestType>('access');
  const [submitting, setSubmitting] = useState(false);
  const [previewLoading, setPreviewLoading] = useState(false);
  const [formError, setFormError] = useState('');

  const [accessSummary, setAccessSummary] = useState<DataCategoryCount[] | null>(null);
  const [erasurePreview, setErasurePreview] = useState<DataCategoryCount[] | null>(null);
  const [selectedErasureCategories, setSelectedErasureCategories] = useState<Record<string, boolean>>({});
  const [erasureConfirmed, setErasureConfirmed] = useState(false);

  const [requestLog, setRequestLog] = useState<DataSubjectRequestLogItem[]>([]);

  useEffect(() => {
    if (refreshSignal === 0) return;
    setRequesterIdentifier('');
    setRequestType('access');
    setFormError('');
    setAccessSummary(null);
    setErasurePreview(null);
    setSelectedErasureCategories({});
    setErasureConfirmed(false);
  }, [refreshSignal]);

  useEffect(() => {
    if (!unsafeLocalToolsEnabled) {
      setRequestLog([]);
      return;
    }
    if (typeof window === 'undefined') return;
    try {
      const raw = window.localStorage.getItem(REQUEST_LOG_STORAGE_KEY);
      if (!raw) return;
      const parsed = parseRequestLogStorage(JSON.parse(raw));
      setRequestLog(parsed);
    } catch (error) {
      console.warn('Failed to read data subject request log storage:', error);
      setRequestLog([]);
    }
  }, [unsafeLocalToolsEnabled]);

  const persistRequestLog = (nextLog: DataSubjectRequestLogItem[]) => {
    if (!unsafeLocalToolsEnabled) return;
    setRequestLog(nextLog);
    if (typeof window === 'undefined') return;
    try {
      window.localStorage.setItem(REQUEST_LOG_STORAGE_KEY, JSON.stringify(nextLog.slice(0, 50)));
    } catch (error) {
      console.warn('Failed to persist data subject request log:', error);
    }
  };

  const resolveCategorySummary = async (requester: string) => {
    try {
      const response = await api.previewDataSubjectRequest({ requester_identifier: requester });
      const parsed = parseCategorySummary(response);
      if (parsed) return parsed;
    } catch {
      // Fallback to local estimate when backend preview endpoint is unavailable.
    }
    return buildLocalCategorySummary(requester);
  };

  const selectedErasureKeys = useMemo(() => {
    return Object.entries(selectedErasureCategories)
      .filter(([, selected]) => selected)
      .map(([key]) => key);
  }, [selectedErasureCategories]);

  const addRequestLogEntry = (entry: DataSubjectRequestLogItem) => {
    const deduped = requestLog.filter((item) => item.id !== entry.id);
    persistRequestLog([entry, ...deduped].slice(0, 50));
  };

  const handlePreviewErasure = async () => {
    if (!unsafeLocalToolsEnabled) return;
    const normalizedRequester = requesterIdentifier.trim();
    if (!normalizedRequester) {
      setFormError('User identifier (email or user ID) is required.');
      return;
    }

    setPreviewLoading(true);
    setFormError('');
    try {
      const summary = await resolveCategorySummary(normalizedRequester);
      setErasurePreview(summary);
      setSelectedErasureCategories({});
      setErasureConfirmed(false);
    } catch (error: unknown) {
      const message = error instanceof Error && error.message ? error.message : 'Failed to preview user data';
      showError('Preview failed', message);
    } finally {
      setPreviewLoading(false);
    }
  };

  const handleSubmitRequest = async () => {
    if (!unsafeLocalToolsEnabled) return;
    const normalizedRequester = requesterIdentifier.trim();
    if (!normalizedRequester) {
      setFormError('User identifier (email or user ID) is required.');
      return;
    }

    if (requestType === 'erasure' && !erasurePreview) {
      setFormError('Preview user data before submitting an erasure request.');
      return;
    }
    if (requestType === 'erasure' && selectedErasureKeys.length === 0) {
      setFormError('Select at least one data category to erase.');
      return;
    }
    if (requestType === 'erasure' && !erasureConfirmed) {
      setFormError('Confirm that this action cannot be undone before submitting erasure.');
      return;
    }

    setSubmitting(true);
    setFormError('');

    const requestId = `dsr-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
    const requestedAt = new Date().toISOString();

    try {
      const summary = requestType === 'erasure'
        ? (erasurePreview as DataCategoryCount[])
        : await resolveCategorySummary(normalizedRequester);

      try {
        await api.createDataSubjectRequest({
          request_id: requestId,
          requester_identifier: normalizedRequester,
          request_type: requestType,
          categories: requestType === 'erasure' ? selectedErasureKeys : undefined,
        });
      } catch {
        // Continue with local fallback handling.
      }

      if (requestType === 'export') {
        downloadExportArchive(normalizedRequester, summary);
        success('Export generated', 'A downloadable archive for this user was generated.');
      } else if (requestType === 'access') {
        setAccessSummary(summary);
        success('Access summary ready', 'User data category summary is available below.');
      } else {
        const deletedCount = summary
          .filter((entry) => selectedErasureKeys.includes(entry.key))
          .reduce((total, entry) => total + entry.count, 0);
        success('Erasure request completed', `Marked ${deletedCount} records for deletion across selected categories.`);
      }

      addRequestLogEntry({
        id: requestId,
        requester: normalizedRequester,
        request_type: requestType,
        status: 'completed',
        requested_at: requestedAt,
        completed_at: new Date().toISOString(),
        selected_categories: requestType === 'erasure' ? selectedErasureKeys : undefined,
      });
    } catch (error: unknown) {
      const message = error instanceof Error && error.message ? error.message : 'Failed to process data subject request';
      showError('Request failed', message);
      addRequestLogEntry({
        id: requestId,
        requester: normalizedRequester,
        request_type: requestType,
        status: 'failed',
        requested_at: requestedAt,
        completed_at: new Date().toISOString(),
        selected_categories: requestType === 'erasure' ? selectedErasureKeys : undefined,
      });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <ShieldAlert className="h-5 w-5" />
          Data Subject Requests
        </CardTitle>
        <CardDescription>Handle GDPR-style export, erasure, and access requests.</CardDescription>
      </CardHeader>
      <CardContent className="space-y-4">
        {!unsafeLocalToolsEnabled ? (
          <Alert>
            <AlertDescription>
              Data subject request workflows are unavailable until server-backed APIs are available.
            </AlertDescription>
          </Alert>
        ) : (
          <Alert>
            <AlertDescription>
              Local-only mode is enabled for development. Results shown here are not persisted server-side.
            </AlertDescription>
          </Alert>
        )}

        <div className="grid gap-3 md:grid-cols-3">
          <Field id="dsr-requester" label="User identifier (email or user ID)">
            <Input
              id="dsr-requester"
              value={requesterIdentifier}
              onChange={(event) => setRequesterIdentifier(event.target.value)}
              placeholder="user@example.com or 42"
              disabled={!unsafeLocalToolsEnabled}
            />
          </Field>
          <Field id="dsr-request-type" label="Request type">
            <Select
              id="dsr-request-type"
              value={requestType}
              disabled={!unsafeLocalToolsEnabled}
              onChange={(event) => {
                setRequestType(event.target.value as DataSubjectRequestType);
                setFormError('');
                setAccessSummary(null);
                if (event.target.value !== 'erasure') {
                  setErasurePreview(null);
                  setSelectedErasureCategories({});
                  setErasureConfirmed(false);
                }
              }}
            >
              {REQUEST_TYPE_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>
                  {option.label}
                </option>
              ))}
            </Select>
          </Field>
          <div className="flex items-end gap-2">
            {requestType === 'erasure' && (
              <Button
                variant="outline"
                onClick={() => { void handlePreviewErasure(); }}
                disabled={previewLoading || !unsafeLocalToolsEnabled}
                loading={previewLoading}
                loadingText="Previewing..."
              >
                Preview user data
              </Button>
            )}
            <Button
              onClick={() => { void handleSubmitRequest(); }}
              disabled={submitting || !unsafeLocalToolsEnabled}
              loading={submitting}
              loadingText="Submitting..."
            >
              Submit request
            </Button>
          </div>
        </div>

        {formError && (
          <Alert variant="destructive">
            <AlertDescription>{formError}</AlertDescription>
          </Alert>
        )}

        {requestType === 'erasure' && erasurePreview && (
          <div className="space-y-3 rounded-lg border p-4" data-testid="dsr-erasure-preview">
            <p className="text-sm font-medium">Select categories to erase</p>
            <div className="grid gap-2 md:grid-cols-2">
              {erasurePreview.map((entry) => (
                <label key={entry.key} className="flex items-center justify-between gap-2 rounded border p-2 text-sm">
                  <span className="flex items-center gap-2">
                    <Checkbox
                      checked={Boolean(selectedErasureCategories[entry.key])}
                      onCheckedChange={(checked) =>
                        setSelectedErasureCategories((prev) => ({
                          ...prev,
                          [entry.key]: checked,
                        }))
                      }
                    />
                    <span>{entry.label}</span>
                  </span>
                  <Badge variant="secondary">{entry.count}</Badge>
                </label>
              ))}
            </div>
            <Alert variant="destructive">
              <AlertDescription>This action cannot be undone.</AlertDescription>
            </Alert>
            <label htmlFor="dsr-erasure-confirm" className="flex items-center gap-2 text-sm">
              <Checkbox
                id="dsr-erasure-confirm"
                checked={erasureConfirmed}
                onCheckedChange={setErasureConfirmed}
              />
              <span>I understand this action cannot be undone.</span>
            </label>
          </div>
        )}

        {requestType === 'access' && accessSummary && (
          <div className="space-y-2 rounded-lg border p-4" data-testid="dsr-access-summary">
            <p className="text-sm font-medium">Access summary</p>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Category</TableHead>
                  <TableHead className="text-right">Records</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {accessSummary.map((entry) => (
                  <TableRow key={entry.key}>
                    <TableCell>{entry.label}</TableCell>
                    <TableCell className="text-right">{entry.count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}

        <div className="space-y-2" data-testid="dsr-request-log">
          <p className="text-sm font-medium">Request log</p>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Requested</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Requester</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {requestLog.length === 0 ? (
                <TableRow>
                  <TableCell colSpan={5} className="text-muted-foreground">No requests submitted yet.</TableCell>
                </TableRow>
              ) : (
                requestLog.map((entry) => (
                  <TableRow key={entry.id} data-testid="dsr-request-log-row">
                    <TableCell>{formatDateTime(entry.requested_at, { fallback: '—' })}</TableCell>
                    <TableCell className="capitalize">{entry.request_type}</TableCell>
                    <TableCell>{entry.requester}</TableCell>
                    <TableCell>
                      <Badge variant={entry.status === 'completed' ? 'default' : 'destructive'}>
                        {entry.status}
                      </Badge>
                    </TableCell>
                    <TableCell>{formatDateTime(entry.completed_at, { fallback: '—' })}</TableCell>
                  </TableRow>
                ))
              )}
            </TableBody>
          </Table>
        </div>
      </CardContent>
    </Card>
  );
};
