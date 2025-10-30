import { useEffect, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';

interface Organization {
  id: number;
  name: string;
  slug?: string | null;
  owner_user_id?: number | null;
  is_active?: boolean | null;
  created_at?: string | null;
  updated_at?: string | null;
}

interface OrganizationListResponse {
  items: Organization[];
  total: number;
  limit: number;
  offset: number;
  has_more: boolean;
}

export default function AdminOrgsPage() {
  const { show } = useToast();
  const [orgs, setOrgs] = useState<Organization[]>([]);
  const [loading, setLoading] = useState(false);
  const [page, setPage] = useState<number>(1);
  const [size, setSize] = useState<number>(20);
  const [filter, setFilter] = useState<string>("");
  const [total, setTotal] = useState<number>(0);
  const [hasMore, setHasMore] = useState<boolean>(false);

  const fetchOrgs = async () => {
    setLoading(true);
    try {
      const offset = (page - 1) * size;
      const params: any = { limit: size, offset };
      if (filter.trim()) params.q = filter.trim();
      const data = await apiClient.get<OrganizationListResponse>('/admin/orgs', { params });
      setOrgs(Array.isArray((data as any)?.items) ? data.items : []);
      setTotal(Number.isFinite((data as any)?.total) ? data.total : 0);
      setHasMore(Boolean((data as any)?.has_more));
    } catch (error: any) {
      setOrgs([]);
      setTotal(0);
      setHasMore(false);
      show({ title: 'Failed to load organizations', description: error?.message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchOrgs();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, size]);

  const copy = async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      show({ title: 'Copied to clipboard', description: text, variant: 'success' });
    } catch (e: any) {
      show({ title: 'Copy failed', description: e?.message, variant: 'danger' });
    }
  };

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-gray-800">Organizations</h1>
            <p className="mt-1 text-sm text-gray-600">List of organizations (admin)</p>
          </div>
          <div className="flex flex-wrap items-center gap-2">
            <Input
              label=""
              value={filter}
              onChange={(e) => setFilter(e.target.value)}
              placeholder="Filter by name, slug, or ID"
            />
            <label className="flex items-center gap-1 text-sm text-gray-700">
              <span>Page size</span>
              <select
                className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                value={size}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  setSize(Number.isFinite(v) && v > 0 ? v : 20);
                  setPage(1);
                }}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
            <div className="text-sm text-gray-700">
              Page {page} of {Math.max(1, Math.ceil((total || 0) / (size || 1)))}
            </div>
            <Button type="button" variant="secondary" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={loading || page <= 1}>
              Prev
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => setPage((p) => p + 1)}
              disabled={loading || !hasMore}
            >
              Next
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={fetchOrgs} disabled={loading}>
              {loading ? 'Refreshing…' : 'Refresh'}
            </Button>
          </div>
        </div>

        {loading && (
          <div className="rounded-md border border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">Loading…</div>
        )}

        {!loading && orgs.length === 0 && (
          <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">
            No organizations found.
          </div>
        )}

        {!loading && orgs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">ID</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Name</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Slug</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Active</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {orgs
                  .filter((o) => {
                    const q = filter.trim().toLowerCase();
                    if (!q) return true;
                    const name = (o.name || '').toLowerCase();
                    const slug = (o.slug || '').toLowerCase();
                    return name.includes(q) || slug.includes(q) || String(o.id).includes(q);
                  })
                  .map((o) => (
                  <tr key={o.id} className="bg-white">
                    <td className="px-3 py-2 text-gray-900">{o.id}</td>
                    <td className="px-3 py-2 text-gray-700">{o.name}</td>
                    <td className="px-3 py-2 text-gray-500">{o.slug || '-'}</td>
                    <td className="px-3 py-2 text-gray-500">{o.is_active ? 'yes' : 'no'}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-2">
                        <Button type="button" size="xs" variant="secondary" onClick={() => copy(String(o.id))}>
                          Copy ID
                        </Button>
                        {o.slug && (
                          <Button type="button" size="xs" variant="ghost" onClick={() => copy(o.slug!)}>
                            Copy slug
                          </Button>
                        )}
                      </div>
                    </td>
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
