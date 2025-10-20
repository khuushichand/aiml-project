import { useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';

interface WatchlistJob {
  id: number;
  name: string;
  description?: string | null;
  scope?: Record<string, any>;
  schedule_expr?: string | null;
  timezone?: string | null;
  active: boolean;
  output_prefs?: Record<string, any> | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
}

interface JobsListResponse {
  items: WatchlistJob[];
  total: number;
}

interface TemplateSummary {
  name: string;
  format: string;
  description?: string | null;
}

interface WatchlistSettings {
  default_output_ttl_seconds?: number;
  temporary_output_ttl_seconds?: number;
}

interface JobFormState {
  templateName: string;
  defaultRetention: string;
  temporaryRetention: string;
  emailEnabled: boolean;
  emailRecipients: string;
  emailSubject: string;
  emailAttach: boolean;
  chatbookEnabled: boolean;
}

const parseRecipients = (value: string): string[] =>
  value
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

export default function WatchlistsPage() {
  const { show } = useToast();
  const [jobs, setJobs] = useState<WatchlistJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [savingJobId, setSavingJobId] = useState<number | null>(null);
  const [runningJobId, setRunningJobId] = useState<number | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [settings, setSettings] = useState<WatchlistSettings>({});
  const [forms, setForms] = useState<Record<number, JobFormState>>({});

  const templateOptions = useMemo(() => templates.map((tpl) => ({ value: tpl.name, label: `${tpl.name} (${tpl.format})` })), [templates]);

  const normalizeFormState = useCallback(
    (job: WatchlistJob): JobFormState => {
      const prefs = job.output_prefs || {};
      const templateCfg = (prefs.template as Record<string, any>) || {};
      const retentionCfg = (prefs.retention as Record<string, any>) || {};
      const deliveriesCfg = (prefs.deliveries as Record<string, any>) || {};
      const emailCfg = (deliveriesCfg.email as Record<string, any>) || {};
      const chatbookCfg = (deliveriesCfg.chatbook as Record<string, any>) || {};

      return {
        templateName: String(templateCfg.default_name || ''),
        defaultRetention: retentionCfg.default_seconds != null ? String(retentionCfg.default_seconds) : '',
        temporaryRetention: retentionCfg.temporary_seconds != null ? String(retentionCfg.temporary_seconds) : '',
        emailEnabled: emailCfg.enabled !== false,
        emailRecipients: (Array.isArray(emailCfg.recipients) ? emailCfg.recipients : []).join(', '),
        emailSubject: emailCfg.subject || '',
        emailAttach: emailCfg.attach_file !== false,
        chatbookEnabled: chatbookCfg.enabled !== false,
      };
    },
    []
  );

  const fetchSettings = useCallback(async () => {
    try {
      const data = await apiClient.get<WatchlistSettings>('/watchlists/settings');
      setSettings(data || {});
    } catch (error: any) {
      show({ title: 'Failed to load watchlist settings', description: error?.message, variant: 'warning' });
    }
  }, [show]);

  const fetchTemplates = useCallback(async () => {
    try {
      const data = await apiClient.get<{ items: TemplateSummary[] }>('/watchlists/templates');
      setTemplates(data.items || []);
    } catch (error: any) {
      show({ title: 'Failed to load templates', description: error?.message, variant: 'warning' });
    }
  }, [show]);

  const fetchJobs = useCallback(async () => {
    setLoadingJobs(true);
    try {
      const data = await apiClient.get<JobsListResponse>('/watchlists/jobs', { params: { page: 1, size: 100 } });
      setJobs(data.items || []);
    } catch (error: any) {
      setJobs([]);
      show({ title: 'Failed to load watchlist jobs', description: error?.message, variant: 'danger' });
    } finally {
      setLoadingJobs(false);
    }
  }, [show]);

  useEffect(() => {
    fetchSettings();
    fetchTemplates();
    fetchJobs();
  }, [fetchJobs, fetchSettings, fetchTemplates]);

  useEffect(() => {
    const map: Record<number, JobFormState> = {};
    jobs.forEach((job) => {
      map[job.id] = normalizeFormState(job);
    });
    setForms(map);
  }, [jobs, normalizeFormState]);

  const updateForm = (jobId: number, patch: Partial<JobFormState>) => {
    setForms((prev) => ({
      ...prev,
      [jobId]: {
        ...(prev[jobId] || normalizeFormState(jobs.find((j) => j.id === jobId)!)),
        ...patch,
      },
    }));
  };

  const buildOutputPrefsPayload = (state: JobFormState, original: WatchlistJob) => {
    const outputPrefs: Record<string, any> = {};

    if (state.templateName) {
      outputPrefs.template = {
        default_name: state.templateName,
      };
    }

    const retention: Record<string, any> = {};
    if (state.defaultRetention.trim()) {
      const val = parseInt(state.defaultRetention, 10);
      if (!Number.isNaN(val) && val > 0) retention.default_seconds = val;
    }
    if (state.temporaryRetention.trim()) {
      const val = parseInt(state.temporaryRetention, 10);
      if (!Number.isNaN(val) && val >= 0) retention.temporary_seconds = val;
    }
    if (Object.keys(retention).length > 0) {
      outputPrefs.retention = retention;
    }

    const deliveries: Record<string, any> = {};
    deliveries.email = {
      enabled: state.emailEnabled,
      recipients: parseRecipients(state.emailRecipients),
      attach_file: state.emailAttach,
    };
    if (state.emailSubject.trim()) {
      deliveries.email.subject = state.emailSubject.trim();
    }
    deliveries.chatbook = {
      enabled: state.chatbookEnabled,
    };
    outputPrefs.deliveries = deliveries;

    // Preserve any untouched keys from original output_prefs to avoid unintended loss
    const existing = (original.output_prefs || {}) as Record<string, any>;
    return {
      ...existing,
      ...outputPrefs,
    };
  };

  const handleSave = async (job: WatchlistJob) => {
    const state = forms[job.id];
    if (!state) return;
    setSavingJobId(job.id);
    try {
      const payload = { output_prefs: buildOutputPrefsPayload(state, job) };
      await apiClient.patch(`/watchlists/jobs/${job.id}`, payload);
      show({ title: `Updated ${job.name}`, variant: 'success' });
      fetchJobs();
    } catch (error: any) {
      show({ title: `Failed to update ${job.name}`, description: error?.message, variant: 'danger' });
    } finally {
      setSavingJobId(null);
    }
  };

  const handleRun = async (jobId: number) => {
    setRunningJobId(jobId);
    try {
      const run = await apiClient.post<{ id: number; status: string }>(`/watchlists/jobs/${jobId}/run`);
      show({ title: 'Run triggered', description: `Run ${run.id} status: ${run.status}`, variant: 'success' });
    } catch (error: any) {
      show({ title: 'Failed to start run', description: error?.message, variant: 'danger' });
    } finally {
      setRunningJobId(null);
    }
  };

  return (
    <Layout>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Watchlists</h1>
          <p className="mt-1 text-sm text-gray-600">
            Configure watchlist jobs, default templates, and delivery preferences for generated outputs.
          </p>
        </div>

        <div className="grid gap-6 rounded-md border border-gray-200 bg-white p-6 shadow-sm md:grid-cols-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Default Retention</h2>
            <p className="mt-1 text-sm text-gray-600">
              Defaults apply when a job does not override retention values. Temporary outputs follow the temporary TTL.
            </p>
          </div>
          <dl className="grid grid-cols-2 gap-4 text-sm">
            <div>
              <dt className="font-medium text-gray-700">Default TTL</dt>
              <dd className="text-gray-900">
                {settings.default_output_ttl_seconds != null
                  ? `${settings.default_output_ttl_seconds} seconds`
                  : 'Not configured'}
              </dd>
            </div>
            <div>
              <dt className="font-medium text-gray-700">Temporary TTL</dt>
              <dd className="text-gray-900">
                {settings.temporary_output_ttl_seconds != null
                  ? `${settings.temporary_output_ttl_seconds} seconds`
                  : 'Not configured'}
              </dd>
            </div>
          </dl>
        </div>

        <div className="space-y-6">
          {loadingJobs && (
            <div className="rounded-md border border-gray-200 bg-white p-6 text-sm text-gray-600 shadow-sm">
              Loading watchlist jobs…
            </div>
          )}

          {!loadingJobs && jobs.length === 0 && (
            <div className="rounded-md border border-gray-200 bg-white p-6 text-sm text-gray-600 shadow-sm">
              No watchlist jobs found. Create a job via the API to see it here.
            </div>
          )}

          {jobs.map((job) => {
            const state = forms[job.id] || normalizeFormState(job);
            return (
              <div key={job.id} className="space-y-4 rounded-lg border border-gray-200 bg-white p-6 shadow-sm">
                <div className="flex flex-wrap items-start justify-between gap-4">
                  <div>
                    <h3 className="text-lg font-semibold text-gray-900">{job.name}</h3>
                    {job.description && <p className="mt-1 text-sm text-gray-600">{job.description}</p>}
                    <div className="mt-2 text-xs text-gray-500">
                      {job.scope?.tags && job.scope.tags.length > 0 && (
                        <span>Tags: {job.scope.tags.join(', ')} </span>
                      )}
                      {job.scope?.sources && job.scope.sources.length > 0 && (
                        <span>| Sources: {job.scope.sources.length} </span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center space-x-2">
                    <Button
                      type="button"
                      variant="secondary"
                      size="sm"
                      onClick={() => handleRun(job.id)}
                      disabled={runningJobId === job.id}
                    >
                      {runningJobId === job.id ? 'Starting…' : 'Run now'}
                    </Button>
                    <Button
                      type="button"
                      variant="primary"
                      size="sm"
                      onClick={() => handleSave(job)}
                      disabled={savingJobId === job.id}
                    >
                      {savingJobId === job.id ? 'Saving…' : 'Save changes'}
                    </Button>
                  </div>
                </div>

                <div className="grid gap-4 md:grid-cols-2">
                  <label className="flex flex-col text-sm text-gray-700">
                    Template
                    <select
                      value={state.templateName}
                      onChange={(e) => updateForm(job.id, { templateName: e.target.value })}
                      className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                    >
                      <option value="">Use default renderer</option>
                      {templateOptions.map((tpl) => (
                        <option key={tpl.value} value={tpl.value}>
                          {tpl.label}
                        </option>
                      ))}
                    </select>
                    <span className="mt-1 text-xs text-gray-500">
                      Templates are managed via <code>/watchlists/templates</code>.
                    </span>
                  </label>

                  <div className="grid grid-cols-2 gap-3">
                    <Input
                      label="Default retention (seconds)"
                      value={state.defaultRetention}
                      onChange={(e) => updateForm(job.id, { defaultRetention: e.target.value })}
                      placeholder={settings.default_output_ttl_seconds?.toString() || '86400'}
                    />
                    <Input
                      label="Temporary retention (seconds)"
                      value={state.temporaryRetention}
                      onChange={(e) => updateForm(job.id, { temporaryRetention: e.target.value })}
                      placeholder={settings.temporary_output_ttl_seconds?.toString() || '3600'}
                    />
                  </div>

                  <div className="space-y-3 rounded-md border border-gray-100 p-3">
                    <h4 className="text-sm font-semibold text-gray-800">Email delivery</h4>
                    <Switch
                      checked={state.emailEnabled}
                      onChange={(checked) => updateForm(job.id, { emailEnabled: checked })}
                      label="Enable email delivery"
                    />
                    <Input
                      label="Recipients"
                      value={state.emailRecipients}
                      onChange={(e) => updateForm(job.id, { emailRecipients: e.target.value })}
                      placeholder="user@example.com, team@example.com"
                    />
                    <Input
                      label="Subject override"
                      value={state.emailSubject}
                      onChange={(e) => updateForm(job.id, { emailSubject: e.target.value })}
                      placeholder="Optional subject"
                    />
                    <Switch
                      checked={state.emailAttach}
                      onChange={(checked) => updateForm(job.id, { emailAttach: checked })}
                      label="Attach rendered file"
                    />
                  </div>

                  <div className="space-y-3 rounded-md border border-gray-100 p-3">
                    <h4 className="text-sm font-semibold text-gray-800">Chatbook delivery</h4>
                    <Switch
                      checked={state.chatbookEnabled}
                      onChange={(checked) => updateForm(job.id, { chatbookEnabled: checked })}
                      label="Enable Chatbook storage"
                    />
                    <p className="text-xs text-gray-500">
                      When enabled, outputs are stored in Chatbook for later reference alongside metadata.
                    </p>
                  </div>
                </div>

                <div className="text-xs text-gray-500">
                  {job.last_run_at && <span className="mr-4">Last run: {new Date(job.last_run_at).toLocaleString()}</span>}
                  {job.next_run_at && <span>Next run: {new Date(job.next_run_at).toLocaleString()}</span>}
                </div>
              </div>
            );
          })}
        </div>
      </div>
    </Layout>
  );
}
