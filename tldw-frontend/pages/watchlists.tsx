import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';
import { isYouTube, isYouTubeFeedUrl, toCanonicalYouTubeFeed } from '@/lib/urlNormalize';

interface WatchlistJob {
  id: number;
  name: string;
  description?: string | null;
  scope?: Record<string, any>;
  schedule_expr?: string | null;
  timezone?: string | null;
  active: boolean;
  output_prefs?: Record<string, any> | null;
  job_filters?: { filters: WatchlistFilter[]; require_include?: boolean } | null;
  last_run_at?: string | null;
  next_run_at?: string | null;
}

interface JobsListResponse {
  items: WatchlistJob[];
  total: number;
}

type SourceType = 'rss' | 'site';

interface WatchlistSource {
  id: number;
  name: string;
  url: string;
  source_type: SourceType;
  active: boolean;
  tags: string[];
  settings?: Record<string, any> | null;
  status?: string | null;
  last_scraped_at?: string | null;
  created_at: string;
  updated_at: string;
}

interface SourcesListResponse {
  items: WatchlistSource[];
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

type FilterType = 'keyword' | 'author' | 'regex' | 'date_range' | 'all';
type FilterAction = 'include' | 'exclude' | 'flag';

interface WatchlistFilter {
  type: FilterType;
  action: FilterAction;
  value: Record<string, any>;
  priority?: number;
  is_active?: boolean;
}

interface SourceFormState {
  name: string;
  url: string;
  sourceType: SourceType;
  tags: string;
  active: boolean;
  rssLimit: string;
  // RSS History & Content
  historyStrategy: string;
  historyMaxPages: string;
  historyPerPageLimit: string;
  historyOn304: boolean;
  historyStopOnSeen: boolean;
  rssUseFeedContent: boolean;
  rssFeedMinChars: string;
  siteTopN: string;
  siteDiscoverMethod: string;
  siteItemLimit: string;
  listUrl: string;
  entrySelector: string;
  linkSelector: string;
  titleSelector: string;
  summarySelector: string;
  contentSelector: string;
  authorSelector: string;
  publishedSelector: string;
  publishedFormat: string;
  summaryJoin: string;
  contentJoin: string;
  nextSelector: string;
  nextAttribute: string;
  maxPages: string;
  skipArticleFetch: boolean;
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
  filters: WatchlistFilter[];
  requireInclude: boolean;
  showAdvancedFilters: boolean;
  advancedFiltersJson: string;
  // New filter draft inputs
  newFilterType: FilterType;
  newFilterAction: FilterAction;
  newFilterPriority: string;
  newFilterValueText: string; // overloaded for keywords/authors/pattern
  newFilterRegexFlags: string;
  newFilterMaxAgeDays: string;
}

const parseRecipients = (value: string): string[] =>
  value
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

const defaultSourceState = (): SourceFormState => ({
  name: '',
  url: '',
  sourceType: 'site',
  tags: '',
  active: true,
  rssLimit: '25',
  historyStrategy: 'auto',
  historyMaxPages: '1',
  historyPerPageLimit: '',
  historyOn304: false,
  historyStopOnSeen: false,
  rssUseFeedContent: false,
  rssFeedMinChars: '400',
  siteTopN: '1',
  siteDiscoverMethod: 'auto',
  siteItemLimit: '25',
  listUrl: '',
  entrySelector: '',
  linkSelector: '',
  titleSelector: '',
  summarySelector: '',
  contentSelector: '',
  authorSelector: '',
  publishedSelector: '',
  publishedFormat: '',
  summaryJoin: ' ',
  contentJoin: '\n\n',
  nextSelector: '',
  nextAttribute: 'href',
  maxPages: '2',
  skipArticleFetch: false,
});

const parseTagList = (value: string): string[] =>
  value
    .split(',')
    .map((t) => t.trim())
    .filter((t) => t.length > 0);

const normalizeSelectorsInput = (value: string): string | string[] | undefined => {
  const lines = value
    .split('\n')
    .map((line) => line.trim())
    .filter((line) => line.length > 0);
  if (lines.length === 0) return undefined;
  if (lines.length === 1) return lines[0];
  return lines;
};

const toOptionalNumber = (value: string, { allowZero = false }: { allowZero?: boolean } = {}): number | undefined => {
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  if (Number.isNaN(parsed)) return undefined;
  if (!allowZero && parsed <= 0) return undefined;
  if (allowZero && parsed < 0) return undefined;
  return parsed;
};

const nonEmpty = (value: string): string | undefined => {
  const trimmed = value.trim();
  return trimmed.length > 0 ? trimmed : undefined;
};

export default function WatchlistsPage() {
  const { show } = useToast();
  const [jobs, setJobs] = useState<WatchlistJob[]>([]);
  const [loadingJobs, setLoadingJobs] = useState(false);
  const [savingJobId, setSavingJobId] = useState<number | null>(null);
  const [runningJobId, setRunningJobId] = useState<number | null>(null);
  const [templates, setTemplates] = useState<TemplateSummary[]>([]);
  const [settings, setSettings] = useState<WatchlistSettings>({});
  // Admin: org-level defaults
  const [orgIdInput, setOrgIdInput] = useState<string>("");
  const [orgRequireInclude, setOrgRequireInclude] = useState<boolean>(false);
  const [orgSaving, setOrgSaving] = useState<boolean>(false);
  const [showOrgPicker, setShowOrgPicker] = useState<boolean>(false);
  const [orgsList, setOrgsList] = useState<{ id: number; name: string; slug?: string | null }[]>([]);
  const [loadingOrgsList, setLoadingOrgsList] = useState<boolean>(false);
  const [orgsPage, setOrgsPage] = useState<number>(1);
  const [orgsSize, setOrgsSize] = useState<number>(10);
  const [orgsFilter, setOrgsFilter] = useState<string>("");
  const [orgsTotal, setOrgsTotal] = useState<number>(0);
  const [orgsHasMore, setOrgsHasMore] = useState<boolean>(false);
  const [forms, setForms] = useState<Record<number, JobFormState>>({});
  const [sources, setSources] = useState<WatchlistSource[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [savingSource, setSavingSource] = useState(false);
  const [newSource, setNewSource] = useState<SourceFormState>(defaultSourceState());
  const [showScrapeAdvanced, setShowScrapeAdvanced] = useState(false);
  const [opmlFile, setOpmlFile] = useState<File | null>(null);
  const [opmlResult, setOpmlResult] = useState<any | null>(null);
  const [showOpmlModal, setShowOpmlModal] = useState(false);
  const [bulkJsonText, setBulkJsonText] = useState<string>('');
  const [bulkResult, setBulkResult] = useState<any | null>(null);
  const [showBulkModal, setShowBulkModal] = useState(false);

  const templateOptions = useMemo(() => templates.map((tpl) => ({ value: tpl.name, label: `${tpl.name} (${tpl.format})` })), [templates]);

  const updateSourceForm = (patch: Partial<SourceFormState>) => {
    setNewSource((prev) => ({
      ...prev,
      ...patch,
    }));
  };

  const handleSourceUrlChange = (value: string) => {
    setNewSource((prev) => ({
      ...prev,
      url: value,
      listUrl: prev.listUrl ? prev.listUrl : value,
    }));
  };

  const resetSourceForm = () => {
    setNewSource(defaultSourceState());
    setShowScrapeAdvanced(false);
  };

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
        filters: (job.job_filters?.filters as WatchlistFilter[]) || [],
        requireInclude: Boolean((job.job_filters as any)?.require_include || false),
        showAdvancedFilters: false,
        advancedFiltersJson: '',
        newFilterType: 'keyword',
        newFilterAction: 'exclude',
        newFilterPriority: '',
        newFilterValueText: '',
        newFilterRegexFlags: 'i',
        newFilterMaxAgeDays: '',
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

  const fetchSources = useCallback(async () => {
    setLoadingSources(true);
    try {
      const data = await apiClient.get<SourcesListResponse>('/watchlists/sources', { params: { page: 1, size: 100 } });
      setSources(data.items || []);
    } catch (error: any) {
      setSources([]);
      show({ title: 'Failed to load watchlist sources', description: error?.message, variant: 'danger' });
    } finally {
      setLoadingSources(false);
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
    fetchSources();
    fetchJobs();
  }, [fetchJobs, fetchSettings, fetchSources, fetchTemplates]);

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

  const handleImportOPML = async () => {
    if (!opmlFile) return;
    try {
      const form = new FormData();
      form.append('file', opmlFile);
      const data = await apiClient.post('/watchlists/sources/import', form, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setOpmlResult(data);
      setShowOpmlModal(true);
      show({ title: 'OPML import completed', description: `Created ${data.created}, errors ${data.errors}`, variant: data.errors ? 'warning' : 'success' });
      setOpmlFile(null);
      fetchSources();
    } catch (error: any) {
      show({ title: 'Import failed', description: error?.message, variant: 'danger' });
    }
  };

  const handleExportOPML = async () => {
    try {
      const data = await apiClient.get<Blob>('/watchlists/sources/export', { responseType: 'blob' });
      const blob = new Blob([data], { type: 'application/xml' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = 'watchlists.opml';
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (error: any) {
      show({ title: 'Export failed', description: error?.message, variant: 'danger' });
    }
  };

  const handleBulkJsonSubmit = async () => {
    try {
      const payload = JSON.parse(bulkJsonText || '{}');
      if (!payload || typeof payload !== 'object' || !Array.isArray(payload.sources)) {
        show({ title: 'Invalid payload', description: 'JSON must be an object with a sources[] array', variant: 'warning' });
        return;
      }
      const data = await apiClient.post('/watchlists/sources/bulk', payload);
      setBulkResult(data);
      setShowBulkModal(true);
      show({ title: 'Bulk create completed', description: `Created ${data.created}, errors ${data.errors}`, variant: data.errors ? 'warning' : 'success' });
      fetchSources();
    } catch (error: any) {
      show({ title: 'Bulk create failed', description: error?.message, variant: 'danger' });
    }
  };

  const saveOrgDefaults = async () => {
    const trimmed = orgIdInput.trim();
    if (!trimmed) {
      show({ title: 'Enter an organization ID', variant: 'warning' });
      return;
    }
    const idNum = Number(trimmed);
    if (!Number.isFinite(idNum) || idNum <= 0) {
      show({ title: 'Invalid organization ID', variant: 'warning' });
      return;
    }
    setOrgSaving(true);
    try {
      await apiClient.patch(`/admin/orgs/${idNum}/watchlists/settings`, { require_include_default: orgRequireInclude });
      show({ title: 'Org defaults saved', description: `Org ${idNum}: require_include_default=${orgRequireInclude}`, variant: 'success' });
    } catch (error: any) {
      show({ title: 'Failed to save org defaults', description: error?.message, variant: 'danger' });
    } finally {
      setOrgSaving(false);
    }
  };

  const loadOrgDefaults = async () => {
    const trimmed = orgIdInput.trim();
    if (!trimmed) {
      show({ title: 'Enter an organization ID', variant: 'warning' });
      return;
    }
    const idNum = Number(trimmed);
    if (!Number.isFinite(idNum) || idNum <= 0) {
      show({ title: 'Invalid organization ID', variant: 'warning' });
      return;
    }
    try {
      const data = await apiClient.get<{ org_id: number; require_include_default?: boolean }>(`/admin/orgs/${idNum}/watchlists/settings`);
      setOrgRequireInclude(Boolean(data?.require_include_default || false));
      show({ title: 'Loaded org defaults', description: `Org ${idNum}: require_include_default=${Boolean(data?.require_include_default || false)}`, variant: 'success' });
    } catch (error: any) {
      show({ title: 'Failed to load org defaults', description: error?.message, variant: 'danger' });
    }
  };

  const fetchOrgListInline = async () => {
    setLoadingOrgsList(true);
    try {
      const offset = (orgsPage - 1) * orgsSize;
      const params: any = { limit: orgsSize, offset };
      if (orgsFilter.trim()) params.q = orgsFilter.trim();
      const data = await apiClient.get<{ items: { id: number; name: string; slug?: string | null }[]; total: number; has_more: boolean }>(
        '/admin/orgs',
        { params }
      );
      setOrgsList(Array.isArray((data as any)?.items) ? data.items : []);
      setOrgsTotal(Number.isFinite((data as any)?.total) ? data.total : 0);
      setOrgsHasMore(Boolean((data as any)?.has_more));
    } catch (error: any) {
      setOrgsList([]);
      setOrgsTotal(0);
      setOrgsHasMore(false);
      show({ title: 'Failed to load organizations', description: error?.message, variant: 'danger' });
    } finally {
      setLoadingOrgsList(false);
    }
  };

  const addFilter = (jobId: number) => {
    const st = forms[jobId];
    if (!st) return;
    const f: WatchlistFilter = { type: st.newFilterType, action: st.newFilterAction, value: {}, is_active: true };
    const pr = parseInt(st.newFilterPriority || '0', 10);
    if (!Number.isNaN(pr)) f.priority = pr;
    if (st.newFilterType === 'keyword') {
      const keywords = parseTagList(st.newFilterValueText);
      if (keywords.length === 0) return;
      f.value = { keywords, match: 'any' };
    } else if (st.newFilterType === 'author') {
      const names = parseTagList(st.newFilterValueText);
      if (names.length === 0) return;
      f.value = { names, match: 'any' };
    } else if (st.newFilterType === 'regex') {
      const pattern = st.newFilterValueText.trim();
      if (!pattern) return;
      const flags = st.newFilterRegexFlags.trim() || 'i';
      f.value = { pattern, flags, field: 'title' };
    } else if (st.newFilterType === 'date_range') {
      const days = parseInt(st.newFilterMaxAgeDays || '0', 10);
      if (!Number.isNaN(days) && days > 0) f.value = { max_age_days: days };
      else return;
    } else {
      f.value = {};
    }
    setForms((prev) => ({
      ...prev,
      [jobId]: { ...prev[jobId], filters: [...(prev[jobId].filters || []), f], newFilterValueText: '', newFilterPriority: '' },
    }));
  };

  const removeFilter = (jobId: number, index: number) => {
    setForms((prev) => {
      const arr = [...(prev[jobId].filters || [])];
      arr.splice(index, 1);
      return { ...prev, [jobId]: { ...prev[jobId], filters: arr } };
    });
  };

  const saveFilters = async (jobId: number) => {
    try {
      const state = forms[jobId];
      if (state.showAdvancedFilters) {
        let payload: any = null;
        try {
          payload = JSON.parse(state.advancedFiltersJson || '{}');
        } catch (e: any) {
          throw new Error('Invalid JSON in advanced filters editor');
        }
        if (!payload || typeof payload !== 'object') {
          throw new Error('Advanced payload must be a JSON object');
        }
        await apiClient.patch(`/watchlists/jobs/${jobId}/filters`, payload);
      } else {
        const filters = (state.filters || []).map((f) => ({ type: f.type, action: f.action, value: f.value, priority: f.priority, is_active: f.is_active !== false }));
        await apiClient.patch(`/watchlists/jobs/${jobId}/filters`, { require_include: state.requireInclude, filters });
      }
      show({ title: 'Filters saved', variant: 'success' });
    } catch (error: any) {
      show({ title: 'Failed to save filters', description: error?.message, variant: 'danger' });
    }
  };

  const handleCreateSource = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const name = newSource.name.trim();
    const url = newSource.url.trim();
    if (!name || !url) {
      show({ title: 'Name and URL are required', variant: 'warning' });
      return;
    }

    const payload: Record<string, any> = {
      name,
      url,
      source_type: newSource.sourceType,
      active: newSource.active,
    };

    // Optional UX: Normalize/validate YouTube URLs for RSS sources before submit
    if (newSource.sourceType === 'rss') {
      if (isYouTube(payload.url) && !isYouTubeFeedUrl(payload.url)) {
        const canonical = toCanonicalYouTubeFeed(payload.url);
        if (canonical) {
          payload.url = canonical;
          show({ title: 'Converted to RSS feed URL', description: 'YouTube URL was normalized to a canonical feed.', variant: 'success' });
        } else {
          show({ title: 'Invalid YouTube URL for RSS', description: 'Use canonical feed URLs: channel → https://www.youtube.com/feeds/videos.xml?channel_id=..., playlist → https://www.youtube.com/feeds/videos.xml?playlist_id=.... Open the channel page to find /channel/<CHANNEL_ID>.', variant: 'warning' });
          return;
        }
      }
    }

    const tags = parseTagList(newSource.tags);
    if (tags.length > 0) {
      payload.tags = tags;
    }

    const settings: Record<string, any> = {};
    if (newSource.sourceType === 'rss') {
      const limit = toOptionalNumber(newSource.rssLimit);
      if (limit !== undefined) settings.limit = limit;
      // History config
      const hist: Record<string, any> = {};
      const strat = nonEmpty(newSource.historyStrategy);
      if (strat) hist.strategy = strat;
      const maxPages = toOptionalNumber(newSource.historyMaxPages);
      if (maxPages !== undefined) hist.max_pages = maxPages;
      const perPage = toOptionalNumber(newSource.historyPerPageLimit, { allowZero: false });
      if (perPage !== undefined) hist.per_page_limit = perPage;
      if (newSource.historyOn304) hist.on_304 = true;
      if (newSource.historyStopOnSeen) hist.stop_on_seen = true;
      if (Object.keys(hist).length > 0) settings.history = hist;
      // RSS content preferences
      const rssCfg: Record<string, any> = {};
      if (newSource.rssUseFeedContent) rssCfg.use_feed_content_if_available = true;
      const minChars = toOptionalNumber(newSource.rssFeedMinChars, { allowZero: false });
      if (minChars !== undefined) rssCfg.feed_content_min_chars = minChars;
      if (Object.keys(rssCfg).length > 0) settings.rss = rssCfg;
    }

    if (newSource.sourceType === 'site') {
      const topN = toOptionalNumber(newSource.siteTopN);
      if (topN !== undefined) settings.top_n = topN;
      const discoverMethod = nonEmpty(newSource.siteDiscoverMethod);
      if (discoverMethod) settings.discover_method = discoverMethod;

      const rules: Record<string, any> = {};
      const listUrl = nonEmpty(newSource.listUrl) || url;
      if (listUrl) rules.list_url = listUrl;

      const entrySelectors = normalizeSelectorsInput(newSource.entrySelector);
      if (entrySelectors) rules.entry_xpath = entrySelectors;

      const linkSelectors = normalizeSelectorsInput(newSource.linkSelector);
      if (linkSelectors) rules.link_xpath = linkSelectors;

      const titleSelectors = normalizeSelectorsInput(newSource.titleSelector);
      if (titleSelectors) rules.title_xpath = titleSelectors;

      const summarySelectors = normalizeSelectorsInput(newSource.summarySelector);
      if (summarySelectors) rules.summary_xpath = summarySelectors;

      const contentSelectors = normalizeSelectorsInput(newSource.contentSelector);
      if (contentSelectors) rules.content_xpath = contentSelectors;

      const authorSelectors = normalizeSelectorsInput(newSource.authorSelector);
      if (authorSelectors) rules.author_xpath = authorSelectors;

      const publishedSelectors = normalizeSelectorsInput(newSource.publishedSelector);
      if (publishedSelectors) rules.published_xpath = publishedSelectors;

      const publishedFormat = nonEmpty(newSource.publishedFormat);
      if (publishedFormat) rules.published_format = publishedFormat;

      const summaryJoin = nonEmpty(newSource.summaryJoin);
      if (summaryJoin) rules.summary_join_with = summaryJoin;

      const contentJoin = nonEmpty(newSource.contentJoin);
      if (contentJoin) rules.content_join_with = contentJoin;

      const ruleLimit = toOptionalNumber(newSource.siteItemLimit);
      if (ruleLimit !== undefined) rules.limit = ruleLimit;

      if (newSource.skipArticleFetch) {
        rules.skip_article_fetch = true;
      }

      const pagination: Record<string, any> = {};
      const nextSelectors = normalizeSelectorsInput(newSource.nextSelector);
      if (nextSelectors) pagination.next_xpath = nextSelectors;
      const nextAttribute = nonEmpty(newSource.nextAttribute);
      if (nextAttribute && nextAttribute !== 'href') {
        pagination.next_attribute = nextAttribute;
      }
      const maxPages = toOptionalNumber(newSource.maxPages);
      if (maxPages !== undefined) {
        pagination.max_pages = maxPages;
      }
      if (Object.keys(pagination).length > 0) {
        rules.pagination = pagination;
      }

      if (Object.keys(rules).length > 0) {
        settings.scrape_rules = rules;
      }
    }

    if (Object.keys(settings).length > 0) {
      payload.settings = settings;
    }

    setSavingSource(true);
    try {
      await apiClient.post('/watchlists/sources', payload);
      show({ title: `Added ${name}`, variant: 'success' });
      resetSourceForm();
      fetchSources();
    } catch (error: any) {
      show({ title: `Failed to add ${name}`, description: error?.message, variant: 'danger' });
    } finally {
      setSavingSource(false);
    }
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

        {/* Import/Export and Bulk Upload */}
        <div className="grid gap-6 rounded-md border border-gray-200 bg-white p-6 shadow-sm md:grid-cols-2">
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-800">OPML Import/Export</h2>
            <input type="file" accept=".opml,.xml" onChange={(e) => setOpmlFile(e.target.files?.[0] || null)} />
            <div className="flex gap-3">
              <Button onClick={handleImportOPML} disabled={!opmlFile}>Import OPML</Button>
              <Button variant="secondary" onClick={handleExportOPML}>Export OPML</Button>
              {opmlResult && (
                <Button variant="ghost" onClick={() => setShowOpmlModal(true)}>View Results</Button>
              )}
            </div>
          </div>
          <div className="space-y-3">
            <h2 className="text-lg font-semibold text-gray-800">Bulk JSON Upload</h2>
            <p className="text-sm text-gray-600">Paste JSON like {'{ "sources": [ ... ] }'} and submit.</p>
            <textarea className="w-full rounded border border-gray-300 p-2 text-sm" rows={6} value={bulkJsonText} onChange={(e) => setBulkJsonText(e.target.value)} placeholder='{"sources":[{"name":"Site A","url":"https://a.example.com/","source_type":"site"}]}' />
            <div className="flex gap-3">
              <Button onClick={handleBulkJsonSubmit}>Upload Bulk JSON</Button>
              {bulkResult && (
                <Button variant="ghost" onClick={() => setShowBulkModal(true)}>View Results</Button>
              )}
            </div>
          </div>
        </div>

        {/* Results Modals */}
        {showOpmlModal && opmlResult && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowOpmlModal(false)}>
            <div className="max-h-[80vh] w-[90vw] max-w-4xl overflow-auto rounded bg-white p-4 shadow-lg" onClick={(e) => e.stopPropagation()}>
              <div className="mb-3 flex items-center justify-between"><h3 className="text-lg font-semibold">OPML Import Results</h3><Button variant="ghost" onClick={() => setShowOpmlModal(false)}>Close</Button></div>
              <p className="mb-2 text-sm text-gray-600">Total: {opmlResult.total} • Created: {opmlResult.created} • Skipped: {opmlResult.skipped} • Errors: {opmlResult.errors}</p>
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead><tr><th className="px-2 py-1">Name</th><th className="px-2 py-1">URL</th><th className="px-2 py-1">Status</th><th className="px-2 py-1">Error</th><th className="px-2 py-1">ID</th></tr></thead>
                  <tbody>
                    {(opmlResult.items || []).map((it: any, idx: number) => (
                      <tr key={idx} className="border-t">
                        <td className="px-2 py-1">{it.name || ''}</td>
                        <td className="px-2 py-1 break-all">{it.url}</td>
                        <td className="px-2 py-1">{it.status}</td>
                        <td className="px-2 py-1">{it.error || ''}</td>
                        <td className="px-2 py-1">{it.id || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {opmlResult.errors > 0 && (
                <div className="mt-3">
                  <Button variant="secondary" onClick={() => {
                    const rows = (opmlResult.items || []).filter((it: any) => it.status !== 'created');
                    const csv = ['name,url,status,error'].concat(rows.map((r: any) => [r.name || '', r.url || '', r.status || '', r.error || ''].map((s: string) => '"' + String(s).replaceAll('"','""') + '"').join(','))).join('\n');
                    const blob = new Blob([csv], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = 'opml_import_errors.csv'; a.click(); URL.revokeObjectURL(url);
                  }}>Download Errors CSV</Button>
                </div>
              )}
            </div>
          </div>
        )}

        {showBulkModal && bulkResult && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowBulkModal(false)}>
            <div className="max-h-[80vh] w-[90vw] max-w-4xl overflow-auto rounded bg-white p-4 shadow-lg" onClick={(e) => e.stopPropagation()}>
              <div className="mb-3 flex items-center justify-between"><h3 className="text-lg font-semibold">Bulk JSON Results</h3><Button variant="ghost" onClick={() => setShowBulkModal(false)}>Close</Button></div>
              <p className="mb-2 text-sm text-gray-600">Total: {bulkResult.total} • Created: {bulkResult.created} • Errors: {bulkResult.errors}</p>
              <div className="overflow-auto">
                <table className="w-full text-left text-sm">
                  <thead><tr><th className="px-2 py-1">Name</th><th className="px-2 py-1">URL</th><th className="px-2 py-1">Type</th><th className="px-2 py-1">Status</th><th className="px-2 py-1">Error</th><th className="px-2 py-1">ID</th></tr></thead>
                  <tbody>
                    {(bulkResult.items || []).map((it: any, idx: number) => (
                      <tr key={idx} className="border-t">
                        <td className="px-2 py-1">{it.name || ''}</td>
                        <td className="px-2 py-1 break-all">{it.url}</td>
                        <td className="px-2 py-1">{it.source_type || ''}</td>
                        <td className="px-2 py-1">{it.status}</td>
                        <td className="px-2 py-1">{it.error || ''}</td>
                        <td className="px-2 py-1">{it.id || ''}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              {bulkResult.errors > 0 && (
                <div className="mt-3">
                  <Button variant="secondary" onClick={() => {
                    const rows = (bulkResult.items || []).filter((it: any) => it.status !== 'created');
                    const csv = ['name,url,source_type,status,error'].concat(rows.map((r: any) => [r.name || '', r.url || '', r.source_type || '', r.status || '', r.error || ''].map((s: string) => '"' + String(s).replaceAll('"','""') + '"').join(','))).join('\n');
                    const blob = new Blob([csv], { type: 'text/csv' });
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url; a.download = 'bulk_create_errors.csv'; a.click(); URL.revokeObjectURL(url);
                  }}>Download Errors CSV</Button>
                </div>
              )}
            </div>
          </div>
        )}

        <div className="grid gap-6 rounded-md border border-gray-200 bg-white p-6 shadow-sm md:grid-cols-2">
          <div>
            <h2 className="text-lg font-semibold text-gray-800">Org Defaults (Admin)</h2>
            <p className="mt-1 text-sm text-gray-600">
              Set default include-only gating for jobs in a specific organization.
            </p>
          </div>
          <div className="grid gap-3">
            <Input
              label="Organization ID"
              value={orgIdInput}
              onChange={(e) => {
                const cleaned = e.target.value.replace(/[^0-9]/g, '');
                setOrgIdInput(cleaned);
              }}
              placeholder="e.g., 1"
              type="number"
              min={1}
              inputMode="numeric"
            />
            <div className="flex items-center gap-3">
              <Switch
                checked={orgRequireInclude}
                onChange={(checked) => setOrgRequireInclude(checked)}
                label="Default: Require include match"
              />
              <Button
                type="button"
                size="sm"
                variant="ghost"
                onClick={async () => {
                  setShowOrgPicker((prev) => !prev);
                  if (!showOrgPicker) {
                    await fetchOrgListInline();
                  }
                }}
              >
                {showOrgPicker ? 'Hide orgs' : 'Browse orgs'}
              </Button>
              <Button type="button" size="sm" variant="secondary" onClick={loadOrgDefaults} disabled={!orgIdInput || Number(orgIdInput) <= 0}>
                Load
              </Button>
              <Button type="button" size="sm" variant="primary" onClick={saveOrgDefaults} disabled={orgSaving || !orgIdInput || Number(orgIdInput) <= 0}>
                {orgSaving ? 'Saving…' : 'Save'}
              </Button>
            </div>
            {showOrgPicker && (
              <div className="mt-2 rounded-md border border-gray-200 bg-gray-50 p-3">
                <div className="mb-2 flex items-center justify-between text-xs text-gray-600">
                  <div className="flex flex-wrap items-center gap-2">
                    <span>Organizations</span>
                    <Input
                      label=""
                      value={orgsFilter}
                      onChange={(e) => setOrgsFilter(e.target.value)}
                      placeholder="Filter by name, slug, or ID"
                    />
                    <label className="flex items-center gap-1">
                      <span>Page size</span>
                      <select
                        className="rounded-md border border-gray-300 bg-white px-1 py-[2px] text-xs"
                        value={orgsSize}
                        onChange={async (e) => {
                          const v = Number(e.target.value);
                          setOrgsSize(Number.isFinite(v) && v > 0 ? v : 10);
                          setOrgsPage(1);
                          await fetchOrgListInline();
                        }}
                      >
                        <option value={5}>5</option>
                        <option value={10}>10</option>
                        <option value={20}>20</option>
                        <option value={50}>50</option>
                      </select>
                    </label>
                    <span>Page {orgsPage} of {Math.max(1, Math.ceil((orgsTotal || 0) / (orgsSize || 1)))}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <Button type="button" size="xs" variant="secondary" onClick={async () => { setOrgsPage((p) => Math.max(1, p - 1)); await fetchOrgListInline(); }} disabled={loadingOrgsList || orgsPage <= 1}>
                      Prev
                    </Button>
                    <Button type="button" size="xs" variant="secondary" onClick={async () => { setOrgsPage((p) => p + 1); await fetchOrgListInline(); }} disabled={loadingOrgsList || !orgsHasMore}>
                      Next
                    </Button>
                    <Button type="button" size="xs" variant="secondary" onClick={fetchOrgListInline} disabled={loadingOrgsList}>
                      {loadingOrgsList ? 'Refreshing…' : 'Refresh'}
                    </Button>
                  </div>
                </div>
                {loadingOrgsList && (
                  <div className="text-xs text-gray-500">Loading…</div>
                )}
                {!loadingOrgsList && orgsList.length === 0 && (
                  <div className="text-xs text-gray-500">No organizations found.</div>
                )}
                {!loadingOrgsList && orgsList.length > 0 && (
                  <ul className="divide-y divide-gray-200 text-sm">
                    {orgsList
                      .filter((o) => {
                        const q = orgsFilter.trim().toLowerCase();
                        if (!q) return true;
                        const name = (o.name || '').toLowerCase();
                        const slug = (o.slug || '').toLowerCase();
                        return name.includes(q) || slug.includes(q) || String(o.id).includes(q);
                      })
                      .map((o) => (
                      <li key={o.id} className="flex items-center justify-between py-1">
                        <div className="truncate text-gray-700">
                          <span className="font-medium text-gray-900">{o.id}</span> · {o.name}
                          {o.slug ? <span className="text-gray-500"> ({o.slug})</span> : null}
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            type="button"
                            size="xs"
                            variant="secondary"
                            onClick={() => {
                              setOrgIdInput(String(o.id));
                              show({ title: 'Selected organization', description: `Org ID ${o.id}`, variant: 'success' });
                            }}
                          >
                            Use
                          </Button>
                          <Button
                            type="button"
                            size="xs"
                            variant="ghost"
                            onClick={async () => {
                              try {
                                await navigator.clipboard.writeText(String(o.id));
                                show({ title: 'Copied ID', description: String(o.id), variant: 'success' });
                              } catch (e: any) {
                                show({ title: 'Copy failed', description: e?.message, variant: 'danger' });
                              }
                            }}
                          >
                            Copy ID
                          </Button>
                          {o.slug && (
                            <Button
                              type="button"
                              size="xs"
                              variant="ghost"
                              onClick={async () => {
                                try {
                                  await navigator.clipboard.writeText(String(o.slug));
                                  show({ title: 'Copied slug', description: String(o.slug), variant: 'success' });
                                } catch (e: any) {
                                  show({ title: 'Copy failed', description: e?.message, variant: 'danger' });
                                }
                              }}
                            >
                              Copy slug
                            </Button>
                          )}
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
              </div>
            )}
          </div>
        </div>

        <div className="space-y-6 rounded-md border border-gray-200 bg-white p-6 shadow-sm">
          <div className="flex flex-wrap items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-gray-800">Sources</h2>
              <p className="mt-1 text-sm text-gray-600">
                Manage RSS feeds and site scrapers. XPath selectors can be combined with optional CSS by prefixing values
                with <code>css:</code>. Provide one selector per line to define fallbacks.
              </p>
              <div className="mt-2 rounded-md border border-indigo-100 bg-indigo-50/50 p-3 text-xs text-indigo-900">
                <div className="font-semibold">Tip: YouTube as RSS</div>
                <p className="mt-1">
                  Add YouTube channels or playlists as RSS by using canonical feed URLs:
                </p>
                <ul className="ml-5 list-disc">
                  <li>
                    Channel: <code>https://www.youtube.com/feeds/videos.xml?channel_id=&lt;CHANNEL_ID&gt;</code>
                  </li>
                  <li>
                    Playlist: <code>https://www.youtube.com/feeds/videos.xml?playlist_id=&lt;PLAYLIST_ID&gt;</code>
                  </li>
                </ul>
                <p className="mt-1">
                  Handle/vanity URLs (e.g., <code>youtube.com/@handle</code>) are not feeds. Open the channel page and copy the
                  URL with <code>/channel/&lt;CHANNEL_ID&gt;</code>, or paste a canonical feed URL directly.
                </p>
              </div>
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={fetchSources} disabled={loadingSources}>
              {loadingSources ? 'Refreshing…' : 'Refresh'}
            </Button>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <input type="file" accept=".opml,.xml" onChange={(e) => setOpmlFile(e.target.files?.[0] || null)} />
            <Button type="button" variant="primary" size="sm" onClick={handleImportOPML} disabled={!opmlFile || savingSource}>
              Import OPML
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={handleExportOPML}>
              Export OPML
            </Button>
          </div>

          {loadingSources && (
            <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
              Loading sources…
            </div>
          )}

          {!loadingSources && sources.length === 0 && (
            <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
              No sources configured yet. Add an RSS feed or configure a site scraper below.
            </div>
          )}

          {!loadingSources && sources.length > 0 && (
            <ul className="divide-y divide-gray-100 rounded-md border border-gray-100">
              {sources.map((source) => (
                <li key={source.id} className="space-y-1 px-4 py-3 text-sm text-gray-700">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <p className="font-medium text-gray-900">{source.name}</p>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noreferrer"
                        className="text-xs text-indigo-600 hover:underline"
                      >
                        {source.url}
                      </a>
                    </div>
                    <div className="text-xs uppercase tracking-wide text-gray-500">
                      {source.source_type} · {source.active ? 'active' : 'paused'}
                    </div>
                  </div>
                  <div className="flex flex-wrap items-center gap-3 text-xs text-gray-500">
                    {source.tags.length > 0 && <span>Tags: {source.tags.join(', ')}</span>}
                    {source.status && <span>Status: {source.status}</span>}
                    {source.last_scraped_at && (
                      <span>
                        Last run: {new Date(source.last_scraped_at).toLocaleString()}
                      </span>
                    )}
                    {source.settings?.scrape_rules && <span className="text-indigo-600">Scrape rules enabled</span>}
                  </div>
                </li>
              ))}
            </ul>
          )}

          <form className="space-y-5 pt-2" onSubmit={handleCreateSource}>
            <div className="grid gap-4 md:grid-cols-2">
              <Input
                label="Name"
                value={newSource.name}
                onChange={(e) => updateSourceForm({ name: e.target.value })}
                placeholder="TechCrunch front page"
                required
              />
              <Input
                label="Primary URL"
                value={newSource.url}
                onChange={(e) => handleSourceUrlChange(e.target.value)}
                placeholder="https://example.com"
                required
              />
              <label className="flex flex-col text-sm text-gray-700">
                Source type
                <select
                  value={newSource.sourceType}
                  onChange={(e) => updateSourceForm({ sourceType: e.target.value as SourceType })}
                  className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                >
                  <option value="site">Site scraper</option>
                  <option value="rss">RSS/Atom feed</option>
                </select>
              </label>
              <Input
                label="Tags (comma separated)"
                value={newSource.tags}
                onChange={(e) => updateSourceForm({ tags: e.target.value })}
                placeholder="news, ai"
              />
            </div>

            <div className="flex items-center gap-4">
              <Switch
                checked={newSource.active}
                onChange={(checked) => updateSourceForm({ active: checked })}
                label="Source active"
              />
            </div>

            {newSource.sourceType === 'rss' && (
              <div className="space-y-4">
                <div className="grid gap-4 md:grid-cols-2">
                  <Input
                    label="Item limit per poll"
                    value={newSource.rssLimit}
                    onChange={(e) => updateSourceForm({ rssLimit: e.target.value })}
                    placeholder="25"
                  />
                </div>

                <div className="rounded-md border border-dashed border-indigo-200 bg-indigo-50/50 p-4">
                  <div className="mb-2">
                    <h3 className="text-sm font-semibold text-indigo-900">History & RSS (advanced)</h3>
                    <p className="text-xs text-indigo-700">Backfill older pages and prefer feed full text when available.</p>
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <label className="flex flex-col text-sm text-gray-700">
                      History strategy
                      <select
                        value={newSource.historyStrategy}
                        onChange={(e) => updateSourceForm({ historyStrategy: e.target.value })}
                        className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                      >
                        <option value="auto">auto</option>
                        <option value="atom">atom</option>
                        <option value="wordpress">wordpress</option>
                        <option value="none">none</option>
                      </select>
                    </label>
                    <Input
                      label="Max pages (incl. first)"
                      value={newSource.historyMaxPages}
                      onChange={(e) => updateSourceForm({ historyMaxPages: e.target.value })}
                      placeholder="1"
                    />
                    <Input
                      label="Per-page item limit"
                      value={newSource.historyPerPageLimit}
                      onChange={(e) => updateSourceForm({ historyPerPageLimit: e.target.value })}
                      placeholder="inherit"
                    />
                  </div>
                  <div className="mt-2 grid gap-3 md:grid-cols-2">
                    <Switch
                      checked={newSource.historyOn304}
                      onChange={(checked) => updateSourceForm({ historyOn304: checked })}
                      label="Backfill on 304"
                    />
                    <Switch
                      checked={newSource.historyStopOnSeen}
                      onChange={(checked) => updateSourceForm({ historyStopOnSeen: checked })}
                      label="Stop when page has no new items"
                    />
                  </div>
                  <div className="mt-3 grid gap-3 md:grid-cols-2">
                    <Switch
                      checked={newSource.rssUseFeedContent}
                      onChange={(checked) => updateSourceForm({ rssUseFeedContent: checked })}
                      label="Prefer feed full text when long"
                    />
                    <Input
                      label="Feed text min chars"
                      value={newSource.rssFeedMinChars}
                      onChange={(e) => updateSourceForm({ rssFeedMinChars: e.target.value })}
                      placeholder="400"
                    />
                  </div>
                </div>
              </div>
            )}

            {newSource.sourceType === 'site' && (
              <div className="space-y-5">
                <div className="grid gap-4 md:grid-cols-3">
                  <Input
                    label="Top links per run"
                    value={newSource.siteTopN}
                    onChange={(e) => updateSourceForm({ siteTopN: e.target.value })}
                    placeholder="3"
                  />
                  <label className="flex flex-col text-sm text-gray-700">
                    Discovery method
                    <select
                      value={newSource.siteDiscoverMethod}
                      onChange={(e) => updateSourceForm({ siteDiscoverMethod: e.target.value })}
                      className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                    >
                      <option value="auto">Auto</option>
                      <option value="frontpage">Front page</option>
                      <option value="sitemap">Sitemap</option>
                    </select>
                  </label>
                  <Input
                    label="Scraped item limit"
                    value={newSource.siteItemLimit}
                    onChange={(e) => updateSourceForm({ siteItemLimit: e.target.value })}
                    placeholder="25"
                  />
                </div>

                <div className="rounded-md border border-dashed border-indigo-200 bg-indigo-50/50 p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div>
                      <h3 className="text-sm font-semibold text-indigo-900">Scrape rules</h3>
                      <p className="text-xs text-indigo-700">
                        Define selectors for list pages and pagination to mirror FreshRSS or Feed‑Me‑Up‑Scotty recipes.
                      </p>
                    </div>
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      onClick={() => setShowScrapeAdvanced((prev) => !prev)}
                    >
                      {showScrapeAdvanced ? 'Hide selectors' : 'Configure selectors'}
                    </Button>
                  </div>

                  {showScrapeAdvanced && (
                    <div className="mt-4 space-y-4">
                      <Input
                        label="List URL override"
                        value={newSource.listUrl}
                        onChange={(e) => updateSourceForm({ listUrl: e.target.value })}
                        placeholder="Defaults to primary URL"
                      />

                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="flex flex-col text-sm text-gray-700">
                          Entry selectors
                          <textarea
                            value={newSource.entrySelector}
                            onChange={(e) => updateSourceForm({ entrySelector: e.target.value })}
                            placeholder="//article | css:.post-card"
                            className="mt-1 min-h-[88px] rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                          <span className="mt-1 text-xs text-gray-500">
                            One XPath or CSS selector per line to find each item container.
                          </span>
                        </label>
                        <label className="flex flex-col text-sm text-gray-700">
                          Link selectors
                          <textarea
                            value={newSource.linkSelector}
                            onChange={(e) => updateSourceForm({ linkSelector: e.target.value })}
                            placeholder=".//a[@class='story']/@href"
                            className="mt-1 min-h-[88px] rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                          <span className="mt-1 text-xs text-gray-500">
                            Provide XPath returning URLs (use <code>@href</code>) or CSS selectors.
                          </span>
                        </label>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="flex flex-col text-sm text-gray-700">
                          Title selectors
                          <textarea
                            value={newSource.titleSelector}
                            onChange={(e) => updateSourceForm({ titleSelector: e.target.value })}
                            placeholder=".//h2/text()"
                            className="mt-1 min-h-[72px] rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </label>
                        <label className="flex flex-col text-sm text-gray-700">
                          Summary selectors
                          <textarea
                            value={newSource.summarySelector}
                            onChange={(e) => updateSourceForm({ summarySelector: e.target.value })}
                            placeholder=".//p[contains(@class,'summary')]/text()"
                            className="mt-1 min-h-[72px] rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                          <span className="mt-1 text-xs text-gray-500">Multiple lines are concatenated.</span>
                        </label>
                      </div>

                      <div className="grid gap-4 md:grid-cols-2">
                        <label className="flex flex-col text-sm text-gray-700">
                          Content selectors
                          <textarea
                            value={newSource.contentSelector}
                            onChange={(e) => updateSourceForm({ contentSelector: e.target.value })}
                            placeholder=".//div[@class='content']//text()"
                            className="mt-1 min-h-[72px] rounded-md border border-gray-300 bg-white px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-indigo-500"
                          />
                        </label>
                        <div className="grid gap-3 md:grid-cols-2">
                          <Input
                            label="Author selectors"
                            value={newSource.authorSelector}
                            onChange={(e) => updateSourceForm({ authorSelector: e.target.value })}
                            placeholder=".//span[@class='byline']/text()"
                          />
                          <Input
                            label="Published selectors"
                            value={newSource.publishedSelector}
                            onChange={(e) => updateSourceForm({ publishedSelector: e.target.value })}
                            placeholder=".//time/@datetime"
                          />
                          <Input
                            label="Published format"
                            value={newSource.publishedFormat}
                            onChange={(e) => updateSourceForm({ publishedFormat: e.target.value })}
                            placeholder="YYYY-MM-DDTHH:mm:ssZ"
                          />
                          <Input
                            label="Summary join"
                            value={newSource.summaryJoin}
                            onChange={(e) => updateSourceForm({ summaryJoin: e.target.value })}
                          />
                          <Input
                            label="Content join"
                            value={newSource.contentJoin}
                            onChange={(e) => updateSourceForm({ contentJoin: e.target.value })}
                          />
                        </div>
                      </div>

                      <div className="space-y-3 rounded-md border border-indigo-100 p-3">
                        <h4 className="text-sm font-semibold text-indigo-900">Pagination</h4>
                        <div className="grid gap-3 md:grid-cols-2">
                          <Input
                            label="Next page selectors"
                            value={newSource.nextSelector}
                            onChange={(e) => updateSourceForm({ nextSelector: e.target.value })}
                            placeholder="//a[contains(@class,'next')]/@href"
                          />
                          <Input
                            label="Next link attribute"
                            value={newSource.nextAttribute}
                            onChange={(e) => updateSourceForm({ nextAttribute: e.target.value })}
                            placeholder="href"
                          />
                          <Input
                            label="Max pages"
                            value={newSource.maxPages}
                            onChange={(e) => updateSourceForm({ maxPages: e.target.value })}
                            placeholder="2"
                          />
                        </div>
                        <Switch
                          checked={newSource.skipArticleFetch}
                          onChange={(checked) => updateSourceForm({ skipArticleFetch: checked })}
                          label="Use list content without refetching article"
                        />
                      </div>
                    </div>
                  )}
                </div>
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button type="submit" variant="primary" disabled={savingSource}>
                {savingSource ? 'Saving…' : 'Add source'}
              </Button>
              <Button type="button" variant="ghost" onClick={resetSourceForm} disabled={savingSource}>
                Reset
              </Button>
            </div>
          </form>
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
                      variant="ghost"
                      size="sm"
                      onClick={async () => {
                        try {
                          const data = await apiClient.post<{ items: any[]; total: number; ingestable: number; filtered: number }>(`/watchlists/jobs/${job.id}/preview`, { }, { params: { limit: 10, per_source: 5 } });
                          updateForm(job.id, { previewItems: data.items, showPreview: true });
                        } catch (e: any) {
                          show({ title: 'Preview failed', description: e?.message, variant: 'danger' });
                        }
                      }}
                    >
                      Preview
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

                <div className="space-y-3 rounded-md border border-gray-100 p-3">
                  <div className="flex items-center justify-between">
                    <h4 className="text-sm font-semibold text-gray-800">Job Filters</h4>
                    <div className="flex items-center gap-3">
                      <div className="flex items-center gap-2 text-xs text-gray-700">
                        <span>Require include match</span>
                        <Switch
                          checked={state.requireInclude}
                          onChange={(checked) => updateForm(job.id, { requireInclude: checked })}
                          label=""
                        />
                      </div>
                      <Button
                        type="button"
                        size="xs"
                        variant="ghost"
                        onClick={() => {
                          if (!state.showAdvancedFilters) {
                            // Prefill with current state
                            const payload = { require_include: state.requireInclude, filters: state.filters || [] } as any;
                            const pretty = JSON.stringify(payload, null, 2);
                            updateForm(job.id, { showAdvancedFilters: true, advancedFiltersJson: pretty });
                          } else {
                            // Attempt to parse and fold back into state
                            try {
                              const obj = JSON.parse(state.advancedFiltersJson || '{}');
                              const filters = Array.isArray(obj?.filters) ? obj.filters : [];
                              const req = Boolean(obj?.require_include || false);
                              updateForm(job.id, { showAdvancedFilters: false, filters, requireInclude: req });
                            } catch (e) {
                              updateForm(job.id, { showAdvancedFilters: false });
                            }
                          }
                        }}
                      >
                        {state.showAdvancedFilters ? 'Basic editor' : 'Advanced JSON'}
                      </Button>
                    </div>
                  </div>
                  {state.showAdvancedFilters && (
                    <label className="flex flex-col text-xs text-gray-700">
                      Advanced filters JSON
                      <textarea
                        value={state.advancedFiltersJson}
                        onChange={(e) => updateForm(job.id, { advancedFiltersJson: e.target.value })}
                        className="mt-1 min-h-[160px] w-full rounded-md border border-gray-300 p-2 font-mono text-[12px]"
                        placeholder='{"require_include": true, "filters": [...]}'
                      />
                      <span className="mt-1 text-[11px] text-gray-500">Use this to set custom shapes (e.g., regex flags, date ranges).</span>
                    </label>
                  )}
                  {(state.filters || []).length === 0 && (
                    <p className="text-xs text-gray-500">No filters configured. Add one below.</p>
                  )}
                  {(state.filters || []).length > 0 && (
                    <ul className="divide-y divide-gray-100 text-sm">
                      {state.filters.map((f, idx) => (
                        <li key={idx} className="flex items-center justify-between py-1">
                          <div className="text-gray-700">
                            <span className="font-medium">{f.type}</span> · {f.action}
                            {typeof f.priority === 'number' && <span> · prio {f.priority}</span>}
                          </div>
                          <Button type="button" size="xs" variant="secondary" onClick={() => removeFilter(job.id, idx)}>Remove</Button>
                        </li>
                      ))}
                    </ul>
                  )}
                  <div className="grid grid-cols-2 gap-2">
                    <label className="flex flex-col text-xs text-gray-700">
                      Type
                      <select value={state.newFilterType} onChange={(e) => updateForm(job.id, { newFilterType: e.target.value as FilterType })} className="mt-1 rounded-md border border-gray-300 px-2 py-1">
                        <option value="keyword">keyword</option>
                        <option value="author">author</option>
                        <option value="regex">regex</option>
                        <option value="date_range">date_range</option>
                        <option value="all">all</option>
                      </select>
                    </label>
                    <label className="flex flex-col text-xs text-gray-700">
                      Action
                      <select value={state.newFilterAction} onChange={(e) => updateForm(job.id, { newFilterAction: e.target.value as FilterAction })} className="mt-1 rounded-md border border-gray-300 px-2 py-1">
                        <option value="include">include</option>
                        <option value="exclude">exclude</option>
                        <option value="flag">flag</option>
                      </select>
                    </label>
                  </div>
                  <div className="grid grid-cols-3 gap-2">
                    <Input label="Priority" value={state.newFilterPriority} onChange={(e) => updateForm(job.id, { newFilterPriority: e.target.value })} placeholder="0" />
                    {(state.newFilterType === 'keyword' || state.newFilterType === 'author') && (
                      <Input label={state.newFilterType === 'keyword' ? 'Keywords (comma)' : 'Authors (comma)'} value={state.newFilterValueText} onChange={(e) => updateForm(job.id, { newFilterValueText: e.target.value })} placeholder="ai, ml" />
                    )}
                    {state.newFilterType === 'regex' && (
                      <>
                        <Input label="Pattern" value={state.newFilterValueText} onChange={(e) => updateForm(job.id, { newFilterValueText: e.target.value })} placeholder="(?i)breaking" />
                        <Input label="Flags" value={state.newFilterRegexFlags} onChange={(e) => updateForm(job.id, { newFilterRegexFlags: e.target.value })} placeholder="i" />
                      </>
                    )}
                    {state.newFilterType === 'date_range' && (
                      <Input label="Max age (days)" value={state.newFilterMaxAgeDays} onChange={(e) => updateForm(job.id, { newFilterMaxAgeDays: e.target.value })} placeholder="7" />
                    )}
                  </div>
                  <div className="flex items-center gap-2">
                    <Button type="button" size="sm" variant="secondary" onClick={() => addFilter(job.id)}>Add filter</Button>
                    <Button type="button" size="sm" variant="primary" onClick={() => saveFilters(job.id)}>Save filters</Button>
                  </div>
                  {!state.showAdvancedFilters && (
                    <p className="text-[11px] text-gray-500">Tip: switch to Advanced to edit raw JSON payload.</p>
                  )}
                </div>

                <div className="text-xs text-gray-500">
                  {job.last_run_at && <span className="mr-4">Last run: {new Date(job.last_run_at).toLocaleString()}</span>}
                  {job.next_run_at && <span>Next run: {new Date(job.next_run_at).toLocaleString()}</span>}
                </div>

                {state.showPreview && (
                  <div className="mt-4 rounded-md border border-indigo-200 bg-indigo-50/50 p-3">
                    <div className="mb-2 text-sm font-semibold text-indigo-900">Preview (dry‑run)</div>
                    {Array.isArray(state.previewItems) && state.previewItems.length > 0 ? (
                      <div className="overflow-x-auto">
                        <table className="min-w-full divide-y divide-gray-200 text-xs">
                          <thead className="bg-indigo-100/60">
                            <tr>
                              <th className="px-2 py-1 text-left font-medium text-indigo-900">Decision</th>
                              <th className="px-2 py-1 text-left font-medium text-indigo-900">Matched</th>
                              <th className="px-2 py-1 text-left font-medium text-indigo-900">Title</th>
                              <th className="px-2 py-1 text-left font-medium text-indigo-900">Source</th>
                            </tr>
                          </thead>
                          <tbody className="divide-y divide-indigo-100">
                            {state.previewItems.map((it: any, idx: number) => (
                              <tr key={idx} className="bg-white">
                                <td className="px-2 py-1">{it.decision}</td>
                                <td className="px-2 py-1">{it.matched_action || '-'} {it.matched_filter_key ? `(${it.matched_filter_key})` : ''}</td>
                                <td className="px-2 py-1">
                                  <a href={it.url || '#'} target="_blank" rel="noreferrer" className="text-indigo-600 hover:underline">
                                    {it.title || '(no title)'}
                                  </a>
                                </td>
                                <td className="px-2 py-1">{it.source_type} #{it.source_id}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </div>
                    ) : (
                      <div className="text-xs text-indigo-800">No candidates in preview.</div>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </Layout>
  );
}
