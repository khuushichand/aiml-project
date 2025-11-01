import { useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';
import JsonEditor from '@/components/ui/JsonEditor';
import JsonViewer from '@/components/ui/JsonViewer';
import JsonTree from '@/components/ui/JsonTree';
import { buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { CardSkeleton } from '@/components/ui/Skeleton';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';

export default function EvaluationsPage() {
  const [tab, setTab] = useState<'ocr_json'|'ocr_pdf'|'geval'|'rq'|'results'|'run'>('ocr_json');
  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4">
        <HotkeysOverlay
          entries={[
            { keys: 'P', description: 'Run Details: start/stop polling' },
            { keys: 'Cmd/Ctrl+Shift+J', description: 'Copy selected result JSON (in Results tab)' },
            { keys: '?', description: 'Toggle shortcuts help' },
          ]}
        />
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Evaluations</h1>
          <div className="w-1/2"><Tabs items={[{key:'ocr_json',label:'OCR (JSON)'},{key:'ocr_pdf',label:'OCR (PDF)'},{key:'geval',label:'G-Eval'},{key:'rq',label:'Response Quality'},{key:'results',label:'Results'},{key:'run',label:'Run Details'}]} value={tab} onChange={(k)=>setTab(k as any)} /></div>
        </div>
        <div className="rounded-md border bg-white p-4 transition-all duration-150">
          {tab === 'ocr_json' && <OCRJson/>}
          {tab === 'ocr_pdf' && <OCRPdf/>}
          {tab === 'geval' && <GEval/>}
          {tab === 'rq' && <ResponseQuality/>}
          {tab === 'results' && <ResultsExplorer/>}
          {tab === 'run' && <RunDetails/>}
        </div>
      </div>
    </Layout>
  );
}

function OCRJson() {
  const { show } = useToast();
  const [body, setBody] = useState<string>(JSON.stringify({ images: [{ url: 'https://example.com/page1.png' }], engine: 'auto' }, null, 2));
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [view, setView] = useState<'pretty'|'tree'>('pretty');
  const send = async () => {
    setLoading(true); setResp(null);
    try {
      const payload = JSON.parse(body);
      const url = `${getApiBaseUrl()}/evaluations/ocr`;
      const headers = buildAuthHeaders('POST','application/json');
      const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload) });
      const text = await r.text(); let json: any; try { json = JSON.parse(text); } catch { json = text; }
      setResp(json);
      show({ title: r.ok ? 'OCR complete' : 'OCR failed', description: `${r.status} ${r.statusText}`, variant: r.ok ? 'success' : 'warning' });
    } catch (e: any) {
      show({ title: 'OCR error', description: e?.message || 'Failed', variant: 'danger' });
    } finally { setLoading(false); }
  };
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm text-gray-700">Request JSON</div>
        <div className="space-x-2">
          <Button variant="secondary" onClick={() => { try { setBody(JSON.stringify(JSON.parse(body), null, 2)); show({title:'Formatted', variant:'success'}); } catch {} }}>Format</Button>
          <Button onClick={send} loading={loading} disabled={loading}>Send</Button>
        </div>
      </div>
      <JsonEditor value={body} onChange={setBody} height={260} />
      <div className="mt-3 rounded border bg-gray-50 p-3">
        <MetricsViewer data={resp} />
        {view === 'pretty' ? <JsonViewer data={resp} /> : <JsonTree data={resp} />}
      </div>
      <div className="mt-2 space-x-2">
        <Button variant="secondary" onClick={() => setView('pretty')} disabled={view==='pretty'}>Pretty</Button>
        <Button variant="secondary" onClick={() => setView('tree')} disabled={view==='tree'}>Tree</Button>
      </div>
    </div>
  );
}

function OCRPdf() {
  const { show } = useToast();
  const [file, setFile] = useState<File|null>(null);
  const [params, setParams] = useState<{engine: string}>({ engine: 'auto' });
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [view, setView] = useState<'pretty'|'tree'>('pretty');

  const send = async () => {
    if (!file) { show({ title: 'Select PDF', variant: 'warning' }); return; }
    setLoading(true); setResp(null);
    try {
      const url = `${getApiBaseUrl()}/evaluations/ocr-pdf`;
      const fd = new FormData();
      fd.append('file', file);
      if (params.engine) fd.append('engine', params.engine);
      const headers = buildAuthHeaders('POST');
      const r = await fetch(url, { method: 'POST', headers, body: fd });
      const text = await r.text(); let json: any; try { json = JSON.parse(text); } catch { json = text; }
      setResp(json);
      show({ title: r.ok ? 'OCR (PDF) complete' : 'OCR (PDF) failed', description: `${r.status} ${r.statusText}`, variant: r.ok ? 'success' : 'warning' });
    } catch (e: any) {
      show({ title: 'OCR (PDF) error', description: e?.message || 'Failed', variant: 'danger' });
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label className="mb-1 block text-sm font-medium text-gray-700">PDF File</label>
          <input type="file" accept="application/pdf" onChange={(e)=>setFile(e.target.files?.[0] || null)} />
        </div>
        <div>
          <Input label="Engine" value={params.engine} onChange={(e)=>setParams({ engine: e.target.value })} />
        </div>
      </div>
      <div className="mt-2">
        <Button onClick={send} loading={loading} disabled={loading}>Upload & Run</Button>
      </div>
      <div className="mt-3 rounded border bg-gray-50 p-3">
        <MetricsViewer data={resp} />
        {view === 'pretty' ? <JsonViewer data={resp} /> : <JsonTree data={resp} />}
      </div>
      <div className="mt-2 space-x-2">
        <Button variant="secondary" onClick={() => setView('pretty')} disabled={view==='pretty'}>Pretty</Button>
        <Button variant="secondary" onClick={() => setView('tree')} disabled={view==='tree'}>Tree</Button>
      </div>
    </div>
  );
}

function GEval() {
  const { show } = useToast();
  const [body, setBody] = useState<string>(JSON.stringify({ name: 'response-quality', inputs: [{ id: '1', prompt: 'Say hello', reference: 'Hello' }] }, null, 2));
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [view, setView] = useState<'pretty'|'tree'>('pretty');
  const send = async () => {
    setLoading(true); setResp(null);
    try {
      const payload = JSON.parse(body);
      const url = `${getApiBaseUrl()}/evaluations/geval/run`;
      const headers = buildAuthHeaders('POST','application/json');
      const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload) });
      const text = await r.text(); let json: any; try { json = JSON.parse(text); } catch { json = text; }
      setResp(json);
      show({ title: r.ok ? 'Evaluation complete' : 'Evaluation failed', description: `${r.status} ${r.statusText}`, variant: r.ok ? 'success' : 'warning' });
    } catch (e: any) {
      show({ title: 'Evaluation error', description: e?.message || 'Failed', variant: 'danger' });
    } finally { setLoading(false); }
  };
  return (
    <div>
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm text-gray-700">Request JSON</div>
        <div className="space-x-2">
          <Button variant="secondary" onClick={() => { try { setBody(JSON.stringify(JSON.parse(body), null, 2)); show({title:'Formatted', variant:'success'}); } catch {} }}>Format</Button>
          <Button onClick={send} loading={loading} disabled={loading}>Run</Button>
        </div>
      </div>
      <JsonEditor value={body} onChange={setBody} height={260} />
      <div className="mt-3 rounded border bg-gray-50 p-3">
        <MetricsViewer data={resp} />
        {view === 'pretty' ? <JsonViewer data={resp} /> : <JsonTree data={resp} />}
      </div>
      <div className="mt-2 space-x-2">
        <Button variant="secondary" onClick={() => setView('pretty')} disabled={view==='pretty'}>Pretty</Button>
        <Button variant="secondary" onClick={() => setView('tree')} disabled={view==='tree'}>Tree</Button>
      </div>
    </div>
  );
}

function ResponseQuality() {
  const { show } = useToast();
  const [predicted, setPredicted] = useState('Hello, world!');
  const [reference, setReference] = useState('Hello world');
  const [criteria, setCriteria] = useState('fluency,adequacy');
  const [loading, setLoading] = useState(false);
  const [resp, setResp] = useState<any>(null);
  const [view, setView] = useState<'pretty'|'tree'>('pretty');

  const send = async () => {
    setLoading(true); setResp(null);
    try {
      const url = `${getApiBaseUrl()}/evaluations/response-quality`;
      const body = { predicted, reference, criteria: criteria.split(',').map(s=>s.trim()).filter(Boolean) };
      const headers = buildAuthHeaders('POST','application/json');
      const r = await fetch(url, { method: 'POST', headers, body: JSON.stringify(body) });
      const text = await r.text(); let json: any; try { json = JSON.parse(text); } catch { json = text; }
      setResp(json);
      show({ title: r.ok ? 'Evaluation complete' : 'Evaluation failed', description: `${r.status} ${r.statusText}`, variant: r.ok ? 'success' : 'warning' });
    } catch (e: any) {
      show({ title: 'Evaluation error', description: e?.message || 'Failed', variant: 'danger' });
    } finally { setLoading(false); }
  };

  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="sm:col-span-2">
          <label className="mb-1 block text-sm font-medium text-gray-700">Predicted</label>
          <textarea className="h-20 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={predicted} onChange={(e)=>setPredicted(e.target.value)} />
        </div>
        <div className="sm:col-span-2">
          <label className="mb-1 block text-sm font-medium text-gray-700">Reference</label>
          <textarea className="h-20 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={reference} onChange={(e)=>setReference(e.target.value)} />
        </div>
        <div>
          <Input label="Criteria (comma)" value={criteria} onChange={(e)=>setCriteria(e.target.value)} />
        </div>
        <div className="flex items-end">
          <Button onClick={send} loading={loading} disabled={loading}>Run</Button>
        </div>
      </div>
      <div className="mt-3 rounded border bg-gray-50 p-3">
        <MetricsViewer data={resp} />
        {view === 'pretty' ? <JsonViewer data={resp} /> : <JsonTree data={resp} />}
      </div>
      <div className="mt-2 space-x-2">
        <Button variant="secondary" onClick={() => setView('pretty')} disabled={view==='pretty'}>Pretty</Button>
        <Button variant="secondary" onClick={() => setView('tree')} disabled={view==='tree'}>Tree</Button>
      </div>
    </div>
  );
}

function MetricsViewer({ data }: { data: any }) {
  if (!data) return null;
  const metrics = (data.metrics) || (Array.isArray(data.results) ? data.results?.[0]?.metrics : undefined);
  if (!metrics || typeof metrics !== 'object') return null;
  const entries = Object.entries(metrics as Record<string, any>);
  if (entries.length === 0) return null;
  return (
    <div className="mb-3">
      <div className="mb-1 text-sm font-semibold text-gray-800">Metrics</div>
      <div className="overflow-x-auto">
        <table className="w-full table-auto text-sm">
          <thead>
            <tr className="text-left text-gray-600">
              <th className="px-2 py-1">Name</th>
              <th className="px-2 py-1">Value</th>
            </tr>
          </thead>
          <tbody>
            {entries.map(([k,v]) => (
              <tr key={k} className="border-t">
                <td className="px-2 py-1 text-gray-700">{k}</td>
                <td className="px-2 py-1 font-mono text-gray-900">{typeof v === 'number' ? v.toFixed(4) : String(v)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function ResultsExplorer() {
  const { show } = useToast();
  const [loading, setLoading] = useState(false);
  const [items, setItems] = useState<any[]>([]);
  const [q, setQ] = useState('');
  const [status, setStatus] = useState<'all'|'success'|'failed'|'running'>('all');
  const [selected, setSelected] = useState<any>(null);
  const [tabSetter, setTabSetter] = useState<any>(null);

  const refresh = async () => {
    setLoading(true);
    setSelected(null);
    try {
      const url = `${getApiBaseUrl()}/evaluations?limit=50`;
      const r = await fetch(url, { headers: buildAuthHeaders('GET') });
      const json = await r.json();
      const arr = Array.isArray(json?.items) ? json.items : (Array.isArray(json) ? json : []);
      setItems(arr);
      show({ title: 'Results loaded', variant: 'success' });
    } catch (e: any) {
      setItems([]);
      show({ title: 'Failed to load results', description: e?.message || 'Failed', variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { refresh(); }, []);

  const filtered = useMemo(() => {
    const t = q.trim().toLowerCase();
    return (items || []).filter((it) => {
      if (status !== 'all') {
        const s = String(it.status || '').toLowerCase();
        const map: any = { success: ['success','completed','done'], failed: ['failed','error'], running: ['running','in_progress'] };
        const allowed: string[] = map[status] || [];
        if (!allowed.some((x) => s.includes(x))) return false;
      }
      if (t) {
        const hay = JSON.stringify(it).toLowerCase();
        if (!hay.includes(t)) return false;
      }
      return true;
    });
  }, [items, q, status]);

  return (
    <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
      <div>
        <div className="mb-2 flex items-center justify-between">
          <div className="text-sm text-gray-700">Results</div>
          <div className="space-x-2">
            <Button variant="secondary" onClick={refresh} disabled={loading}>Refresh</Button>
          </div>
        </div>
        <div className="mb-2 grid grid-cols-1 gap-3 md:grid-cols-6">
          <div className="md:col-span-4"><Input placeholder="Filter…" value={q} onChange={(e)=>setQ(e.target.value)} /></div>
          <div className="md:col-span-2">
            <label className="mb-1 block text-sm font-medium text-gray-700">Status</label>
            <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={status} onChange={(e)=>setStatus(e.target.value as any)}>
              <option value="all">All</option>
              <option value="success">Success</option>
              <option value="failed">Failed</option>
              <option value="running">Running</option>
            </select>
          </div>
        </div>
        {loading ? (
          <div className="space-y-2">{Array.from({ length: 6 }).map((_, i) => (<CardSkeleton key={i} />))}</div>
        ) : filtered.length === 0 ? (
          <div className="text-sm text-gray-600">No results.</div>
        ) : (
          <ul className="space-y-2">
            {filtered.map((it, idx) => (
              <li key={idx} className="rounded border p-2 hover:bg-gray-50">
                <div className="flex items-center justify-between">
                  <div>
                    <div className="font-medium text-gray-800">{it.name || it.type || 'Evaluation'}</div>
                    <div className="text-xs text-gray-500">{it.status || '-'} • {it.created_at ? new Date(it.created_at).toLocaleString() : ''}</div>
                  </div>
                  <div className="text-xs text-gray-400">{it.id || it.eval_id || ''}</div>
                </div>
                <div className="mt-2 flex items-center space-x-2 text-xs">
                  <Button variant="secondary" onClick={()=>setSelected(it)}>View</Button>
                  {(it.run_id || it.id) && (
                    <Button variant="secondary" onClick={() => {
                      try {
                        const id = String(it.run_id || it.id);
                        sessionStorage.setItem('tldw-eval-run-id', id);
                        window.location.hash = '#run';
                        window.dispatchEvent(new CustomEvent('tldw-switch-eval-tab', { detail: { tab: 'run', runId: id } }));
                      } catch {}
                    }}>Watch</Button>
                  )}
                  <Button variant="secondary" onClick={async ()=>{ try { await navigator.clipboard.writeText(JSON.stringify(it, null, 2)); } catch {} }}>Copy JSON</Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
      <div>
        <div className="mb-2 text-sm text-gray-700">Selected</div>
        <div className="rounded border bg-gray-50 p-3">
          {selected ? <JsonViewer data={selected} /> : <div className="text-sm text-gray-600">Pick a result on the left.</div>}
        </div>
      </div>
    </div>
  );
}

function RunDetails() {
  const { show } = useToast();
  const [runId, setRunId] = useState('');
  const [polling, setPolling] = useState(false);
  const [data, setData] = useState<any>(null);
  const [view, setView] = useState<'pretty'|'tree'>('pretty');
  const timerRef = useRef<any>(null);

  const fetchRun = async (id: string) => {
    if (!id.trim()) { show({ title: 'Enter run id', variant: 'warning' }); return; }
    try {
      const url = `${getApiBaseUrl()}/evaluations/runs/${encodeURIComponent(id.trim())}`;
      const r = await fetch(url, { headers: buildAuthHeaders('GET') });
      const text = await r.text(); let json: any; try { json = JSON.parse(text); } catch { json = text; }
      setData(json);
      if (!r.ok) show({ title: 'Fetch failed', description: `${r.status} ${r.statusText}`, variant: 'warning' });
    } catch (e: any) {
      show({ title: 'Error fetching run', description: e?.message || 'Failed', variant: 'danger' });
    }
  };

  const startPolling = () => {
    if (!runId.trim()) { show({ title: 'Enter run id', variant: 'warning' }); return; }
    setPolling(true);
    fetchRun(runId);
    timerRef.current = setInterval(() => fetchRun(runId), 2000);
    show({ title: 'Polling started', variant: 'info' });
  };
  const stopPolling = () => {
    setPolling(false);
    if (timerRef.current) { clearInterval(timerRef.current); timerRef.current = null; }
    show({ title: 'Polling stopped', variant: 'info' });
  };
  useEffect(() => () => { if (timerRef.current) clearInterval(timerRef.current); }, []);
  // Listen for watch events from Results tab and pick stored run id
  useEffect(() => {
    const h = (e: any) => {
      const d = e?.detail || {};
      if (d?.tab === 'run' && d?.runId) setRunId(String(d.runId));
    };
    window.addEventListener('tldw-switch-eval-tab', h as any);
    try { const saved = sessionStorage.getItem('tldw-eval-run-id'); if (saved) setRunId(saved); } catch {}
    return () => window.removeEventListener('tldw-switch-eval-tab', h as any);
  }, []);

  const cancelRun = async () => {
    if (!runId.trim()) return;
    try {
      const url = `${getApiBaseUrl()}/evaluations/runs/${encodeURIComponent(runId.trim())}/cancel`;
      const r = await fetch(url, { method: 'POST', headers: buildAuthHeaders('POST') });
      show({ title: r.ok ? 'Cancel sent' : 'Cancel failed', description: `${r.status} ${r.statusText}`, variant: r.ok ? 'success' : 'warning' });
    } catch (e: any) {
      show({ title: 'Cancel error', description: e?.message || 'Failed', variant: 'danger' });
    }
  };

  return (
    <div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <div className="sm:col-span-2"><Input label="Run ID" value={runId} onChange={(e)=>setRunId(e.target.value)} /></div>
        <div className="flex items-end space-x-2">
          {!polling ? (
            <Button onClick={startPolling}>Start Poll</Button>
          ) : (
            <Button variant="secondary" onClick={stopPolling}>Stop Poll</Button>
          )}
          <Button variant="secondary" onClick={cancelRun}>Cancel Run</Button>
        </div>
      </div>
      <div className="mt-3 rounded border bg-gray-50 p-3">
        {view === 'pretty' ? <JsonViewer data={data} /> : <JsonTree data={data} />}
      </div>
      <div className="mt-2 space-x-2">
        <Button variant="secondary" onClick={() => setView('pretty')} disabled={view==='pretty'}>Pretty</Button>
        <Button variant="secondary" onClick={() => setView('tree')} disabled={view==='tree'}>Tree</Button>
      </div>
    </div>
  );
}
