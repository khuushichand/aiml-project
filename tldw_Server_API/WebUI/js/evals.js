// Evaluations tab module (migrated from inline scripts)
// Exposes functions on window for existing onclick bindings.

(function(){
  'use strict';

  function updateEvalsCreateJSON() {
    try {
      const modelSelect = document.getElementById('evalsCreate_model');
      const payloadTextarea = document.getElementById('evalsCreate_payload');
      if (!modelSelect || !payloadTextarea) return;
      const payload = JSON.parse(payloadTextarea.value || '{}');
      if (modelSelect.value) {
        const modelName = modelSelect.value.split('/').pop();
        payload.config = payload.config || {};
        payload.config.model = modelName;
        payloadTextarea.value = JSON.stringify(payload, null, 2);
      }
    } catch (e) {
      console.error('Error updating evaluation JSON:', e);
    }
  }

  function updateGEvalJSON() {
    try {
      const modelSelect = document.getElementById('geval_model');
      const payloadTextarea = document.getElementById('geval_payload');
      if (!modelSelect || !payloadTextarea) return;
      const payload = JSON.parse(payloadTextarea.value || '{}');
      if (modelSelect.value) {
        const modelName = modelSelect.value.split('/').pop();
        payload.model = modelName;
        payloadTextarea.value = JSON.stringify(payload, null, 2);
      }
    } catch (e) {
      console.error('Error updating G-Eval JSON:', e);
    }
  }

  // RAG eval preset helpers
  async function ragEvalRefreshPresets() {
    try {
      const resp = await apiClient.makeRequest('GET', '/api/v1/evaluations/rag/pipeline/presets');
      const sel = document.getElementById('ragEvalPreset_select');
      if (!sel) return;
      sel.innerHTML = '';
      const items = (resp && resp.items) ? resp.items : [];
      items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.name;
        opt.textContent = item.name;
        sel.appendChild(opt);
      });
      if (typeof Toast !== 'undefined') Toast.success(`Loaded ${items.length} presets`);
    } catch (e) {
      if (typeof Toast !== 'undefined') Toast.error('Failed to list presets: ' + (e?.message || e));
    }
  }

  async function ragEvalApplyPresetTemplate() {
    try {
      const sel = document.getElementById('ragEvalPreset_select');
      const name = sel && sel.value ? sel.value : null;
      if (!name) { alert('Select a preset first'); return; }
      const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
      if (!(resp && resp.config)) { alert('Preset not found'); return; }
      const cfg = resp.config;
      let apiName = 'openai';
      try {
        const model = (cfg.rag && (Array.isArray(cfg.rag.model) ? cfg.rag.model[0] : cfg.rag.model)) || '';
        const m = String(model).toLowerCase();
        if (m.includes('claude')) apiName = 'anthropic';
        else if (m.includes('groq')) apiName = 'groq';
        else if (m.includes('gemini') || m.includes('google')) apiName = 'google';
        else if (m.includes('mistral')) apiName = 'mistral';
        else apiName = 'openai';
      } catch (_) { apiName = 'openai'; }
      const tmpl = {
        query: 'Your question here',
        retrieved_contexts: ['Paste or fetch retrieved contexts here'],
        generated_response: 'Your model response here',
        ground_truth: 'Optional gold answer',
        metrics: ['relevance', 'faithfulness', 'answer_similarity', 'context_precision'],
        api_name: apiName
      };
      const ta = document.getElementById('ragEval_payload');
      if (ta) ta.value = JSON.stringify(tmpl, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Inserted test template from preset. Fill contexts/response and run.');
    } catch (e) {
      alert('Failed to apply preset to RAG Eval: ' + (e?.message || e));
    }
  }

  // rag_pipeline helpers
  function extractBestConfigFromRun() {
    try {
      const pre = document.getElementById('ragPipelineRun_response');
      const text = pre ? pre.textContent.trim() : '';
      const obj = JSON.parse(text);
      const best = obj && (obj.best_config || (obj.results && obj.results.best_config));
      if (!best) { alert('best_config not found in response'); return; }
      const cfg = best.config || best;
      const box = document.getElementById('ragPipelinePreset_json');
      if (box) box.value = JSON.stringify(cfg, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Best config extracted.');
    } catch (_) {
      alert('Could not parse run response as JSON. Try copying best_config manually.');
    }
  }

  function saveRagPipelinePreset() {
    const name = (document.getElementById('ragPipelinePreset_name')?.value || 'rag_pipeline_best').trim();
    const text = document.getElementById('ragPipelinePreset_json')?.value || '';
    try {
      const cfg = JSON.parse(text);
      localStorage.setItem('ragPipelinePreset_' + name, JSON.stringify(cfg));
      if (typeof Toast !== 'undefined') Toast.success('Preset saved as ' + name);
    } catch (e) {
      alert('Invalid JSON for preset: ' + e.message);
    }
  }

  function applyPresetToCreatePayload() {
    const name = (document.getElementById('ragPipelinePreset_name')?.value || 'rag_pipeline_best').trim();
    const presetRaw = localStorage.getItem('ragPipelinePreset_' + name);
    if (!presetRaw) { alert('Preset not found: ' + name); return; }
    try {
      const preset = JSON.parse(presetRaw);
      const ta = document.getElementById('ragPipelineCreate_payload');
      if (!ta) return;
      const obj = JSON.parse(ta.value || '{}');
      const rp = (((obj || {}).eval_spec || {}).rag_pipeline || {});
      rp.chunking = preset.chunking || rp.chunking;
      rp.retrievers = preset.retriever ? [preset.retriever] : (rp.retrievers || []);
      rp.rerankers = preset.reranker ? [preset.reranker] : (rp.rerankers || []);
      rp.rag = preset.rag || rp.rag;
      obj.eval_spec = obj.eval_spec || {};
      obj.eval_spec.rag_pipeline = rp;
      ta.value = JSON.stringify(obj, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Preset applied to create payload.');
    } catch (e) {
      alert('Failed to apply preset: ' + e.message);
    }
  }

  async function savePresetToServer() {
    try {
      const name = (document.getElementById('ragPipelinePreset_name')?.value || 'rag_pipeline_best').trim();
      const text = document.getElementById('ragPipelinePreset_json')?.value || '';
      const cfg = JSON.parse(text || '{}');
      const body = { name, config: cfg };
      const resp = await apiClient.makeRequest('POST', '/api/v1/evaluations/rag/pipeline/presets', { body });
      if (resp && resp.name) {
        if (typeof Toast !== 'undefined') Toast.success('Preset saved on server: ' + resp.name);
      } else {
        if (typeof Toast !== 'undefined') Toast.error('Server did not confirm preset save.');
      }
    } catch (e) {
      alert('Failed to save preset to server: ' + (e?.message || e));
    }
  }

  async function loadPresetFromServer() {
    try {
      const name = (document.getElementById('ragPipelinePreset_name')?.value || 'rag_pipeline_best').trim();
      const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
      if (!(resp && resp.config)) { alert('Preset not found on server'); return; }
      const box = document.getElementById('ragPipelinePreset_json');
      if (box) box.value = JSON.stringify(resp.config, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Preset loaded from server.');
    } catch (e) {
      alert('Failed to load preset from server: ' + (e?.message || e));
    }
  }

  async function refreshServerPresets() {
    try {
      const resp = await apiClient.makeRequest('GET', '/api/v1/evaluations/rag/pipeline/presets');
      const sel = document.getElementById('ragPipelinePreset_select');
      if (!sel) return;
      sel.innerHTML = '';
      const items = (resp && resp.items) ? resp.items : [];
      items.forEach(item => {
        const opt = document.createElement('option');
        opt.value = item.name;
        opt.textContent = item.name;
        sel.appendChild(opt);
      });
    } catch (e) {
      if (typeof Toast !== 'undefined') Toast.error('Failed to list presets: ' + (e?.message || e));
    }
  }

  async function applySelectedServerPreset() {
    try {
      const sel = document.getElementById('ragPipelinePreset_select');
      const name = sel && sel.value ? sel.value : null;
      if (!name) { alert('Select a preset first'); return; }
      const resp = await apiClient.makeRequest('GET', `/api/v1/evaluations/rag/pipeline/presets/${encodeURIComponent(name)}`);
      if (!(resp && resp.config)) { alert('Preset not found'); return; }
      const ta = document.getElementById('ragPipelineCreate_payload');
      if (ta) ta.value = JSON.stringify(resp.config, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Applied preset to create payload.');
    } catch (e) {
      alert('Failed to apply preset: ' + (e?.message || e));
    }
  }

  function initializeEvaluationsTab() {
    // Called by main.js when evaluations sub-tabs are shown
    if (typeof populateModelDropdowns === 'function') {
      setTimeout(() => { try { populateModelDropdowns(); } catch(_){} }, 100);
    }
  }

  // --------- Run details helpers (leaderboard preview + CSV exports) ---------
  function _parseRunFromPreId(preId) {
    const pre = document.getElementById(preId);
    if (!pre) throw new Error('Run response area not found');
    const text = (pre.textContent || pre.innerText || '').trim();
    if (!text || text === '---') throw new Error('No run JSON loaded yet');
    try { return JSON.parse(text); } catch (e) { throw new Error('Invalid JSON in run response'); }
  }

  function _getRunResults(runObj) {
    if (!runObj) return {};
    // Prefer nested results; fallback to object root for direct structures
    return runObj.results || runObj;
  }

  function _createEl(tag, attrs = {}, html = '') {
    const el = document.createElement(tag);
    Object.entries(attrs || {}).forEach(([k,v]) => el.setAttribute(k, String(v)));
    if (html) el.innerHTML = html;
    return el;
  }

  function _renderLeaderboardPreviewFrom(preId, containerId) {
    let run; try { run = _parseRunFromPreId(preId); } catch (e) { alert(e.message); return; }
    const res = _getRunResults(run);
    const lb = Array.isArray(res?.leaderboard) ? res.leaderboard : [];
    const box = document.getElementById(containerId);
    if (!box) return;
    if (!lb.length) { box.innerHTML = '<em>No leaderboard in run results.</em>'; return; }
    const top = lb.slice(0, 10);
    const table = _createEl('table', { style: 'width:100%; border-collapse:collapse;' });
    const thead = _createEl('thead');
    thead.innerHTML = '<tr>'+
      '<th style="text-align:left; padding:6px; border-bottom:1px solid var(--color-border);">#</th>'+
      '<th style="text-align:left; padding:6px; border-bottom:1px solid var(--color-border);">Config ID</th>'+
      '<th style="text-align:right; padding:6px; border-bottom:1px solid var(--color-border);">Score</th>'+
      '<th style="text-align:right; padding:6px; border-bottom:1px solid var(--color-border);">Overall</th>'+
      '<th style="text-align:right; padding:6px; border-bottom:1px solid var(--color-border);">Latency (ms)</th>'+
      '<th style="text-align:left; padding:6px; border-bottom:1px solid var(--color-border);">Modes</th>'+
      '<th style="text-align:left; padding:6px; border-bottom:1px solid var(--color-border);">Model</th>'+
    '</tr>';
    table.appendChild(thead);
    const tbody = _createEl('tbody');
    top.forEach((row, idx) => {
      const cfg = row.config || {};
      const retr = cfg.retriever || {};
      const rerk = cfg.reranker || {};
      const rag = cfg.rag || {};
      const tr = _createEl('tr');
      const modes = [retr.search_mode, rerk.strategy].filter(Boolean).join(' + ');
      tr.innerHTML = '<td style="padding:6px;">'+(idx+1)+'</td>'+
        '<td style="padding:6px;">'+(row.config_id || '')+'</td>'+
        '<td style="padding:6px; text-align:right;">'+(Number(row.config_score||0).toFixed(3))+'</td>'+
        '<td style="padding:6px; text-align:right;">'+(Number(row.overall||0).toFixed(3))+'</td>'+
        '<td style="padding:6px; text-align:right;">'+(Number(row.latency_ms||0).toFixed(0))+'</td>'+
        '<td style="padding:6px;">'+(modes||'')+'</td>'+
        '<td style="padding:6px;">'+(Array.isArray(rag.model)? rag.model[0] : (rag.model||''))+'</td>';
      tbody.appendChild(tr);
    });
    table.appendChild(tbody);
    box.innerHTML = '';
    box.appendChild(table);
  }

  function renderRunLeaderboardPreview() { _renderLeaderboardPreviewFrom('evalRunGet_response', 'evalRunGet_preview'); }
  function renderRagPipelineLeaderboardPreview() { _renderLeaderboardPreviewFrom('ragPipelineRun_response', 'ragPipelineRun_preview'); }

  function _downloadCsv(filename, csvText) {
    const blob = new Blob([csvText], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url; a.download = filename;
    document.body.appendChild(a); a.click();
    setTimeout(() => { URL.revokeObjectURL(url); document.body.removeChild(a); }, 0);
  }

  function _csvEscape(val) {
    const s = val == null ? '' : String(val);
    if (/[",\n]/.test(s)) return '"' + s.replaceAll('"', '""') + '"';
    return s;
  }

  function _exportLeaderboardCsvFrom(preId, filenamePrefix) {
    let run; try { run = _parseRunFromPreId(preId); } catch (e) { alert(e.message); return; }
    const res = _getRunResults(run);
    const lb = Array.isArray(res?.leaderboard) ? res.leaderboard : [];
    if (!lb.length) { alert('No leaderboard found in run results'); return; }
    const header = [
      'rank','config_id','config_score','overall','latency_ms',
      'retrieval_mode','hybrid_alpha','retriever_top_k','rerank_strategy','rerank_top_k',
      'gen_model','gen_temperature','gen_max_tokens','chunk_method','chunk_size','chunk_overlap'
    ];
    const rows = [header];
    lb.forEach((row, idx) => {
      const cfg = row.config || {};
      const retr = cfg.retriever || {};
      const rerk = cfg.reranker || {};
      const rag = cfg.rag || {};
      const chunk = cfg.chunking || {};
      rows.push([
        String(idx+1),
        row.config_id || '',
        Number(row.config_score||0).toFixed(6),
        Number(row.overall||0).toFixed(6),
        Number(row.latency_ms||0).toFixed(0),
        retr.search_mode || '',
        retr.hybrid_alpha != null ? retr.hybrid_alpha : '',
        retr.top_k != null ? retr.top_k : '',
        rerk.strategy || '',
        rerk.top_k != null ? rerk.top_k : '',
        Array.isArray(rag.model)? rag.model[0] : (rag.model||''),
        rag.temperature != null ? rag.temperature : '',
        rag.max_tokens != null ? rag.max_tokens : '',
        chunk.method || '',
        chunk.chunk_size != null ? chunk.chunk_size : '',
        chunk.overlap != null ? chunk.overlap : ''
      ].map(_csvEscape).join(','));
    });
    const csv = rows.map(r => Array.isArray(r) ? r : r.split(',')).join('\n');
    const rid = run.id || 'run';
    _downloadCsv(`${filenamePrefix}_${rid}.csv`, csv);
  }

  function exportRunLeaderboardCsv() { _exportLeaderboardCsvFrom('evalRunGet_response', 'rag_leaderboard'); }
  function exportRagPipelineLeaderboardCsv() { _exportLeaderboardCsvFrom('ragPipelineRun_response', 'rag_leaderboard'); }

  function _exportPerConfigCsvFrom(preId, filenamePrefix) {
    let run; try { run = _parseRunFromPreId(preId); } catch (e) { alert(e.message); return; }
    const res = _getRunResults(run);
    const items = Array.isArray(res?.by_config) ? res.by_config : [];
    if (!items.length) { alert('No by_config records found'); return; }
    const header = [
      'config_id','overall','latency_ms','retrieval_coverage','retrieval_diversity','mrr','ndcg','chunk_cohesion','chunk_separation'
    ];
    const rows = [header.join(',')];
    items.forEach(c => {
      const agg = c.aggregate || {};
      rows.push([
        c.config_id || '',
        Number(agg.overall||0).toFixed(6),
        Number(agg.latency_ms||0).toFixed(0),
        Number(agg.retrieval_coverage||0).toFixed(6),
        Number(agg.retrieval_diversity||0).toFixed(6),
        Number(agg.mrr||0).toFixed(6),
        Number(agg.ndcg||0).toFixed(6),
        Number(agg.chunk_cohesion||0).toFixed(6),
        Number(agg.chunk_separation||0).toFixed(6)
      ].map(_csvEscape).join(','));
    });
    const csv = rows.join('\n');
    const rid = run.id || 'run';
    _downloadCsv(`${filenamePrefix}_${rid}.csv`, csv);
  }

  function exportRunPerConfigCsv() { _exportPerConfigCsvFrom('evalRunGet_response', 'rag_by_config'); }
  function exportRagPipelinePerConfigCsv() { _exportPerConfigCsvFrom('ragPipelineRun_response', 'rag_by_config'); }

  async function _saveBestConfigPresetFrom(preId, nameInputId) {
    try {
      const run = _parseRunFromPreId(preId);
      const results = _getRunResults(run);
      const best = results.best_config || run.best_config;
      if (!best) { alert('best_config not found in run results'); return; }
      const cfg = best.config || best;
      const name = (document.getElementById(nameInputId)?.value || 'rag_pipeline_best').trim();
      const body = { name, config: cfg };
      const resp = await apiClient.makeRequest('POST', '/api/v1/evaluations/rag/pipeline/presets', { body });
      if (resp && resp.name) {
        if (typeof Toast !== 'undefined') Toast.success('Preset saved on server: ' + resp.name);
      } else {
        if (typeof Toast !== 'undefined') Toast.error('Server did not confirm preset save.');
      }
    } catch (e) {
      alert('Failed to save best config preset: ' + (e?.message || e));
    }
  }
  function saveBestConfigPresetFromRun() { return _saveBestConfigPresetFrom('evalRunGet_response', 'evalRunPreset_name'); }
  function saveBestConfigPresetLocalFromRun() {
    try {
      const run = _parseRunFromPreId('evalRunGet_response');
      const results = _getRunResults(run);
      const best = results.best_config || run.best_config;
      if (!best) { alert('best_config not found in run results'); return; }
      const cfg = best.config || best;
      const name = (document.getElementById('evalRunPreset_name')?.value || 'rag_pipeline_best').trim();
      localStorage.setItem('ragPipelinePreset_' + name, JSON.stringify(cfg));
      if (typeof Toast !== 'undefined') Toast.success('Preset saved locally as ' + name);
    } catch (e) {
      alert('Failed to save local preset: ' + (e?.message || e));
    }
  }

  function applyBestConfigToCreatePayload() {
    try {
      const run = _parseRunFromPreId('ragPipelineRun_response');
      const results = _getRunResults(run);
      const best = results.best_config || run.best_config;
      if (!best) { alert('best_config not found in run results'); return; }
      const cfg = best.config || best;
      const ta = document.getElementById('ragPipelineCreate_payload');
      if (!ta) { alert('Create payload textarea not found'); return; }
      const obj = JSON.parse(ta.value || '{}');
      const es = obj.eval_spec = obj.eval_spec || {};
      const rp = es.rag_pipeline = es.rag_pipeline || {};
      rp.chunking = cfg.chunking || rp.chunking;
      rp.retrievers = cfg.retriever ? [cfg.retriever] : (rp.retrievers || []);
      rp.rerankers = cfg.reranker ? [cfg.reranker] : (rp.rerankers || []);
      rp.rag = cfg.rag || rp.rag;
      ta.value = JSON.stringify(obj, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Applied best config to create payload.');
    } catch (e) {
      alert('Failed to apply best config: ' + (e?.message || e));
    }
  }

  // --------- Local presets quick selector (Runs tab) ---------
  function _listLocalPresetNames() {
    const names = [];
    try {
      for (let i = 0; i < localStorage.length; i++) {
        const key = localStorage.key(i);
        if (key && key.startsWith('ragPipelinePreset_')) {
          names.push(key.substring('ragPipelinePreset_'.length));
        }
      }
    } catch (_) {}
    names.sort((a,b)=> a.localeCompare(b));
    return names;
  }
  function refreshRunLocalPresetsDropdown() {
    const sel = document.getElementById('evalRunLocalPreset_select');
    if (!sel) return;
    sel.innerHTML = '';
    const items = _listLocalPresetNames();
    items.forEach(n => {
      const opt = document.createElement('option');
      opt.value = n; opt.textContent = n;
      sel.appendChild(opt);
    });
    if (typeof Toast !== 'undefined') Toast.success(`Loaded ${items.length} local presets`);
  }
  function applyRunLocalPresetToCreate() {
    try {
      const sel = document.getElementById('evalRunLocalPreset_select');
      const name = sel && sel.value ? sel.value : null;
      if (!name) { alert('Select a local preset'); return; }
      const raw = localStorage.getItem('ragPipelinePreset_' + name);
      if (!raw) { alert('Local preset not found: ' + name); return; }
      const cfg = JSON.parse(raw);
      const ta = document.getElementById('ragPipelineCreate_payload');
      if (!ta) { alert('Create payload textarea not found'); return; }
      const obj = JSON.parse(ta.value || '{}');
      const es = obj.eval_spec = obj.eval_spec || {};
      const rp = es.rag_pipeline = es.rag_pipeline || {};
      rp.chunking = cfg.chunking || rp.chunking;
      rp.retrievers = cfg.retriever ? [cfg.retriever] : (rp.retrievers || []);
      rp.rerankers = cfg.reranker ? [cfg.reranker] : (rp.rerankers || []);
      rp.rag = cfg.rag || rp.rag;
      ta.value = JSON.stringify(obj, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Applied local preset to create payload.');
    } catch (e) {
      alert('Failed to apply local preset: ' + (e?.message || e));
    }
  }

  // expose globals for inline attributes until we remove them
  window.updateEvalsCreateJSON = updateEvalsCreateJSON;
  window.updateGEvalJSON = updateGEvalJSON;
  window.ragEvalRefreshPresets = ragEvalRefreshPresets;
  window.ragEvalApplyPresetTemplate = ragEvalApplyPresetTemplate;
  window.extractBestConfigFromRun = extractBestConfigFromRun;
  window.saveRagPipelinePreset = saveRagPipelinePreset;
  window.applyPresetToCreatePayload = applyPresetToCreatePayload;
  window.savePresetToServer = savePresetToServer;
  window.loadPresetFromServer = loadPresetFromServer;
  window.refreshServerPresets = refreshServerPresets;
  window.applySelectedServerPreset = applySelectedServerPreset;
  window.initializeEvaluationsTab = initializeEvaluationsTab;
  window.renderRunLeaderboardPreview = renderRunLeaderboardPreview;
  window.exportRunLeaderboardCsv = exportRunLeaderboardCsv;
  window.exportRunPerConfigCsv = exportRunPerConfigCsv;
  window.renderRagPipelineLeaderboardPreview = renderRagPipelineLeaderboardPreview;
  window.exportRagPipelineLeaderboardCsv = exportRagPipelineLeaderboardCsv;
  window.exportRagPipelinePerConfigCsv = exportRagPipelinePerConfigCsv;
  window.saveBestConfigPresetFromRun = saveBestConfigPresetFromRun;
  window.saveBestConfigPresetLocalFromRun = saveBestConfigPresetLocalFromRun;
  window.applyBestConfigToCreatePayload = applyBestConfigToCreatePayload;
  window.refreshRunLocalPresetsDropdown = refreshRunLocalPresetsDropdown;
  window.applyRunLocalPresetToCreate = applyRunLocalPresetToCreate;
})();

// Bind UI events to remove inline handlers for Evals tabs
(function bindEvalsUi(){
  const byId = (id) => document.getElementById(id);
  // model selects
  byId('evalsCreate_model')?.addEventListener('change', updateEvalsCreateJSON);
  byId('geval_model')?.addEventListener('change', updateGEvalJSON);
  // rag eval buttons
  byId('btnRagEvalRefreshPresets')?.addEventListener('click', ragEvalRefreshPresets);
  byId('btnRagEvalApplyPresetTemplate')?.addEventListener('click', ragEvalApplyPresetTemplate);
  // rag pipeline presets
  byId('btnExtractBestConfig')?.addEventListener('click', extractBestConfigFromRun);
  byId('btnSaveRagPipelinePreset')?.addEventListener('click', saveRagPipelinePreset);
  byId('btnApplyPresetToCreate')?.addEventListener('click', applyPresetToCreatePayload);
  byId('btnSavePresetToServer')?.addEventListener('click', savePresetToServer);
  byId('btnLoadPresetFromServer')?.addEventListener('click', loadPresetFromServer);
  byId('btnRefreshServerPresets')?.addEventListener('click', refreshServerPresets);
  byId('btnApplySelectedServerPreset')?.addEventListener('click', applySelectedServerPreset);

  // run details: preview and exports
  byId('btnEvalRunRenderLeaderboard')?.addEventListener('click', renderRunLeaderboardPreview);
  byId('btnEvalRunExportCsv')?.addEventListener('click', exportRunLeaderboardCsv);
  byId('btnEvalRunExportPerConfigCsv')?.addEventListener('click', exportRunPerConfigCsv);
  byId('btnRagPipelineRenderLeaderboard')?.addEventListener('click', renderRagPipelineLeaderboardPreview);
  byId('btnRagPipelineExportCsv')?.addEventListener('click', exportRagPipelineLeaderboardCsv);
  byId('btnRagPipelineExportPerConfigCsv')?.addEventListener('click', exportRagPipelinePerConfigCsv);
  byId('btnEvalRunSaveBestPreset')?.addEventListener('click', saveBestConfigPresetFromRun);
  byId('btnEvalRunSaveBestPresetLocal')?.addEventListener('click', saveBestConfigPresetLocalFromRun);
  byId('btnApplyBestConfigToCreate')?.addEventListener('click', applyBestConfigToCreatePayload);
  byId('btnEvalRunLocalPresetRefresh')?.addEventListener('click', refreshRunLocalPresetsDropdown);
  byId('btnEvalRunApplyLocalPreset')?.addEventListener('click', applyRunLocalPresetToCreate);

  // Delegate to legacy makeRequest for data-req buttons
  document.addEventListener('click', (ev) => {
    const btn = ev.target.closest('button[data-req-section]');
    if (!btn) return;
    const section = btn.getAttribute('data-req-section');
    const method = btn.getAttribute('data-req-method') || 'GET';
    const path = btn.getAttribute('data-req-path') || '/';
    const bodyType = btn.getAttribute('data-req-body-type') || 'none';
    const confirmMsg = btn.getAttribute('data-confirm');
    if (confirmMsg && !window.confirm(confirmMsg)) return;
    if (typeof window.makeRequest === 'function') {
      ev.preventDefault();
      window.makeRequest(section, method, path, bodyType);
    }
  });
})();
