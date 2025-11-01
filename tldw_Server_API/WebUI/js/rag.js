// Extracted RAG tab inline scripts into this module

// ---- Global Presets (apply to Simple & Complex) ----
async function refreshGlobalRagPresets() {
  try {
    const resp = await apiClient.makeRequest('GET', '/api/v1/evaluations/rag/pipeline/presets');
    const sel = document.getElementById('ragGlobalPreset_select');
    if (!sel) return;
    sel.innerHTML = '';
    const items = (resp && resp.items) ? resp.items : [];
    items.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.name; opt.textContent = item.name;
      sel.appendChild(opt);
    });
    Toast.success(`Loaded ${items.length} presets`);
  } catch (e) {
    Toast.error('Failed to list presets: ' + (e?.message || e));
  }
}

async function applyGlobalRagPreset() {
  try {
    const sel = document.getElementById('ragGlobalPreset_select');
    const name = sel && sel.value ? sel.value : null;
    if (!name) { alert('Select a preset first'); return; }
    const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
    if (!(resp && resp.config)) { alert('Preset not found'); return; }
    const cfg = resp.config;
    // Apply to Simple controls
    if (cfg.retriever) {
      const sm = cfg.retriever.search_mode || cfg.retriever.search_type;
      if (sm) {
        const selType = document.getElementById('ragSimpleSearch_search_type');
        const norm = (sm === 'vector') ? 'semantic' : (sm === 'fts' ? 'fulltext' : 'hybrid');
        if (selType) selType.value = norm;
      }
      if (cfg.retriever.top_k !== undefined) {
        const lim = document.getElementById('ragSimpleSearch_limit');
        if (lim) lim.value = cfg.retriever.top_k;
      }
    }
    // Apply to Complex JSON
    const ta = document.getElementById('ragComplexSearch_payload');
    if (!ta) return;
    let obj = {};
    try { obj = JSON.parse(ta.value); } catch (e) { obj = {}; }
    obj.retrieval = obj.retrieval || { search_type: 'hybrid', hybrid_config: {}, vector_config: {}, fts_config: {} };
    obj.reranking = obj.reranking || { enabled: true, strategies: ['similarity'], top_k: 10 };
    if (cfg.retriever) {
      const sm = cfg.retriever.search_mode || cfg.retriever.search_type;
      if (sm) obj.retrieval.search_type = (sm === 'vector') ? 'semantic' : (sm === 'fts' ? 'fulltext' : 'hybrid');
      if (cfg.retriever.hybrid_alpha !== undefined) {
        obj.retrieval.hybrid_config = obj.retrieval.hybrid_config || {};
        obj.retrieval.hybrid_config.alpha = cfg.retriever.hybrid_alpha;
      }
      if (cfg.retriever.top_k !== undefined) {
        obj.retrieval.vector_config = obj.retrieval.vector_config || {};
        obj.retrieval.vector_config.top_k = cfg.retriever.top_k;
      }
    }
    if (cfg.reranker) {
      const strat = cfg.reranker.strategy;
      if (strat) {
        if (strat === 'flashrank') obj.reranking.strategies = ['similarity'];
        else if (strat === 'cross_encoder') obj.reranking.strategies = ['cross_encoder'];
        else obj.reranking.strategies = [String(strat)];
        // Unified keys
        obj.enable_reranking = true;
        obj.reranking_strategy = String(strat);
      }
      if (cfg.reranker.top_k !== undefined) {
        obj.reranking.top_k = cfg.reranker.top_k;
        obj.rerank_top_k = cfg.reranker.top_k;
      }
      if (cfg.reranker.model) obj.reranking.model = cfg.reranker.model;
      obj.reranking.enabled = true;
    }
    ta.value = JSON.stringify(obj, null, 2);
    Toast.success('Preset applied to both Simple & Complex forms.');
  } catch (e) {
    alert('Failed to apply preset: ' + (e?.message || e));
  }
}

// ---- RAG Selector (category/keywords/items) ----
const ragSelState = { media_ids: new Set(), note_ids: new Set() };

async function ragSelInitSources() {
  const sel = document.getElementById('ragSel_category');
  if (!sel) return;
  sel.innerHTML = '';
  const opts = [
    { value: 'notes', label: 'Notes Keywords' },
    { value: 'media', label: 'Media Keywords' }
  ];
  opts.forEach(o => { const opt = document.createElement('option'); opt.value = o.value; opt.textContent = o.label; sel.appendChild(opt); });
  ragSelToggleKeywordInput();
  Toast.success('Sources loaded');
}

function ragSelToggleKeywordInput() {
  const cat = document.getElementById('ragSel_category')?.value || 'notes';
  const sel = document.getElementById('ragSel_keywords');
  const input = document.getElementById('ragSel_keyword_text');
  if (cat === 'notes') { sel.style.display = ''; input.style.display = 'none'; }
  else { sel.style.display = 'none'; input.style.display = ''; }
}

async function ragSelLoadKeywords() {
  const cat = document.getElementById('ragSel_category')?.value || 'notes';
  if (cat !== 'notes') { ragSelToggleKeywordInput(); return; }
  try {
    const resp = await apiClient.makeRequest('GET', `/api/v1/notes/keywords/?limit=500&offset=0`);
    const sel = document.getElementById('ragSel_keywords');
    if (!sel) return;
    sel.innerHTML = '';
    (resp || []).forEach(k => {
      const opt = document.createElement('option');
      opt.value = k.id; opt.textContent = k.keyword; sel.appendChild(opt);
    });
    Toast.success(`Loaded ${ (resp||[]).length } keywords`);
  } catch (e) {
    Toast.error('Failed to load keywords: ' + (e?.message || e));
  }
}

function ragSelRenderSelected() {
  const el = document.getElementById('ragSel_selected');
  if (!el) return;
  const media = Array.from(ragSelState.media_ids);
  const notes = Array.from(ragSelState.note_ids);
  el.textContent = `Media: ${media.join(', ')}  |  Notes: ${notes.join(', ')}`;
}

function ragSelAddSelected() {
  const cont = document.getElementById('ragSel_items');
  if (!cont) return;
  const boxes = cont.querySelectorAll('input[type="checkbox"][data-source][data-id]');
  let added = 0;
  boxes.forEach(cb => {
    if (!cb.checked) return;
    const src = cb.getAttribute('data-source');
    const id = cb.getAttribute('data-id');
    if (src === 'media_db') { ragSelState.media_ids.add(parseInt(id, 10)); added++; }
    else if (src === 'notes') { ragSelState.note_ids.add(String(id)); added++; }
  });
  if (added) Toast.success(`Added ${added} item(s)`);
  ragSelRenderSelected();
}

function ragSelClear() {
  ragSelState.media_ids.clear();
  ragSelState.note_ids.clear();
  ragSelRenderSelected();
}

function ragSelApplyToComplex() {
  try {
    const ta = document.getElementById('ragComplexSearch_payload');
    if (!ta) return;
    let obj = {};
    try { obj = JSON.parse(ta.value); } catch (e) { obj = {}; }
    const media = Array.from(ragSelState.media_ids);
    const notes = Array.from(ragSelState.note_ids);
    if (media.length) obj.include_media_ids = media;
    if (notes.length) obj.include_note_ids = notes;
    ta.value = JSON.stringify(obj, null, 2);
    Toast.success('Selected items applied to payload');
  } catch (e) {
    Toast.error('Failed to apply items: ' + (e?.message || e));
  }
}

async function ragSelLoadItems2() {
  const cat = document.getElementById('ragSel_category')?.value || 'notes';
  const cont = document.getElementById('ragSel_items');
  if (!cont) return;
  cont.innerHTML = '';
  try {
    if (cat === 'notes') {
      const kid = document.getElementById('ragSel_keywords')?.value;
      if (!kid) { alert('Select a keyword'); return; }
      const resp = await apiClient.makeRequest('GET', `/api/v1/notes/keywords/${kid}/notes/?limit=50&offset=0`);
      const items = (resp?.notes || []).map(n => ({ source: 'notes', id: n.id, title: n.title }));
      items.forEach(item => {
        const div = document.createElement('div');
        div.style.marginBottom = '4px';
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.setAttribute('data-source', String(item.source));
        input.setAttribute('data-id', String(item.id));
        label.appendChild(input);
        label.appendChild(document.createTextNode(` [${String(item.source)}] ${String(item.title || item.id)}`));
        div.appendChild(label);
        cont.appendChild(div);
      });
      Toast.success(`Loaded ${items.length} notes items`);
    } else {
      const kw = (document.getElementById('ragSel_keyword_text')?.value || '').trim();
      if (!kw) { alert('Enter a keyword for media'); return; }
      const body = { query: null, fields: ["title","content"], must_have: [kw], sort_by: 'relevance' };
      const resp = await apiClient.makeRequest('POST', `/api/v1/media/search?page=1&results_per_page=50`, body);
      const items = (resp?.items || resp?.results || resp?.data || []).map(m => ({ source: 'media_db', id: m.id || m.media_id || m['id'], title: m.title || m['title'] }));
      items.forEach(item => {
        const div = document.createElement('div');
        div.style.marginBottom = '4px';
        const label = document.createElement('label');
        const input = document.createElement('input');
        input.type = 'checkbox';
        input.setAttribute('data-source', String(item.source));
        input.setAttribute('data-id', String(item.id));
        label.appendChild(input);
        label.appendChild(document.createTextNode(` [${String(item.source)}] ${String(item.title || item.id)}`));
        div.appendChild(label);
        cont.appendChild(div);
      });
      Toast.success(`Loaded ${items.length} media items for '${kw}'`);
    }
  } catch (e) {
    Toast.error('Failed to load items: ' + (e?.message || e));
  }
}

// Auto-init sources when loaded
(function(){ try { ragSelInitSources(); ragSelLoadKeywords(); } catch(e){} })();
document.getElementById('ragSel_category')?.addEventListener('change', () => { ragSelToggleKeywordInput(); ragSelLoadKeywords(); });

// ---- Simple form -> payload and send ----
function ragSimpleApplyAndSend() {
  try {
    const q = (document.getElementById('ragSimpleSearch_query')?.value || '').trim();
    if (!q) { alert('Enter a query'); return; }
    const st = (document.getElementById('ragSimpleSearch_search_type')?.value || 'hybrid');
    const limStr = (document.getElementById('ragSimpleSearch_limit')?.value || '10');
    const thrStr = (document.getElementById('ragSimpleSearch_threshold')?.value || '0');
    const corpus = (document.getElementById('ragSimpleSearch_corpus')?.value || '').trim();

    const topK = parseInt(limStr, 10);
    const minScore = parseFloat(thrStr);
    const searchMode = (st === 'semantic') ? 'vector' : ((st === 'fulltext') ? 'fts' : 'hybrid');

    const payload = {
      query: q,
      search_mode: searchMode,
      ...(topK > 0 ? { top_k: topK } : {}),
      ...(minScore >= 0 && minScore <= 1 ? { min_score: minScore } : {}),
      ...(corpus ? { corpus, index_namespace: corpus } : {})
    };
    // Unified reranking (simple controls)
    try {
      const en = !!document.getElementById('ragSimple_enableRerank')?.checked;
      const strat = (document.getElementById('ragSimple_rerankStrategy')?.value || '').trim();
      const rtkStr = (document.getElementById('ragSimple_rerankTopK')?.value || '').trim();
      payload.enable_reranking = en;
      if (strat) payload.reranking_strategy = strat;
      if (rtkStr) payload.rerank_top_k = parseInt(rtkStr, 10);
    } catch (_) {}

    // VLM late-chunking (simple controls)
    try {
      const en = !!document.getElementById('ragSimple_enableVlmLC')?.checked;
      const backend = (document.getElementById('ragSimple_vlmBackend')?.value || '').trim();
      const tablesOnly = !!document.getElementById('ragSimple_vlmDetectTablesOnly')?.checked;
      const maxPagesStr = (document.getElementById('ragSimple_vlmMaxPages')?.value || '').trim();
      payload.enable_vlm_late_chunking = en;
      if (backend) payload.vlm_backend = backend;
      payload.vlm_detect_tables_only = tablesOnly;
      if (maxPagesStr) payload.vlm_max_pages = parseInt(maxPagesStr, 10);
    } catch (_) {}
    const hidden = document.getElementById('ragSimpleSearch_payload');
    if (hidden) hidden.value = JSON.stringify(payload, null, 2);
    makeRequest('ragSimpleSearch', 'POST', '/api/v1/rag/search', 'json');
  } catch (e) {
    Toast.error('Failed to build request: ' + (e?.message || e));
  }
}

// ---- Streaming Preview (NDJSON) ----
let ragStreamAbort = null;
let ragStreamActive = false;
function _ragAuthHeaders(hdr = {}) {
  try {
    if (!apiClient || !apiClient.token) return hdr;
    if (apiClient.authMode === 'single-user' || apiClient.preferApiKeyInMultiUser) hdr['X-API-KEY'] = apiClient.token;
    else hdr['Authorization'] = `Bearer ${apiClient.token}`;
  } catch (e) {}
  return hdr;
}

async function startRagStreaming() {
  try {
    if (ragStreamActive) return;
    const btnStart = document.getElementById('ragStream_start');
    const btnStop = document.getElementById('ragStream_stop');
    const preC = document.getElementById('ragStream_contexts');
    const preW = document.getElementById('ragStream_why');
    const preA = document.getElementById('ragStream_answer');
    // Auto-clear panes if enabled
    const autoClear = !!document.getElementById('ragStream_autoClear')?.checked;
    if (autoClear) {
      if (preC) preC.textContent = '(waiting...)';
      if (preW) preW.textContent = '(waiting...)';
      if (preA) preA.textContent = '(waiting...)';
    }
    if (btnStart) btnStart.disabled = true; if (btnStop) btnStop.disabled = false;
    ragStreamActive = true;

    // Build payload from Simple controls
    const q = (document.getElementById('ragSimpleSearch_query')?.value || '').trim();
    const st = (document.getElementById('ragSimpleSearch_search_type')?.value || 'hybrid');
    const limStr = (document.getElementById('ragSimpleSearch_limit')?.value || '10');
    const topK = parseInt(limStr, 10);
    const searchMode = (st === 'semantic') ? 'vector' : ((st === 'fulltext') ? 'fts' : 'hybrid');
    const payload = { query: q, search_mode: searchMode, top_k: isNaN(topK) ? 10 : topK, enable_generation: true, enable_claims: false };

    const ctrl = new AbortController();
    ragStreamAbort = ctrl;
    const url = `${apiClient.baseUrl}/api/v1/rag/search/stream`;
    const headers = _ragAuthHeaders({ 'Content-Type': 'application/json', 'Accept': 'application/x-ndjson' });
    const resp = await fetch(url, { method: 'POST', headers, body: JSON.stringify(payload), signal: ctrl.signal });
    if (!resp.ok || !resp.body) { throw new Error(`HTTP ${resp.status}`); }
    const reader = resp.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    let ans = '';
    const _update = (evt) => {
      try {
        if (evt.type === 'contexts') {
          const list = Array.isArray(evt.contexts) ? evt.contexts : [];
          if (preC) preC.textContent = JSON.stringify(list, null, 2);
          if (evt.why && preW) preW.textContent = JSON.stringify(evt.why, null, 2);
        } else if (evt.type === 'reasoning') {
          const cur = preW?.textContent?.trim();
          const plan = { plan: evt.plan || [] };
          if (preW) preW.textContent = (cur === '(waiting...)' || !cur) ? JSON.stringify(plan, null, 2)
            : (cur + '\n' + JSON.stringify(plan, null, 2));
        } else if (evt.type === 'delta') {
          const t = (evt.delta || evt.text || '');
          if (t) ans += String(t);
          if (preA) preA.textContent = ans;
        } else if (evt.type === 'final') {
          if (preA) preA.textContent = (preA.textContent || '') + '\n[complete]';
        } else if (evt.type === 'claims_overlay') {
          const cur = preW?.textContent || '';
          const overlay = { claims_overlay: evt.spans || evt.claims || evt.overlay || evt.data || [] };
          if (preW) preW.textContent = cur + '\n' + JSON.stringify(overlay, null, 2);
        } else if (evt.type === 'final_claims') {
          const cur = preW?.textContent || '';
          const out = { final_claims: evt.claims || evt.data || [] };
          if (preW) preW.textContent = cur + '\n' + JSON.stringify(out, null, 2);
        }
      } catch (_) {}
    };
    while (ragStreamActive) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';
      for (const line of lines) {
        const trimmed = (line || '').trim();
        if (!trimmed) continue;
        try { const evt = JSON.parse(trimmed); _update(evt); } catch (_) {}
      }
    }
  } catch (e) {
    console.warn('stream error', e?.message || e);
  } finally {
    ragStreamActive = false;
    const btnStart = document.getElementById('ragStream_start');
    const btnStop = document.getElementById('ragStream_stop');
    if (btnStart) btnStart.disabled = false; if (btnStop) btnStop.disabled = true;
  }
}

function stopRagStreaming() {
  try { if (ragStreamAbort) ragStreamAbort.abort(); } catch (e) {}
  ragStreamActive = false;
  const btnStart = document.getElementById('ragStream_start');
  const btnStop = document.getElementById('ragStream_stop');
  if (btnStart) btnStart.disabled = false; if (btnStop) btnStop.disabled = true;
}

// ---- Streaming panel clear ----
function clearRagStreamingPanels() {
  try {
    const preC = document.getElementById('ragStream_contexts');
    const preW = document.getElementById('ragStream_why');
    const preA = document.getElementById('ragStream_answer');
    if (preC) preC.textContent = '(none)';
    if (preW) preW.textContent = '(none)';
    if (preA) preA.textContent = '(none)';
  } catch (_) {}
}

// ---- Complex helpers ----
function ragApplyCorpusToPayload() {
  try {
    const input = document.getElementById('ragComplexSearch_corpus');
    const name = (input?.value || '').trim();
    const ta = document.getElementById('ragComplexSearch_payload');
    if (!ta) return;
    let obj = {};
    try { obj = JSON.parse(ta.value); } catch (e) { obj = {}; }
    if (name) { obj.corpus = name; obj.index_namespace = name; }
    else { delete obj.corpus; delete obj.index_namespace; }
    ta.value = JSON.stringify(obj, null, 2);
    Toast.success('Corpus applied to payload');
  } catch (e) {
    Toast.error('Failed to apply corpus: ' + (e?.message || e));
  }
}

async function refreshRagServerPresets() {
  try {
    const resp = await apiClient.makeRequest('GET', '/api/v1/evaluations/rag/pipeline/presets');
    const sel = document.getElementById('ragServerPreset_select');
    if (!sel) return;
    sel.innerHTML = '';
    const items = (resp && resp.items) ? resp.items : [];
    items.forEach(item => {
      const opt = document.createElement('option');
      opt.value = item.name; opt.textContent = item.name; sel.appendChild(opt);
    });
    Toast.success(`Loaded ${items.length} presets`);
  } catch (e) {
    alert('Failed to list presets: ' + (e?.message || e));
  }
}

async function applyRagServerPreset() {
  try {
    const sel = document.getElementById('ragServerPreset_select');
    const name = sel && sel.value ? sel.value : null;
    if (!name) { alert('Select a preset first'); return; }
    const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
    if (!(resp && resp.config)) { alert('Preset not found'); return; }
    const cfg = resp.config;
    const ta = document.getElementById('ragComplexSearch_payload');
    if (!ta) return;
    let obj = {};
    try { obj = JSON.parse(ta.value); } catch (e) { obj = {}; }
    obj.retrieval = obj.retrieval || { search_type: 'hybrid', hybrid_config: {}, vector_config: {}, fts_config: {} };
    obj.reranking = obj.reranking || { enabled: true, strategies: ['similarity'], top_k: 10 };
    if (cfg.retriever) {
      const sm = cfg.retriever.search_mode || cfg.retriever.search_type;
      if (sm) obj.retrieval.search_type = (sm === 'vector') ? 'semantic' : (sm === 'fts' ? 'fulltext' : 'hybrid');
      if (cfg.retriever.hybrid_alpha !== undefined) {
        obj.retrieval.hybrid_config = obj.retrieval.hybrid_config || {};
        obj.retrieval.hybrid_config.alpha = cfg.retriever.hybrid_alpha;
      }
      if (cfg.retriever.top_k !== undefined) {
        obj.retrieval.vector_config = obj.retrieval.vector_config || {};
        obj.retrieval.vector_config.top_k = cfg.retriever.top_k;
      }
    }
    if (cfg.reranker) {
      const strat = cfg.reranker.strategy;
      if (strat) {
        if (strat === 'flashrank') obj.reranking.strategies = ['similarity'];
        else if (strat === 'cross_encoder') obj.reranking.strategies = ['cross_encoder'];
        else obj.reranking.strategies = [String(strat)];
        obj.enable_reranking = true;
        obj.reranking_strategy = String(strat);
      }
      if (cfg.reranker.top_k !== undefined) {
        obj.reranking.top_k = cfg.reranker.top_k;
        obj.rerank_top_k = cfg.reranker.top_k;
      }
      if (cfg.reranker.model) obj.reranking.model = cfg.reranker.model;
      obj.reranking.enabled = true;
    }
    ta.value = JSON.stringify(obj, null, 2);
    Toast.success('Preset applied to RAG search payload.');
  } catch (e) {
    alert('Failed to apply server preset: ' + (e?.message || e));
  }
}

// ---- Simple presets and sync to complex ----
async function refreshSimpleRagPresets() {
  try {
    const resp = await apiClient.makeRequest('GET', '/api/v1/evaluations/rag/pipeline/presets');
    const sel = document.getElementById('ragSimplePreset_select');
    if (!sel) return;
    sel.innerHTML = '';
    const items = (resp && resp.items) ? resp.items : [];
    items.forEach(item => { const opt = document.createElement('option'); opt.value = item.name; opt.textContent = item.name; sel.appendChild(opt); });
    Toast.success(`Loaded ${items.length} presets`);
  } catch (e) { alert('Failed to list presets: ' + (e?.message || e)); }
}

async function applySimpleRagPreset() {
  try {
    const sel = document.getElementById('ragSimplePreset_select');
    const name = sel && sel.value ? sel.value : null;
    if (!name) { alert('Select a preset first'); return; }
    const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
    if (!(resp && resp.config)) { alert('Preset not found'); return; }
    const cfg = resp.config;
    if (cfg.retriever) {
      const sm = cfg.retriever.search_mode || cfg.retriever.search_type;
      if (sm) {
        const selType = document.getElementById('ragSimpleSearch_search_type');
        const norm = (sm === 'vector') ? 'semantic' : (sm === 'fts' ? 'fulltext' : 'hybrid');
        if (selType) selType.value = norm;
      }
      if (cfg.retriever.top_k !== undefined) {
        const lim = document.getElementById('ragSimpleSearch_limit');
        if (lim) lim.value = cfg.retriever.top_k;
      }
    }
    Toast.success('Preset applied to simple search controls.');
  } catch (e) { alert('Failed to apply preset: ' + (e?.message || e)); }
}

function updateComplexFromSimple() {
  try {
    const ta = document.getElementById('ragComplexSearch_payload');
    if (!ta) return;
    let obj = {};
    try { obj = JSON.parse(ta.value); } catch (e) { obj = {}; }
    obj.retrieval = obj.retrieval || { search_type: 'hybrid', hybrid_config: {}, vector_config: {}, fts_config: {} };
    const st = (document.getElementById('ragSimpleSearch_search_type')?.value || 'hybrid');
    obj.retrieval.search_type = (st === 'semantic') ? 'semantic' : (st === 'fulltext' ? 'fulltext' : 'hybrid');
    const limStr = (document.getElementById('ragSimpleSearch_limit')?.value || '10');
    const lim = parseInt(limStr, 10);
    if (!isNaN(lim) && lim > 0) {
      obj.retrieval.vector_config = obj.retrieval.vector_config || {};
      obj.retrieval.vector_config.top_k = lim;
    }
    const thresholdStr = (document.getElementById('ragSimpleSearch_threshold')?.value || '0');
    const thr = parseFloat(thresholdStr);
    if (!isNaN(thr) && thr >= 0 && thr <= 1) obj.retrieval.min_score = thr;
    ta.value = JSON.stringify(obj, null, 2);
  } catch (e) { console.warn('Failed to sync complex form:', e?.message || e); }
}

(function attachSimpleSyncListeners() {
  try {
    const st = document.getElementById('ragSimpleSearch_search_type');
    const lm = document.getElementById('ragSimpleSearch_limit');
    const th = document.getElementById('ragSimpleSearch_threshold');
    st?.addEventListener('change', updateComplexFromSimple);
    lm?.addEventListener('change', updateComplexFromSimple);
    th?.addEventListener('change', updateComplexFromSimple);
  } catch (_) {}
})();

// ---- Result list observers and explain renderers ----
function sendImplicitRagFeedback(eventType, docId, rank, impression, query, corpus) {
  (async () => {
    try {
      const payload = { event_type: eventType, doc_id: docId, rank, impression_list: impression, query: query || null, corpus: corpus || null };
      await apiClient.makeRequest('POST', '/api/v1/rag/feedback/implicit', payload);
    } catch (e) { console.warn('implicit feedback failed', e?.message || e); }
  })();
}

function buildResultList(containerId, responsePreId, corpusInputId) {
  const cont = document.getElementById(containerId);
  const pre = document.getElementById(responsePreId);
  const corpusInput = document.getElementById(corpusInputId);
  if (!cont || !pre) return;
  const render = () => {
    let data = null;
    try { data = JSON.parse(pre.textContent || ''); } catch (e) { cont.innerHTML = ''; return; }
    const docs = Array.isArray(data?.documents) ? data.documents : [];
    const query = data?.query || '';
    const corpus = (corpusInput && corpusInput.value) ? corpusInput.value.trim() : (data?.metadata?.index_namespace || data?.index_namespace || null);
    if (!docs.length) { cont.innerHTML = ''; return; }
    const impression = docs.map((d) => d.id);
    const container = document.createElement('div');
    container.className = 'card-list';
    docs.slice(0, 10).forEach((d, i) => {
      const card = document.createElement('div'); card.className = 'card';
      const header = document.createElement('div'); header.className = 'card-header'; header.style.cursor = 'pointer';
      header.textContent = `[${i+1}] ${d.id}  (score=${(d.score||0).toFixed(3)})`;
      const body = document.createElement('div'); body.className = 'card-body'; body.style.display = 'none';
      const content = document.createElement('pre'); content.textContent = (d.content || '').slice(0, 1200);
      const copyBtn = document.createElement('button'); copyBtn.className = 'btn btn-sm'; copyBtn.textContent = 'Copy snippet';
      copyBtn.addEventListener('click', async (ev) => { ev.stopPropagation(); const ok = await Utils.copyToClipboard(d.content || ''); if (ok) Toast.success('Copied snippet'); else Toast.error('Copy failed'); sendImplicitRagFeedback('copy', d.id, i+1, impression, query, corpus); });
      body.appendChild(content); body.appendChild(copyBtn);
      header.addEventListener('click', () => { const show = body.style.display === 'none'; body.style.display = show ? 'block' : 'none'; sendImplicitRagFeedback('expand', d.id, i+1, impression, query, corpus); });
      card.appendChild(header); card.appendChild(body);
      card.addEventListener('click', () => { sendImplicitRagFeedback('click', d.id, i+1, impression, query, corpus); });
      container.appendChild(card);
    });
    cont.innerHTML = '';
    cont.appendChild(container);
  };
  const observer = new MutationObserver(render);
  observer.observe(pre, { characterData: true, childList: true, subtree: true });
}

(function() {
  buildResultList('ragSimpleSearch_resultList', 'ragSimpleSearch_response', 'ragSimpleSearch_corpus');
  buildResultList('ragComplexSearch_resultList', 'ragComplexSearch_response', 'ragComplexSearch_corpus');
  // Bind buttons (remove inline handlers)
  const byId = (id) => document.getElementById(id);
  byId('btnRagGlobalRefresh')?.addEventListener('click', refreshGlobalRagPresets);
  byId('btnRagGlobalApply')?.addEventListener('click', applyGlobalRagPreset);
  byId('btnRagSelInit')?.addEventListener('click', ragSelInitSources);
  byId('btnRagSelLoadKeywords')?.addEventListener('click', ragSelLoadKeywords);
  byId('btnRagSelLoadItems')?.addEventListener('click', ragSelLoadItems2);
  byId('btnRagSelAddSelected')?.addEventListener('click', ragSelAddSelected);
  byId('btnRagSelApplyToComplex')?.addEventListener('click', ragSelApplyToComplex);
  byId('btnRagSelClear')?.addEventListener('click', ragSelClear);
  byId('btnRagSimpleSend')?.addEventListener('click', ragSimpleApplyAndSend);
  // Simple rerank controls: persist and apply
  const _srs = () => {
    try {
      const en = !!document.getElementById('ragSimple_enableRerank')?.checked;
      const strat = (document.getElementById('ragSimple_rerankStrategy')?.value || '').trim();
      const topk = (document.getElementById('ragSimple_rerankTopK')?.value || '').trim();
      const prefs = { en, strat, topk };
      try { Utils.saveToStorage('rag-simple-rerank', prefs); } catch (_) {}
    } catch (_) {}
  };
  byId('ragSimple_enableRerank')?.addEventListener('change', _srs);
  byId('ragSimple_rerankStrategy')?.addEventListener('change', _srs);
  byId('ragSimple_rerankTopK')?.addEventListener('input', _srs);
  // Simple VLM loader
  byId('btnRagSimpleVlmLoadFromCaps')?.addEventListener('click', ragLoadVlmControlsFromCapabilities);
  byId('btnRagSimpleRefreshPresets')?.addEventListener('click', refreshSimpleRagPresets);
  byId('btnRagSimpleApplyPreset')?.addEventListener('click', applySimpleRagPreset);
  byId('btnRagSimpleShowExplain')?.addEventListener('click', ragSimpleShowExplain);
  byId('ragStream_start')?.addEventListener('click', startRagStreaming);
  byId('ragStream_stop')?.addEventListener('click', stopRagStreaming);
  byId('ragStream_clear')?.addEventListener('click', clearRagStreamingPanels);
  byId('ragStream_copyWhy')?.addEventListener('click', async () => {
    try { const pre = document.getElementById('ragStream_why'); const t = pre?.textContent || ''; const ok = await Utils.copyToClipboard(t); if (ok) Toast.success('Copied Why'); else Toast.error('Copy failed'); } catch (_) {}
  });
  byId('ragStream_copyAnswer')?.addEventListener('click', async () => {
    try { const pre = document.getElementById('ragStream_answer'); const t = pre?.textContent || ''; const ok = await Utils.copyToClipboard(t); if (ok) Toast.success('Copied Answer'); else Toast.error('Copy failed'); } catch (_) {}
  });
  byId('ragStream_autoClear')?.addEventListener('change', (e) => {
    try { const prefs = Utils.getFromStorage('rag-stream-prefs') || {}; prefs.autoClear = !!e.target.checked; Utils.saveToStorage('rag-stream-prefs', prefs); } catch (_) {}
  });
  // Load autoClear pref
  try { const prefs = Utils.getFromStorage('rag-stream-prefs'); if (prefs && typeof prefs.autoClear === 'boolean') { const cb = document.getElementById('ragStream_autoClear'); if (cb) cb.checked = !!prefs.autoClear; } } catch (_) {}
  byId('btnRagApplyCorpus')?.addEventListener('click', ragApplyCorpusToPayload);
  byId('btnRagServerRefresh')?.addEventListener('click', refreshRagServerPresets);
  byId('btnRagServerApply')?.addEventListener('click', applyRagServerPreset);
  byId('btnRagComplexShowExplain')?.addEventListener('click', ragComplexShowExplain);
  byId('btnRagEmbRefreshPresets')?.addEventListener('click', ragEmbRefreshPresets);
  byId('btnRagEmbLoadPreset')?.addEventListener('click', ragEmbLoadPreset);
  byId('btnRagFetchVlmBackends')?.addEventListener('click', ragFetchVlmBackends);
  // Unified reranking controls
  const _rs = () => ragComplexApplyRerankingFromControls();
  byId('ragComplex_enableRerank')?.addEventListener('change', _rs);
  byId('ragComplex_rerankStrategy')?.addEventListener('change', _rs);
  byId('ragComplex_rerankTopK')?.addEventListener('input', _rs);
  byId('ragComplex_rerankMinProb')?.addEventListener('input', _rs);
  byId('ragComplex_rerankSentinelMargin')?.addEventListener('input', _rs);
  // VLM Late-chunking controls
  const _vlm = () => ragComplexApplyVlmControls();
  byId('ragComplex_enableVlmLC')?.addEventListener('change', _vlm);
  byId('ragComplex_vlmBackend')?.addEventListener('change', _vlm);
  byId('ragComplex_vlmDetectTablesOnly')?.addEventListener('change', _vlm);
  byId('ragComplex_vlmMaxPages')?.addEventListener('input', _vlm);
  byId('btnRagVlmLoadFromCaps')?.addEventListener('click', ragLoadVlmControlsFromCapabilities);
  // Load persisted rerank controls (simple & complex)
  try {
    const s = Utils.getFromStorage('rag-simple-rerank');
    if (s) {
      const en = document.getElementById('ragSimple_enableRerank'); if (en) en.checked = !!s.en;
      const st = document.getElementById('ragSimple_rerankStrategy'); if (st && s.strat) st.value = s.strat;
      const tk = document.getElementById('ragSimple_rerankTopK'); if (tk && s.topk) tk.value = s.topk;
    }
  } catch (_) {}
  try {
    const c = Utils.getFromStorage('rag-complex-rerank');
    if (c) {
      const en = document.getElementById('ragComplex_enableRerank'); if (en) en.checked = !!c.en;
      const st = document.getElementById('ragComplex_rerankStrategy'); if (st && c.strat) st.value = c.strat;
      const tk = document.getElementById('ragComplex_rerankTopK'); if (tk && c.topk) tk.value = c.topk;
      const mp = document.getElementById('ragComplex_rerankMinProb'); if (mp && c.minProb) mp.value = c.minProb;
      const sm = document.getElementById('ragComplex_rerankSentinelMargin'); if (sm && c.sentinel) sm.value = c.sentinel;
      ragComplexApplyRerankingFromControls();
    }
  } catch (_) {}
  byId('btnRagGotoEmbeddings')?.addEventListener('click', () => {
    try {
      const target = document.querySelector('[data-toptab="embeddings"]');
      if (window.webUI && typeof webUI.activateTopTab === 'function' && target) webUI.activateTopTab(target);
    } catch (_) {}
  });
  // Delegate api-button with data-req-* to legacy makeRequest
  document.getElementById('tabRAGSearch')?.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-req-section]');
    if (!btn) return;
    const section = btn.getAttribute('data-req-section');
    const method = btn.getAttribute('data-req-method') || 'GET';
    const path = btn.getAttribute('data-req-path') || '/';
    const bodyType = btn.getAttribute('data-req-body-type') || 'none';
    if (typeof window.makeRequest === 'function') {
      ev.preventDefault();
      window.makeRequest(section, method, path, bodyType);
    }
  });
})();

function _renderExplainFromPre(preId, mountId) {
  try {
    const pre = document.getElementById(preId);
    const mount = document.getElementById(mountId);
    if (!pre || !mount) return;
    let data = null;
    try { data = JSON.parse(pre.textContent || ''); } catch (e) { data = null; }
    if (!data || !data.metadata) { mount.textContent = 'No metadata available.'; return; }
    const md = data.metadata;
    if (typeof window.renderAgenticExplainPanel === 'function') window.renderAgenticExplainPanel(md, mount);
    else mount.textContent = 'Explain renderer not available.';
  } catch (e) { console.error('Explain render failed', e); }
}
function ragSimpleShowExplain() { _renderExplainFromPre('ragSimpleSearch_response', 'ragSimpleSearch_explainPanel'); }
function ragComplexShowExplain() { _renderExplainFromPre('ragComplexSearch_response', 'ragComplexSearch_explainPanel'); }

// ---- Embeddings preset viewers ----
async function ragEmbRefreshPresets() {
  try {
    const resp = await apiClient.makeRequest('GET', '/api/v1/evaluations/rag/pipeline/presets');
    const sel = document.getElementById('ragEmbPreset_select');
    if (!sel) return; sel.innerHTML = '';
    const items = (resp && resp.items) ? resp.items : [];
    items.forEach(item => { const opt = document.createElement('option'); opt.value = item.name; opt.textContent = item.name; sel.appendChild(opt); });
    Toast.success(`Loaded ${items.length} presets`);
  } catch (e) { Toast.error('Failed to list presets: ' + (e?.message || e)); }
}
async function ragEmbLoadPreset() {
  try {
    const sel = document.getElementById('ragEmbPreset_select'); const name = sel && sel.value ? sel.value : null;
    if (!name) { alert('Select a preset first'); return; }
    const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
    const pre = document.getElementById('ragEmbPreset_view');
    if (resp && resp.config) { pre.textContent = JSON.stringify(resp.config, null, 2); Toast.success('Preset loaded'); }
    else { pre.textContent = '(not found)'; }
  } catch (e) { Toast.error('Failed to load preset: ' + (e?.message || e)); }
}

// ---- VLM backends discovery ----
async function ragFetchVlmBackends() {
  try {
    const epSpan = document.getElementById('ragVlmBackends_ep');
    const listEl = document.getElementById('ragVlmBackends_list');
    const pre = document.getElementById('ragVlmBackends_json');
    if (listEl) listEl.innerHTML = 'Loading...';
    if (pre) pre.textContent = '(loading)';

    const caps = await apiClient.makeRequest('GET', '/api/v1/rag/capabilities');
    const discovered = caps?.features?.vlm_late_chunking?.backends_endpoint || '/api/v1/rag/vlm/backends';
    if (epSpan) epSpan.textContent = `Endpoint: ${discovered}`;

    const data = await apiClient.makeRequest('GET', discovered);
    if (pre) pre.textContent = JSON.stringify(data, null, 2);
    const backends = data?.backends || {};
    const items = Object.entries(backends).map(([name, val]) => {
      const available = typeof val === 'object' && val !== null ? !!val.available : !!val;
      return { name, available };
    }).sort((a,b)=> a.name.localeCompare(b.name));
    if (listEl) {
      if (!items.length) { listEl.textContent = 'No VLM backends reported.'; }
      else {
        const ul = document.createElement('ul');
        items.forEach(it => {
          const li = document.createElement('li');
          li.textContent = `${it.name}: ${it.available ? 'Available' : 'Unavailable'}`;
          li.style.color = it.available ? '#065f46' : '#6b7280';
          ul.appendChild(li);
        });
        listEl.innerHTML = '';
        listEl.appendChild(ul);
      }
    }
  } catch (e) {
    const listEl = document.getElementById('ragVlmBackends_list');
    const pre = document.getElementById('ragVlmBackends_json');
    if (listEl) listEl.textContent = `Error: ${e?.message || e}`;
    if (pre) pre.textContent = `Error: ${e?.message || e}`;
  }
}

// ---- VLM controls helpers ----
async function ragLoadVlmControlsFromCapabilities() {
  try {
    const caps = await apiClient.makeRequest('GET', '/api/v1/rag/capabilities');
    const defaults = caps?.features?.vlm_late_chunking?.defaults || {};
    const backendsStatic = caps?.features?.vlm_late_chunking?.backends || [];
    let choices = Array.isArray(backendsStatic) ? backendsStatic.slice() : [];
    try {
      const be = await apiClient.makeRequest('GET', '/api/v1/rag/vlm/backends');
      const names = Object.keys(be?.backends || {});
      if (names.length) choices = names;
    } catch (_) {}
    const complexSel = document.getElementById('ragComplex_vlmBackend');
    if (complexSel) {
      const prev = complexSel.value;
      complexSel.innerHTML = '<option value="">(auto)</option>';
      choices.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n; opt.textContent = n; complexSel.appendChild(opt);
      });
      if (prev && choices.includes(prev)) complexSel.value = prev;
    }
    const simpleSel = document.getElementById('ragSimple_vlmBackend');
    if (simpleSel) {
      const prevS = simpleSel.value;
      simpleSel.innerHTML = '<option value="">(auto)</option>';
      choices.forEach(n => {
        const opt = document.createElement('option');
        opt.value = n; opt.textContent = n; simpleSel.appendChild(opt);
      });
      if (prevS && choices.includes(prevS)) simpleSel.value = prevS;
    }
    const en = document.getElementById('ragComplex_enableVlmLC');
    const det = document.getElementById('ragComplex_vlmDetectTablesOnly');
    const mp = document.getElementById('ragComplex_vlmMaxPages');
    if (typeof defaults.enable_vlm_late_chunking === 'boolean' && en) en.checked = !!defaults.enable_vlm_late_chunking;
    if (typeof defaults.vlm_detect_tables_only === 'boolean' && det) det.checked = !!defaults.vlm_detect_tables_only;
    if (defaults.vlm_max_pages && mp) mp.value = String(defaults.vlm_max_pages);
    ragComplexApplyVlmControls();
  } catch (e) {
    Toast.error('Failed to load VLM defaults: ' + (e?.message || e));
  }
}

function ragComplexApplyVlmControls() {
  try {
    const ta = document.getElementById('ragComplexSearch_payload'); if (!ta) return;
    let obj = {}; try { obj = JSON.parse(ta.value || '{}'); } catch (_) { obj = {}; }
    const en = !!document.getElementById('ragComplex_enableVlmLC')?.checked;
    const backend = (document.getElementById('ragComplex_vlmBackend')?.value || '').trim();
    const tablesOnly = !!document.getElementById('ragComplex_vlmDetectTablesOnly')?.checked;
    const maxPagesStr = (document.getElementById('ragComplex_vlmMaxPages')?.value || '').trim();
    obj.enable_vlm_late_chunking = en;
    if (backend) obj.vlm_backend = backend; else delete obj.vlm_backend;
    obj.vlm_detect_tables_only = tablesOnly;
    if (maxPagesStr) obj.vlm_max_pages = parseInt(maxPagesStr, 10); else delete obj.vlm_max_pages;
    ta.value = JSON.stringify(obj, null, 2);
  } catch (e) { console.warn('Failed to apply VLM controls:', e?.message || e); }
}

// ---- Unified reranking controls -> JSON payload ----
function ragComplexApplyRerankingFromControls() {
  try {
    const ta = document.getElementById('ragComplexSearch_payload');
    if (!ta) return;
    let obj = {};
    try { obj = JSON.parse(ta.value || '{}'); } catch (_) { obj = {}; }
    const en = !!document.getElementById('ragComplex_enableRerank')?.checked;
    const strat = (document.getElementById('ragComplex_rerankStrategy')?.value || '').trim();
    const topkStr = (document.getElementById('ragComplex_rerankTopK')?.value || '').trim();
    const minProbStr = (document.getElementById('ragComplex_rerankMinProb')?.value || '').trim();
    const sentMarStr = (document.getElementById('ragComplex_rerankSentinelMargin')?.value || '').trim();

    obj.enable_reranking = en;
    if (strat) obj.reranking_strategy = strat; else delete obj.reranking_strategy;
    if (topkStr) obj.rerank_top_k = parseInt(topkStr, 10); else delete obj.rerank_top_k;

    // Two-tier extras
    const twoTierRow = document.getElementById('ragComplex_twoTierRow');
    if (twoTierRow) twoTierRow.style.display = (strat === 'two_tier') ? '' : 'none';
    if (strat === 'two_tier') {
      if (minProbStr) obj.rerank_min_relevance_prob = parseFloat(minProbStr);
      else delete obj.rerank_min_relevance_prob;
      if (sentMarStr) obj.rerank_sentinel_margin = parseFloat(sentMarStr);
      else delete obj.rerank_sentinel_margin;
    } else {
      delete obj.rerank_min_relevance_prob;
      delete obj.rerank_sentinel_margin;
    }

    // Maintain legacy mirroring for back-compat
    obj.reranking = obj.reranking || { enabled: en, strategies: [], top_k: obj.rerank_top_k || 10 };
    obj.reranking.enabled = en;
    if (strat) {
      if (strat === 'flashrank') obj.reranking.strategies = ['similarity'];
      else if (strat === 'cross_encoder') obj.reranking.strategies = ['cross_encoder'];
      else obj.reranking.strategies = [strat];
    }
    if (obj.rerank_top_k) obj.reranking.top_k = obj.rerank_top_k;

    ta.value = JSON.stringify(obj, null, 2);
    // Persist selections
    try {
      const prefs = {
        en,
        strat,
        topk: topkStr,
        minProb: minProbStr,
        sentinel: sentMarStr,
      };
      Utils.saveToStorage('rag-complex-rerank', prefs);
    } catch (_) {}
  } catch (e) {
    console.warn('Failed to apply reranking controls:', e?.message || e);
  }
}

// Test-friendly export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    refreshGlobalRagPresets,
    applyGlobalRagPreset,
    ragSelInitSources,
    ragSelLoadKeywords,
    ragSelAddSelected,
    ragSimpleApplyAndSend,
    startRagStreaming,
    stopRagStreaming,
    refreshRagServerPresets,
    applyRagServerPreset,
    updateComplexFromSimple,
    buildResultList,
    ragFetchVlmBackends,
    ragComplexApplyRerankingFromControls,
    ragLoadVlmControlsFromCapabilities,
    ragComplexApplyVlmControls,
  };
}
