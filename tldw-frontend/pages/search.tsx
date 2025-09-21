import { useEffect, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/lib/api';

export default function SearchPage() {
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic' | 'fulltext'>('hybrid');
  const [limit, setLimit] = useState<number>(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<any>(null);
  const [presets, setPresets] = useState<string[]>([]);
  const [selectedPreset, setSelectedPreset] = useState<string>('');
  // Advanced options (subset covering all categories)
  const [sources, setSources] = useState<{media_db: boolean; notes: boolean; characters: boolean; chats: boolean}>({ media_db: true, notes: false, characters: false, chats: false });
  const [hybridAlpha, setHybridAlpha] = useState<number>(0.7);
  const [minScore, setMinScore] = useState<number>(0);
  const [expandQuery, setExpandQuery] = useState<boolean>(false);
  const [expansionStrategies, setExpansionStrategies] = useState<string>(''); // comma-separated
  const [enableCache, setEnableCache] = useState<boolean>(true);
  const [adaptiveCache, setAdaptiveCache] = useState<boolean>(true);
  const [cacheThreshold, setCacheThreshold] = useState<number>(0.85);
  const [keywordFilter, setKeywordFilter] = useState<string>('');
  const [securityFilter, setSecurityFilter] = useState<boolean>(false);
  const [detectPII, setDetectPII] = useState<boolean>(false);
  const [redactPII, setRedactPII] = useState<boolean>(false);
  const [sensitivity, setSensitivity] = useState<'public' | 'internal' | 'confidential' | 'restricted'>('public');
  const [contentFilter, setContentFilter] = useState<boolean>(false);
  const [enableTable, setEnableTable] = useState<boolean>(false);
  const [tableMethod, setTableMethod] = useState<'markdown' | 'html' | 'hybrid'>('markdown');
  const [chunkTypes, setChunkTypes] = useState<{text: boolean; code: boolean; table: boolean; list: boolean}>({ text: true, code: false, table: false, list: false });
  const [parentExpansion, setParentExpansion] = useState<boolean>(false);
  const [parentContext, setParentContext] = useState<number>(500);
  const [siblingChunks, setSiblingChunks] = useState<boolean>(false);
  const [siblingWindow, setSiblingWindow] = useState<number>(1);
  const [includeParentDoc, setIncludeParentDoc] = useState<boolean>(false);
  const [parentMaxTokens, setParentMaxTokens] = useState<number>(1200);
  const [enableClaims, setEnableClaims] = useState<boolean>(false);
  const [claimExtractor, setClaimExtractor] = useState<'aps' | 'claimify' | 'auto'>('auto');
  const [claimVerifier, setClaimVerifier] = useState<'nli' | 'llm' | 'hybrid'>('hybrid');
  const [claimsTopK, setClaimsTopK] = useState<number>(5);
  const [claimsConf, setClaimsConf] = useState<number>(0.7);
  const [claimsMax, setClaimsMax] = useState<number>(25);
  const [nliModel, setNliModel] = useState<string>('');
  const [enableRerank, setEnableRerank] = useState<boolean>(true);
  const [rerankStrategy, setRerankStrategy] = useState<'flashrank' | 'cross_encoder' | 'hybrid' | 'none'>('flashrank');
  const [rerankTopK, setRerankTopK] = useState<number | ''>('');
  const [enableCitations, setEnableCitations] = useState<boolean>(false);
  const [citationStyle, setCitationStyle] = useState<'apa' | 'mla' | 'chicago' | 'harvard' | 'ieee'>('apa');
  const [includePageNumbers, setIncludePageNumbers] = useState<boolean>(false);
  const [enableChunkCitations, setEnableChunkCitations] = useState<boolean>(true);
  const [enableGen, setEnableGen] = useState<boolean>(false);
  const [genModel, setGenModel] = useState<string>('');
  const [genPrompt, setGenPrompt] = useState<string>('');
  const [genMaxTokens, setGenMaxTokens] = useState<number>(500);
  const [collectFeedback, setCollectFeedback] = useState<boolean>(false);
  const [feedbackUser, setFeedbackUser] = useState<string>('');
  const [applyFeedbackBoost, setApplyFeedbackBoost] = useState<boolean>(false);
  const [enableMonitoring, setEnableMonitoring] = useState<boolean>(false);
  const [enableObservability, setEnableObservability] = useState<boolean>(false);
  const [trackCost, setTrackCost] = useState<boolean>(false);
  const [debugMode, setDebugMode] = useState<boolean>(false);
  const [perfAnalysis, setPerfAnalysis] = useState<boolean>(false);
  const [timeoutSeconds, setTimeoutSeconds] = useState<number | ''>('');
  const [enableResilience, setEnableResilience] = useState<boolean>(false);
  const [retryAttempts, setRetryAttempts] = useState<number>(3);
  const [circuitBreaker, setCircuitBreaker] = useState<boolean>(false);
  const [userId, setUserId] = useState<string>('');
  const [sessionId, setSessionId] = useState<string>('');

  const onSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const payload: any = { query };
      // Sources
      payload.sources = Object.entries(sources).filter(([k, v]) => v).map(([k]) => k);
      // Search config
      payload.search_mode = searchType === 'semantic' ? 'vector' : searchType === 'fulltext' ? 'fts' : 'hybrid';
      payload.hybrid_alpha = hybridAlpha;
      payload.top_k = limit;
      payload.min_score = minScore;
      // Expansion & caching
      payload.expand_query = expandQuery;
      if (expansionStrategies.trim()) payload.expansion_strategies = expansionStrategies.split(',').map(s => s.trim()).filter(Boolean);
      payload.enable_cache = enableCache;
      payload.adaptive_cache = adaptiveCache;
      payload.cache_threshold = cacheThreshold;
      // Filtering
      if (keywordFilter.trim()) payload.keyword_filter = keywordFilter.split(',').map(s => s.trim()).filter(Boolean);
      // Security
      payload.enable_security_filter = securityFilter;
      payload.detect_pii = detectPII;
      payload.redact_pii = redactPII;
      payload.sensitivity_level = sensitivity;
      payload.content_filter = contentFilter;
      // Document processing
      payload.enable_table_processing = enableTable;
      payload.table_method = tableMethod;
      // Chunking & context
      const ct: string[] = [];
      Object.entries(chunkTypes).forEach(([k, v]) => { if (v) ct.push(k); });
      if (ct.length) payload.chunk_type_filter = ct;
      payload.enable_parent_expansion = parentExpansion;
      payload.parent_context_size = parentContext;
      payload.include_sibling_chunks = siblingChunks;
      payload.sibling_window = siblingWindow;
      payload.include_parent_document = includeParentDoc;
      payload.parent_max_tokens = parentMaxTokens;
      // Claims & factuality
      payload.enable_claims = enableClaims;
      payload.claim_extractor = claimExtractor;
      payload.claim_verifier = claimVerifier;
      payload.claims_top_k = claimsTopK;
      payload.claims_conf_threshold = claimsConf;
      payload.claims_max = claimsMax;
      if (nliModel.trim()) payload.nli_model = nliModel.trim();
      // Reranking
      payload.enable_reranking = enableRerank;
      payload.reranking_strategy = rerankStrategy;
      if (rerankTopK) payload.rerank_top_k = Number(rerankTopK);
      // Citations
      payload.enable_citations = enableCitations;
      payload.citation_style = citationStyle;
      payload.include_page_numbers = includePageNumbers;
      payload.enable_chunk_citations = enableChunkCitations;
      // Generation
      payload.enable_generation = enableGen;
      if (genModel.trim()) payload.generation_model = genModel.trim();
      if (genPrompt.trim()) payload.generation_prompt = genPrompt;
      payload.max_generation_tokens = genMaxTokens;
      // Feedback
      payload.collect_feedback = collectFeedback;
      if (feedbackUser.trim()) payload.feedback_user_id = feedbackUser.trim();
      payload.apply_feedback_boost = applyFeedbackBoost;
      // Monitoring & performance
      payload.enable_monitoring = enableMonitoring;
      payload.enable_observability = enableObservability;
      payload.track_cost = trackCost;
      payload.debug_mode = debugMode;
      payload.enable_performance_analysis = perfAnalysis;
      if (timeoutSeconds) payload.timeout_seconds = Number(timeoutSeconds);
      // Resilience
      payload.enable_resilience = enableResilience;
      payload.retry_attempts = retryAttempts;
      payload.circuit_breaker = circuitBreaker;
      // User context
      if (userId.trim()) payload.user_id = userId.trim();
      if (sessionId.trim()) payload.session_id = sessionId.trim();
      const res = await apiClient.post('/rag/search', payload);
      setResult(res);
    } catch (e: any) {
      setError(e.message || 'Search failed');
    } finally {
      setLoading(false);
    }
  };

  // Load server presets list
  useEffect(() => {
    (async () => {
      try {
        const resp = await apiClient.get<any>('/evaluations/rag/pipeline/presets');
        const items = Array.isArray(resp?.items) ? resp.items : [];
        setPresets(items.map((i: any) => i.name).filter(Boolean));
      } catch (e) {
        // ignore
      }
    })();
  }, []);

  const applyPreset = async () => {
    if (!selectedPreset) return;
    try {
      const resp = await apiClient.get<any>(`/evaluations/rag/pipeline/presets/${encodeURIComponent(selectedPreset)}`);
      const cfg = resp?.config || {};
      const retr = cfg.retriever || {};
      const mode = retr.search_mode || retr.search_type;
      if (mode) {
        setSearchType(mode === 'vector' ? 'semantic' : mode === 'fts' ? 'fulltext' : 'hybrid');
      }
      if (typeof retr.top_k === 'number') {
        setLimit(retr.top_k);
      }
    } catch (e) {
      // ignore
    }
  };

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4">
        <h1 className="text-2xl font-bold text-gray-900">Unified RAG Search</h1>
        <div className="rounded-md border bg-white p-4">
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-6">
            <div className="sm:col-span-3">
              <Input label="Query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your media..." />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Search Type</label>
              <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={searchType} onChange={(e) => setSearchType(e.target.value as any)}>
                <option value="hybrid">Hybrid</option>
                <option value="semantic">Semantic</option>
                <option value="fulltext">Full Text</option>
              </select>
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Top K</label>
              <input type="number" min={1} max={50} className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={limit} onChange={(e) => setLimit(parseInt(e.target.value || '10', 10))} />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Preset</label>
              <div className="flex items-center space-x-2">
                <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={selectedPreset} onChange={(e) => setSelectedPreset(e.target.value)}>
                  <option value="">-- none --</option>
                  {presets.map((p) => (
                    <option key={p} value={p}>{p}</option>
                  ))}
                </select>
                <Button variant="secondary" onClick={applyPreset}>Apply</Button>
              </div>
            </div>
            <div className="flex items-end">
              <Button onClick={onSearch} loading={loading} disabled={loading || !query.trim()}>Search</Button>
            </div>
          </div>
          {/* Advanced Options (collapsible sections) */}
          <details className="mb-4 rounded border p-3">
            <summary className="cursor-pointer text-sm font-medium">Advanced Options</summary>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Sources</summary>
                <div className="mt-2">
                  {(['media_db','notes','characters','chats'] as const).map((s) => (
                    <label key={s} className="mr-3 inline-flex items-center space-x-2 text-sm">
                      <input type="checkbox" checked={(sources as any)[s]} onChange={(e) => setSources({ ...sources, [s]: e.target.checked })} />
                      <span>{s}</span>
                    </label>
                  ))}
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Search</summary>
                <div className="mt-2">
                  <label className="block text-xs text-gray-700">Hybrid alpha</label>
                  <input type="number" min={0} max={1} step={0.05} className="w-full rounded border p-1" value={hybridAlpha} onChange={(e) => setHybridAlpha(parseFloat(e.target.value || '0.7'))} />
                  <label className="mt-2 block text-xs text-gray-700">Min score</label>
                  <input type="number" min={0} max={1} step={0.01} className="w-full rounded border p-1" value={minScore} onChange={(e) => setMinScore(parseFloat(e.target.value || '0'))} />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Expansion</summary>
                <div className="mt-2">
                  <label className="inline-flex items-center space-x-2 text-sm"><input type="checkbox" checked={expandQuery} onChange={(e)=>setExpandQuery(e.target.checked)} /><span>Enable expansion</span></label>
                  <label className="mt-2 block text-xs text-gray-700">Strategies (comma)</label>
                  <input className="w-full rounded border p-1" value={expansionStrategies} onChange={(e)=>setExpansionStrategies(e.target.value)} placeholder="acronym,synonym,domain,entity" />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Caching</summary>
                <div className="mt-2">
                  <label className="block text-xs text-gray-700">Threshold</label>
                  <input type="number" min={0} max={1} step={0.01} className="w-full rounded border p-1" value={cacheThreshold} onChange={(e)=>setCacheThreshold(parseFloat(e.target.value||'0.85'))} />
                  <div className="mt-2 space-x-4 text-sm">
                    <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={enableCache} onChange={e=>setEnableCache(e.target.checked)} /><span>Enable</span></label>
                    <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={adaptiveCache} onChange={e=>setAdaptiveCache(e.target.checked)} /><span>Adaptive</span></label>
                  </div>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Filtering</summary>
                <div className="mt-2">
                  <label className="block text-xs text-gray-700">Keywords (comma)</label>
                  <input className="w-full rounded border p-1" value={keywordFilter} onChange={(e)=>setKeywordFilter(e.target.value)} />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Security</summary>
                <div className="mt-2">
                  {[
                    {label:'Security filter', val:securityFilter,set:setSecurityFilter},
                    {label:'Detect PII', val:detectPII,set:setDetectPII},
                    {label:'Redact PII', val:redactPII,set:setRedactPII},
                    {label:'Content filter', val:contentFilter,set:setContentFilter},
                  ].map((x,i)=>(
                    <label key={i} className="block text-sm"><input type="checkbox" checked={x.val} onChange={(e)=>x.set(e.target.checked)} /> <span>{x.label}</span></label>
                  ))}
                  <label className="mt-2 block text-xs text-gray-700">Sensitivity</label>
                  <select className="w-full rounded border p-1" value={sensitivity} onChange={(e)=>setSensitivity(e.target.value as any)}>
                    {['public','internal','confidential','restricted'].map((v)=> <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Tables</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableTable} onChange={(e)=>setEnableTable(e.target.checked)} /> <span>Enable table processing</span></label>
                  <label className="mt-2 block text-xs text-gray-700">Method</label>
                  <select className="w-full rounded border p-1" value={tableMethod} onChange={(e)=>setTableMethod(e.target.value as any)}>
                    {['markdown','html','hybrid'].map((v)=> <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </details>
              <details className="rounded border p-3 md:col-span-2">
                <summary className="cursor-pointer text-sm font-semibold">Chunking & Context</summary>
                <div className="mt-2">
                  {(['text','code','table','list'] as const).map((t) => (
                    <label key={t} className="mr-3 inline-flex items-center space-x-2 text-sm">
                      <input type="checkbox" checked={(chunkTypes as any)[t]} onChange={(e)=>setChunkTypes({ ...chunkTypes, [t]: e.target.checked })} /> <span>{t}</span>
                    </label>
                  ))}
                  <div className="mt-2 space-y-2 text-sm">
                    <label className="block"><input type="checkbox" checked={parentExpansion} onChange={(e)=>setParentExpansion(e.target.checked)} /> <span>Enable parent expansion</span></label>
                    <label className="block"><input type="checkbox" checked={siblingChunks} onChange={(e)=>setSiblingChunks(e.target.checked)} /> <span>Include sibling chunks</span></label>
                    <label className="block"><input type="checkbox" checked={includeParentDoc} onChange={(e)=>setIncludeParentDoc(e.target.checked)} /> <span>Include parent doc</span></label>
                  </div>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div><div>Parent ctx</div><input type="number" className="w-full rounded border p-1" value={parentContext} onChange={(e)=>setParentContext(parseInt(e.target.value||'500',10))} /></div>
                    <div><div>Sibling win</div><input type="number" className="w-full rounded border p-1" value={siblingWindow} onChange={(e)=>setSiblingWindow(parseInt(e.target.value||'1',10))} /></div>
                    <div><div>Parent max tok</div><input type="number" className="w-full rounded border p-1" value={parentMaxTokens} onChange={(e)=>setParentMaxTokens(parseInt(e.target.value||'1200',10))} /></div>
                  </div>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Claims & Factuality</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableClaims} onChange={(e)=>setEnableClaims(e.target.checked)} /> <span>Enable claims</span></label>
                  <div className="mt-2 grid grid-cols-3 gap-2 text-xs">
                    <div>
                      <div>Extractor</div>
                      <select className="w-full rounded border p-1" value={claimExtractor} onChange={(e)=>setClaimExtractor(e.target.value as any)}>
                        {['auto','aps','claimify'].map(v=> <option key={v} value={v}>{v}</option>)}
                      </select>
                    </div>
                    <div>
                      <div>Verifier</div>
                      <select className="w-full rounded border p-1" value={claimVerifier} onChange={(e)=>setClaimVerifier(e.target.value as any)}>
                        {['hybrid','nli','llm'].map(v=> <option key={v} value={v}>{v}</option>)}
                      </select>
                    </div>
                    <div>
                      <div>Top K</div>
                      <input type="number" className="w-full rounded border p-1" value={claimsTopK} onChange={(e)=>setClaimsTopK(parseInt(e.target.value||'5',10))} />
                    </div>
                  </div>
                  <div className="mt-2 grid grid-cols-2 gap-2 text-xs">
                    <div><div>Conf thresh</div><input type="number" min={0} max={1} step={0.01} className="w-full rounded border p-1" value={claimsConf} onChange={(e)=>setClaimsConf(parseFloat(e.target.value||'0.7'))} /></div>
                    <div><div>Max claims</div><input type="number" className="w-full rounded border p-1" value={claimsMax} onChange={(e)=>setClaimsMax(parseInt(e.target.value||'25',10))} /></div>
                  </div>
                  <label className="mt-2 block text-xs text-gray-700">NLI model</label>
                  <input className="w-full rounded border p-1" value={nliModel} onChange={(e)=>setNliModel(e.target.value)} placeholder="roberta-large-mnli" />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Reranking</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableRerank} onChange={(e)=>setEnableRerank(e.target.checked)} /> <span>Enable reranking</span></label>
                  <label className="mt-2 block text-xs">Strategy</label>
                  <select className="w-full rounded border p-1" value={rerankStrategy} onChange={(e)=>setRerankStrategy(e.target.value as any)}>
                    {['flashrank','cross_encoder','hybrid','none'].map(v=> <option key={v} value={v}>{v}</option>)}
                  </select>
                  <label className="mt-2 block text-xs">Rerank top K</label>
                  <input type="number" className="w-full rounded border p-1" value={rerankTopK} onChange={(e)=>setRerankTopK(e.target.value ? parseInt(e.target.value,10): '')} />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Citations</summary>
                <div className="mt-2">
                  {([
                    {label:'Enable citations',val:enableCitations,set:setEnableCitations},
                    {label:'Chunk citations',val:enableChunkCitations,set:setEnableChunkCitations},
                    {label:'Include page numbers',val:includePageNumbers,set:setIncludePageNumbers},
                  ]).map((x,i)=>(
                    <label key={i} className="block text-sm"><input type="checkbox" checked={x.val} onChange={(e)=>x.set(e.target.checked)} /> <span>{x.label}</span></label>
                  ))}
                  <label className="mt-2 block text-xs">Style</label>
                  <select className="w-full rounded border p-1" value={citationStyle} onChange={(e)=>setCitationStyle(e.target.value as any)}>
                    {['apa','mla','chicago','harvard','ieee'].map(v=> <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Answer Generation</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableGen} onChange={(e)=>setEnableGen(e.target.checked)} /> <span>Enable generation</span></label>
                  <label className="mt-2 block text-xs">Model</label>
                  <input className="w-full rounded border p-1" value={genModel} onChange={(e)=>setGenModel(e.target.value)} placeholder="provider/model or model" />
                  <label className="mt-2 block text-xs">Prompt</label>
                  <textarea className="w-full rounded border p-1" rows={3} value={genPrompt} onChange={(e)=>setGenPrompt(e.target.value)} placeholder="Optional custom prompt" />
                  <label className="mt-2 block text-xs">Max tokens</label>
                  <input type="number" className="w-full rounded border p-1" value={genMaxTokens} onChange={(e)=>setGenMaxTokens(parseInt(e.target.value||'500',10))} />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Feedback</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={collectFeedback} onChange={(e)=>setCollectFeedback(e.target.checked)} /> <span>Collect feedback</span></label>
                  <label className="mt-2 block text-xs">User ID</label>
                  <input className="w-full rounded border p-1" value={feedbackUser} onChange={(e)=>setFeedbackUser(e.target.value)} />
                  <label className="mt-2 block text-sm"><input type="checkbox" checked={applyFeedbackBoost} onChange={(e)=>setApplyFeedbackBoost(e.target.checked)} /> <span>Apply boost</span></label>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Monitoring & Performance</summary>
                <div className="mt-2">
                  {([
                    {label:'Enable monitoring',val:enableMonitoring,set:setEnableMonitoring},
                    {label:'Observability',val:enableObservability,set:setEnableObservability},
                    {label:'Track cost',val:trackCost,set:setTrackCost},
                    {label:'Debug mode',val:debugMode,set:setDebugMode},
                    {label:'Perf analysis',val:perfAnalysis,set:setPerfAnalysis},
                  ]).map((x,i)=>(
                    <label key={i} className="block text-sm"><input type="checkbox" checked={x.val} onChange={(e)=>x.set(e.target.checked)} /> <span>{x.label}</span></label>
                  ))}
                  <label className="mt-2 block text-xs">Timeout (s)</label>
                  <input type="number" min={1} max={60} step={1} className="w-full rounded border p-1" value={timeoutSeconds} onChange={(e)=>setTimeoutSeconds(e.target.value ? parseInt(e.target.value,10) : '')} />
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Resilience</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableResilience} onChange={(e)=>setEnableResilience(e.target.checked)} /> <span>Enable resilience</span></label>
                  <label className="mt-2 block text-xs">Retry attempts</label>
                  <input type="number" min={1} max={5} className="w-full rounded border p-1" value={retryAttempts} onChange={(e)=>setRetryAttempts(parseInt(e.target.value||'3',10))} />
                  <label className="mt-2 block text-sm"><input type="checkbox" checked={circuitBreaker} onChange={(e)=>setCircuitBreaker(e.target.checked)} /> <span>Circuit breaker</span></label>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">User Context</summary>
                <div className="mt-2">
                  <label className="block text-xs">User ID</label>
                  <input className="w-full rounded border p-1" value={userId} onChange={(e)=>setUserId(e.target.value)} />
                  <label className="mt-2 block text-xs">Session ID</label>
                  <input className="w-full rounded border p-1" value={sessionId} onChange={(e)=>setSessionId(e.target.value)} />
                </div>
              </details>
            </div>
          </details>
          {error && <div className="rounded bg-red-50 p-3 text-sm text-red-800">{error}</div>}
          {result && (
            <div className="space-y-4">
              {result.generated_answer && (
                <div>
                  <h2 className="text-lg font-semibold">Answer</h2>
                  <div className="whitespace-pre-wrap rounded bg-gray-50 p-3 text-sm">{result.generated_answer}</div>
                </div>
              )}
              <div>
                <h2 className="text-lg font-semibold">Documents</h2>
                <ul className="space-y-2 text-sm">
                  {(result.documents || []).map((d: any, i: number) => (
                    <li key={i} className="rounded border p-3">
                      <div className="text-gray-800">{d.metadata?.title || d.id || `Doc ${i+1}`}</div>
                      {d.content && <div className="mt-1 line-clamp-3 text-gray-600">{d.content}</div>}
                      {typeof d.score !== 'undefined' && (
                        <div className="mt-1 text-xs text-gray-500">Score: {d.score}</div>
                      )}
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
