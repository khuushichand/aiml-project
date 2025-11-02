import { useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { useToast } from '@/components/ui/ToastProvider';
import { apiClient } from '@/lib/api';
import { useAuth } from '@/hooks/useAuth';
import { useIsAdmin } from '@/hooks/useIsAdmin';
import { toBool } from '@/lib/authz';

interface RunRow {
  id: number;
  job_id: number;
  status: string;
  started_at?: string | null;
  finished_at?: string | null;
  stats?: { [k: string]: any } | null;
}

/**
 * Admin interface for browsing, inspecting, and exporting watchlists runs.
 *
 * Provides two viewing modes (by job or global), pagination, optional inclusion of per-run filter tallies and a filtered sample, client-side JSON/CSV exports, and links to server-side CSV exports for large datasets. When the NEXT_PUBLIC_RUNS_REQUIRE_ADMIN flag is set, access is restricted to users with administrative privileges.
 *
 * @returns The rendered admin Watchlists Runs page element
 */
export default function AdminWatchlistsRunsPage() {
  const { user } = useAuth();
  const { show } = useToast();
  const [mode, setMode] = useState<'byJob' | 'global'>('byJob');
  const [jobIdInput, setJobIdInput] = useState<string>('');
  const [q, setQ] = useState<string>('');
  const [page, setPage] = useState<number>(1);
  const [size, setSize] = useState<number>(20);
  const [total, setTotal] = useState<number>(0);
  // By Job pagination
  const [pageByJob, setPageByJob] = useState<number>(1);
  const [sizeByJob, setSizeByJob] = useState<number>(20);
  const [runs, setRuns] = useState<RunRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [includeTallies, setIncludeTallies] = useState<boolean>(false);
  const [filteredSampleMax, setFilteredSampleMax] = useState<number>(0);
  const [selectedRunTallies, setSelectedRunTallies] = useState<{ [runId: number]: Record<string, number> }>({});
  const [selectedRunFiltered, setSelectedRunFiltered] = useState<{ [runId: number]: { id: number; title?: string | null; url?: string | null; status: string }[] }>({});

  const hasMore = useMemo(() => (page * size) < (total || 0), [page, size, total]);
  const hasMoreByJob = useMemo(() => (pageByJob * sizeByJob) < (total || 0), [pageByJob, sizeByJob, total]);

  const runsRequireAdmin = toBool(process.env.NEXT_PUBLIC_RUNS_REQUIRE_ADMIN);
  const serverCsvThreshold = (() => {
    const raw = (process.env.NEXT_PUBLIC_RUNS_CSV_SERVER_THRESHOLD ?? '2000').toString();
    const n = Number(raw);
    return Number.isFinite(n) && n > 0 ? n : 2000;
  })();
  const userIsAdmin = useIsAdmin();

  const fetchRunsByJob = async (opts?: { page?: number; size?: number }) => {
    const text = jobIdInput.trim();
    const idNum = Number(text);
    if (!Number.isFinite(idNum) || idNum <= 0) {
      show({ title: 'Enter a valid job ID', variant: 'warning' });
      return;
    }
    setLoading(true);
    try {
      const data = await apiClient.get<{ items: RunRow[]; total: number }>(`/watchlists/jobs/${idNum}/runs`, { params: { page: opts?.page ?? pageByJob, size: opts?.size ?? sizeByJob } });
      const items = Array.isArray(data?.items) ? data.items : [];
      setRuns(items);
      setTotal(Number(data?.total || 0));
      if ((includeTallies || (filteredSampleMax || 0) > 0) && items.length > 0) {
        await fetchTalliesForRuns(items.map((r) => r.id));
      }
    } catch (e: any) {
      setRuns([]);
      show({ title: 'Failed to load runs', description: e?.message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const fetchTallies = async (runId: number) => {
    try {
      const detail = await apiClient.get<{ filter_tallies?: Record<string, number>; filtered_sample?: { id: number; title?: string | null; url?: string | null; status: string }[] }>(`/watchlists/runs/${runId}/details`, { params: { include_tallies: includeTallies ? 1 : 0, filtered_sample_max: filteredSampleMax || 0 } });
      const tallies = (detail?.filter_tallies || {}) as Record<string, number>;
      const filteredSample = Array.isArray(detail?.filtered_sample) ? detail.filtered_sample : [];
      setSelectedRunTallies((prev) => ({ ...prev, [runId]: tallies }));
      if ((filteredSampleMax || 0) > 0) {
        setSelectedRunFiltered((prev) => ({ ...prev, [runId]: filteredSample }));
      }
    } catch (e: any) {
      show({ title: 'Failed to load tallies', description: e?.message, variant: 'danger' });
    }
  };

  const fetchTalliesForRuns = async (runIds: number[]) => {
    try {
      await Promise.all(runIds.map((rid) => fetchTallies(rid)));
    } catch {
      // handled per-run
    }
  };

  const fetchRunsGlobal = async () => {
    setLoading(true);
    try {
      const data = await apiClient.get<{ items: RunRow[]; total: number }>(`/watchlists/runs`, { params: { q: q.trim() || undefined, page, size } });
      const items = Array.isArray(data?.items) ? data.items : [];
      setRuns(items);
      setTotal(Number(data?.total || 0));
      if ((includeTallies || (filteredSampleMax || 0) > 0) && items.length > 0) {
        await fetchTalliesForRuns(items.map((r) => r.id));
      }
    } catch (e: any) {
      setRuns([]);
      setTotal(0);
      show({ title: 'Failed to load runs', description: e?.message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  const toCSV = (rows: RunRow[]) => {
    const headers = [
      'id','job_id','status','started_at','finished_at','items_found','items_ingested','filters_include','filters_exclude','filters_flag'
    ];
    const lines = [headers.join(',')];
    for (const r of rows) {
      const found = Number((r.stats || {})['items_found'] || 0);
      const ing = Number((r.stats || {})['items_ingested'] || 0);
      const inc = Number((r.stats || {})['filters_include'] || 0);
      const exc = Number((r.stats || {})['filters_exclude'] || 0);
      const flg = Number((r.stats || {})['filters_flag'] || 0);
      const row = [
        r.id,
        r.job_id,
        JSON.stringify(r.status ?? ''),
        JSON.stringify(r.started_at ?? ''),
        JSON.stringify(r.finished_at ?? ''),
        found,
        ing,
        inc,
        exc,
        flg,
      ];
      lines.push(row.join(','));
    }
    return lines.join('\n');
  };

  const download = (filename: string, content: string, mime = 'text/plain') => {
    const blob = new Blob([content], { type: mime });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
  };

  // Persist toggles in localStorage
  useEffect(() => {
    try {
      const sTallies = localStorage.getItem('wl_runs_includeTallies');
      const sFiltered = localStorage.getItem('wl_runs_filteredSampleMax');
      if (sTallies) setIncludeTallies(sTallies === '1');
      if (sFiltered) {
        const n = Number(sFiltered);
        if (Number.isFinite(n) && n >= 0) setFilteredSampleMax(n);
      }
    } catch {}
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  useEffect(() => {
    try { localStorage.setItem('wl_runs_includeTallies', includeTallies ? '1' : '0'); } catch {}
  }, [includeTallies]);
  useEffect(() => {
    try { localStorage.setItem('wl_runs_filteredSampleMax', String(filteredSampleMax || 0)); } catch {}
  }, [filteredSampleMax]);

  const exportJSON = () => {
    if (!runs.length) { return; }
    const data = runs.map((r) => ({
      id: r.id,
      job_id: r.job_id,
      status: r.status,
      started_at: r.started_at,
      finished_at: r.finished_at,
      items_found: Number((r.stats || {})['items_found'] || 0),
      items_ingested: Number((r.stats || {})['items_ingested'] || 0),
      filters_include: Number((r.stats || {})['filters_include'] || 0),
      filters_exclude: Number((r.stats || {})['filters_exclude'] || 0),
      filters_flag: Number((r.stats || {})['filters_flag'] || 0),
    }));
    download(`watchlists-runs.json`, JSON.stringify({ total, items: data }, null, 2), 'application/json');
  };

  const exportCSV = () => {
    if (!runs.length) { return; }
    const csv = toCSV(runs);
    download(`watchlists-runs.csv`, csv, 'text/csv');
  };

  const exportTalliesCSV = () => {
    if (!includeTallies || Object.keys(selectedRunTallies).length === 0) { return; }
    const headers = ['run_id','filter_key','count'];
    const lines: string[] = [headers.join(',')];
    for (const [rid, tallies] of Object.entries(selectedRunTallies)) {
      const runId = Number(rid);
      for (const [k, v] of Object.entries(tallies)) {
        lines.push([runId, JSON.stringify(k), Number(v)].join(','));
      }
    }
    download(`watchlists-runs-tallies.csv`, lines.join('\n'), 'text/csv');
  };

  useEffect(() => {
    // Reset results when switching modes
    setRuns([]);
    setTotal(0);
    setSelectedRunTallies({});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode]);

  if (runsRequireAdmin && !userIsAdmin) {
    return (
      <Layout>
        <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">Admin access required to view runs.</div>
      </Layout>
    );
  }

  return (
    <Layout>
      <div className="space-y-6">
        <div className="flex flex-wrap items-end justify-between gap-3">
          <div>
            <h1 className="text-2xl font-semibold text-gray-800">Watchlists Runs (Admin)</h1>
            <p className="mt-1 text-sm text-gray-600">Browse runs globally or by job and inspect filter counters.</p>
          </div>
          <div className="flex items-center gap-3 text-sm">
            <label className="flex items-center gap-2">
              <span>Mode</span>
              <select className="rounded-md border border-gray-300 bg-white px-2 py-1" value={mode} onChange={(e) => setMode(e.target.value as any)}>
                <option value="byJob">By Job</option>
                <option value="global">Global</option>
              </select>
            </label>
            <label className="flex items-center gap-2">
              <input type="checkbox" checked={includeTallies} onChange={(e) => setIncludeTallies(e.target.checked)} />
              <span>Include tallies</span>
            </label>
          </div>
        </div>

        {mode === 'byJob' && (
          <div className="flex flex-wrap items-end gap-2">
            <Input
              label="Job ID"
              value={jobIdInput}
              onChange={(e) => setJobIdInput(e.target.value.replace(/[^0-9]/g, ''))}
              inputMode="numeric"
              placeholder="e.g., 1"
            />
            <label className="flex items-center gap-1 text-sm text-gray-700">
              <span>Page size</span>
              <select
                className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                value={sizeByJob}
                onChange={(e) => {
                  const v = Number(e.target.value);
                  const next = Number.isFinite(v) && v > 0 ? v : 20;
                  setSizeByJob(next);
                  setPageByJob(1);
                }}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
            <div className="text-sm text-gray-700">Page {pageByJob} of {Math.max(1, Math.ceil((total || 0) / (sizeByJob || 1)))}</div>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                const next = Math.max(1, pageByJob - 1);
                setPageByJob(next);
                fetchRunsByJob({ page: next });
              }}
              disabled={loading || pageByJob <= 1}
            >
              Prev
            </Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => fetchRunsByJob()} disabled={loading}>
              {loading ? 'Loading…' : 'Load'}
            </Button>
            <Button
              type="button"
              variant="secondary"
              size="sm"
              onClick={() => {
                const next = pageByJob + 1;
                setPageByJob(next);
                fetchRunsByJob({ page: next });
              }}
              disabled={loading || !hasMoreByJob}
            >
              Next
            </Button>
          </div>
        )}

        {mode === 'global' && (
          <div className="flex flex-wrap items-end gap-2">
            <Input label="Search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="job name, status, run id" />
            <label className="flex items-center gap-1 text-sm text-gray-700">
              <span>Page size</span>
              <select
                className="rounded-md border border-gray-300 bg-white px-2 py-1 text-sm"
                value={size}
                onChange={(e) => { const v = Number(e.target.value); setSize(Number.isFinite(v) && v > 0 ? v : 20); setPage(1); }}
              >
                <option value={10}>10</option>
                <option value={20}>20</option>
                <option value={50}>50</option>
                <option value={100}>100</option>
              </select>
            </label>
            <div className="text-sm text-gray-700">Page {page} of {Math.max(1, Math.ceil((total || 0) / (size || 1)))}</div>
            <Button type="button" variant="secondary" size="sm" onClick={() => setPage((p) => Math.max(1, p - 1))} disabled={loading || page <= 1}>Prev</Button>
            <Button type="button" variant="secondary" size="sm" onClick={fetchRunsGlobal} disabled={loading}>Search</Button>
            <Button type="button" variant="secondary" size="sm" onClick={() => setPage((p) => p + 1)} disabled={loading || !hasMore}>Next</Button>
          </div>
        )}

        {runs.length === 0 && (
          <div className="rounded-md border border-dashed border-gray-200 bg-gray-50 p-4 text-sm text-gray-600">No runs yet. Enter a Job ID and click Load.</div>
        )}

        {runs.length > 0 && (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-gray-200 text-sm">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Run ID</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Status</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Started</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Finished</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Items (found/ingested)</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Filters (inc/exc/flag)</th>
                  <th className="px-3 py-2 text-left font-medium text-gray-700">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-gray-100">
                {runs.map((r) => {
                  const found = Number((r.stats || {})['items_found'] || 0);
                  const ing = Number((r.stats || {})['items_ingested'] || 0);
                  const inc = Number((r.stats || {})['filters_include'] || 0);
                  const exc = Number((r.stats || {})['filters_exclude'] || 0);
                  const flg = Number((r.stats || {})['filters_flag'] || 0);
                  const tallies = selectedRunTallies[r.id];
                  return (
                    <tr key={r.id} className="bg-white">
                      <td className="px-3 py-2 text-gray-900">{r.id}</td>
                      <td className="px-3 py-2 text-gray-700">{r.status}</td>
                      <td className="px-3 py-2 text-gray-500">{r.started_at ? new Date(r.started_at).toLocaleString() : '-'}</td>
                      <td className="px-3 py-2 text-gray-500">{r.finished_at ? new Date(r.finished_at).toLocaleString() : '-'}</td>
                      <td className="px-3 py-2 text-gray-700">{found} / {ing}</td>
                      <td className="px-3 py-2 text-gray-700">{inc} / {exc} / {flg}</td>
                      <td className="px-3 py-2 space-x-2">
                        <Button type="button" size="xs" variant="secondary" onClick={() => fetchTallies(r.id)}>
                          View tallies
                        </Button>
                        <a
                          href={`/admin/watchlists-items?run_id=${r.id}`}
                          className="text-xs text-indigo-600 hover:underline"
                        >
                          View items
                        </a>
                        <a
                          href={`/api/v1/watchlists/runs/${r.id}/tallies.csv`}
                          className="text-xs text-indigo-600 hover:underline"
                        >
                          Tallies CSV
                        </a>
                      </td>
                  </tr>
                  );
                })}
              </tbody>
            </table>
            <div className="mt-3 flex items-center gap-2">
              <Button type="button" variant="secondary" size="sm" onClick={exportJSON}>Download JSON</Button>
              <Button type="button" variant="secondary" size="sm" onClick={exportCSV}>Download CSV</Button>
              {includeTallies && (
                <Button type="button" variant="secondary" size="sm" onClick={exportTalliesCSV} disabled={Object.keys(selectedRunTallies).length === 0}>
                  Download Tallies CSV
                </Button>
              )}
              {/* Prefer server-side CSV export for large datasets */}
              {mode === 'global' ? (
                (total > serverCsvThreshold) && (
                  <a
                    className="text-sm text-indigo-700 hover:underline"
                    href={`/api/v1/watchlists/runs/export.csv?scope=global&q=${encodeURIComponent(q)}&page=${page}&size=${size}&include_tallies=${includeTallies ? 'true' : 'false'}`}
                  >
                    Server CSV (global)
                  </a>
                )
              ) : (
                (() => {
                  const idNum = Number(jobIdInput.trim());
                  if (!Number.isFinite(idNum) || idNum <= 0) return null;
                  return (total > serverCsvThreshold) ? (
                    <a
                      className="text-sm text-indigo-700 hover:underline"
                      href={`/api/v1/watchlists/runs/export.csv?scope=job&job_id=${idNum}&page=${pageByJob}&size=${sizeByJob}&include_tallies=${includeTallies ? 'true' : 'false'}`}
                    >
                      Server CSV (by job)
                    </a>
                  ) : null;
                })()
              )}
            </div>
          </div>
        )}

        {(Object.keys(selectedRunTallies).length > 0 || Object.keys(selectedRunFiltered).length > 0) && (
          <div className="rounded-md border border-gray-200 bg-white p-4 text-sm">
            <h2 className="text-base font-semibold text-gray-800">Run Details</h2>
            <div className="mt-2 space-y-2">
              {Object.entries(selectedRunTallies).map(([rid, tallies]) => (
                <div key={rid} className="rounded border border-gray-100 p-2">
                  <div className="text-gray-700 font-medium">Run {rid} Tallies</div>
                  {Object.keys(tallies).length === 0 && <div className="text-gray-500">No tallies recorded.</div>}
                  {Object.entries(tallies).map(([k, v]) => (
                    <div key={k} className="text-gray-600">{k}: {v}</div>
                  ))}
                </div>
              ))}
              {Object.entries(selectedRunFiltered).map(([rid, rows]) => (
                <div key={`filtered-${rid}`} className="rounded border border-gray-100 p-2">
                  <div className="text-gray-700 font-medium">Run {rid} Filtered sample</div>
                  {(!rows || rows.length === 0) && <div className="text-gray-500">No filtered items in sample.</div>}
                  {rows && rows.length > 0 && (
                    <ul className="list-disc pl-5 text-gray-600">
                      {rows.map((r) => (
                        <li key={r.id}>
                          <a className="text-indigo-600 hover:underline" href={r.url || '#'} target="_blank" rel="noreferrer">{r.title || r.url || '(no title)'}</a>
                        </li>
                      ))}
                    </ul>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Controls for tallies and filtered sample */}
        <div className="rounded-md border border-gray-200 bg-white p-3 text-sm flex items-end gap-3">
          <label className="flex items-center gap-2 text-gray-700">
            <input type="checkbox" checked={includeTallies} onChange={(e) => setIncludeTallies(e.target.checked)} /> Include tallies in Run Details
          </label>
          <label className="flex items-center gap-2 text-gray-700">
            <span>Filtered sample size</span>
            <input
              type="number"
              min={0}
              max={50}
              className="w-16 rounded-md border border-gray-300 px-2 py-1"
              value={filteredSampleMax}
              onChange={(e) => {
                const v = Number(e.target.value);
                if (Number.isFinite(v) && v >= 0 && v <= 50) setFilteredSampleMax(v);
              }}
            />
          </label>
          <Button type="button" size="sm" variant="secondary" onClick={() => {
            if (runs.length > 0) void fetchTalliesForRuns(runs.map((r) => r.id));
          }}>Refresh Details</Button>
        </div>
      </div>
    </Layout>
  );
}
