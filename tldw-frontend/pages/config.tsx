import { useEffect, useMemo, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import api, { buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useConfig } from '@/hooks/useConfig';
import { addRequestHistory, getRequestHistory, RequestHistoryItem, clearRequestHistory } from '@/lib/history';
import JsonViewer from '@/components/ui/JsonViewer';
import JsonTree from '@/components/ui/JsonTree';
import JsonEditor from '@/components/ui/JsonEditor';
import { QUICK_FORMS, QuickFormPreset } from '@/lib/quickforms';
import { validateJsonSchema } from '@/lib/schema';
import { Tabs } from '@/components/ui/Tabs';
import { Switch } from '@/components/ui/Switch';
import { Badge } from '@/components/ui/Badge';
import { validateWithAjv } from '@/lib/ajv';
import { formatRelativeTime } from '@/lib/utils';
import { useToast } from '@/components/ui/ToastProvider';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';

type Method = 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';

function tryParseJSON(text: string): { ok: boolean; value?: any; error?: string } {
  if (!text.trim()) return { ok: true, value: undefined };
  try {
    return { ok: true, value: JSON.parse(text) };
  } catch (e: any) {
    return { ok: false, error: e?.message || 'Invalid JSON' };
  }
}

function jsonPrettify(value: any): string {
  try { return JSON.stringify(value, null, 2); } catch { return String(value); }
}

function buildCurl(method: string, url: string, headers: Record<string, string>, body?: any): string {
  const parts: string[] = [
    `curl -X ${method.toUpperCase()} \\\n+  '${url}' \\\n+  -H 'Accept: application/json'`,
  ];
  Object.entries(headers || {}).forEach(([k, v]) => {
    if (!v) return;
    parts.push(`  -H '${k}: ${v}'`);
  });
  if (body !== undefined) {
    const data = typeof body === 'string' ? body : JSON.stringify(body);
    parts.push(`  -H 'Content-Type: application/json' \\\n+  --data '${data.replace(/'/g, "'\\''")}'`);
  }
  return parts.join(' \\\n');
}

export default function ConfigPage() {
  const { show } = useToast();
  const { config, setApiBaseHost, setApiVersion, setXApiKey, setApiBearer, setTheme, reloadBootstrapConfig } = useConfig();

  // Connection status
  const [latencyMs, setLatencyMs] = useState<number | null>(null);
  const [status, setStatus] = useState<'idle' | 'ok' | 'fail' | 'loading'>('idle');
  const [statusDetail, setStatusDetail] = useState<string>('');

  const ping = async () => {
    setStatus('loading');
    setStatusDetail('');
    const start = Date.now();
    try {
      // Use a lightweight endpoint
      const url = `${getApiBaseUrl()}/llm/providers`;
      const resp = await fetch(url, { headers: buildAuthHeaders('GET') });
      const dur = Date.now() - start;
      setLatencyMs(dur);
      if (!resp.ok) throw new Error(`${resp.status} ${resp.statusText}`);
      setStatus('ok');
    } catch (e: any) {
      setStatus('fail');
      setStatusDetail(e?.message || 'Request failed');
      setLatencyMs(Date.now() - start);
    }
  };

  useEffect(() => { ping(); }, []);

  // Endpoint request builder
  const [method, setMethod] = useState<Method>('GET');
  const [path, setPath] = useState('/llm/providers');
  const [fullUrlMode, setFullUrlMode] = useState(false);
  const [headersText, setHeadersText] = useState('');
  const [bodyText, setBodyText] = useState('');
  const [jsonError, setJsonError] = useState<string>('');
  const [sending, setSending] = useState(false);
  const [respStatus, setRespStatus] = useState<string>('');
  const [respBody, setRespBody] = useState<any>(null);
  const [builderView, setBuilderView] = useState<'form' | 'response' | 'curl'>('form');

  const finalUrl = useMemo(() => {
    if (fullUrlMode) return path;
    return `${getApiBaseUrl()}${path.startsWith('/') ? '' : '/'}${path}`;
  }, [fullUrlMode, path]);

  const computedHeaders = useMemo(() => {
    let extra: Record<string, string> = {};
    try {
      if (headersText.trim()) extra = JSON.parse(headersText);
    } catch {}
    return { ...buildAuthHeaders(method), ...extra } as Record<string, string>;
  }, [headersText, method]);

  const sendRequest = async () => {
    setSending(true);
    setRespStatus('');
    setRespBody(null);
    setJsonError('');
    let bodyVal: any = undefined;
    if (['POST', 'PUT', 'PATCH', 'DELETE'].includes(method)) {
      const r = tryParseJSON(bodyText);
      if (!r.ok) { setJsonError(r.error || 'Invalid JSON'); setSending(false); return; }
      bodyVal = r.value;
    }
    const headers = computedHeaders;
    const start = Date.now();
    try {
      const resp = await fetch(finalUrl, {
        method,
        headers,
        body: bodyVal !== undefined ? JSON.stringify(bodyVal) : undefined,
      });
      const text = await resp.text();
      let parsed: any = null;
      try { parsed = JSON.parse(text); } catch { parsed = text; }
      setRespStatus(`${resp.status} ${resp.statusText}`);
      setRespBody(parsed);
      setBuilderView('response');
      show({ title: 'Request sent', description: `${resp.status} ${resp.statusText}`, variant: resp.ok ? 'success' : 'warning' });
      addRequestHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        method,
        url: finalUrl,
        baseURL: getApiBaseUrl(),
        status: resp.status,
        ok: resp.ok,
        duration_ms: Date.now() - start,
        timestamp: new Date().toISOString(),
        requestHeaders: headers,
        requestBody: bodyVal,
        responseBody: parsed,
      });
    } catch (e: any) {
      setRespStatus(`Error`);
      setRespBody({ error: e?.message || 'Request failed' });
      show({ title: 'Request failed', description: e?.message || 'Request failed', variant: 'danger' });
    } finally {
      setSending(false);
    }
  };

  const [history, setHistory] = useState<RequestHistoryItem[]>([]);
  const loadHistory = () => setHistory(getRequestHistory());
  useEffect(() => { loadHistory(); }, [respStatus]);

  const replay = (item: RequestHistoryItem) => {
    setMethod((item.method as Method) || 'GET');
    setFullUrlMode(true);
    setPath(item.url);
    setHeadersText(item.requestHeaders ? jsonPrettify(item.requestHeaders) : '');
    setBodyText(item.requestBody ? jsonPrettify(item.requestBody) : '');
    setRespStatus('');
    setRespBody(null);
  };

  // cURL generation for current request
  const curl = useMemo(() => buildCurl(method, finalUrl, computedHeaders, ['POST','PUT','PATCH','DELETE'].includes(method) ? tryParseJSON(bodyText).value : undefined), [method, finalUrl, computedHeaders, bodyText]);

  // Helpers
  const copy = async (text: string, label?: string) => { try { await navigator.clipboard.writeText(text); show({ title: label || 'Copied', variant: 'success' }); } catch {} };

  // Clipboard hotkeys: Cmd/Ctrl+Shift+C copies cURL, Cmd/Ctrl+Shift+J copies response JSON
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || !e.shiftKey) return;
      if (e.key.toLowerCase() === 'c') {
        e.preventDefault();
        copy(curl, 'cURL copied');
      }
      if (e.key.toLowerCase() === 'j') {
        e.preventDefault();
        copy(jsonPrettify(respBody), 'Response JSON copied');
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [curl, respBody]);

  return (
    <Layout>
      <div className="space-y-6">
        <HotkeysOverlay
          entries={[
            { keys: 'Cmd/Ctrl+Shift+C', description: 'Copy cURL' },
            { keys: 'Cmd/Ctrl+Shift+J', description: 'Copy response JSON' },
            { keys: '?', description: 'Toggle shortcuts help' },
          ]}
        />
        <h1 className="text-2xl font-bold text-gray-900">General & Utilities</h1>

        {/* Connection Status */}
        <div className="rounded-md border bg-white p-4">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-lg font-semibold text-gray-800">Connection Status</div>
            <div className="space-x-2">
              <Button variant="secondary" onClick={reloadBootstrapConfig}>Load /webui/config.json</Button>
              <Button onClick={ping}>Ping</Button>
            </div>
          </div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3 text-sm">
            <div>
              <div className="text-gray-500">API Base</div>
              <div className="font-mono break-words">{getApiBaseUrl()}</div>
            </div>
            <div>
              <div className="text-gray-500">Latency</div>
              <div className="font-semibold">{latencyMs != null ? `${latencyMs} ms` : '-'}</div>
            </div>
            <div>
              <div className="text-gray-500">Status</div>
              <div className={status === 'ok' ? 'text-green-600' : status === 'fail' ? 'text-red-600' : 'text-gray-700'}>
                {status === 'loading' ? 'Checking…' : status === 'ok' ? 'Healthy' : status === 'fail' ? 'Unreachable' : 'Idle'}
              </div>
            </div>
          </div>
          {status === 'fail' && statusDetail && (
            <div className="mt-2 text-xs text-red-600">{statusDetail}</div>
          )}
        </div>

        {/* Global Configuration */}
        <div className="rounded-md border bg-white p-4">
          <div className="mb-3 text-lg font-semibold text-gray-800">Configuration</div>
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <Input label="API Host (scheme://host:port)" value={config.apiBaseHost} onChange={(e) => setApiBaseHost(e.target.value)} placeholder="http://127.0.0.1:8000" />
            <Input label="API Version" value={config.apiVersion} onChange={(e) => setApiVersion(e.target.value)} placeholder="v1" />
            <Input label="X-API-KEY (single user)" value={config.xApiKey || ''} onChange={(e) => setXApiKey(e.target.value)} placeholder="optional" />
            <Input label="API Bearer (chat module)" value={config.apiBearer || ''} onChange={(e) => setApiBearer(e.target.value)} placeholder="optional" />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Theme</label>
              <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={config.theme} onChange={(e) => setTheme(e.target.value as any)}>
                <option value="system">System</option>
                <option value="light">Light</option>
                <option value="dark">Dark</option>
              </select>
            </div>
          </div>
        </div>

        {/* Endpoint Request Builder */}
        <div className="rounded-md border bg-white p-4">
          <div className="mb-3 text-lg font-semibold text-gray-800">Endpoint Request Builder</div>
          <div className="mb-2">
            <Tabs items={[{ key: 'form', label: 'Form' }, { key: 'response', label: 'Response' }, { key: 'curl', label: 'cURL' }]} value={builderView} onChange={(k)=>setBuilderView(k as any)} />
          </div>
          {builderView === 'form' && (
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-6">
            <div className="sm:col-span-1">
              <label className="mb-1 block text-sm font-medium text-gray-700">Method</label>
              <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={method} onChange={(e) => setMethod(e.target.value as Method)}>
                {['GET','POST','PUT','PATCH','DELETE'].map((m) => (<option key={m} value={m}>{m}</option>))}
              </select>
            </div>
            <div className="sm:col-span-5">
              <label className="mb-1 block text-sm font-medium text-gray-700">{fullUrlMode ? 'Full URL' : 'Endpoint Path (relative to /api/version)'}
              </label>
              <input className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={path} onChange={(e) => setPath(e.target.value)} placeholder="/llm/providers" />
            </div>
          </div>
          <div className="mb-2 flex items-center space-x-3 text-sm">
            <label className="inline-flex items-center space-x-2"><input type="checkbox" className="h-4 w-4" checked={fullUrlMode} onChange={(e) => setFullUrlMode(e.target.checked)} /><span>Use Full URL</span></label>
            <div className="text-gray-500">Final: <span className="font-mono">{finalUrl}</span></div>
          </div>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Headers (JSON)</label>
              <JsonEditor value={headersText} onChange={setHeadersText} height={180} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Body (JSON)</label>
              <JsonEditor value={bodyText} onChange={setBodyText} height={180} />
              {jsonError && <div className="mt-1 text-xs text-red-600">{jsonError}</div>}
            </div>
          </div>
          <div className="mt-3 flex items-center justify-between">
            <Button onClick={sendRequest} loading={sending}>Send Request</Button>
            <div className="text-xs text-gray-600">Auth and CSRF headers are auto-included.</div>
          </div>
          )}

          {/* Response */}
          {builderView === 'response' && (
          <div className="mt-4 rounded border bg-gray-50 p-3">
            <div className="mb-2 flex items-center justify-between text-sm">
              <div className="font-medium text-gray-800">Response: <span className="font-mono">{respStatus || '-'}</span></div>
              <div className="space-x-2">
                <Button variant="secondary" onClick={() => copy(jsonPrettify(respBody), 'Response JSON copied')}>Copy JSON</Button>
              </div>
            </div>
            <JsonViewer data={respBody} />
          </div>
          )}

          {/* cURL */}
          {builderView === 'curl' && (
          <div className="mt-4 rounded border bg-gray-50 p-3">
            <div className="mb-2 flex items-center justify-between text-sm">
              <div className="font-medium text-gray-800">cURL</div>
              <div className="space-x-2">
                <Button variant="secondary" onClick={() => copy(curl, 'cURL copied')}>Copy cURL</Button>
              </div>
            </div>
            <pre className="overflow-auto whitespace-pre break-words font-mono text-xs text-gray-800">{curl}</pre>
          </div>
          )}
        </div>

        {/* Quick Endpoint Forms */}
        <QuickFormsSection />

        {/* Global Request History */}
        <RequestHistorySection history={history} replay={replay} reload={loadHistory} />
      </div>
    </Layout>
  );
}

function methodBadgeVariant(m?: string) {
  switch ((m || '').toUpperCase()) {
    case 'GET': return 'info';
    case 'POST': return 'primary';
    case 'PUT': return 'warning';
    case 'PATCH': return 'neutral';
    case 'DELETE': return 'danger';
    default: return 'neutral';
  }
}

function statusBadgeVariant(status?: number, ok?: boolean) {
  if (!status && ok === false) return 'danger';
  if (!status) return 'neutral';
  if (status >= 200 && status < 300) return 'success';
  if (status >= 400 && status < 500) return 'warning';
  if (status >= 500) return 'danger';
  return 'neutral';
}

function RequestHistorySection({ history, replay, reload }: { history: RequestHistoryItem[]; replay: (h: RequestHistoryItem) => void; reload: () => void; }) {
  const [q, setQ] = useState('');
  const [m, setM] = useState<'ALL' | 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE'>('ALL');
  const [s, setS] = useState<'all' | '2xx' | '4xx' | '5xx' | 'error'>('all');

  const copy = async (text: string) => { try { await navigator.clipboard.writeText(text); } catch {} };

  const filtered = useMemo(() => {
    const term = q.trim().toLowerCase();
    return (history || []).filter((h) => {
      if (m !== 'ALL' && (h.method || '').toUpperCase() !== m) return false;
      if (s !== 'all') {
        if (s === 'error' && h.ok !== false) return false;
        if (s === '2xx' && !(h.status && h.status >= 200 && h.status < 300)) return false;
        if (s === '4xx' && !(h.status && h.status >= 400 && h.status < 500)) return false;
        if (s === '5xx' && !(h.status && h.status >= 500)) return false;
      }
      if (term) {
        const hay = `${h.method} ${h.url} ${h.status} ${h.errorMessage || ''}`.toLowerCase();
        if (!hay.includes(term)) return false;
      }
      return true;
    });
  }, [history, q, m, s]);

  return (
    <div className="rounded-md border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-lg font-semibold text-gray-800">Request History</div>
        <div className="space-x-2">
          <Button variant="secondary" onClick={() => { clearRequestHistory(); reload(); }}>Clear</Button>
          <Button variant="secondary" onClick={reload}>Refresh</Button>
        </div>
      </div>
      <div className="mb-3 grid grid-cols-1 gap-3 md:grid-cols-6">
        <div className="md:col-span-3">
          <Input placeholder="Filter by URL, status…" value={q} onChange={(e) => setQ(e.target.value)} />
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Method</label>
          <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={m} onChange={(e)=>setM(e.target.value as any)}>
            {['ALL','GET','POST','PUT','PATCH','DELETE'].map((x) => (<option key={x} value={x}>{x}</option>))}
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Status</label>
          <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={s} onChange={(e)=>setS(e.target.value as any)}>
            <option value="all">All</option>
            <option value="2xx">2xx</option>
            <option value="4xx">4xx</option>
            <option value="5xx">5xx</option>
            <option value="error">Errors</option>
          </select>
        </div>
        <div className="md:col-span-1 flex items-end text-sm text-gray-600">{filtered.length} of {history.length}</div>
      </div>
      {filtered.length === 0 ? (
        <div className="text-sm text-gray-600">No matching requests.</div>
      ) : (
        <div className="grid grid-cols-1 gap-3">
          {filtered.map((h) => (
            <div key={h.id} className="rounded border p-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center space-x-2">
                  <span className="font-mono text-xs text-gray-500" title={new Date(h.timestamp).toLocaleString()}>{formatRelativeTime(h.timestamp)}</span>
                  <Badge variant={methodBadgeVariant(h.method) as any}>{h.method}</Badge>
                  <Badge variant={statusBadgeVariant(h.status, h.ok) as any}>{h.status ?? (h.ok === false ? 'Error' : '-')}</Badge>
                  <span className="text-xs text-gray-600">{h.duration_ms != null ? `${h.duration_ms} ms` : ''}</span>
                </div>
                <div className="space-x-2">
                  <Button variant="secondary" onClick={() => replay(h)}>Replay</Button>
                  <Button variant="secondary" onClick={() => copy(buildCurl(h.method, h.url, h.requestHeaders || {}, h.requestBody))}>Copy cURL</Button>
                </div>
              </div>
              <div className="mt-2 truncate font-mono text-sm" title={h.url}>{h.url}</div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

function QuickFormsSection() {
  const { show } = useToast();
  const [selected, setSelected] = useState<string>(QUICK_FORMS[0]?.id || '');
  const preset = useMemo(() => QUICK_FORMS.find(p => p.id === selected) as QuickFormPreset | undefined, [selected]);
  const [state, setState] = useState<Record<string, any>>(preset?.defaults || {});
  const [validateOnSend, setValidateOnSend] = useState(true);
  const [resp, setResp] = useState<any>(null);
  const [status, setStatus] = useState<string>('');
  const [sending, setSending] = useState(false);
  const [bodyText, setBodyText] = useState('');
  const [errors, setErrors] = useState<string[]>([]);
  const [view, setView] = useState<'form' | 'json' | 'response' | 'curl'>('form');
  const [respView, setRespView] = useState<'pretty' | 'tree'>('pretty');

  useEffect(() => {
    setState(preset?.defaults || {});
    setResp(null);
    setStatus('');
    setErrors([]);
    setBodyText('');
  }, [preset?.id]);

  const computedBody = useMemo(() => {
    if (!preset) return undefined;
    return preset.toBody(state);
  }, [preset, state]);

  useEffect(() => {
    try { setBodyText(JSON.stringify(computedBody, null, 2)); } catch { setBodyText(''); }
  }, [computedBody]);

  const onSend = async () => {
    if (!preset) return;
    setSending(true);
    setResp(null);
    setStatus('');
    setErrors([]);
    let body: any = computedBody;
    // Prefer edited JSON if valid
    try {
      if (bodyText && bodyText.trim()) {
        const parsed = JSON.parse(bodyText);
        body = parsed;
      }
    } catch (e) {
      // keep computed body; surface a non-blocking error note
      setErrors([...(errors || []), 'Advanced JSON invalid; using form values']);
    }
    const errs: string[] = [];
    if (validateOnSend && typeof preset.validate === 'function') {
      errs.push(...preset.validate(body));
    }
    if (validateOnSend && preset.schema) {
      errs.push(...validateJsonSchema(body, preset.schema));
      const ajvErrs = await validateWithAjv(body, preset.schema);
      if (ajvErrs.length) errs.push(...ajvErrs);
    }
    if (errs.length) { setErrors(errs); setSending(false); show({ title: 'Validation failed', description: errs.join('; '), variant: 'warning' }); return; }
    try {
      const url = `${getApiBaseUrl()}${preset.path.startsWith('/') ? '' : '/'}${preset.path}`;
      const method = preset.method;
      const headers = buildAuthHeaders(method);
      const respRaw = await fetch(url, { method, headers, body: method === 'GET' ? undefined : JSON.stringify(body) });
      const text = await respRaw.text();
      let parsed: any = null;
      try { parsed = JSON.parse(text); } catch { parsed = text; }
      setStatus(`${respRaw.status} ${respRaw.statusText}`);
      setResp(parsed);
      setView('response');
      show({ title: 'Request sent', description: `${respRaw.status} ${respRaw.statusText}`, variant: respRaw.ok ? 'success' : 'warning' });
      addRequestHistory({
        id: `${Date.now()}-${Math.random().toString(36).slice(2)}`,
        method,
        url,
        baseURL: getApiBaseUrl(),
        status: respRaw.status,
        ok: respRaw.ok,
        duration_ms: undefined,
        timestamp: new Date().toISOString(),
        requestHeaders: headers,
        requestBody: body,
        responseBody: parsed,
      });
    } catch (e: any) {
      setStatus('Error');
      setResp({ error: e?.message || 'Request failed' });
      show({ title: 'Request failed', description: e?.message || 'Request failed', variant: 'danger' });
    } finally {
      setSending(false);
    }
  };

  const copy = async (text: string, label?: string) => { try { await navigator.clipboard.writeText(text); show({ title: label || 'Copied', variant: 'success' }); } catch {} };

  const curl = `curl -X ${preset?.method} \\\n+  '${getApiBaseUrl()}${preset?.path || ''}' \\\n+  -H 'Accept: application/json' \\\n+  -H 'Content-Type: application/json' \\\n+  --data '${(bodyText || '').replace(/'/g, "'\\''")}'`;

  return (
    <div className="rounded-md border bg-white p-4">
      <div className="mb-3 flex items-center justify-between">
        <div className="text-lg font-semibold text-gray-800">Quick Endpoint Forms</div>
        <div className="flex items-center space-x-3">
          <Switch checked={validateOnSend} onChange={setValidateOnSend} label="Validate" />
          {errors.length > 0 ? <Badge variant="danger">{errors.length} error(s)</Badge> : <Badge variant="success">Ready</Badge>}
        </div>
      </div>
      <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
        <div className="sm:col-span-2">
          <label className="mb-1 block text-sm font-medium text-gray-700">Endpoint</label>
          <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={selected} onChange={(e) => setSelected(e.target.value)}>
            {QUICK_FORMS.map((p) => (
              <option key={p.id} value={p.id}>{p.title}</option>
            ))}
          </select>
          {preset?.describe && (<div className="mt-1 text-xs text-gray-600">{preset.describe}</div>)}
        </div>
        {preset && (
          <div className="sm:col-span-1">
            <div className="text-sm text-gray-700">Method/Path</div>
            <div className="font-mono text-xs">{preset.method} {preset.path}</div>
          </div>
        )}
      </div>
      {/* Tabs */}
      <div className="mt-2">
        <Tabs
          items={[{ key: 'form', label: 'Form' }, { key: 'json', label: 'JSON' }, { key: 'response', label: 'Response' }, { key: 'curl', label: 'cURL' }]}
          value={view}
          onChange={(k) => setView(k as any)}
        />
      </div>

      {view === 'form' && (
        <div className="mt-3">
          {/* Form fields (enhanced helpers per preset) */}
          {preset?.id === 'chat/completions' && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Input label="Model" value={state.model || ''} onChange={(e) => setState({ ...state, model: e.target.value })} placeholder="provider/model or auto" />
              <div className="flex items-end"><Switch checked={!!state.stream} onChange={(v) => setState({ ...state, stream: v })} label="Stream" /></div>
              <div className="flex items-end"><Switch checked={!!state.save_to_db} onChange={(v) => setState({ ...state, save_to_db: v })} label="Save to DB" /></div>
              <div className="md:col-span-3"><Input label="Prompt" value={state.prompt || ''} onChange={(e) => setState({ ...state, prompt: e.target.value })} placeholder="Ask something..." /></div>
            </div>
          )}
          {preset?.id === 'rag/search' && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="md:col-span-2"><Input label="Query" value={state.query || ''} onChange={(e) => setState({ ...state, query: e.target.value })} placeholder="Search your media..." /></div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Top K</label>
                <input type="number" min={1} className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={state.top_k ?? 10} onChange={(e) => setState({ ...state, top_k: parseInt(e.target.value || '10', 10) })} />
              </div>
              <div className="md:col-span-3"><Switch checked={!!state.generation} onChange={(v) => setState({ ...state, generation: v })} label="Enable Generation" /></div>
            </div>
          )}
          {preset?.id === 'embeddings' && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Input label="Model" value={state.model || ''} onChange={(e) => setState({ ...state, model: e.target.value })} placeholder="text-embedding-3-small" />
              <div className="md:col-span-2"><Input label="Input" value={state.input || ''} onChange={(e) => setState({ ...state, input: e.target.value })} placeholder="Text to embed" /></div>
            </div>
          )}
          {preset?.id === 'media/search' && (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="md:col-span-2"><Input label="Query" value={state.query || ''} onChange={(e) => setState({ ...state, query: e.target.value })} placeholder="Find media..." /></div>
              <div>
                <label className="mb-1 block text-sm font-medium text-gray-700">Per Page</label>
                <input type="number" min={1} className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={state.per_page ?? 20} onChange={(e) => setState({ ...state, per_page: parseInt(e.target.value || '20', 10) })} />
              </div>
            </div>
          )}
          <div className="mt-3 flex items-center justify-between">
            <Button onClick={onSend} loading={sending} disabled={sending || !preset}>Send</Button>
            <div className="text-xs text-gray-600">Response: <span className="font-mono">{status || '-'}</span></div>
          </div>
        </div>
      )}

      {view === 'json' && (
        <div className="mt-3">
      <div className="mb-2 flex items-center justify-between">
        <div className="text-sm text-gray-700">Edit JSON payload</div>
        <div className="space-x-2">
              <Button variant="secondary" onClick={() => copy(bodyText, 'Payload copied')}>Copy</Button>
          <Button variant="secondary" onClick={() => { try { setBodyText(JSON.stringify(JSON.parse(bodyText), null, 2)); } catch {} }}>Format</Button>
          <Button onClick={onSend} loading={sending} disabled={sending || !preset}>Send</Button>
        </div>
      </div>
      <JsonEditor value={bodyText} onChange={setBodyText} height={320} schema={preset?.schema} />
      {preset?.schema && (
        <div className="mt-2 text-xs text-gray-600">Schema: {preset.schema.title || preset.title}</div>
      )}
      {errors.length > 0 && (<div className="mt-2 text-xs text-red-600">{errors.join('; ')}</div>)}
      </div>
      )}

      {view === 'response' && (
        <div className="mt-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm text-gray-700">Response <span className="font-mono">{status || '-'}</span></div>
            <div className="space-x-2">
              <Button variant="secondary" onClick={() => setRespView('pretty')} disabled={respView === 'pretty'}>Pretty</Button>
              <Button variant="secondary" onClick={() => setRespView('tree')} disabled={respView === 'tree'}>Tree</Button>
              <Button variant="secondary" onClick={() => copy(JSON.stringify(resp, null, 2), 'Response JSON copied')}>Copy JSON</Button>
            </div>
          </div>
          <div className="rounded border bg-gray-50 p-3">
            {respView === 'pretty' ? <JsonViewer data={resp} /> : <JsonTree data={resp} />}
          </div>
        </div>
      )}

      {view === 'curl' && (
        <div className="mt-3">
          <div className="mb-2 flex items-center justify-between">
            <div className="text-sm text-gray-700">cURL</div>
            <div className="space-x-2"><Button variant="secondary" onClick={() => copy(curl, 'cURL copied')}>Copy</Button></div>
          </div>
          <pre className="overflow-auto whitespace-pre break-words rounded border bg-gray-50 p-3 font-mono text-xs text-gray-800">{curl}</pre>
        </div>
      )}
    </div>
  );
}
