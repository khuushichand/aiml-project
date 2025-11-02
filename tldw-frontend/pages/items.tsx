import { useCallback, useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';

interface ItemRecord {
  id: number;
  title: string;
  url?: string;
  domain?: string;
  summary?: string;
  published_at?: string;
  tags?: string[];
  type?: string;
}

interface ItemsResponse {
  items: ItemRecord[];
  total: number;
  page: number;
  size: number;
}

const PAGE_SIZE = 10;

const originOptions = [
  { value: 'all', label: 'All Origins' },
  { value: 'watchlist', label: 'Watchlists' },
  { value: 'reading', label: 'Reading List' },
  { value: 'media', label: 'Media Library' },
];

const statusOptions = [
  { value: 'all', label: 'Any Status' },
  { value: 'saved', label: 'Saved' },
  { value: 'reading', label: 'Reading' },
  { value: 'read', label: 'Read' },
  { value: 'archived', label: 'Archived' },
];

export default function ItemsPage() {
  const { show } = useToast();
  const [items, setItems] = useState<ItemRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [origin, setOrigin] = useState('all');
  const [status, setStatus] = useState('all');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, any> = { page, size: PAGE_SIZE };
      if (query.trim()) params.q = query.trim();
      if (origin !== 'all') params.origin = origin;
      if (status !== 'all') params.status_filter = [status];
      if (favoriteOnly) params.favorite = true;

      const data = await apiClient.get<ItemsResponse>('/items', { params });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (error: any) {
      setItems([]);
      setTotal(0);
      show({ title: 'Failed to load items', description: error?.message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly, origin, page, query, show, status]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  const handleSearchSubmit = (event: React.FormEvent) => {
    event.preventDefault();
    setPage(1);
    loadItems();
  };

  const handleResetFilters = () => {
    setQuery('');
    setOrigin('all');
    setStatus('all');
    setFavoriteOnly(false);
    setPage(1);
  };

  const handlePrev = () => {
    setPage((prev) => Math.max(1, prev - 1));
  };

  const handleNext = () => {
    setPage((prev) => Math.min(totalPages, prev + 1));
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div>
          <h1 className="text-2xl font-semibold text-gray-800">Collections Items</h1>
          <p className="mt-1 text-sm text-gray-600">
            Unified view of watchlist and reading content. Use filters to focus on specific sources or favorites.
          </p>
        </div>

        <form onSubmit={handleSearchSubmit} className="grid gap-4 rounded-md border border-gray-200 bg-white p-4 md:grid-cols-2 lg:grid-cols-4">
          <Input
            label="Search"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Title or content…"
          />
          <label className="flex flex-col text-sm text-gray-700">
            Origin
            <select
              value={origin}
              onChange={(e) => {
                setOrigin(e.target.value);
                setPage(1);
              }}
              className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
            >
              {originOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <label className="flex flex-col text-sm text-gray-700">
            Status
            <select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
              className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
            >
              {statusOptions.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <div className="flex items-center justify-between">
            <Switch checked={favoriteOnly} onChange={(checked) => { setFavoriteOnly(checked); setPage(1); }} label="Favorites only" />
            <div className="flex space-x-2">
              <Button type="submit" variant="primary" disabled={loading}>
                {loading ? 'Loading…' : 'Apply'}
              </Button>
              <Button type="button" variant="secondary" onClick={handleResetFilters}>
                Reset
              </Button>
            </div>
          </div>
        </form>

        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Title
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Origin
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Tags
                </th>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  Published
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-200 bg-white">
              {items.length === 0 && (
                <tr>
                  <td colSpan={4} className="px-4 py-6 text-center text-sm text-gray-500">
                    {loading ? 'Loading items…' : 'No items found for the selected filters.'}
                  </td>
                </tr>
              )}
              {items.map((item) => (
                <tr key={`${item.type || 'item'}-${item.id}`}>
                  <td className="px-4 py-3">
                    <div className="space-y-1">
                      <div className="text-sm font-medium text-gray-900">{item.title || 'Untitled'}</div>
                      {item.summary && <p className="text-xs text-gray-600 line-clamp-2">{item.summary}</p>}
                      {item.url && (
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noreferrer"
                          className="text-xs text-blue-600 hover:underline"
                        >
                          {item.url}
                        </a>
                      )}
                    </div>
                  </td>
                  <td className="px-4 py-3 text-sm text-gray-700">
                    <span className="rounded bg-gray-100 px-2 py-1 text-xs font-medium text-gray-700">{item.type || 'legacy'}</span>
                    {item.domain && <div className="mt-1 text-xs text-gray-500">{item.domain}</div>}
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
                    {item.published_at ? new Date(item.published_at).toLocaleString() : '-'}
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
