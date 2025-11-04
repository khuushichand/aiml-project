// Simple Mode: Quick Actions landing handlers
(function() {
  'use strict';

  let jobsStreamHandle = null;
  let jobsStatsTimer = null;

  function setSimpleDefaults() {
    try {
      // Set Save to DB default from server-provided config
      const def = window.apiClient && window.apiClient.loadedConfig && window.apiClient.loadedConfig.chat && typeof window.apiClient.loadedConfig.chat.default_save_to_db === 'boolean'
        ? !!window.apiClient.loadedConfig.chat.default_save_to_db
        : false;
      const saveEl = document.getElementById('simpleChat_save');
      if (saveEl) saveEl.checked = def;
    } catch (_) { /* ignore */ }

    // Restore last used chat model if available
    try {
      const pref = Utils.getFromStorage('chat-ui-selection');
      if (pref && pref.model) {
        const sm = document.getElementById('simpleChat_model');
        if (sm) sm.value = pref.model;
      }
    } catch (_) { /* ignore */ }
  }

  function startInlineJobsFeedback(container) {
    try {
      const el = document.getElementById('simpleIngest_job');
      if (!el) return;
      el.style.display = 'block';
      el.innerHTML = '<div style="padding:6px; background: var(--color-surface-alt); border:1px solid var(--color-border); border-radius:6px;">'
        + '<strong>Live job activity</strong><div id="simpleJobsEvents" class="text-small" style="max-height:120px; overflow:auto; margin-top:6px;"></div>'
        + '<div id="simpleJobsStats" class="text-muted" style="margin-top:6px;"></div>'
        + '</div>';

      // Stream events
      try { if (jobsStreamHandle && jobsStreamHandle.abort) jobsStreamHandle.abort(); } catch (_) {}
      const domainWhitelist = new Set(['media','webscrape','web_scrape','webscraping']);
      jobsStreamHandle = apiClient.streamSSE('/api/v1/jobs/events/stream', {
        onEvent: (obj) => {
          if (!obj || !domainWhitelist.has(String(obj.domain))) return;
          const list = document.getElementById('simpleJobsEvents');
          if (!list) return;
          // Render a compact line
          const line = document.createElement('div');
          const dqt = [obj.domain, obj.queue, obj.job_type].filter(Boolean).join('/');
          const jid = obj.job_id || '-';
          const ev = obj.event || '';
          const txt = `${new Date().toLocaleTimeString()} · ${ev} · ${dqt} · id:${jid}`;
          line.textContent = txt;
          list.appendChild(line);
          // Keep last ~30
          while (list.children.length > 30) list.removeChild(list.firstChild);
          // Auto-scroll
          list.scrollTop = list.scrollHeight;
        },
        timeout: 600000
      });

      // Poll stats every 10s
      if (jobsStatsTimer) clearInterval(jobsStatsTimer);
      const statsEl = document.getElementById('simpleJobsStats');
      const updateStats = async () => {
        try {
          // Sum media and webscrape domains only
          const agg = { processing: 0, queued: 0, quarantined: 0 };
          for (const dom of ['media','webscrape']) {
            try {
              const res = await apiClient.get('/api/v1/jobs/stats', { domain: dom });
              const arr = Array.isArray(res) ? res : (res && res.data) ? res.data : [];
              agg.processing += arr.reduce((a, r) => a + (r.processing || 0), 0);
              agg.queued += arr.reduce((a, r) => a + (r.queued || 0), 0);
              agg.quarantined += arr.reduce((a, r) => a + (r.quarantined || 0), 0);
            } catch (_) { /* ignore per-domain errors */ }
          }
          const totalProcessing = agg.processing;
          const totalQueued = agg.queued;
          const totalQuarantine = agg.quarantined;
          if (statsEl) statsEl.textContent = `processing=${totalProcessing} queued=${totalQueued} quarantined=${totalQuarantine}`;
        } catch (_) { /* ignore */ }
      };
      updateStats();
      jobsStatsTimer = setInterval(updateStats, 10000);
    } catch (e) {
      console.warn('Jobs feedback unavailable:', e);
    }
  }

  function stopInlineJobsFeedback() {
    try { if (jobsStreamHandle && jobsStreamHandle.abort) jobsStreamHandle.abort(); } catch (_) {}
    jobsStreamHandle = null;
    try { if (jobsStatsTimer) clearInterval(jobsStatsTimer); } catch (_) {}
    jobsStatsTimer = null;
  }

  async function simpleIngestSubmit() {
    const resp = document.getElementById('simpleIngest_response');
    const container = document.getElementById('simpleIngest');
    if (!resp || !container) return;

    const mediaType = document.getElementById('simpleIngest_media_type')?.value || 'document';
    const url = (document.getElementById('simpleIngest_url')?.value || '').trim();
    const file = document.getElementById('simpleIngest_file')?.files?.[0] || null;
    const model = document.getElementById('simpleIngest_model')?.value || '';
    const performAnalysis = !!document.getElementById('simpleIngest_perform_analysis')?.checked;
    const doChunk = !!document.getElementById('simpleIngest_chunking')?.checked;

    const isWeb = (mediaType === 'web');
    const webUrl = (document.getElementById('simpleIngest_web_url')?.value || '').trim();

    // Safely initialize prompts used in both FormData and JSON paths
    const seedPrompt = (document.getElementById('simpleIngest_seed')?.value || '').trim();
    const systemPrompt = (document.getElementById('simpleIngest_system')?.value || '').trim();

    if (!isWeb && !url && !file) {
      Toast && Toast.warning ? Toast.warning('Provide a URL or choose a file') : alert('Provide a URL or choose a file');
      return;
    }
    if (isWeb && !webUrl) {
      Toast && Toast.warning ? Toast.warning('Enter a Start URL for web scraping') : alert('Enter a Start URL for web scraping');
      return;
    }

    let requestPath = '/api/v1/media/add';
    let requestOptions = {};
    if (!isWeb) {
      const fd = new FormData();
      fd.append('media_type', mediaType);
      if (url) fd.append('urls', url);
      if (file) fd.append('files', file);
      if (model) fd.append('api_name', model);
      fd.append('perform_analysis', String(performAnalysis));
      fd.append('perform_chunking', String(doChunk));
      if (seedPrompt) fd.append('custom_prompt', seedPrompt);
      if (systemPrompt) fd.append('system_prompt', systemPrompt);
      // Reasonable defaults
      fd.append('timestamp_option', 'true');
      fd.append('chunk_size', '500');
      fd.append('chunk_overlap', '200');
      requestOptions = { body: fd, timeout: 600000 };
    } else {
      // Web scraping ingest, JSON payload
      const methodSel = document.getElementById('simpleIngest_scrape_method');
      const method = methodSel ? methodSel.value : 'individual';
      const body = {
        urls: webUrl ? [webUrl] : [],
        scrape_method: method,
        perform_analysis: performAnalysis,
        custom_prompt: seedPrompt || undefined,
        system_prompt: systemPrompt || undefined,
        api_name: model || undefined,
        perform_chunking: doChunk
      };
      if (method === 'url_level') {
        const lvl = parseInt(document.getElementById('simpleIngest_url_level')?.value || '2', 10);
        if (!isNaN(lvl) && lvl > 0) body.url_level = lvl;
      } else if (method === 'recursive_scraping') {
        const maxPages = parseInt(document.getElementById('simpleIngest_max_pages')?.value || '10', 10);
        const maxDepth = parseInt(document.getElementById('simpleIngest_max_depth')?.value || '3', 10);
        if (!isNaN(maxPages) && maxPages > 0) body.max_pages = maxPages;
        if (!isNaN(maxDepth) && maxDepth > 0) body.max_depth = maxDepth;
      }
      // Crawl flags
      const includeExternal = !!document.getElementById('simpleIngest_include_external')?.checked;
      const crawlStrategy = (document.getElementById('simpleIngest_crawl_strategy')?.value || '').trim();
      if (includeExternal) body.include_external = true;
      if (crawlStrategy) body.crawl_strategy = crawlStrategy;
      requestPath = '/api/v1/media/ingest-web-content';
      requestOptions = { body, timeout: 600000 };
    }

    try {
      Loading.show(container, 'Ingesting...');
      startInlineJobsFeedback(container);
      const data = await apiClient.post(requestPath, requestOptions.body, { timeout: requestOptions.timeout });
      resp.textContent = Utils.syntaxHighlight ? Utils.syntaxHighlight(data) : JSON.stringify(data, null, 2);
    } catch (e) {
      resp.textContent = (e && e.message) ? String(e.message) : 'Failed';
    } finally {
      Loading.hide(container);
      stopInlineJobsFeedback();
    }
  }

  function simpleIngestClear() {
    try { const el = document.getElementById('simpleIngest_url'); if (el) el.value = ''; } catch(_){}
    try { const f = document.getElementById('simpleIngest_file'); if (f) f.value=''; } catch(_){}
    try { document.getElementById('simpleIngest_response').textContent = '---'; } catch(_){}
    try { const job = document.getElementById('simpleIngest_job'); if (job) { job.style.display='none'; job.innerHTML=''; } } catch(_){}
  }

  async function simpleChatSend() {
    const input = document.getElementById('simpleChat_input');
    const modelSel = document.getElementById('simpleChat_model');
    const saveEl = document.getElementById('simpleChat_save');
    const out = document.getElementById('simpleChat_response');
    if (!input || !out) return;
    const msg = (input.value || '').trim();
    if (!msg) return;
    input.value = '';
    const payload = {
      messages: [{ role: 'user', content: msg }]
    };
    const model = modelSel ? (modelSel.value || '') : '';
    if (model) payload.model = model;
    if (saveEl && saveEl.checked) payload.save_to_db = true;
    try {
      Loading.show(out.parentElement, 'Sending...');
      const res = await apiClient.post('/api/v1/chat/completions', payload);
      out.textContent = JSON.stringify(res, null, 2);
      // Persist last used model
      try { Utils.saveToStorage('chat-ui-selection', { model }); } catch(_){}
      try { endpointHelper.updateCorrelationSnippet(out); } catch(_){}
    } catch (e) {
      out.textContent = (e && e.message) ? String(e.message) : 'Failed';
      try { endpointHelper.updateCorrelationSnippet(out); } catch(_){}
    } finally {
      Loading.hide(out.parentElement);
    }
  }

  let __simpleSearchState = { q: '', page: 1, rpp: 10, totalPages: 0, totalItems: 0 };
  async function simpleSearchRun(pageOverride) {
    const box = document.getElementById('simpleSearch_results');
    const qEl = document.getElementById('simpleSearch_q');
    const rppEl = document.getElementById('simpleSearch_rpp');
    const prevBtn = document.getElementById('simpleSearch_prev');
    const nextBtn = document.getElementById('simpleSearch_next');
    const infoEl = document.getElementById('simpleSearch_pageinfo');
    if (!box) return;
    const q = (qEl && qEl.value || '').trim();
    if (!q) { box.innerHTML = '<span class="text-muted">Enter a query.</span>'; return; }
    const rpp = Math.max(1, Math.min(100, parseInt((rppEl && rppEl.value) || '10', 10)));
    const page = (typeof pageOverride === 'number') ? pageOverride : (__simpleSearchState.page || 1);
    __simpleSearchState.q = q; __simpleSearchState.rpp = rpp; __simpleSearchState.page = page;
    box.innerHTML = '';
    try {
      Loading.show(box.parentElement, 'Searching...');
      const payload = { query: q, fields: ['title','content'], sort_by: 'relevance' };
      const res = await apiClient.post('/api/v1/media/search', payload, { query: { page, results_per_page: rpp } });
      const items = (res && res.items) || [];
      const pagination = res && res.pagination;
      const totalPages = (pagination && pagination.total_pages) || 0;
      const totalItems = (pagination && pagination.total_items) || (items.length || 0);
      __simpleSearchState.totalPages = totalPages; __simpleSearchState.totalItems = totalItems;

      if (!Array.isArray(items) || items.length === 0) {
        box.innerHTML = '<span class="text-muted">No results</span>';
      } else {
        const ul = document.createElement('ul');
        ul.style.listStyle = 'none';
        ul.style.padding = '0';
        items.forEach((r) => {
          const li = document.createElement('li');
          li.style.padding = '6px 0';
          const title = (r.title || r.metadata?.title || '(untitled)');
          const id = r.id || r.media_id || '';
          const open = document.createElement('a');
          open.href = '#';
          open.textContent = title;
          open.title = 'Open in Media → Management';
          open.addEventListener('click', (e) => {
            e.preventDefault();
            try {
              const btn = document.querySelector('.top-tab-button[data-toptab="media"]');
              if (btn && window.webUI) {
                window.webUI.activateTopTab(btn).then(() => {
                  setTimeout(() => {
                    try { const mid = document.getElementById('getMediaItem_media_id'); if (mid) mid.value = String(id || ''); } catch(_){}
                    try { makeRequest('getMediaItem', 'GET', '/api/v1/media/{media_id}', 'none'); } catch(_){}
                  }, 200);
                });
              }
            } catch (_) {}
          });
          li.appendChild(open);
          ul.appendChild(li);
        });
        box.appendChild(ul);
      }

      // Update pagination controls
      if (infoEl) infoEl.textContent = totalPages > 0 ? `Page ${page} of ${totalPages} (${totalItems})` : '';
      if (prevBtn) prevBtn.disabled = (page <= 1);
      if (nextBtn) nextBtn.disabled = (totalPages && page >= totalPages);
    } catch (e) {
      box.textContent = (e && e.message) ? String(e.message) : 'Search failed';
    } finally {
      Loading.hide(box.parentElement);
    }
  }

  function bindSimpleHandlers() {
    const ingestBtn = document.getElementById('simpleIngest_submit');
    if (ingestBtn && !ingestBtn._bound) { ingestBtn.addEventListener('click', simpleIngestSubmit); ingestBtn._bound = true; }
    const ingestClr = document.getElementById('simpleIngest_clear');
    if (ingestClr && !ingestClr._bound) { ingestClr.addEventListener('click', simpleIngestClear); ingestClr._bound = true; }
    const chatBtn = document.getElementById('simpleChat_send');
    if (chatBtn && !chatBtn._bound) { chatBtn.addEventListener('click', simpleChatSend); chatBtn._bound = true; }
    const searchBtn = document.getElementById('simpleSearch_run');
    if (searchBtn && !searchBtn._bound) { searchBtn.addEventListener('click', () => { __simpleSearchState.page = 1; simpleSearchRun(1); }); searchBtn._bound = true; }
    const prevBtn = document.getElementById('simpleSearch_prev');
    if (prevBtn && !prevBtn._bound) {
      prevBtn.addEventListener('click', () => {
        const newPage = Math.max(1, (__simpleSearchState.page || 1) - 1);
        __simpleSearchState.page = newPage;
        simpleSearchRun(newPage);
      });
      prevBtn._bound = true;
    }
    const nextBtn = document.getElementById('simpleSearch_next');
    if (nextBtn && !nextBtn._bound) {
      nextBtn.addEventListener('click', () => {
        const tp = __simpleSearchState.totalPages || 0;
        const newPage = (__simpleSearchState.page || 1) + 1;
        if (!tp || newPage <= tp) {
          __simpleSearchState.page = newPage;
          simpleSearchRun(newPage);
        }
      });
      nextBtn._bound = true;
    }
    const qEl = document.getElementById('simpleSearch_q');
    if (qEl && !qEl._bound) {
      qEl.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') {
          __simpleSearchState.page = 1;
          simpleSearchRun(1);
        }
      });
      qEl._bound = true;
    }
  }

  // Public initializer used by main.js when the Simple tab is shown
  window.initializeSimpleLanding = function initializeSimpleLanding() {
    try {
      // Ensure model dropdowns are populated (shared util)
      if (typeof window.populateModelDropdowns === 'function') {
        setTimeout(() => window.populateModelDropdowns(), 50);
      }
    } catch (_) {}
    bindSimpleHandlers();
    setSimpleDefaults();
    // Re-apply defaults shortly after models populate
    setTimeout(setSimpleDefaults, 200);

    // Initialize simple ingest UI toggles
    try {
      const mediaSel = document.getElementById('simpleIngest_media_type');
      const methodSel = document.getElementById('simpleIngest_scrape_method');
      if (mediaSel && !mediaSel._bound) {
        mediaSel.addEventListener('change', updateSimpleIngestUI);
        mediaSel._bound = true;
      }
      if (methodSel && !methodSel._bound) {
        methodSel.addEventListener('change', updateSimpleIngestUI);
        methodSel._bound = true;
      }
      updateSimpleIngestUI();
    } catch (_) {}

    // Bind paging keyboard shortcuts
    bindSimpleSearchShortcuts();
  };

  function updateSimpleIngestUI() {
    try {
      const mediaSel = document.getElementById('simpleIngest_media_type');
      const isWeb = mediaSel && mediaSel.value === 'web';
      const webBox = document.getElementById('simpleIngest_web_opts');
      const urlGroup = document.getElementById('simpleIngest_url_group');
      const fileGroup = document.getElementById('simpleIngest_file_group');
      const webUrlGroup = document.getElementById('simpleIngest_web_url_group');
      if (webBox) webBox.style.display = isWeb ? 'block' : 'none';
      if (urlGroup) urlGroup.style.display = isWeb ? 'none' : 'block';
      if (fileGroup) fileGroup.style.display = isWeb ? 'none' : 'block';
      if (webUrlGroup) webUrlGroup.style.display = isWeb ? 'block' : 'none';

      const methodSel = document.getElementById('simpleIngest_scrape_method');
      const urlLevelGroup = document.getElementById('simpleIngest_url_level_group');
      const recGroup = document.getElementById('simpleIngest_recursive_group');
      const method = methodSel ? methodSel.value : 'individual';
      if (urlLevelGroup) urlLevelGroup.style.display = (isWeb && method === 'url_level') ? 'block' : 'none';
      if (recGroup) recGroup.style.display = (isWeb && method === 'recursive_scraping') ? 'flex' : 'none';
    } catch (_) {}
  }

  let __simpleSearchKbBound = false;
  function bindSimpleSearchShortcuts() {
    if (__simpleSearchKbBound) return;
    __simpleSearchKbBound = true;
    document.addEventListener('keydown', (e) => {
      try {
        const isVisible = !!document.getElementById('tabSimpleLanding')?.classList.contains('active');
        if (!isVisible) return;
        // Skip if modifier keys
        if (e.ctrlKey || e.altKey || e.metaKey) return;
        // Avoid when focus is in inputs other than the page
        const tag = (document.activeElement && document.activeElement.tagName || '').toLowerCase();
        if (tag === 'input' || tag === 'textarea' || tag === 'select') return;
        if (e.key === 'ArrowLeft') {
          e.preventDefault();
          const newPage = Math.max(1, (__simpleSearchState.page || 1) - 1);
          if (newPage !== (__simpleSearchState.page || 1)) {
            __simpleSearchState.page = newPage;
            simpleSearchRun(newPage);
          }
        } else if (e.key === 'ArrowRight') {
          e.preventDefault();
          const tp = __simpleSearchState.totalPages || 0;
          const newPage = (__simpleSearchState.page || 1) + 1;
          if (!tp || newPage <= tp) {
            __simpleSearchState.page = newPage;
            simpleSearchRun(newPage);
          }
        }
      } catch (_) {}
    });
  }

})();
