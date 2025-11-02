import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';

interface ItemRow {
  id: number;
  run_id: number;
  job_id: number;
  source_id: number;
  url?: string | null;
  title?: string | null;
  summary?: string | null;
  status: string;
  created_at: string;
}

interface ItemsListResponse {
  items: ItemRow[];
  total: number;
}

export default function AdminWatchlistsItemsPage() {
  const router = useRouter();
  const { show } = useToast();
  const [runId, setRunId] = useState<string>('');
  const [status, setStatus] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [size, setSize] = useState<number>(50);
  const [total, setTotal] = useState<number>(0);
  const [items, setItems] = useState<ItemRow[]>([]);
  const [loading, setLoading] = useState(false);

  const hasMore = useMemo(() => (page * size) < (total || 0), [page, size, total]);

  useEffect(() => {
    const rid = router.query.run_id as string | undefined;
    if (rid && /^[0-9]+$/.test(rid)) {
      setRunId(rid);
      void fetchItems(Number(rid), page, size, status || undefined);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.query.run_id]);

  const fetchItems = async (rid: number, p: number, s: number, st?: string) => {
    setLoading(true);
    try {
      const data = await apiClient.get<ItemsListResponse>(`/watchlists/items`, { params: { run_id: rid, status: st || undefined, page: p, size: s } });
      setItems(Array.isArray(data?.items) ? data.items : []);
      setTotal(Number(data?.total || 0));
    } catch (e: any) {
      setItems([]);
      setTotal(0);
      show({ title: 'Failed to load items', description: e?.message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-end gap-2">
          <Input label="Run ID" value={runId} onChange={(e) => setRunId(e.target.value.replace(/[^0-9]/g, ''))} inputMode="numeric" placeholder="e.g., 1" />
          <label className="flex flex-col text-sm text-gray-700">
            Status
            <select value={status} onChange={(e) => setStatus(e.target.value)} className="mt-1 rounded-md border border-gray-300 bg-white px-2 py-1 text-sm">
              <option value="">All</option>
              <option value="ingested">ingested</option>
              <option value="filtered">filtered</option>
              <option value="flagged">flagged</option>
            </select>
          </label>
          <Button
            type="button"
            variant="secondary"
            onClick={() => {
              const id = Number(runId);
              if (!Number.isFinite(id) || id <= 0) { show({ title: 'Enter a valid run ID', variant: 'warning' }); return; }
              setPage(1);
              void fetchItems(id, 1, size, status || undefined);
            }}
            disabled={loading}
          >
            {loading ? 'Loading…' : 'Load'}
          </Button>
          <label className="flex items-center gap-1 text-sm text-gray-700">
            <span>Page size</span>
            <select className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm" value={size} onChange={(e) => { const v = Number(e.target.value); setSize(Number.isFinite(v) && v > 0 ? v : 50); setPage(1); }}>
              <option value={20}>20</option>
              <option value={50}>50</option>
              <option value={100}>100</option>
            </select>
          </label>
          <div className="text-sm text-gray-700">Page {page} of {Math.max(1, Math.ceil((total || 0) / (size || 1)))}</div>
          <Button type="button" variant="secondary" size="sm" onClick={() => { const p = Math.max(1, page - 1); setPage(p); const id = Number(runId); if (Number.isFinite(id)) void fetchItems(id, p, size, status || undefined); }} disabled={loading || page <= 1}>Prev</Button>
          <Button type="button" variant="secondary" size="sm" onClick={() => { const p = page + 1; setPage(p); const id = Number(runId); if (Number.isFinite(id)) void fetchItems(id, p, size, status || undefined); }} disabled={loading || !hasMore}>Next</Button>
        </div>

        {items.length === 0 && (
          <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">No items for this run.</div>
        )}

        {items.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Title</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">URL</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Status</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Created</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {items.map((it) => (
                  <tr key={it.id} className="bg-white">
                    <td className="px-3 py-2 text-gray-900">{it.title || '-'}</td>
                    <td className="px-3 py-2 text-indigo-600"><a href={it.url || '#'} target="_blank" rel="noreferrer" className="hover:underline">{it.url || '-'}</a></td>
                    <td className="px-3 py-2 text-gray-700">{it.status}</td>
                    <td className="px-3 py-2 text-gray-500">{it.created_at ? new Date(it.created_at).toLocaleString() : '-'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </Layout>
  );
}
