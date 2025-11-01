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
