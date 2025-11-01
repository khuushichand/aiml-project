import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { apiClient } from '@/lib/api';
import { debounce } from '@/lib/utils';
import { useToast } from '@/components/ui/ToastProvider';
import JsonEditor from '@/components/ui/JsonEditor';
import { CardSkeleton } from '@/components/ui/Skeleton';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';

type MediaType = 'video' | 'audio' | 'document' | 'pdf';

export default function MediaPage() {
  const { show } = useToast();
  const router = useRouter();
  const [mediaType, setMediaType] = useState<MediaType>('document');
  const [files, setFiles] = useState<FileList | null>(null);
  const [urls, setUrls] = useState('');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);

  // Search/list state
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [allItems, setAllItems] = useState<any[]>([]);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [totalItems, setTotalItems] = useState(0);
  const itemsPerPage = 10;
  const [selectedItem, setSelectedItem] = useState<any | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResult, setAnalysisResult] = useState<string | null>(null);
  const [analysisModel, setAnalysisModel] = useState<string>('gpt-3.5-turbo');
  const [analysisPrompt, setAnalysisPrompt] = useState<string>('Summarize the following content in 5 bullet points.');
  const [showAdvanced, setShowAdvanced] = useState(false);
  const [advancedJson, setAdvancedJson] = useState<string>(JSON.stringify({ perform_analysis: true, perform_chunking: true }, null, 2));
  type ClaimsToggle = 'inherit' | 'enabled' | 'disabled';
  const [claimsExtraction, setClaimsExtraction] = useState<ClaimsToggle>('inherit');
  const [claimsExtractorMode, setClaimsExtractorMode] = useState<string>('');
  const [claimsMaxPerChunk, setClaimsMaxPerChunk] = useState<string>('');

  const endpoint = (t: MediaType) => {
    switch (t) {
      case 'video': return '/media/process-videos';
      case 'audio': return '/media/process-audios';
      case 'pdf': return '/media/process-pdfs';
      default: return '/media/process-documents';
    }
  };

  const onSubmit = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const fd = new FormData();
      // Append URLs (multiple)
      const list = urls.split(/\n|,/).map(s => s.trim()).filter(Boolean);
      for (const u of list) fd.append('urls', u);
      // Append files (multiple)
      if (files) {
        Array.from(files).forEach((f) => fd.append('files', f));
      }
      // Advanced options JSON appended as fields
      try {
        const opts = JSON.parse(advancedJson || '{}');
        delete opts.perform_claims_extraction;
        delete opts.claims_extractor_mode;
        delete opts.claims_max_per_chunk;
        Object.entries(opts).forEach(([k, v]) => {
          if (v !== undefined && v !== null) fd.append(k, typeof v === 'string' ? v : JSON.stringify(v));
        });
      } catch {}
      if (claimsExtraction !== 'inherit') {
        fd.append('perform_claims_extraction', claimsExtraction === 'enabled' ? 'true' : 'false');
      }
      if (claimsExtractorMode.trim().length > 0) {
        fd.append('claims_extractor_mode', claimsExtractorMode.trim());
      }
      if (claimsMaxPerChunk.trim().length > 0) {
        const parsed = parseInt(claimsMaxPerChunk, 10);
        if (!Number.isNaN(parsed) && parsed >= 1 && parsed <= 12) {
          fd.append('claims_max_per_chunk', String(parsed));
        }
      }

      const res = await apiClient.post(endpoint(mediaType), fd, {
        headers: { 'Content-Type': 'multipart/form-data' },
      });
      setResult(res);
      show({ title: 'Ingestion started', variant: 'success' });
    } catch (e: any) {
      setError(e.message || 'Upload failed');
      show({ title: 'Upload failed', description: e?.message || 'Failed', variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  // Debounced search function (GET /media/search)
  const doSearch = useMemo(() => debounce(async (q: string) => {
    if (!q || q.trim().length < 2) {
      setSearchResults([]);
      return;
    }
    setSearchLoading(true);
    try {
      const data = await apiClient.get<any>('/media/search', { params: { query: q, limit: 10 } });
      setSearchResults(data?.items || []);
    } catch (e) {
      setSearchResults([]);
    } finally {
      setSearchLoading(false);
    }
  }, 300), []);

  useEffect(() => {
    doSearch(searchQuery);
  }, [searchQuery, doSearch]);

  const loadAll = async (p = 1) => {
    setSearchLoading(true);
    try {
      const data = await apiClient.post<any>('/media/search', {
        query: '',
        media_types: [],
        tags: [],
        keywords: [],
      }, { params: { page: p, results_per_page: itemsPerPage } });

      setAllItems(data?.items || []);
      setPage(p);
      setTotalItems(data?.pagination?.total_items || 0);
      setTotalPages(data?.pagination?.total_pages || 1);
      show({ title: 'Media loaded', description: `Page ${p}`, variant: 'success' });
    } catch (e) {
      setAllItems([]);
      show({ title: 'Load failed', variant: 'warning' });
    } finally {
      setSearchLoading(false);
    }
  };

  const loadDetails = async (id: number) => {
    try {
      const data = await apiClient.get<any>(`/media/${id}`);
      setSelectedItem(data);
      setAnalysisResult(null);
      show({ title: 'Loaded details', variant: 'info' });
    } catch (e) {
      setSelectedItem(null);
      show({ title: 'Load details failed', variant: 'warning' });
    }
  };

  const summarizeSelected = async () => {
    if (!selectedItem) return;
    setAnalyzing(true);
    setAnalysisResult(null);
    try {
      const text: string = selectedItem?.content?.text || '';
      const snippet = text.slice(0, 12000); // avoid very large payloads
      const payload = {
        model: analysisModel,
        stream: false,
        messages: [
          { role: 'system', content: 'You are a helpful assistant that summarizes content concisely.' },
          { role: 'user', content: `${analysisPrompt}\n\n${snippet}` }
        ],
      };
      const res = await apiClient.post<any>('/chat/completions', payload);
      const textOut = res?.choices?.[0]?.message?.content || '';
      setAnalysisResult(textOut);
      show({ title: 'Summary ready', variant: 'success' });
    } catch (e: any) {
      setAnalysisResult(`Error: ${e.message || e}`);
      show({ title: 'Summarize failed', variant: 'danger' });
    } finally {
      setAnalyzing(false);
    }
  };

  const sendToChatSelected = async () => {
    if (!selectedItem) return;
    try {
      const text: string = selectedItem?.content?.text || '';
      const snippet = text.slice(0, 12000); // keep reasonable size
      const payload = { message: snippet, title: selectedItem?.source?.title || '' };
      localStorage.setItem('tldw-chat-prefill', JSON.stringify(payload));
      router.push('/chat');
      show({ title: 'Sent to Chat', variant: 'success' });
    } catch {
      // no-op
    }
  };

  // Media hotkeys: Cmd/Ctrl+Shift+L (Load all), Cmd/Ctrl+Shift+S (Summarize), Cmd/Ctrl+Shift+J (Copy result JSON)
  useEffect(() => {
    const onKey = async (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || !e.shiftKey) return;
      const k = e.key.toLowerCase();
      if (k === 'l') { e.preventDefault(); await loadAll(1); }
      if (k === 's') { e.preventDefault(); await summarizeSelected(); }
      if (k === 'j') {
        e.preventDefault();
        try { await navigator.clipboard.writeText(JSON.stringify(result, null, 2)); show({ title: 'Result copied', variant: 'success' }); } catch {}
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [result, summarizeSelected]);

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4 transition-all duration-150">
        <HotkeysOverlay
          entries={[
            { keys: 'Cmd/Ctrl+Shift+L', description: 'Load all media' },
            { keys: 'Cmd/Ctrl+Shift+S', description: 'Summarize selected media' },
            { keys: 'Cmd/Ctrl+Shift+J', description: 'Copy latest result JSON' },
            { keys: '?', description: 'Toggle shortcuts help' },
          ]}
        />
        <h1 className="text-2xl font-bold text-gray-900">Media Processing</h1>

        <div className="rounded-md border bg-white p-4 space-y-4 transition-all duration-150">
          {/* Search section */}
          <div className="rounded border p-3">
            <h2 className="mb-2 text-lg font-semibold">Search Media</h2>
            <Input label="Search" value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)} placeholder="Type to search (min 2 chars)..." />
            <div className="mt-2 text-sm text-gray-600">{searchLoading ? 'Searching…' : searchResults.length > 0 ? `${searchResults.length} result(s)` : searchQuery.length >= 2 ? 'No results' : 'Enter at least 2 characters'}</div>
            {searchResults.length > 0 && (
              <ul className="mt-2 space-y-2">
                {searchResults.map((item, idx) => (
                  <li key={idx} className="rounded border p-2">
                    <div className="font-medium text-gray-800">{item.title || 'Untitled'}</div>
                    <div className="text-xs text-gray-500">{item.media_type || 'unknown'}</div>
                  </li>
                ))}
              </ul>
            )}
          </div>

          {/* All media listing */}
          <div className="rounded border p-3">
            <div className="mb-2 flex items-center justify-between">
              <h2 className="text-lg font-semibold">All Media</h2>
              <div className="space-x-2">
                <Button variant="secondary" onClick={() => loadAll(1)}>Load</Button>
                <Button variant="secondary" onClick={() => loadAll(page)}>Refresh</Button>
              </div>
            </div>
            <div className="mb-2 text-sm text-gray-600">Page {page} of {totalPages} ({totalItems} items)</div>
            {searchLoading ? (
              <div className="space-y-2">
                {Array.from({ length: 5 }).map((_, i) => (<CardSkeleton key={i} />))}
              </div>
            ) : allItems.length > 0 ? (
              <ul className="space-y-2">
                {allItems.map((item, idx) => (
                  <li key={idx} className="cursor-pointer rounded border p-2 hover:bg-gray-50" onClick={() => loadDetails(item.id)}>
                    <div className="flex items-center justify-between">
                      <div>
                        <div className="font-medium text-gray-800">{item.title || 'Untitled'}</div>
                        <div className="text-xs text-gray-500">{item.media_type || 'unknown'} • {item.author || 'Unknown'}</div>
                      </div>
                      <div className="text-xs text-gray-400">{item.created_at ? new Date(item.created_at).toLocaleDateString() : ''}</div>
                    </div>
                  </li>
                ))}
              </ul>
            ) : (
              <div className="text-sm text-gray-600">{searchLoading ? 'Loading…' : 'No items loaded yet.'}</div>
            )}
            <div className="mt-2 flex items-center justify-between">
              <Button variant="secondary" onClick={() => page > 1 && loadAll(page - 1)} disabled={page <= 1}>Prev</Button>
              <Button variant="secondary" onClick={() => page < totalPages && loadAll(page + 1)} disabled={page >= totalPages}>Next</Button>
            </div>
          </div>

          <details className="rounded border p-3">
            <summary className="cursor-pointer text-sm font-medium">Advanced Options (JSON)</summary>
            <div className="mt-2 space-y-2">
              <div className="text-xs text-gray-600">These keys are appended as form fields. Non-string values are JSON-stringified.</div>
              <JsonEditor value={advancedJson} onChange={setAdvancedJson} height={200} />
            </div>
          </details>

          <div className="rounded border p-3 space-y-3">
            <div className="flex items-center justify-between">
              <h2 className="text-lg font-semibold">Claims Extraction</h2>
              <span className="text-xs text-gray-500">Controls ingestion-time factual claim extraction.</span>
            </div>
            <div className="grid gap-3 sm:grid-cols-3">
              <div className="sm:col-span-1">
                <label className="mb-1 block text-sm font-medium text-gray-700">Extraction behaviour</label>
                <select
                  className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                  value={claimsExtraction}
                  onChange={(e) => setClaimsExtraction(e.target.value as ClaimsToggle)}
                >
                  <option value="inherit">Use server default</option>
                  <option value="enabled">Always extract claims</option>
                  <option value="disabled">Skip claims extraction</option>
                </select>
              </div>
              <div className="sm:col-span-1">
                <Input
                  label="Extractor mode (optional)"
                  placeholder="heuristic, ner, provider id…"
                  value={claimsExtractorMode}
                  onChange={(e) => setClaimsExtractorMode(e.target.value)}
                />
              </div>
              <div className="sm:col-span-1">
                <label className="mb-1 block text-sm font-medium text-gray-700">Max claims per chunk</label>
                <input
                  type="number"
                  min={1}
                  max={12}
                  placeholder="e.g. 3"
                  value={claimsMaxPerChunk}
                  onChange={(e) => setClaimsMaxPerChunk(e.target.value)}
                  className="block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                />
                <p className="mt-1 text-xs text-gray-500">Leave blank to use the server default.</p>
              </div>
            </div>
          </div>

          {/* Selected item details */}
          {selectedItem && (
            <div className="rounded border p-3">
              <div className="mb-2 flex items-center justify-between">
                <h2 className="text-lg font-semibold">Details: {selectedItem?.source?.title || 'Untitled'}</h2>
                <div className="space-x-2">
                  <Button onClick={summarizeSelected} loading={analyzing} disabled={analyzing}>Summarize</Button>
                  <Button variant="secondary" onClick={sendToChatSelected}>Send to Chat</Button>
                </div>
              </div>
              <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <div className="text-xs text-gray-500">Type</div>
                  <div className="text-sm">{selectedItem?.source?.type}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Author</div>
                  <div className="text-sm">{selectedItem?.source?.author || '-'}</div>
                </div>
                <div>
                  <div className="text-xs text-gray-500">Words</div>
                  <div className="text-sm">{selectedItem?.content?.word_count}</div>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-3 sm:grid-cols-3">
                <div>
                  <label className="mb-1 block text-xs text-gray-700">Analysis Model</label>
                  <div className="flex items-center space-x-2">
                    <input className="w-full rounded border p-2" value={analysisModel} onChange={(e)=>setAnalysisModel(e.target.value)} placeholder="provider/model or model" />
                    <Button variant="secondary" onClick={() => { try { const m = localStorage.getItem('tldw-current-chat-model'); if (m) setAnalysisModel(m); } catch {} }}>Use Chat model</Button>
                  </div>
                </div>
                <div className="sm:col-span-2">
                  <label className="mb-1 block text-xs text-gray-700">Prompt</label>
                  <input className="w-full rounded border p-2" value={analysisPrompt} onChange={(e)=>setAnalysisPrompt(e.target.value)} />
                </div>
              </div>
              {selectedItem?.keywords?.length > 0 && (
                <div className="mt-2 text-sm text-gray-700">Keywords: {selectedItem.keywords.join(', ')}</div>
              )}
              <div className="mt-3">
                <div className="text-xs text-gray-500">Content (preview)</div>
                <div className="whitespace-pre-wrap rounded bg-gray-50 p-2 text-sm max-h-64 overflow-auto">{selectedItem?.content?.text?.slice(0, 4000) || 'No content'}</div>
              </div>
              {analysisResult && (
                <div className="mt-3">
                  <div className="text-xs text-gray-500">Analysis</div>
                  <div className="whitespace-pre-wrap rounded bg-blue-50 p-2 text-sm">{analysisResult}</div>
                </div>
              )}
            </div>
          )}
          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Type</label>
              <select
                className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
                value={mediaType}
                onChange={(e) => setMediaType(e.target.value as MediaType)}
              >
                <option value="document">Document</option>
                <option value="pdf">PDF</option>
                <option value="video">Video</option>
                <option value="audio">Audio</option>
              </select>
            </div>
            <div className="sm:col-span-2">
              <Input label="URLs (comma or newline separated)" value={urls} onChange={(e) => setUrls(e.target.value)} />
            </div>
          </div>

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">Files</label>
            <input type="file" multiple onChange={(e) => setFiles(e.target.files)} />
          </div>

          <div>
            <Button onClick={onSubmit} loading={loading} disabled={loading}>Process</Button>
          </div>

          {error && (
            <div className="rounded bg-red-50 p-3 text-sm text-red-800">{error}</div>
          )}

          {result && (
            <div className="mt-4">
              <h2 className="mb-2 text-lg font-semibold">Result</h2>
              <pre className="max-h-96 overflow-auto rounded bg-gray-50 p-3 text-xs">{JSON.stringify(result, null, 2)}</pre>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
