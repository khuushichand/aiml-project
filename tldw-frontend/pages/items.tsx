import { useCallback, useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { Switch } from '@/components/ui/Switch';
import { LineSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';

interface ItemRecord {
  id: number;
  content_item_id?: number | null;
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

interface OutputTemplateOption {
  id: number;
  name: string;
  format: string;
  type?: string;
  description?: string;
  is_default?: boolean;
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

type BulkAction = 'set_status' | 'set_favorite' | 'add_tags' | 'remove_tags' | 'replace_tags' | 'delete' | 'generate_output';

export default function ItemsPage() {
  const router = useRouter();
  const { show } = useToast();
  const [items, setItems] = useState<ItemRecord[]>([]);
  const [loading, setLoading] = useState(false);
  const [query, setQuery] = useState('');
  const [origin, setOrigin] = useState('all');
  const [status, setStatus] = useState('all');
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [page, setPage] = useState(1);
  const [total, setTotal] = useState(0);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [bulkAction, setBulkAction] = useState<BulkAction>('add_tags');
  const [bulkTags, setBulkTags] = useState('');
  const [bulkStatus, setBulkStatus] = useState('saved');
  const [bulkFavorite, setBulkFavorite] = useState(true);
  const [bulkHardDelete, setBulkHardDelete] = useState(false);
  const [bulkApplying, setBulkApplying] = useState(false);
  const [outputTemplates, setOutputTemplates] = useState<OutputTemplateOption[]>([]);
  const [templatesLoading, setTemplatesLoading] = useState(false);
  const [bulkTemplateId, setBulkTemplateId] = useState<number | ''>('');
  const [bulkOutputTitle, setBulkOutputTitle] = useState('');

  const totalPages = useMemo(() => Math.max(1, Math.ceil(total / PAGE_SIZE)), [total]);
  const selectableIds = useMemo(
    () => items.map((item) => item.content_item_id).filter((id): id is number => typeof id === 'number'),
    [items]
  );
  const allSelected = selectableIds.length > 0 && selectableIds.every((id) => selectedIds.includes(id));
  const selectedItems = useMemo(
    () => items.filter((item) => item.content_item_id && selectedIds.includes(item.content_item_id)),
    [items, selectedIds]
  );
  const outputItemIds = useMemo(
    () =>
      selectedItems
        .filter((item) => item.content_item_id && item.id !== item.content_item_id)
        .map((item) => item.content_item_id)
        .filter((id): id is number => typeof id === 'number'),
    [selectedItems]
  );
  const outputSkippedCount = Math.max(0, selectedItems.length - outputItemIds.length);

  const parseTags = (value: string): string[] =>
    value
      .split(',')
      .map((t) => t.trim())
      .filter((t) => t.length > 0);

  useEffect(() => {
    if (!router.isReady) return;
    const qp = router.query;
    const get = (k: string, def = '') => (qp[k] !== undefined ? qp[k] : def);
    const getStr = (k: string, def = '') => String(get(k, def));
    const favRaw = getStr('fav', '0');
    setQuery(getStr('q', ''));
    setOrigin(getStr('origin', 'all'));
    setStatus(getStr('status', 'all'));
    setFavoriteOnly(favRaw === '1' || favRaw === 'true');
    setPage(Number(getStr('page', '1')) || 1);
  }, [router.isReady, router.query]);

  const loadItems = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, unknown> = { page, size: PAGE_SIZE };
      if (query.trim()) params.q = query.trim();
      if (origin !== 'all') params.origin = origin;
      if (status !== 'all') params.status_filter = [status];
      if (favoriteOnly) params.favorite = true;

      const data = await apiClient.get<ItemsResponse>('/items', { params });
      setItems(data.items || []);
      setTotal(data.total || 0);
    } catch (error: unknown) {
      setItems([]);
      setTotal(0);
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Failed to load items', description: message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  }, [favoriteOnly, origin, page, query, show, status]);

  useEffect(() => {
    loadItems();
  }, [loadItems]);

  useEffect(() => {
    setSelectedIds((prev) => prev.filter((id) => selectableIds.includes(id)));
  }, [selectableIds]);

  useEffect(() => {
    if (!router.isReady) return;
    const queryParams: Record<string, string> = {};
    if (query.trim()) queryParams.q = query.trim();
    if (origin !== 'all') queryParams.origin = origin;
    if (status !== 'all') queryParams.status = status;
    if (favoriteOnly) queryParams.fav = '1';
    if (page !== 1) queryParams.page = String(page);
    router.replace({ pathname: router.pathname, query: queryParams }, undefined, { shallow: true });
  }, [favoriteOnly, origin, page, query, router, status]);

  const loadTemplates = useCallback(async () => {
    setTemplatesLoading(true);
    try {
      const data = await apiClient.get<{ items: OutputTemplateOption[] }>('/outputs/templates', {
        params: { limit: 200, offset: 0 },
      });
      setOutputTemplates(data.items || []);
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Failed to load templates', description: message, variant: 'warning' });
    } finally {
      setTemplatesLoading(false);
    }
  }, [show]);

  useEffect(() => {
    loadTemplates();
  }, [loadTemplates]);

  useEffect(() => {
    if (outputTemplates.length === 0 || bulkTemplateId) return;
    const defaultTemplate = outputTemplates.find((tpl) => tpl.is_default) || outputTemplates[0];
    if (defaultTemplate) {
      setBulkTemplateId(defaultTemplate.id);
    }
  }, [bulkTemplateId, outputTemplates]);

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

  const toggleSelectAll = () => {
    if (allSelected) {
      setSelectedIds([]);
    } else {
      setSelectedIds(selectableIds);
    }
  };

  const toggleSelectOne = (itemId: number, checked: boolean) => {
    setSelectedIds((prev) => {
      if (checked) {
        return prev.includes(itemId) ? prev : [...prev, itemId];
      }
      return prev.filter((id) => id !== itemId);
    });
  };

  const applyBulkAction = async () => {
    if (selectedIds.length === 0) {
      show({ title: 'Select at least one item', variant: 'warning' });
      return;
    }
    if (bulkAction === 'generate_output') {
      if (!bulkTemplateId) {
        show({ title: 'Select a template', variant: 'warning' });
        return;
      }
      if (outputItemIds.length === 0) {
        show({ title: 'No selected items are eligible for outputs', description: 'Items must have media IDs.', variant: 'warning' });
        return;
      }
      setBulkApplying(true);
      try {
        const payload: Record<string, unknown> = {
          template_id: bulkTemplateId,
          item_ids: outputItemIds,
        };
        if (bulkOutputTitle.trim()) {
          payload.title = bulkOutputTitle.trim();
        }
        const res = await apiClient.post<{ id: number; title: string; format: string }>('/outputs', payload);
        const skipped = outputSkippedCount;
        show({
          title: 'Output generated',
          description: skipped
            ? `Created output "${res.title}". Skipped ${skipped} item(s) without media IDs.`
            : `Created output "${res.title}".`,
          variant: skipped ? 'warning' : 'success',
        });
        setSelectedIds([]);
        setBulkOutputTitle('');
      } catch (error: unknown) {
        const message = error instanceof Error ? error.message : 'Unknown error';
        show({ title: 'Output generation failed', description: message, variant: 'danger' });
      } finally {
        setBulkApplying(false);
      }
      return;
    }
    if (bulkAction === 'delete' && bulkHardDelete) {
      const ok = window.confirm('Hard delete permanently removes items. Continue?');
      if (!ok) return;
    }
    if (bulkAction === 'set_status' && !bulkStatus) {
      show({ title: 'Select a status for bulk update', variant: 'warning' });
      return;
    }
    if (['add_tags', 'remove_tags', 'replace_tags'].includes(bulkAction)) {
      if (parseTags(bulkTags).length === 0) {
        show({ title: 'Enter at least one tag', variant: 'warning' });
        return;
      }
    }

    const payload: Record<string, unknown> = {
      item_ids: selectedIds,
      action: bulkAction,
    };
    if (bulkAction === 'set_status') payload.status = bulkStatus;
    if (bulkAction === 'set_favorite') payload.favorite = bulkFavorite;
    if (bulkAction === 'delete') payload.hard = bulkHardDelete;
    if (['add_tags', 'remove_tags', 'replace_tags'].includes(bulkAction)) {
      payload.tags = parseTags(bulkTags);
    }

    setBulkApplying(true);
    try {
      const res = await apiClient.post<{ total: number; succeeded: number; failed: number }>('/items/bulk', payload);
      const failed = res.failed || 0;
      show({
        title: failed ? 'Bulk action completed with errors' : 'Bulk action completed',
        description: `Updated ${res.succeeded} of ${res.total} items.`,
        variant: failed ? 'warning' : 'success',
      });
      setSelectedIds([]);
      loadItems();
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      show({ title: 'Bulk action failed', description: message, variant: 'danger' });
    } finally {
      setBulkApplying(false);
    }
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

        <div className="space-y-3 rounded-md border border-gray-200 bg-white p-4">
          <div className="flex flex-wrap items-center gap-3">
            <div className="text-sm text-gray-700">Selected: {selectedIds.length}</div>
            <label className="flex flex-col text-sm text-gray-700">
              Bulk action
              <select
                value={bulkAction}
                onChange={(e) => setBulkAction(e.target.value as BulkAction)}
                className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
              >
                <option value="add_tags">Add tags</option>
                <option value="remove_tags">Remove tags</option>
                <option value="replace_tags">Replace tags</option>
                <option value="set_status">Set status</option>
                <option value="set_favorite">Set favorite</option>
                <option value="generate_output">Generate output</option>
                <option value="delete">Delete</option>
              </select>
            </label>
            {['add_tags', 'remove_tags', 'replace_tags'].includes(bulkAction) && (
              <Input
                label="Tags"
                value={bulkTags}
                onChange={(e) => setBulkTags(e.target.value)}
                placeholder="ai, research"
              />
            )}
            {bulkAction === 'set_status' && (
              <label className="flex flex-col text-sm text-gray-700">
                Status
                <select
                  value={bulkStatus}
                  onChange={(e) => setBulkStatus(e.target.value)}
                  className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                >
                  {statusOptions.filter((opt) => opt.value !== 'all').map((opt) => (
                    <option key={opt.value} value={opt.value}>
                      {opt.label}
                    </option>
                  ))}
                </select>
              </label>
            )}
            {bulkAction === 'set_favorite' && (
              <label className="flex flex-col text-sm text-gray-700">
                Favorite
                <select
                  value={bulkFavorite ? 'true' : 'false'}
                  onChange={(e) => setBulkFavorite(e.target.value === 'true')}
                  className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                >
                  <option value="true">Favorite</option>
                  <option value="false">Unfavorite</option>
                </select>
              </label>
            )}
            {bulkAction === 'generate_output' && (
              <>
                <label className="flex flex-col text-sm text-gray-700">
                  Template
                  <select
                    value={bulkTemplateId}
                    onChange={(e) => {
                      const next = Number(e.target.value);
                      setBulkTemplateId(Number.isFinite(next) && next > 0 ? next : '');
                    }}
                    className="mt-1 rounded-md border border-gray-300 bg-white px-3 py-2 text-sm"
                    disabled={templatesLoading || outputTemplates.length === 0}
                  >
                    {outputTemplates.length === 0 && (
                      <option value="">
                        {templatesLoading ? 'Loading templates…' : 'No templates available'}
                      </option>
                    )}
                    {outputTemplates.map((tpl) => (
                      <option key={tpl.id} value={tpl.id}>
                        {tpl.name} ({tpl.format})
                      </option>
                    ))}
                  </select>
                </label>
                <Input
                  label="Output title (optional)"
                  value={bulkOutputTitle}
                  onChange={(e) => setBulkOutputTitle(e.target.value)}
                  placeholder="Weekly briefing"
                />
                <div className="text-xs text-gray-500">
                  Generates an output from {outputItemIds.length} item(s).
                  {outputSkippedCount > 0 ? ` Skipping ${outputSkippedCount} item(s) without media IDs.` : ''}
                </div>
              </>
            )}
            {bulkAction === 'delete' && (
              <div className="flex items-center pt-5">
                <Switch checked={bulkHardDelete} onChange={setBulkHardDelete} label="Hard delete" />
              </div>
            )}
            <div className="ml-auto flex items-center gap-2">
              <Button type="button" variant="secondary" onClick={() => setSelectedIds([])} disabled={selectedIds.length === 0}>
                Clear
              </Button>
              <Button type="button" variant="primary" onClick={applyBulkAction} disabled={bulkApplying || selectedIds.length === 0}>
                {bulkApplying ? 'Applying…' : 'Apply'}
              </Button>
            </div>
          </div>
          {selectableIds.length === 0 && (
            <div className="text-xs text-gray-500">
              Bulk actions apply to collections items only. Legacy media items are not selectable here.
            </div>
          )}
        </div>

        <div className="overflow-hidden rounded-lg border border-gray-200 bg-white shadow-sm">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th scope="col" className="px-4 py-3 text-left text-xs font-semibold uppercase tracking-wider text-gray-500">
                  <input
                    type="checkbox"
                    checked={allSelected}
                    onChange={toggleSelectAll}
                    disabled={selectableIds.length === 0}
                  />
                </th>
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
              {loading && (
                Array.from({ length: 5 }).map((_, index) => (
                  <tr key={`skeleton-${index}`}>
                    <td className="px-4 py-3">
                      <LineSkeleton width="20%" height={12} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="space-y-2">
                        <LineSkeleton width="70%" height={14} />
                        <LineSkeleton width="90%" height={10} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <LineSkeleton width="60%" height={12} />
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-2">
                        <LineSkeleton width={52} height={10} />
                        <LineSkeleton width={40} height={10} />
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <LineSkeleton width="50%" height={12} />
                    </td>
                  </tr>
                ))
              )}
              {!loading && items.length === 0 && (
                <tr>
                  <td colSpan={5} className="px-4 py-6 text-center text-sm text-gray-500">
                    No items found for the selected filters.
                  </td>
                </tr>
              )}
              {!loading && items.map((item) => (
                <tr key={`${item.type || 'item'}-${item.id}`}>
                  <td className="px-4 py-3">
                    <input
                      type="checkbox"
                      checked={item.content_item_id ? selectedIds.includes(item.content_item_id) : false}
                      onChange={(e) => item.content_item_id && toggleSelectOne(item.content_item_id, e.target.checked)}
                      disabled={!item.content_item_id}
                    />
                  </td>
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
