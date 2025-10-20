import { FormEvent, useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';

interface ReadingItem {
  id: number;
  title: string;
  url?: string;
  domain?: string;
  summary?: string;
  status?: string;
  favorite: boolean;
  tags: string[];
  created_at?: string;
  updated_at?: string;
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
  const [formFavorite, setFormFavorite] = useState(false);
  const [formStatus, setFormStatus] = useState('saved');
  const [saving, setSaving] = useState(false);

  const [items, setItems] = useState<ReadingItem[]>([]);
  const [statusFilter, setStatusFilter] = useState<'all' | typeof STATUS_OPTIONS[number]>('all');
  const [search, setSearch] = useState('');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const parseTags = (value: string): string[] =>
    value
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, size: PAGE_SIZE };
      if (statusFilter !== 'all') params.status = [statusFilter];
      if (search.trim()) params.q = search.trim();
      if (favoriteOnly) params.favorite = true;

      const data = await apiClient.get<ReadingListResponse>('/reading/items', { params });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (error: any) {
      setItems([]);
      setTotal(0);
      show({ title: 'Failed to load reading items', description: error?.message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly, page, search, show, statusFilter]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

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
        content: formContent.trim() || undefined,
      });
      show({ title: 'Saved to reading list', variant: 'success' });
      setFormUrl('');
      setFormTitle('');
      setFormTags('');
      setFormContent('');
      setFormSummary('');
      setFormFavorite(false);
      setFormStatus('saved');
      setPage(1);
      loadItems();
    } catch (error: any) {
      show({ title: 'Save failed', description: error?.message, variant: 'danger' });
    } finally {
      setSaving(false);
    }
  };

  const updateItem = async (itemId: number, patch: Partial<ReadingItem>) => {
    try {
      await apiClient.patch(`/reading/items/${itemId}`, patch);
      loadItems();
    } catch (error: any) {
      show({ title: 'Update failed', description: error?.message, variant: 'danger' });
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
                <th className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-500">
                    {loading ? 'Loading reading list…' : 'No items found.'}
                  </td>
                </tr>
              )}
              {items.map((item) => (
                <tr key={`reading-${item.id}`}>
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
                    <div className="flex flex-wrap gap-2">
                      <Button
                        type="button"
                        variant={item.favorite ? 'secondary' : 'primary'}
                        onClick={() => updateItem(item.id, { favorite: !item.favorite })}
                        size="sm"
                      >
                        {item.favorite ? 'Unfavorite' : 'Favorite'}
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
