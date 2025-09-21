import { useEffect, useMemo, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { Tabs } from '@/components/ui/Tabs';
import JsonEditor from '@/components/ui/JsonEditor';
import JsonViewer from '@/components/ui/JsonViewer';
import JsonTree from '@/components/ui/JsonTree';
import { buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';

export default function EvaluationsPage() {
  const [tab, setTab] = useState<'ocr_json'|'ocr_pdf'|'geval'|'rq'>('ocr_json');
  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4">
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Evaluations</h1>
          <div className="w-1/2"><Tabs items={[{key:'ocr_json',label:'OCR (JSON)'},{key:'ocr_pdf',label:'OCR (PDF)'},{key:'geval',label:'G-Eval'},{key:'rq',label:'Response Quality'}]} value={tab} onChange={(k)=>setTab(k as any)} /></div>
        </div>
        <div className="rounded-md border bg-white p-4 transition-all duration-150">
          {tab === 'ocr_json' && <OCRJson/>}
          {tab === 'ocr_pdf' && <OCRPdf/>}
          {tab === 'geval' && <GEval/>}
          {tab === 'rq' && <ResponseQuality/>}
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
