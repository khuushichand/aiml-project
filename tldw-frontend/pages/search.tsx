import { useEffect, useMemo, useState } from 'react';
import { useRouter } from 'next/router';
import { Layout } from '@/components/layout/Layout';
import { Input } from '@/components/ui/Input';
import { Button } from '@/components/ui/Button';
import { apiClient } from '@/lib/api';
import { VlmBackendsCard } from '@/components/VlmBackendsCard';
import { Tabs } from '@/components/ui/Tabs';
import JsonEditor from '@/components/ui/JsonEditor';
import JsonViewer from '@/components/ui/JsonViewer';
import JsonTree from '@/components/ui/JsonTree';
import { CardSkeleton, LineSkeleton } from '@/components/ui/Skeleton';
import { useToast } from '@/components/ui/ToastProvider';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';

// eslint-disable-next-line @typescript-eslint/no-explicit-any
function buildCurl(url: string, method: string, headers: Record<string, string>, body?: any) {
  const parts: string[] = [
    `curl -X ${method.toUpperCase()} \\\n+  '${url}' \\\n+  -H 'Accept: application/json'`,
  ];
  Object.entries(headers || {}).forEach(([k, v]) => { if (v) parts.push(`  -H '${k}: ${v}'`); });
  if (body !== undefined) parts.push(`  -H 'Content-Type: application/json' \\\n+  --data '${JSON.stringify(body).replace(/'/g, "'\\''")}'`);
  return parts.join(' \\\n');
}

export default function SearchPage() {
  const { show } = useToast();
  const router = useRouter();
  const [query, setQuery] = useState('');
  const [searchType, setSearchType] = useState<'hybrid' | 'semantic' | 'fulltext'>('hybrid');
  const [limit, setLimit] = useState<number>(10);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = // eslint-disable-next-line @typescript-eslint/no-explicit-any
  useState<any>(null);
  const [providers, _setProviders] = useState<Array<{name: string; display_name?: string; models?: string[]; is_configured?: boolean}>>([]);
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
  const [sourceFeedbackEnabled, setSourceFeedbackEnabled] = useState<boolean>(false);
  const [docFeedbackById, setDocFeedbackById] = useState<Record<string, { value?: 'up' | 'down'; pending?: boolean }>>({});
  const [expandedDocs, setExpandedDocs] = useState<Record<string, boolean>>({});

  const [view, setView] = useState<'basic' | 'json' | 'response' | 'curl'>('basic');
  const [jsonBody, setJsonBody] = useState<string>('');
  const [respView, setRespView] = useState<'pretty' | 'tree'>('pretty');
  const [preset, setPreset] = useState<'fast'|'balanced'|'accurate'>('balanced');
  const [extras, setExtras] = useState<string>('{}');

  const buildDocId = (doc: Record<string, any>, fallback: string) => {
    const candidate = doc.id || doc.metadata?.doc_id || doc.metadata?.document_id || fallback;
    return candidate ? String(candidate) : '';
  };

  const buildChunkIds = (doc: Record<string, any>) => {
    const chunkIds = doc.metadata?.chunk_ids || doc.metadata?.chunkIds;
    const chunkId = doc.metadata?.chunk_id || doc.metadata?.chunkId;
    if (Array.isArray(chunkIds)) {
      return chunkIds.map((id: unknown) => String(id)).filter(Boolean);
    }
    if (chunkId) {
      return [String(chunkId)];
    }
    return [];
  };

  const buildCorpus = (doc: Record<string, any>) => {
    return doc.metadata?.corpus || doc.metadata?.source || doc.metadata?.source_name || undefined;
  };

  const sendImplicitFeedback = async (payload: Record<string, unknown>) => {
    try {
      await apiClient.post('/rag/feedback/implicit', {
        query: query || undefined,
        session_id: sessionId || undefined,
        ...payload,
      });
    } catch (err) {
      // best-effort
      if (process.env.NODE_ENV === 'development') {
        console.debug('[ImplicitFeedback] failed:', err);
      }
    }
  };

  const handleSourceFeedback = async (
    docId: string,
    helpful: boolean,
    meta: { chunkIds: string[]; corpus?: string; rank: number; impressionList: string[] }
  ) => {
    if (!docId) {
      show({ title: 'Missing document id', variant: 'warning' });
      return;
    }
    const current = docFeedbackById[docId];
    const nextValue = helpful ? 'up' : 'down';
    if (current?.pending || current?.value === nextValue) return;

    setDocFeedbackById((prev) => ({
      ...prev,
      [docId]: { value: nextValue, pending: true },
    }));

    try {
      await apiClient.post('/feedback/explicit', {
        feedback_type: 'helpful',
        helpful,
        query,
        document_ids: [docId],
        chunk_ids: meta.chunkIds.length ? meta.chunkIds : undefined,
        corpus: meta.corpus,
        session_id: sessionId || undefined,
      });
      setDocFeedbackById((prev) => ({
        ...prev,
        [docId]: { value: nextValue, pending: false },
      }));
      show({ title: 'Feedback sent', variant: 'success' });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Could not submit feedback';
      setDocFeedbackById((prev) => ({
        ...prev,
        [docId]: { value: current?.value, pending: false },
      }));
      show({ title: 'Feedback failed', description: message, variant: 'danger' });
    }
  };
  const onSearch = async () => {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      let payload: any = { query };
      // Sources
      payload.sources = Object.entries(sources).filter(([_k, v]) => v).map(([k]) => k);
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
      // JSON tab overrides
      if (view === 'json') {
        try { payload = JSON.parse(jsonBody || '{}'); } catch { show({ title: 'Invalid JSON', description: 'Fix JSON before searching', variant: 'warning' }); setLoading(false); return; }
      } else {
        // Apply simple preset tuning and merge extras
        if (preset === 'fast') { payload.enable_reranking = false; }
        if (preset === 'balanced') { payload.enable_reranking = true; payload.reranking_strategy = 'flashrank'; }
        if (preset === 'accurate') { payload.enable_reranking = true; payload.reranking_strategy = 'cross_encoder'; }
        if (payload.enable_generation) {
          payload.generation_temperature = preset === 'accurate' ? 0.2 : preset === 'fast' ? 0.8 : 0.7;
        }
        try { const extraObj = JSON.parse(extras || '{}'); if (extraObj && typeof extraObj === 'object') payload = { ...payload, ...extraObj }; } catch {}
      }
      const res = await apiClient.post('/rag/search', payload);
      setResult(res);
      setDocFeedbackById({});
      setExpandedDocs({});
      setView('response');
      show({ title: 'Search complete', variant: 'success' });

      // Update URL params to share current state
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
      const queryParams: Record<string, any> = {
        q: query,
        st: searchType,
        k: limit,
        ha: hybridAlpha,
        ms: minScore,
        src: Object.entries(sources).filter(([_k, v]) => v).map(([k]) => k).join(','),
        ex: expandQuery ? '1' : '0',
        exs: expansionStrategies,
        ce: enableCache ? '1' : '0',
        ca: adaptiveCache ? '1' : '0',
        ct: cacheThreshold,
        kw: keywordFilter,
        sec: securityFilter ? '1' : '0',
        dpi: detectPII ? '1' : '0',
        rpii: redactPII ? '1' : '0',
        sens: sensitivity,
        cf: contentFilter ? '1' : '0',
        et: enableTable ? '1' : '0',
        tm: tableMethod,
        cts: Object.entries(chunkTypes).filter(([_k,v]) => v).map(([k]) => k).join(','),
        pexp: parentExpansion ? '1' : '0',
        pctx: parentContext,
        sb: siblingChunks ? '1' : '0',
        sw: siblingWindow,
        ipd: includeParentDoc ? '1' : '0',
        pmt: parentMaxTokens,
        ecl: enableClaims ? '1' : '0',
        cle: claimExtractor,
        clv: claimVerifier,
        ctk: claimsTopK,
        cconf: claimsConf,
        cmax: claimsMax,
        nli: nliModel,
        err: enableRerank ? '1' : '0',
        rrs: rerankStrategy,
        rtk: rerankTopK || '',
        ecit: enableCitations ? '1' : '0',
        echunk: enableChunkCitations ? '1' : '0',
        ipn: includePageNumbers ? '1' : '0',
        cstyle: citationStyle,
        egen: enableGen ? '1' : '0',
        gmod: genModel,
        gpr: genPrompt,
        gmax: genMaxTokens,
        fb: collectFeedback ? '1' : '0',
        fuid: feedbackUser,
        fboost: applyFeedbackBoost ? '1' : '0',
        mon: enableMonitoring ? '1' : '0',
        obs: enableObservability ? '1' : '0',
        cost: trackCost ? '1' : '0',
        dbg: debugMode ? '1' : '0',
        perf: perfAnalysis ? '1' : '0',
        to: timeoutSeconds || '',
        res: enableResilience ? '1' : '0',
        rat: retryAttempts,
        cb: circuitBreaker ? '1' : '0',
        uid: userId,
        sid: sessionId,
      };
      router.replace({ pathname: '/search', query: queryParams }, undefined, { shallow: true });
    } catch (error: unknown) {
      const message = error instanceof Error ? error.message : 'Unknown error';
      setError(message);
      show({ title: 'Search failed', description: message, variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  // Load state from URL parameters
  useEffect(() => {
    if (!router.isReady) return;
    const qp = router.query;
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const get = (k: string, def?: any): any => (qp[k] !== undefined ? qp[k] : def);
    const getB = (k: string, def=false) => (get(k) === '1' ? true : def);
    try {
      setQuery(String(get('q', '')));
      setSearchType(get('st', 'hybrid'));
      setLimit(Number(get('k', 10)) || 10);
      setHybridAlpha(parseFloat(get('ha', 0.7)) || 0.7);
      setMinScore(parseFloat(get('ms', 0)) || 0);
      const srcStr = String(get('src', 'media_db'));
      const srcSet = new Set(srcStr.split(',').filter(Boolean));
      setSources({ media_db: srcSet.has('media_db'), notes: srcSet.has('notes'), characters: srcSet.has('characters'), chats: srcSet.has('chats') });
      setExpandQuery(getB('ex', false));
      setExpansionStrategies(String(get('exs', '')));
      setEnableCache(getB('ce', true));
      setAdaptiveCache(getB('ca', true));
      setCacheThreshold(parseFloat(get('ct', 0.85)) || 0.85);
      setKeywordFilter(String(get('kw', '')));
      setSecurityFilter(getB('sec', false));
      setDetectPII(getB('dpi', false));
      setRedactPII(getB('rpii', false));
      setSensitivity(get('sens', 'public'));
      setContentFilter(getB('cf', false));
      setEnableTable(getB('et', false));
      setTableMethod(get('tm', 'markdown'));
      const ctsStr = String(get('cts', 'text'));
      const ctsSet = new Set(ctsStr.split(',').filter(Boolean));
      setChunkTypes({ text: ctsSet.has('text'), code: ctsSet.has('code'), table: ctsSet.has('table'), list: ctsSet.has('list') });
      setParentExpansion(getB('pexp', false));
      setParentContext(Number(get('pctx', 500)) || 500);
      setSiblingChunks(getB('sb', false));
      setSiblingWindow(Number(get('sw', 1)) || 1);
      setIncludeParentDoc(getB('ipd', false));
      setParentMaxTokens(Number(get('pmt', 1200)) || 1200);
      setEnableClaims(getB('ecl', false));
      setClaimExtractor(get('cle', 'auto'));
      setClaimVerifier(get('clv', 'hybrid'));
      setClaimsTopK(Number(get('ctk', 5)) || 5);
      setClaimsConf(parseFloat(get('cconf', 0.7)) || 0.7);
      setClaimsMax(Number(get('cmax', 25)) || 25);
      setNliModel(String(get('nli', '')));
      setEnableRerank(getB('err', true));
      setRerankStrategy(get('rrs', 'flashrank'));
      const rtkVal = get('rtk', '');
      setRerankTopK(rtkVal === '' ? '' : Number(rtkVal));
      setEnableCitations(getB('ecit', false));
      setEnableChunkCitations(getB('echunk', true));
      setIncludePageNumbers(getB('ipn', false));
      setCitationStyle(get('cstyle', 'apa'));
      setEnableGen(getB('egen', false));
      setGenModel(String(get('gmod', '')));
      setGenPrompt(String(get('gpr', '')));
      setGenMaxTokens(Number(get('gmax', 500)) || 500);
      setCollectFeedback(getB('fb', false));
      setFeedbackUser(String(get('fuid', '')));
      setApplyFeedbackBoost(getB('fboost', false));
      setEnableMonitoring(getB('mon', false));
      setEnableObservability(getB('obs', false));
      setTrackCost(getB('cost', false));
      setDebugMode(getB('dbg', false));
      setPerfAnalysis(getB('perf', false));
      const toVal = get('to', '');
      setTimeoutSeconds(toVal === '' ? '' : Number(toVal));
      setEnableResilience(getB('res', false));
      setRetryAttempts(Number(get('rat', 3)) || 3);
      setCircuitBreaker(getB('cb', false));
      setUserId(String(get('uid', '')));
      setSessionId(String(get('sid', '')));
    } catch {
      // ignore parse errors
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [router.isReady]);

  // Load server presets list
  useEffect(() => {
    (async () => {
      try {
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        const resp = await apiClient.get<any>('/evaluations/rag/pipeline/presets');
        const items = Array.isArray(resp?.items) ? resp.items : [];
        // eslint-disable-next-line @typescript-eslint/no-explicit-any
        setPresets(items.map((i: any) => i.name).filter(Boolean));
      } catch {
        // ignore
      }
    })();
  }, []);

  const applyPreset = async () => {
    if (!selectedPreset) return;
    try {
      // eslint-disable-next-line @typescript-eslint/no-explicit-any
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
      show({ title: 'Preset applied', description: selectedPreset, variant: 'success' });
    } catch {
      show({ title: 'Failed to apply preset', variant: 'warning' });
    }
  };

  // Keep a JSON body snapshot up to date from current basic form
  useEffect(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const payload: any = { query };
    payload.sources = Object.entries(sources).filter(([_k, v]) => v).map(([k]) => k);
    payload.search_mode = searchType === 'semantic' ? 'vector' : searchType === 'fulltext' ? 'fts' : 'hybrid';
    payload.hybrid_alpha = hybridAlpha;
    payload.top_k = limit;
    payload.min_score = minScore;
    payload.expand_query = expandQuery;
    if (expansionStrategies.trim()) payload.expansion_strategies = expansionStrategies.split(',').map(s => s.trim()).filter(Boolean);
    payload.enable_cache = enableCache;
    payload.adaptive_cache = adaptiveCache;
    payload.cache_threshold = cacheThreshold;
    if (keywordFilter.trim()) payload.keyword_filter = keywordFilter.split(',').map(s => s.trim()).filter(Boolean);
    payload.enable_security_filter = securityFilter;
    payload.detect_pii = detectPII;
    payload.redact_pii = redactPII;
    payload.sensitivity_level = sensitivity;
    payload.content_filter = contentFilter;
    payload.enable_table_processing = enableTable;
    payload.table_method = tableMethod;
    const ct: string[] = []; Object.entries(chunkTypes).forEach(([k, v]) => { if (v) ct.push(k); }); if (ct.length) payload.chunk_type_filter = ct;
    payload.enable_parent_expansion = parentExpansion;
    payload.parent_context_size = parentContext;
    payload.include_sibling_chunks = siblingChunks;
    payload.sibling_window = siblingWindow;
    payload.include_parent_document = includeParentDoc;
    payload.parent_max_tokens = parentMaxTokens;
    payload.enable_claims = enableClaims;
    payload.claim_extractor = claimExtractor;
    payload.claim_verifier = claimVerifier;
    payload.claims_top_k = claimsTopK;
    payload.claims_conf_threshold = claimsConf;
    payload.claims_max = claimsMax;
    if (nliModel.trim()) payload.nli_model = nliModel.trim();
    payload.enable_reranking = enableRerank;
    payload.reranking_strategy = rerankStrategy;
    if (rerankTopK) payload.rerank_top_k = Number(rerankTopK);
    payload.enable_citations = enableCitations;
    payload.citation_style = citationStyle;
    payload.include_page_numbers = includePageNumbers;
    payload.enable_chunk_citations = enableChunkCitations;
    payload.enable_generation = enableGen;
    if (genModel.trim()) payload.generation_model = genModel.trim();
    if (genPrompt.trim()) payload.generation_prompt = genPrompt;
    payload.max_generation_tokens = genMaxTokens;
    payload.collect_feedback = collectFeedback;
    if (feedbackUser.trim()) payload.feedback_user_id = feedbackUser.trim();
    payload.apply_feedback_boost = applyFeedbackBoost;
    payload.enable_monitoring = enableMonitoring;
    payload.enable_observability = enableObservability;
    payload.track_cost = trackCost;
    payload.debug_mode = debugMode;
    payload.enable_performance_analysis = perfAnalysis;
    if (timeoutSeconds) payload.timeout_seconds = Number(timeoutSeconds);
    payload.enable_resilience = enableResilience;
    payload.retry_attempts = retryAttempts;
    payload.circuit_breaker = circuitBreaker;
    if (userId.trim()) payload.user_id = userId.trim();
    if (sessionId.trim()) payload.session_id = sessionId.trim();
    try { setJsonBody(JSON.stringify(payload, null, 2)); } catch {}
  }, [
    query, sources, searchType, hybridAlpha, limit, minScore, expandQuery, expansionStrategies, enableCache, adaptiveCache, cacheThreshold, keywordFilter,
    securityFilter, detectPII, redactPII, sensitivity, contentFilter, enableTable, tableMethod, chunkTypes, parentExpansion, parentContext, siblingChunks, siblingWindow, includeParentDoc, parentMaxTokens,
    enableClaims, claimExtractor, claimVerifier, claimsTopK, claimsConf, claimsMax, nliModel, enableRerank, rerankStrategy, rerankTopK, enableCitations, citationStyle, includePageNumbers, enableChunkCitations,
    enableGen, genModel, genPrompt, genMaxTokens, collectFeedback, feedbackUser, applyFeedbackBoost, enableMonitoring, enableObservability, trackCost, debugMode, perfAnalysis, timeoutSeconds, enableResilience, retryAttempts, circuitBreaker, userId, sessionId
  ]);

  const curl = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let body: any = {};
    try { body = jsonBody ? JSON.parse(jsonBody) : {}; } catch { body = {}; }
    return buildCurl('/api/v1/rag/search', 'POST', { 'Content-Type': 'application/json' }, body);
  }, [jsonBody]);

  // Mini payload diff: compare Extras JSON keys vs base JSON body
  const extrasObj = useMemo(() => {
    try { return JSON.parse(extras || '{}'); } catch { return {}; }
  }, [extras]);
  const payloadDiff = useMemo(() => {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const changes: Array<{ key: string; type: 'added'|'changed'|'unchanged'; from?: any; to?: any }> = [];
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    let base: any = {};
    try { base = jsonBody ? JSON.parse(jsonBody) : {}; } catch {}
    if (extrasObj && typeof extrasObj === 'object') {
      for (const k of Object.keys(extrasObj)) {
        const to = extrasObj[k];
        const from = base[k];
        if (typeof from === 'undefined') changes.push({ key: k, type: 'added', to });
        else if (JSON.stringify(from) !== JSON.stringify(to)) changes.push({ key: k, type: 'changed', from, to });
        else changes.push({ key: k, type: 'unchanged', from, to });
      }
    }
    return changes;
  }, [extrasObj, jsonBody]);

  // Clipboard hotkeys
  useEffect(() => {
    const key = (e: KeyboardEvent) => {
      if (!(e.metaKey || e.ctrlKey) || !e.shiftKey) return;
      if (e.key.toLowerCase() === 'c') { e.preventDefault(); try { navigator.clipboard.writeText(curl); show({ title: 'cURL copied', variant: 'success' }); } catch {} }
      if (e.key.toLowerCase() === 'j') { e.preventDefault(); try { navigator.clipboard.writeText(JSON.stringify(result, null, 2)); show({ title: 'Response copied', variant: 'success' }); } catch {} }
    };
    window.addEventListener('keydown', key);
    return () => window.removeEventListener('keydown', key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [curl, result]); // show is stable from toast hook

  const documents = result?.documents || [];
  const impressionList = documents
    .map((doc: any, idx: number) => buildDocId(doc, `doc-${idx + 1}`))
    .filter(Boolean);

  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4">
        <HotkeysOverlay
          entries={[
            { keys: 'Cmd/Ctrl+Shift+C', description: 'Copy cURL' },
            { keys: 'Cmd/Ctrl+Shift+J', description: 'Copy response JSON' },
            { keys: '?', description: 'Toggle shortcuts help' },
          ]}
        />
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Unified RAG Search</h1>
          <div className="w-1/2">
            <Tabs items={[{ key: 'basic', label: 'Basic' }, { key: 'json', label: 'JSON' }, { key: 'response', label: 'Response' }, { key: 'curl', label: 'cURL' }]} value={view} onChange={(k)=>setView(k as typeof view)} />
          </div>
        </div>
        <div className="rounded-md border bg-white p-4 transition-all duration-150">
          <div className="mb-3 grid grid-cols-1 gap-3 sm:grid-cols-6">
            <div className="sm:col-span-3">
              <Input label="Query" value={query} onChange={(e) => setQuery(e.target.value)} placeholder="Search your media..." />
            </div>
            <div>
              <label className="mb-1 block text-sm font-medium text-gray-700">Search Type</label>
              <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={searchType} onChange={(e) => setSearchType(e.target.value as typeof searchType)}>
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
              <Button onClick={onSearch} loading={loading} disabled={loading || (view === 'basic' && !query.trim())}>Search</Button>
            </div>
          </div>
          {/* Advanced Options (collapsible sections) */}
          {view === 'basic' && (
          <details className="mb-4 rounded border p-3">
            <summary className="cursor-pointer text-sm font-medium">Advanced Options</summary>
            <div className="mt-3 grid grid-cols-1 gap-3 md:grid-cols-2">
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Sources</summary>
                <div className="mt-2">
                  {(['media_db','notes','characters','chats'] as const).map((s) => (
                    <label key={s} className="mr-3 inline-flex items-center space-x-2 text-sm">
                      <input type="checkbox" checked={sources[s as keyof typeof sources]} onChange={(e) => setSources({ ...sources, [s]: e.target.checked })} />
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
                  <select className="w-full rounded border p-1" value={sensitivity} onChange={(e)=>setSensitivity(e.target.value as typeof sensitivity)}>
                    {['public','internal','confidential','restricted'].map((v)=> <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Tables</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableTable} onChange={(e)=>setEnableTable(e.target.checked)} /> <span>Enable table processing</span></label>
                  <label className="mt-2 block text-xs text-gray-700">Method</label>
                  <select className="w-full rounded border p-1" value={tableMethod} onChange={(e)=>setTableMethod(e.target.value as typeof tableMethod)}>
                    {['markdown','html','hybrid'].map((v)=> <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </details>
              <details className="rounded border p-3 md:col-span-2">
                <summary className="cursor-pointer text-sm font-semibold">Chunking & Context</summary>
                <div className="mt-2">
                  {(['text','code','table','list'] as const).map((t) => (
                    <label key={t} className="mr-3 inline-flex items-center space-x-2 text-sm">
                      <input type="checkbox" checked={chunkTypes[t as keyof typeof chunkTypes]} onChange={(e)=>setChunkTypes({ ...chunkTypes, [t]: e.target.checked })} /> <span>{t}</span>
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
                      <select className="w-full rounded border p-1" value={claimExtractor} onChange={(e)=>setClaimExtractor(e.target.value as typeof claimExtractor)}>
                        {['auto','aps','claimify'].map(v=> <option key={v} value={v}>{v}</option>)}
                      </select>
                    </div>
                    <div>
                      <div>Verifier</div>
                      <select className="w-full rounded border p-1" value={claimVerifier} onChange={(e)=>setClaimVerifier(e.target.value as typeof claimVerifier)}>
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
                  <select className="w-full rounded border p-1" value={rerankStrategy} onChange={(e)=>setRerankStrategy(e.target.value as typeof rerankStrategy)}>
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
                  <select className="w-full rounded border p-1" value={citationStyle} onChange={(e)=>setCitationStyle(e.target.value as typeof citationStyle)}>
                    {['apa','mla','chicago','harvard','ieee'].map(v=> <option key={v} value={v}>{v}</option>)}
                  </select>
                </div>
              </details>
              <details className="rounded border p-3">
                <summary className="cursor-pointer text-sm font-semibold">Answer Generation</summary>
                <div className="mt-2">
                  <label className="block text-sm"><input type="checkbox" checked={enableGen} onChange={(e)=>setEnableGen(e.target.checked)} /> <span>Enable generation</span></label>
                  <label className="mt-2 block text-xs">Model</label>
                  {/* Provider/model dropdown if available, else free text */}
                  {providers.length > 0 ? (
                    <select className="w-full rounded border p-1" value={genModel} onChange={(e)=>setGenModel(e.target.value)}>
                      <option value="">Use default</option>
                      {providers.map((p) => (
                        <optgroup key={p.name} label={`${p.display_name || p.name}${p.is_configured === false ? ' (Not Configured)' : ''}`}>
                          {(p.models || []).map((m) => (
                            <option key={`${p.name}/${m}`} value={`${p.name}/${m}`} disabled={p.is_configured === false}>{m}</option>
                          ))}
                        </optgroup>
                      ))}
                    </select>
                  ) : (
                    <input className="w-full rounded border p-1" value={genModel} onChange={(e)=>setGenModel(e.target.value)} placeholder="provider/model or model" />
                  )}
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
              <VlmBackendsCard />
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
          )}

          {view === 'basic' && (
            <details className="mb-4 rounded border p-3">
              <summary className="cursor-pointer text-sm font-semibold">Advanced Parameters</summary>
              <div className="mt-2 grid grid-cols-1 gap-3 md:grid-cols-3">
                <div>
                  <label className="mb-1 block text-sm font-medium text-gray-700">Preset</label>
                  <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={preset} onChange={(e)=>setPreset(e.target.value as typeof preset)}>
                    <option value="fast">Fast (no rerank)</option>
                    <option value="balanced">Balanced (flashrank)</option>
                    <option value="accurate">Accurate (cross_encoder)</option>
                  </select>
                </div>
                <div className="md:col-span-2">
                  <label className="mb-1 block text-sm font-medium text-gray-700">Extras (JSON)</label>
                  <JsonEditor value={extras} onChange={setExtras} height={140} />
                  {payloadDiff.length > 0 && (
                    <div className="mt-2 rounded border bg-gray-50 p-2 text-xs">
                      <div className="mb-1 font-semibold text-gray-800">Payload overrides</div>
                      <ul className="space-y-1">
                        {payloadDiff.map((d, i) => (
                          <li key={i} className="flex items-start justify-between">
                            <div className="font-mono">{d.key}</div>
                            <div className="ml-2 text-right">
                              {d.type === 'added' && <span className="text-green-700">added</span>}
                              {d.type === 'changed' && <span className="text-blue-700">changed</span>}
                              {d.type === 'unchanged' && <span className="text-gray-500">unchanged</span>}
                            </div>
                          </li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              </div>
            </details>
          )}

          {view === 'json' && (
            <div className="mt-2">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm text-gray-700">Advanced JSON</div>
                <div className="space-x-2">
                  <Button variant="secondary" onClick={() => { try { setJsonBody(JSON.stringify(JSON.parse(jsonBody), null, 2)); show({ title: 'Formatted', variant: 'success' }); } catch {} }}>Format</Button>
                  <Button variant="secondary" onClick={() => { try { navigator.clipboard.writeText(jsonBody); show({ title: 'Payload copied', variant: 'success' }); } catch {} }}>Copy</Button>
                  <Button onClick={onSearch} loading={loading} disabled={loading}>Search</Button>
                </div>
              </div>
              <JsonEditor value={jsonBody} onChange={setJsonBody} height={360} />
            </div>
          )}

          {view === 'response' && (
            <div className="mt-2">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm text-gray-700">Response</div>
                <div className="space-x-2">
                  <Button variant="secondary" onClick={() => setRespView('pretty')} disabled={respView==='pretty'}>Pretty</Button>
                  <Button variant="secondary" onClick={() => setRespView('tree')} disabled={respView==='tree'}>Tree</Button>
                  <Button variant="secondary" onClick={() => { try { navigator.clipboard.writeText(JSON.stringify(result, null, 2)); show({ title: 'Response copied', variant: 'success' }); } catch {} }}>Copy JSON</Button>
                </div>
              </div>
              <div className="rounded border bg-gray-50 p-3">
                {loading ? (
                  <div className="space-y-2">
                    <LineSkeleton width="30%" height={12} />
                    <LineSkeleton height={12} />
                    <LineSkeleton width="80%" height={12} />
                    <LineSkeleton width="65%" height={12} />
                  </div>
                ) : respView === 'pretty' ? (
                  <JsonViewer data={result} />
                ) : (
                  <JsonTree data={result} />
                )}
              </div>
            </div>
          )}

          {view === 'curl' && (
            <div className="mt-2">
              <div className="mb-2 flex items-center justify-between">
                <div className="text-sm text-gray-700">cURL</div>
                <div className="space-x-2">
                  <Button variant="secondary" onClick={() => { try { navigator.clipboard.writeText(curl); show({ title: 'cURL copied', variant: 'success' }); } catch {} }}>Copy</Button>
                </div>
              </div>
              <pre className="overflow-auto whitespace-pre break-words rounded border bg-gray-50 p-3 font-mono text-xs text-gray-800">{curl}</pre>
            </div>
          )}

          {error && <div className="rounded bg-red-50 p-3 text-sm text-red-800">{error}</div>}
          {loading && !result && (
            <div className="space-y-4">
              <div>
                <LineSkeleton width="25%" height={16} />
                <div className="mt-2 space-y-2">
                  <LineSkeleton height={12} />
                  <LineSkeleton width="85%" height={12} />
                </div>
              </div>
              <div>
                <LineSkeleton width="30%" height={16} />
                <div className="mt-2 space-y-2">
                  {Array.from({ length: 3 }).map((_, i) => (
                    <CardSkeleton key={`doc-skeleton-${i}`} />
                  ))}
                </div>
              </div>
            </div>
          )}
          {result && !loading && (
            <div className="space-y-4">
              {result.generated_answer && (
                <div>
                  <div className="mb-2 flex items-center justify-between">
                    <h2 className="text-lg font-semibold">Answer</h2>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={async () => {
                          try {
                            await navigator.clipboard.writeText(result.generated_answer || '');
                            show({ title: 'Answer copied', variant: 'success' });
                            void sendImplicitFeedback({ event_type: 'copy' });
                          } catch {
                            show({ title: 'Copy failed', variant: 'danger' });
                          }
                        }}
                      >
                        Copy
                      </Button>
                      {(result.academic_citations || []).length > 0 && (
                        <Button
                          variant="secondary"
                          size="sm"
                          onClick={async () => {
                            const citations = (result.academic_citations || []).join('\n');
                            const copyText = `${result.generated_answer}\n\nSources:\n${citations}`;
                            try {
                              await navigator.clipboard.writeText(copyText);
                              show({ title: 'Answer with citations copied', variant: 'success' });
                              void sendImplicitFeedback({ event_type: 'citation_used' });
                            } catch {
                              show({ title: 'Copy failed', variant: 'danger' });
                            }
                          }}
                        >
                          Copy with citations
                        </Button>
                      )}
                    </div>
                  </div>
                  <div className="whitespace-pre-wrap rounded bg-gray-50 p-3 text-sm">{result.generated_answer}</div>
                </div>
              )}
              <div>
                <div className="mb-2 flex items-center justify-between">
                  <h2 className="text-lg font-semibold">Documents</h2>
                  <label className="inline-flex items-center gap-2 text-xs text-gray-600">
                    <input
                      type="checkbox"
                      checked={sourceFeedbackEnabled}
                      onChange={(event) => setSourceFeedbackEnabled(event.target.checked)}
                    />
                    <span>Pro mode: source feedback</span>
                  </label>
                </div>
                <ul className="space-y-2 text-sm">
                  {/* eslint-disable-next-line @typescript-eslint/no-explicit-any */}
                  {documents.map((d: any, i: number) => {
                    const docId = buildDocId(d, `doc-${i + 1}`);
                    const docKey = docId || `doc-${i + 1}`;
                    const chunkIds = buildChunkIds(d);
                    const corpus = buildCorpus(d);
                    const feedbackState = docFeedbackById[docId] || {};
                    const pending = feedbackState.pending;
                    const upSelected = feedbackState.value === 'up';
                    const downSelected = feedbackState.value === 'down';
                    const docUrl = d.metadata?.url || d.metadata?.source_url;
                    const isExpanded = !!expandedDocs[docKey];
                    return (
                      <li key={docKey} className="rounded border p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div className="text-gray-800">
                            {d.metadata?.title || d.id || `Doc ${i + 1}`}
                            {docUrl && (
                              <a
                                className="ml-2 text-xs text-blue-600 hover:underline"
                                href={docUrl}
                                target="_blank"
                                rel="noreferrer"
                                onClick={() => {
                                  void sendImplicitFeedback({
                                    event_type: 'click',
                                    doc_id: docId || undefined,
                                    rank: i + 1,
                                    impression_list: impressionList,
                                    corpus,
                                  });
                                }}
                              >
                                Open
                              </a>
                            )}
                          </div>
                          {sourceFeedbackEnabled && (
                            <div className="flex items-center gap-2 text-xs text-gray-500">
                              <button
                                type="button"
                                className={`rounded border px-2 py-0.5 ${upSelected ? 'border-blue-400 bg-blue-50 text-blue-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100'}`}
                                disabled={pending || !docId}
                                onClick={() => handleSourceFeedback(docId, true, { chunkIds, corpus, rank: i + 1, impressionList })}
                                aria-label="Send source helpful feedback"
                              >
                                Yes
                              </button>
                              <button
                                type="button"
                                className={`rounded border px-2 py-0.5 ${downSelected ? 'border-red-400 bg-red-50 text-red-700' : 'border-gray-300 text-gray-600 hover:bg-gray-100'}`}
                                disabled={pending || !docId}
                                onClick={() => handleSourceFeedback(docId, false, { chunkIds, corpus, rank: i + 1, impressionList })}
                                aria-label="Send source not helpful feedback"
                              >
                                No
                              </button>
                            </div>
                          )}
                        </div>
                        {d.content && (
                          <div className="mt-1 text-gray-600">
                            <div className={isExpanded ? '' : 'line-clamp-3'}>{d.content}</div>
                            <button
                              type="button"
                              className="mt-1 text-xs text-blue-600 hover:underline"
                              onClick={() => {
                                const next = !isExpanded;
                                setExpandedDocs((prev) => ({ ...prev, [docKey]: next }));
                                if (next) {
                                  void sendImplicitFeedback({
                                    event_type: 'expand',
                                    doc_id: docId || undefined,
                                    rank: i + 1,
                                    impression_list: impressionList,
                                    corpus,
                                  });
                                }
                              }}
                            >
                              {isExpanded ? 'Show less' : 'Show more'}
                            </button>
                          </div>
                        )}
                        {typeof d.score !== 'undefined' && (
                          <div className="mt-1 text-xs text-gray-500">Score: {d.score}</div>
                        )}
                      </li>
                    );
                  })}
                </ul>
              </div>
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
