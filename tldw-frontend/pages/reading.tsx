import { FormEvent, Fragment, useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient, buildAuthHeaders, getApiBaseUrl } from '@/lib/api';

interface ReadingItem {
  id: number;
  title: string;
  url?: string;
  domain?: string;
  summary?: string;
  notes?: string;
  status?: string;
  favorite: boolean;
  tags: string[];
  created_at?: string;
  updated_at?: string;
}

interface Highlight {
  id: number;
  item_id: number;
  quote: string;
  start_offset?: number | null;
  end_offset?: number | null;
  color?: string | null;
  note?: string | null;
  created_at: string;
  anchor_strategy: string;
  state: 'active' | 'stale';
}

interface ReadingListResponse {
  items: ReadingItem[];
  total: number;
  page: number;
  size: number;
}

const STATUS_OPTIONS = ['saved', 'reading', 'read', 'archived'];
const PAGE_SIZE = 10;

export default function ReadingPage() {
  const { show } = useToast();
  const [formUrl, setFormUrl] = useState('');
  const [formTitle, setFormTitle] = useState('');
  const [formTags, setFormTags] = useState('');
  const [formContent, setFormContent] = useState('');
  const [formSummary, setFormSummary] = useState('');
  const [formNotes, setFormNotes] = useState('');
  const [formFavorite, setFormFavorite] = useState(false);
  const [formStatus, setFormStatus] = useState('saved');
  const [saving, setSaving] = useState(false);

  const [items, setItems] = useState<ReadingItem[]>([]);
  const [noteDrafts, setNoteDrafts] = useState<Record<number, string>>({});
  const [noteSaveState, setNoteSaveState] = useState<Record<number, 'saving' | 'saved' | 'error'>>({});
  const [expandedItemId, setExpandedItemId] = useState<number | null>(null);
  const [highlightsByItem, setHighlightsByItem] = useState<Record<number, Highlight[]>>({});
  const [highlightLoading, setHighlightLoading] = useState<Record<number, boolean>>({});
  const [highlightDrafts, setHighlightDrafts] = useState<Record<number, { quote: string; note: string; color: string; anchor_strategy: string }>>({});
  const [highlightEdits, setHighlightEdits] = useState<Record<number, { note: string; color: string; state: 'active' | 'stale' }>>({});
  const [statusFilter, setStatusFilter] = useState<'all' | typeof STATUS_OPTIONS[number]>('all');
  const [search, setSearch] = useState('');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importSource, setImportSource] = useState<'auto' | 'pocket' | 'instapaper'>('auto');
  const [mergeTags, setMergeTags] = useState(true);
  const [importing, setImporting] = useState(false);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const parseTags = (value: string): string[] =>
    value
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, size: PAGE_SIZE };
      if (statusFilter !== 'all') params.status = [statusFilter];
      if (search.trim()) params.q = search.trim();
      if (favoriteOnly) params.favorite = true;

      const data = await apiClient.get<ReadingListResponse>('/reading/items', { params });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (error: unknown) {
      setItems([]);
      setTotal(0);
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Failed to load reading items', description: message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly, page, search, show, statusFilter]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    const drafts: Record<number, string> = {};
    items.forEach((item) => {
      drafts[item.id] = item.notes || '';
    });
    setNoteDrafts(drafts);
    setNoteSaveState((prev) => {
      const next: Record<number, 'saving' | 'saved' | 'error'> = {};
      items.forEach((item) => {
        if (prev[item.id]) {
          next[item.id] = prev[item.id];
        }
      });
      return next;
    });
  }, [items]);

  const handleSave = async (event: FormEvent) => {
    event.preventDefault();
    if (!formUrl.trim()) {
      show({ title: 'URL is required', variant: 'warning' });
      return;
    }
    setSaving(true);
    try {
      await apiClient.post('/reading/save', {
        url: formUrl.trim(),
        title: formTitle.trim() || undefined,
        tags: parseTags(formTags),
        status: formStatus,
        favorite: formFavorite,
        summary: formSummary.trim() || undefined,
        notes: formNotes.trim() || undefined,
        content: formContent.trim() || undefined,
      });
      show({ title: 'Saved to reading list', variant: 'success' });
      setFormUrl('');
      setFormTitle('');
      setFormTags('');
      setFormContent('');
      setFormSummary('');
      setFormNotes('');
      setFormFavorite(false);
      setFormStatus('saved');
      setPage(1);
      loadItems();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Save failed', description: message, variant: 'danger' });
    } finally {
      setSaving(false);
    }
  };

  const updateItem = async (itemId: number, patch: Partial<ReadingItem>) => {
    try {
      await apiClient.patch(`/reading/items/${itemId}`, patch);
      await loadItems();
      return true;
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Update failed', description: message, variant: 'danger' });
      return false;
    }
  };

  const saveNotes = async (item: ReadingItem, draftValue?: string) => {
    const draft = (draftValue ?? noteDrafts[item.id] ?? '').trim();
    const current = (item.notes ?? '').trim();
    if (draft === current) return;
    setNoteSaveState((prev) => ({ ...prev, [item.id]: 'saving' }));
    const ok = await updateItem(item.id, { notes: draft });
    setNoteSaveState((prev) => ({ ...prev, [item.id]: ok ? 'saved' : 'error' }));
  };

  const loadHighlights = useCallback(async (itemId: number) => {
    setHighlightLoading((prev) => ({ ...prev, [itemId]: true }));
    try {
      const data = await apiClient.get<Highlight[]>(`/reading/items/${itemId}/highlights`);
      setHighlightsByItem((prev) => ({ ...prev, [itemId]: data || [] }));
      setHighlightEdits((prev) => {
        const next = { ...prev };
        (data || []).forEach((highlight) => {
          next[highlight.id] = {
            note: highlight.note || '',
            color: highlight.color || '',
            state: highlight.state || 'active',
          };
        });
        return next;
      });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Failed to load highlights', description: message, variant: 'danger' });
    } finally {
      setHighlightLoading((prev) => ({ ...prev, [itemId]: false }));
    }
  }, [show]);

  const toggleHighlights = (itemId: number) => {
    if (expandedItemId === itemId) {
      setExpandedItemId(null);
      return;
    }
    setExpandedItemId(itemId);
    if (!highlightsByItem[itemId]) {
      loadHighlights(itemId);
    }
  };

  const updateHighlightDraft = (itemId: number, patch: Partial<{ quote: string; note: string; color: string; anchor_strategy: string }>) => {
    setHighlightDrafts((prev) => {
      const current = prev[itemId] || { quote: '', note: '', color: '', anchor_strategy: 'fuzzy_quote' };
      return { ...prev, [itemId]: { ...current, ...patch } };
    });
  };

  const createHighlight = async (item: ReadingItem) => {
    const draft = highlightDrafts[item.id] || { quote: '', note: '', color: '', anchor_strategy: 'fuzzy_quote' };
    if (!draft.quote.trim()) {
      show({ title: 'Highlight quote is required', variant: 'warning' });
      return;
    }
    try {
      await apiClient.post(`/reading/items/${item.id}/highlight`, {
        item_id: item.id,
        quote: draft.quote.trim(),
        note: draft.note.trim() || undefined,
        color: draft.color.trim() || undefined,
        anchor_strategy: draft.anchor_strategy || 'fuzzy_quote',
      });
      setHighlightDrafts((prev) => ({ ...prev, [item.id]: { quote: '', note: '', color: '', anchor_strategy: 'fuzzy_quote' } }));
      loadHighlights(item.id);
      show({ title: 'Highlight added', variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Highlight create failed', description: message, variant: 'danger' });
    }
  };

  const saveHighlight = async (highlight: Highlight) => {
    const patch = highlightEdits[highlight.id];
    if (!patch) return;
    try {
      await apiClient.patch(`/reading/highlights/${highlight.id}`, {
        note: patch.note.trim() || undefined,
        color: patch.color.trim() || undefined,
        state: patch.state,
      });
      loadHighlights(highlight.item_id);
      show({ title: 'Highlight updated', variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Highlight update failed', description: message, variant: 'danger' });
    }
  };

  const deleteHighlight = async (highlight: Highlight) => {
    try {
      await apiClient.delete(`/reading/highlights/${highlight.id}`);
      loadHighlights(highlight.item_id);
      show({ title: 'Highlight deleted', variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Highlight delete failed', description: message, variant: 'danger' });
    }
  };

  const handleImport = async () => {
    if (!importFile) {
      show({ title: 'Select a file to import', variant: 'warning' });
      return;
    }
    setImporting(true);
    const formData = new FormData();
    formData.append('file', importFile);
    formData.append('source', importSource);
    formData.append('merge_tags', String(mergeTags));
    try {
      const result = await apiClient.post<{ imported: number; updated: number; skipped: number }>(
        '/reading/import',
        formData,
        { headers: { 'Content-Type': 'multipart/form-data' } }
      );
      show({
        title: 'Import complete',
        description: `Imported ${result.imported}, updated ${result.updated}, skipped ${result.skipped}.`,
        variant: 'success',
      });
      setImportFile(null);
      loadItems();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Import failed', description: message, variant: 'danger' });
    } finally {
      setImporting(false);
    }
  };

  const downloadExport = async (format: 'jsonl' | 'zip') => {
    try {
      const params = new URLSearchParams({ format });
      const url = `${getApiBaseUrl()}/reading/export?${params.toString()}`;
      const response = await fetch(url, { headers: buildAuthHeaders('GET') });
      if (!response.ok) {
        throw new Error(`Export failed (${response.status})`);
      }
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const anchor = document.createElement('a');
      anchor.href = blobUrl;
      anchor.download = format === 'zip' ? 'reading_export.zip' : 'reading_export.jsonl';
      document.body.appendChild(anchor);
      anchor.click();
      anchor.remove();
      window.URL.revokeObjectURL(blobUrl);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Export failed', description: message, variant: 'danger' });
    }
  };

  const handlePrev = () => setPage((prev) => Math.max(1, prev - 1));
  const handleNext = () => setPage((prev) => Math.min(totalPages, prev + 1));

  return (
    <Layout>
      <div className="space-y-8">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Reading List</h1>
          <p className="mt-1 text-sm text-gray-600">
            Capture links for later review, manage statuses, and favorite important articles.
          </p>
        </div>

        <form onSubmit={handleSave} className="space-y-4 rounded-md border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Save a Link</h2>
          <Input label="URL" value={formUrl} onChange={(e) => setFormUrl(e.target.value)} placeholder="https://example.com/article" required />
          <Input label="Title (optional)" value={formTitle} onChange={(e) => setFormTitle(e.target.value)} placeholder="Readable title" />
          <Input
            label="Tags (comma separated)"
            value={formTags}
            onChange={(e) => setFormTags(e.target.value)}
            placeholder="research, ai, longform"
          />
          <label className="block text-sm font-medium text-gray-700">
            Summary (optional)
            <textarea
              value={formSummary}
              onChange={(e) => setFormSummary(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Notes (optional)
            <textarea
              value={formNotes}
              onChange={(e) => setFormNotes(e.target.value)}
              rows={3}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </label>
          <label className="block text-sm font-medium text-gray-700">
            Content override (optional)
            <textarea
              value={formContent}
              onChange={(e) => setFormContent(e.target.value)}
              rows={4}
              className="mt-1 w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
            />
          </label>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex flex-col text-sm text-gray-700">
              Status
              <select
                value={formStatus}
                onChange={(e) => setFormStatus(e.target.value)}
                className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <Switch checked={formFavorite} onChange={setFormFavorite} label="Mark as favorite" />
            <div className="ml-auto flex space-x-2">
              <Button type="submit" variant="primary" disabled={saving}>
                {saving ? 'Saving…' : 'Save Item'}
              </Button>
            </div>
          </div>
        </form>

        <div className="space-y-4 rounded-md border border-gray-200 bg-white p-6 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-800">Import & Export</h2>
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex flex-col text-sm text-gray-700">
              Import file
              <input
                type="file"
                accept=".json,.csv"
                onChange={(event) => setImportFile(event.target.files?.[0] || null)}
                className="mt-1 text-sm"
              />
            </label>
            <label className="flex flex-col text-sm text-gray-700">
              Source
              <select
                value={importSource}
                onChange={(event) => setImportSource(event.target.value as typeof importSource)}
                className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="auto">Auto-detect</option>
                <option value="pocket">Pocket</option>
                <option value="instapaper">Instapaper</option>
              </select>
            </label>
            <Switch checked={mergeTags} onChange={setMergeTags} label="Merge tags with existing items" />
            <Button type="button" variant="primary" onClick={handleImport} disabled={importing}>
              {importing ? 'Importing…' : 'Import'}
            </Button>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <Button type="button" variant="secondary" onClick={() => downloadExport('jsonl')}>
              Export JSONL
            </Button>
            <Button type="button" variant="secondary" onClick={() => downloadExport('zip')}>
              Export ZIP
            </Button>
          </div>
        </div>

        <div className="rounded-md border border-gray-200 bg-white p-4 shadow-sm">
          <div className="flex flex-wrap items-center gap-4">
            <label className="flex flex-col text-sm text-gray-700">
              Status filter
              <select
                value={statusFilter}
                onChange={(e) => {
                  setStatusFilter(e.target.value as typeof statusFilter);
                  setPage(1);
                }}
                className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="all">All statuses</option>
                {STATUS_OPTIONS.map((status) => (
                  <option key={status} value={status}>
                    {status}
                  </option>
                ))}
              </select>
            </label>
            <Input label="Search" value={search} onChange={(e) => { setSearch(e.target.value); setPage(1); }} placeholder="Title or summary…" />
            <Switch checked={favoriteOnly} onChange={(checked) => { setFavoriteOnly(checked); setPage(1); }} label="Favorites only" />
            <Button type="button" variant="secondary" onClick={loadItems} disabled={loading}>
              {loading ? 'Refreshing…' : 'Refresh'}
            </Button>
          </div>
        </div>

        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Title</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Status</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Tags</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Notes</th>
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-500">
                    {loading ? 'Loading reading list…' : 'No items found.'}
                  </td>
                </tr>
              )}
              {items.map((item) => (
                <Fragment key={`reading-${item.id}`}>
                  <tr>
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        <div className="flex items-center space-x-2">
                          <span className="text-sm font-medium text-gray-900">{item.title || 'Untitled'}</span>
                          {item.favorite && <span className="rounded bg-yellow-100 px-2 py-0.5 text-xs font-semibold text-yellow-700">Favorite</span>}
                        </div>
                        {item.summary && <p className="text-xs text-gray-600 line-clamp-2">{item.summary}</p>}
                        {item.url && (
                          <a href={item.url} target="_blank" rel="noreferrer" className="text-xs text-blue-600 hover:underline">
                            {item.url}
                          </a>
                        )}
                        {item.domain && <div className="text-xs text-gray-500">{item.domain}</div>}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      <select
                        value={item.status || 'saved'}
                        onChange={(e) => updateItem(item.id, { status: e.target.value })}
                        className="rounded-md border border-gray-300 bg-white px-2 py-1 text-xs"
                      >
                        {STATUS_OPTIONS.map((status) => (
                          <option key={`${item.id}-${status}`} value={status}>
                            {status}
                          </option>
                        ))}
                      </select>
                      {item.created_at && (
                        <div className="mt-1 text-xs text-gray-500">
                          Added {new Date(item.created_at).toLocaleString()}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      <div className="flex flex-wrap gap-1">
                        {(item.tags || []).map((tag) => (
                          <span key={`${item.id}-${tag}`} className="rounded bg-blue-50 px-2 py-1 text-xs text-blue-700">
                            {tag}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      <textarea
                        value={noteDrafts[item.id] ?? ''}
                        onChange={(event) => {
                          setNoteDrafts((prev) => ({ ...prev, [item.id]: event.target.value }));
                          setNoteSaveState((prev) => {
                            if (!(item.id in prev)) return prev;
                            const { [item.id]: _removed, ...rest } = prev;
                            return rest;
                          });
                        }}
                        onBlur={(event) => saveNotes(item, event.currentTarget.value)}
                        rows={3}
                        className="w-full rounded-md border border-gray-300 px-3 py-2 text-xs focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500"
                      />
                      {(noteDrafts[item.id] ?? '').trim() !== (item.notes ?? '').trim() && (
                        <div className="mt-1 text-right text-xs text-amber-600">Unsaved</div>
                      )}
                      {noteSaveState[item.id] && (
                        <div className="mt-1 text-right text-xs text-gray-500">
                          {noteSaveState[item.id] === 'saving'
                            ? 'Saving…'
                            : noteSaveState[item.id] === 'saved'
                              ? 'Saved'
                              : 'Save failed'}
                        </div>
                      )}
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-700">
                      <div className="flex flex-wrap gap-2">
                        <Button
                          type="button"
                          variant={item.favorite ? 'secondary' : 'primary'}
                          onClick={() => updateItem(item.id, { favorite: !item.favorite })}
                          size="sm"
                        >
                          {item.favorite ? 'Unfavorite' : 'Favorite'}
                        </Button>
                        <Button
                          type="button"
                          variant="secondary"
                          onClick={() => toggleHighlights(item.id)}
                          size="sm"
                        >
                          {expandedItemId === item.id ? 'Hide Highlights' : 'Highlights'}
                        </Button>
                        {item.url && (
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noreferrer"
                            className="inline-flex items-center rounded-md border border-gray-300 px-3 py-1 text-xs font-medium text-gray-700 hover:bg-gray-100"
                          >
                            Open
                          </a>
                        )}
                      </div>
                    </td>
                  </tr>
                  {expandedItemId === item.id && (
                    <tr>
                      <td colSpan={5} className="bg-gray-50 px-4 py-4">
                        <div className="space-y-4">
                          <div className="flex items-center justify-between">
                            <h3 className="text-sm font-semibold text-gray-800">Highlights</h3>
                            <span className="text-xs text-gray-500">
                              {highlightsByItem[item.id]?.length || 0} items
                            </span>
                          </div>
                          {highlightLoading[item.id] ? (
                            <div className="text-sm text-gray-500">Loading highlights…</div>
                          ) : (highlightsByItem[item.id] || []).length === 0 ? (
                            <div className="text-sm text-gray-500">No highlights yet.</div>
                          ) : (
                            <div className="space-y-3">
                              {(highlightsByItem[item.id] || []).map((highlight) => (
                                <div key={`highlight-${highlight.id}`} className="rounded-md border border-gray-200 bg-white p-3">
                                  <div className="text-sm text-gray-800">“{highlight.quote}”</div>
                                  <div className="mt-3 grid gap-3 md:grid-cols-3">
                                    <label className="text-xs text-gray-600">
                                      Color
                                      <input
                                        value={highlightEdits[highlight.id]?.color ?? highlight.color ?? ''}
                                        onChange={(event) =>
                                          setHighlightEdits((prev) => ({
                                            ...prev,
                                            [highlight.id]: {
                                              note: prev[highlight.id]?.note ?? highlight.note ?? '',
                                              color: event.target.value,
                                              state: prev[highlight.id]?.state ?? highlight.state,
                                            },
                                          }))
                                        }
                                        className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                      />
                                    </label>
                                    <label className="text-xs text-gray-600">
                                      State
                                      <select
                                        value={highlightEdits[highlight.id]?.state ?? highlight.state}
                                        onChange={(event) =>
                                          setHighlightEdits((prev) => ({
                                            ...prev,
                                            [highlight.id]: {
                                              note: prev[highlight.id]?.note ?? highlight.note ?? '',
                                              color: prev[highlight.id]?.color ?? highlight.color ?? '',
                                              state: event.target.value as 'active' | 'stale',
                                            },
                                          }))
                                        }
                                        className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                      >
                                        <option value="active">active</option>
                                        <option value="stale">stale</option>
                                      </select>
                                    </label>
                                    <label className="text-xs text-gray-600 md:col-span-1">
                                      Note
                                      <textarea
                                        value={highlightEdits[highlight.id]?.note ?? highlight.note ?? ''}
                                        onChange={(event) =>
                                          setHighlightEdits((prev) => ({
                                            ...prev,
                                            [highlight.id]: {
                                              note: event.target.value,
                                              color: prev[highlight.id]?.color ?? highlight.color ?? '',
                                              state: prev[highlight.id]?.state ?? highlight.state,
                                            },
                                          }))
                                        }
                                        rows={2}
                                        className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                      />
                                    </label>
                                  </div>
                                  <div className="mt-3 flex flex-wrap gap-2">
                                    <Button type="button" variant="secondary" size="sm" onClick={() => saveHighlight(highlight)}>
                                      Save
                                    </Button>
                                    <Button type="button" variant="secondary" size="sm" onClick={() => deleteHighlight(highlight)}>
                                      Delete
                                    </Button>
                                  </div>
                                </div>
                              ))}
                            </div>
                          )}
                          <div className="rounded-md border border-gray-200 bg-white p-4">
                            <h4 className="text-sm font-semibold text-gray-800">Add highlight</h4>
                            <div className="mt-3 grid gap-3 md:grid-cols-2">
                              <label className="text-xs text-gray-600 md:col-span-2">
                                Quote
                                <textarea
                                  value={highlightDrafts[item.id]?.quote ?? ''}
                                  onChange={(event) => updateHighlightDraft(item.id, { quote: event.target.value })}
                                  rows={2}
                                  className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                />
                              </label>
                              <label className="text-xs text-gray-600">
                                Color
                                <input
                                  value={highlightDrafts[item.id]?.color ?? ''}
                                  onChange={(event) => updateHighlightDraft(item.id, { color: event.target.value })}
                                  className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                />
                              </label>
                              <label className="text-xs text-gray-600">
                                Anchor strategy
                                <select
                                  value={highlightDrafts[item.id]?.anchor_strategy ?? 'fuzzy_quote'}
                                  onChange={(event) => updateHighlightDraft(item.id, { anchor_strategy: event.target.value })}
                                  className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                >
                                  <option value="fuzzy_quote">fuzzy_quote</option>
                                  <option value="exact_offset">exact_offset</option>
                                </select>
                              </label>
                              <label className="text-xs text-gray-600 md:col-span-2">
                                Note
                                <textarea
                                  value={highlightDrafts[item.id]?.note ?? ''}
                                  onChange={(event) => updateHighlightDraft(item.id, { note: event.target.value })}
                                  rows={2}
                                  className="mt-1 w-full rounded-md border border-gray-300 px-2 py-1 text-xs"
                                />
                              </label>
                            </div>
                            <div className="mt-3 flex justify-end">
                              <Button type="button" variant="primary" size="sm" onClick={() => createHighlight(item)}>
                                Add Highlight
                              </Button>
                            </div>
                          </div>
                        </div>
                      </td>
                    </tr>
                  )}
                </Fragment>
              ))}
            </tbody>
          </table>
        </div>

        <div className="flex items-center justify-between">
          <div className="text-sm text-gray-600">
            Showing page {page} of {totalPages} ({total} items)
          </div>
          <div className="flex space-x-2">
            <Button type="button" variant="secondary" onClick={handlePrev} disabled={page <= 1 || loading}>
              Previous
            </Button>
            <Button type="button" variant="secondary" onClick={handleNext} disabled={page >= totalPages || loading}>
              Next
            </Button>
          </div>
        </div>
      </div>
    </Layout>
  );
}
