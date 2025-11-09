// Simple Mode: Quick Actions landing handlers
(function() {
  'use strict';

  let jobsStreamHandle = null;
  let jobsStatsTimer = null;
  let __boundEnhancements = false;
  let simpleChatStreamHandle = null;
  // Ephemeral client-threaded chat history for Simple Chat
  let __simpleChatHistory = [];
  const __simpleChatMaxHistory = 40; // keep last N messages
  // When Save to DB is enabled, reuse a single server conversation_id
  let __simpleChatConversationId = null;

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
      // Only include domains actually emitted by the backend
      const domainWhitelist = new Set(['media','webscrape']);
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
    const fileList = document.getElementById('simpleIngest_file')?.files || null;
    const model = document.getElementById('simpleIngest_model')?.value || '';
    const performAnalysis = !!document.getElementById('simpleIngest_perform_analysis')?.checked;
    const doChunk = !!document.getElementById('simpleIngest_chunking')?.checked;

    const isWeb = (mediaType === 'web');
    const webUrl = (document.getElementById('simpleIngest_web_url')?.value || '').trim();

    // Safely initialize prompts used in both FormData and JSON paths
    const seedPrompt = (document.getElementById('simpleIngest_seed')?.value || '').trim();
    const systemPrompt = (document.getElementById('simpleIngest_system')?.value || '').trim();

    if (!isWeb && !url && !(fileList && fileList.length)) {
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
      if (fileList && fileList.length) { Array.from(fileList).forEach(f => fd.append('files', f)); }
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
      // Reflect queue submit
      try {
        const files = Array.from(document.getElementById('simpleIngest_file')?.files || []);
        renderIngestQueue(files);
      } catch (_) {}
      const data = await apiClient.post(requestPath, requestOptions.body, { timeout: requestOptions.timeout });
      if (typeof Utils !== 'undefined' && typeof Utils.syntaxHighlightJSON === 'function') {
        resp.innerHTML = Utils.syntaxHighlightJSON(data);
      } else {
        resp.textContent = JSON.stringify(data, null, 2);
      }
      try { endpointHelper.updateCorrelationSnippet(resp); } catch(_){}
      try { renderIngestJobsLink(data, isWeb ? 'webscrape' : 'media'); } catch(_){}
    } catch (e) {
      try { endpointHelper.displayError(resp, e); } catch(_) { resp.textContent = (e && e.message) ? String(e.message) : 'Failed'; }
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
    // Build payload using ephemeral local history + current user message
    try {
      // Push user message into local history
      __simpleChatHistory.push({ role: 'user', content: msg });
      // Trim history to last N messages
      if (__simpleChatHistory.length > __simpleChatMaxHistory) {
        __simpleChatHistory = __simpleChatHistory.slice(-__simpleChatMaxHistory);
      }
    } catch (_) {}
    const payload = { messages: __simpleChatHistory.slice() };
    const model = modelSel ? (modelSel.value || '') : '';
    if (model) payload.model = model;
    if (saveEl && saveEl.checked) payload.save_to_db = true;
    // If persisting, attach existing conversation_id so we don't create new threads server-side
    if (payload.save_to_db && __simpleChatConversationId) {
      payload.conversation_id = __simpleChatConversationId;
    }

    const wantStream = !!document.getElementById('simpleChat_stream_toggle')?.checked;
    if (wantStream) {
      // Ensure server streams via SSE
      payload.stream = true;
      // Streaming path (optional fallback to non-stream on failure)
      try {
        await simpleChatStartStream(payload);
        try { Utils.saveToStorage('chat-ui-selection', { model }); } catch(_){}
      } catch (streamErr) {
        try { endpointHelper.displayError(out, streamErr); } catch(_) { out.textContent = (streamErr && streamErr.message) ? String(streamErr.message) : 'Failed'; }
        try { endpointHelper.updateCorrelationSnippet(out); } catch(_){}
      }
    } else {
      // Non-streaming
      try {
        Loading.show(out.parentElement, 'Sending...');
        const chatEp = (apiClient.endpoint('chat','completions') || '/api/v1/chat/completions');
        const res = await apiClient.post(chatEp, payload);
        // Render plain answer content if present
        try {
          const answerEl = document.getElementById('simpleChat_answer');
          const streamBox = document.getElementById('simpleChat_stream');
          if (answerEl) {
            const content = res?.choices?.[0]?.message?.content || res?.message || '';
            if (typeof content === 'string' && content) {
              if (typeof renderMarkdownToElement === 'function') { renderMarkdownToElement(content, answerEl); }
              else { answerEl.textContent = content; }
              if (streamBox) streamBox.style.display = '';
              try {
                __simpleChatHistory.push({ role: 'assistant', content });
                if (__simpleChatHistory.length > __simpleChatMaxHistory) {
                  __simpleChatHistory = __simpleChatHistory.slice(-__simpleChatMaxHistory);
                }
              } catch (_) {}
            }
            // Capture server conversation_id if persistence is enabled
            try {
              if (payload.save_to_db) {
                const cid = res?.tldw_conversation_id || res?.tldw_metadata?.conversation_id || res?.conversation_id;
                if (cid && typeof cid === 'string') __simpleChatConversationId = cid;
              }
            } catch (_) {}
          }
        } catch (_) { /* ignore */ }
        out.textContent = JSON.stringify(res, null, 2);
        try { endpointHelper.updateCorrelationSnippet(out); } catch(_){}
      } catch (e) {
        try { endpointHelper.displayError(out, e); } catch(_) { out.textContent = (e && e.message) ? String(e.message) : 'Failed'; }
        try { endpointHelper.updateCorrelationSnippet(out); } catch(_){}
      } finally {
        Loading.hide(out.parentElement);
      }
    }
  }

  async function simpleChatStartStream(requestPayload) {
    const streamBox = document.getElementById('simpleChat_stream');
    const answerEl = document.getElementById('simpleChat_answer');
    const usageEl = document.getElementById('simpleChat_usage');
    const copyBtn = document.getElementById('simpleChat_copy');
    const stopBtn = document.getElementById('simpleChat_stop');
    const out = document.getElementById('simpleChat_response');
    if (!streamBox || !answerEl || !usageEl || !copyBtn || !stopBtn) return;
    // Reset
    answerEl.textContent = '';
    usageEl.textContent = 'tokens: –';
    streamBox.style.display = '';
    stopBtn.style.display = '';
    copyBtn.disabled = true;
    let assembled = '';
    let usage = null;

    // Bind copy
    if (!copyBtn._bound) {
      copyBtn.addEventListener('click', async () => {
        try { await Utils.copyToClipboard(assembled); if (Toast && Toast.success) Toast.success('Copied answer'); } catch (_) {}
      });
      copyBtn._bound = true;
    }
    // Bind stop
    if (!stopBtn._bound) {
      stopBtn.addEventListener('click', () => { try { if (simpleChatStreamHandle && simpleChatStreamHandle.abort) simpleChatStreamHandle.abort(); } catch (_) {} });
      stopBtn._bound = true;
    }

    // Start SSE
    let seenConvId = null;
    simpleChatStreamHandle = apiClient.streamSSE((apiClient.endpoint('chat','completions') || '/api/v1/chat/completions'), {
      method: 'POST',
      body: requestPayload,
      onEvent: (evt) => {
        try {
          // Support multiple streaming shapes
          let piece = evt?.choices?.[0]?.delta?.content;
          if (!piece && evt?.choices?.[0]?.text) piece = evt.choices[0].text; // some providers
          if (!piece && typeof evt?.content === 'string') piece = evt.content; // generic
          if (!piece && evt?.choices?.[0]?.message?.content && !assembled) piece = evt.choices[0].message.content; // final-only message

          if (typeof piece === 'string' && piece.length > 0) {
            assembled += piece;
            try {
              if (typeof renderMarkdownToElement === 'function') { renderMarkdownToElement(assembled, answerEl); }
              else { answerEl.textContent = assembled; }
            } catch (_) { answerEl.textContent = assembled; }
          }
          // Detect token usage if provided by server
          const maybeUsage = evt?.usage || evt?.tldw_usage || evt?.tldw_metadata?.usage;
          if (maybeUsage) {
            usage = maybeUsage;
            const pt = usage.prompt_tokens ?? usage.input_tokens ?? usage.prompt ?? '-';
            const ct = usage.completion_tokens ?? usage.output_tokens ?? usage.completion ?? '-';
            const tt = usage.total_tokens ?? ((Number(pt)||0) + (Number(ct)||0));
            usageEl.textContent = `tokens: prompt=${pt} completion=${ct} total=${tt}`;
          }
          // Capture conversation id from metadata during stream
          try {
            const meta = evt?.tldw_metadata || evt?.metadata || null;
            const cid = meta?.conversation_id || evt?.tldw_conversation_id || evt?.conversation_id || null;
            if (!seenConvId && cid && typeof cid === 'string') seenConvId = cid;
          } catch (_) {}
        } catch (_) { /* ignore */ }
      },
      timeout: 600000
    });

    try {
      await simpleChatStreamHandle.done;
      copyBtn.disabled = false;
      stopBtn.style.display = 'none';
      // Also render a final JSON object into the pre for debugging/repro
      try {
        const finalObj = { message: assembled, usage: usage || null, finished_at: new Date().toISOString() };
        out.textContent = JSON.stringify(finalObj, null, 2);
        endpointHelper.updateCorrelationSnippet(out);
        // Append assistant message to ephemeral history
        if (assembled && assembled.length > 0) {
          try {
            __simpleChatHistory.push({ role: 'assistant', content: assembled });
            if (__simpleChatHistory.length > __simpleChatMaxHistory) {
              __simpleChatHistory = __simpleChatHistory.slice(-__simpleChatMaxHistory);
            }
          } catch (_) {}
        }
        // Persist conversation id for next turn if saving to DB
        try {
          if (requestPayload && requestPayload.save_to_db) {
            if (seenConvId && typeof seenConvId === 'string') __simpleChatConversationId = seenConvId;
          }
        } catch (_) {}
      } catch (_) {}
    } catch (e) {
      stopBtn.style.display = 'none';
      copyBtn.disabled = assembled.length === 0;
      try { endpointHelper.displayError(out, e); } catch(_) { out.textContent = (e && e.message) ? String(e.message) : 'Failed'; }
      endpointHelper.updateCorrelationSnippet(out);
      throw e;
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
        const frag = document.createDocumentFragment();
        const qLower = q.toLowerCase();
        items.forEach((r) => {
          const card = document.createElement('div');
          card.className = 'card';
          card.style.margin = '6px 0';
          card.style.padding = '8px';
          card.style.border = '1px solid var(--color-border)';
          card.style.borderRadius = '6px';
          const title = (r.title || r.metadata?.title || '(untitled)');
          const id = r.id || r.media_id || '';
          const mediaType = r.media_type || r.type || r.metadata?.media_type || '';
          // Build snippet from possible fields
          let snippet = r.snippet || r.content_snippet || r.content || r.text || '';
          if (!snippet && r.highlights && typeof r.highlights === 'string') snippet = r.highlights;
          snippet = String(snippet).slice(0, 400);
          card.innerHTML = `
            <div style="display:flex; justify-content:space-between; align-items:center; gap:8px;">
              <div style="font-weight:600;">${escapeHtml(title)}</div>
              <div class="text-small text-muted">${escapeHtml(mediaType || '')}</div>
            </div>
            <div class="text-small" style="margin-top:6px;">${highlightPlain(snippet, q)}</div>
            <div class="btn-group" style="margin-top:6px;">
              <button class="btn btn-secondary btn-sm" data-open-media="${String(id)}">Open in Media Management</button>
            </div>
          `;
          frag.appendChild(card);
        });
        box.appendChild(frag);
        // Bind open buttons
        box.querySelectorAll('button[data-open-media]').forEach(btn => {
          if (!btn._bound) {
            btn.addEventListener('click', (e) => {
              e.preventDefault();
              const id = btn.getAttribute('data-open-media');
              try {
                const tb = document.querySelector('.top-tab-button[data-toptab="media"]');
                if (tb && window.webUI) {
                  window.webUI.activateTopTab(tb).then(() => {
                    setTimeout(() => {
                      try { const mid = document.getElementById('getMediaItem_media_id'); if (mid) mid.value = String(id || ''); } catch(_){}
                      try { if (typeof window.makeRequest === 'function') window.makeRequest('getMediaItem', 'GET', '/api/v1/media/{media_id}', 'none'); } catch(_){}
                    }, 200);
                  });
                }
              } catch (_) {}
            });
            btn._bound = true;
          }
        });
      }

      // Update pagination controls
      if (infoEl) infoEl.textContent = totalPages > 0 ? `Page ${page} of ${totalPages} (${totalItems})` : '';
      if (prevBtn) prevBtn.disabled = (page <= 1);
      if (nextBtn) nextBtn.disabled = (totalPages && page >= totalPages);
      // Persist search prefs
      try { Utils.saveToStorage('simple-search-prefs', { page, rpp }); } catch(_){}
    } catch (e) {
      try { endpointHelper.displayError(box, e); } catch(_) { box.textContent = (e && e.message) ? String(e.message) : 'Search failed'; }
    } finally {
      Loading.hide(box.parentElement);
    }
  }

  function renderIngestJobsLink(data, domain) {
    const jobBox = document.getElementById('simpleIngest_job');
    if (!jobBox) return;
    try {
      let ids = [];
      if (Array.isArray(data?.job_ids)) ids = data.job_ids.filter(Boolean);
      else if (data?.job_id) ids = [data.job_id];
      else if (Array.isArray(data?.jobs)) ids = data.jobs.map(j => j?.job_id || j?.id).filter(Boolean);
      const linkId = 'simpleIngest_view_jobs';
      const idChips = ids.slice(0, 5).map(j => `<span class="chip">${String(j)}</span>`).join(' ');
      const html = `<div style="margin-top:6px;">${idChips} <a href="#" id="${linkId}">View in Admin → Jobs</a></div>`;
      const wrap = document.createElement('div');
      wrap.innerHTML = html;
      jobBox.appendChild(wrap);
      const a = document.getElementById(linkId);
      if (a && !a._bound) {
        a.addEventListener('click', (e) => { e.preventDefault(); openJobsFiltered(domain || 'media', '', ''); });
        a._bound = true;
      }
    } catch (_) {}
  }

  function escapeHtml(s) {
    try { return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;'); } catch(_) { return s; }
  }
  function highlightPlain(text, query) {
    try {
      const esc = escapeHtml(text || '');
      const q = (query || '').trim();
      if (!q) return esc;
      const re = new RegExp(`(${q.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')})`, 'ig');
      return esc.replace(re, '<mark>$1</mark>');
    } catch (_) { return escapeHtml(text || ''); }
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

    // Enhanced UX bindings (only once)
    if (!__boundEnhancements) {
      __boundEnhancements = true;
      try { bindEnhancedInputs(); } catch(_){}
      try { bindCurlToggles(); } catch(_){}
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
    try { bindSimpleCollapsibles(); } catch(_){}
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

    // Apply saved preferences (media type, scrape method, search rpp/page)
    try {
      const savedMedia = Utils.getFromStorage('simple-media-type');
      if (savedMedia) { const s = document.getElementById('simpleIngest_media_type'); if (s) { s.value = savedMedia; updateSimpleIngestUI(); } }
    } catch (_) {}
    try {
      const savedScrape = Utils.getFromStorage('simple-scrape-method');
      if (savedScrape) { const s = document.getElementById('simpleIngest_scrape_method'); if (s) { s.value = savedScrape; updateSimpleIngestUI(); } }
    } catch (_) {}
    try {
      const prefs = Utils.getFromStorage('simple-search-prefs');
      if (prefs) {
        const rppEl = document.getElementById('simpleSearch_rpp'); if (rppEl && prefs.rpp) rppEl.value = String(prefs.rpp);
        if (prefs.page) __simpleSearchState.page = parseInt(prefs.page, 10) || 1;
      }
      updateSimpleSearchButtonState();
    } catch (_) {}

    // Restore chat stream toggle preference
    try {
      const savedStream = Utils.getFromStorage('simple-chat-stream');
      const st = document.getElementById('simpleChat_stream_toggle');
      if (st && typeof savedStream === 'boolean') st.checked = savedStream;
    } catch (_) {}

    try {
      if (window.SharedChatPortal && typeof window.SharedChatPortal.mount === 'function') {
        window.SharedChatPortal.mount('simple');
      }
    } catch (_) {}
  };

  // Collapsible controls for Simple Landing panels
  function bindSimpleCollapsibles() {
    const ids = ['simpleIngest','simpleChat','simpleSearch'];
    ids.forEach((id) => {
      const header = document.querySelector(`.collapsible-header[data-collapsible="${id}"]`);
      const btn = document.querySelector(`.collapsible-toggle-btn[data-target="${id}"]`);
      const body = document.getElementById(`${id}_body`);
      if (!header || !btn || !body) return;

      // Restore saved state
      try {
        const saved = Utils.getFromStorage(`simple-collapsed-${id}`);
        const collapsed = saved === true; // store booleans only
        setCollapsedState(id, collapsed);
      } catch (_) {}

      if (!header._bound) {
        header.addEventListener('click', (e) => {
          // Avoid double-toggle when clicking the button; button has its own handler
          try {
            const targetEl = e && e.target && e.target.closest ? e.target.closest('.collapsible-toggle-btn') : null;
            if (targetEl) return;
          } catch (_) {}
          toggleCollapsible(id);
        });
        header._bound = true;
      }
      if (!btn._bound) {
        btn.addEventListener('click', (e) => {
          e.preventDefault();
          e.stopPropagation();
          toggleCollapsible(id);
        });
        btn._bound = true;
      }
    });
  }

  function setCollapsedState(id, collapsed) {
    try {
      const header = document.querySelector(`.collapsible-header[data-collapsible="${id}"]`);
      const btn = document.querySelector(`.collapsible-toggle-btn[data-target="${id}"]`);
      const body = document.getElementById(`${id}_body`);
      if (!header || !btn || !body) return;
      body.style.display = collapsed ? 'none' : '';
      header.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
      btn.textContent = collapsed ? 'Show' : 'Hide';
      Utils.saveToStorage(`simple-collapsed-${id}`, collapsed);
    } catch (_) {}
  }

  function toggleCollapsible(id) {
    try {
      const body = document.getElementById(`${id}_body`);
      if (!body) return;
      const collapsed = body.style.display !== 'none' ? true : false;
      setCollapsedState(id, collapsed);
    } catch (_) {}
  }

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
      // Update ingest button disabled state based on current inputs
      updateSimpleIngestButtonState();
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

  // --------------------------
  // UX Enhancements
  // --------------------------
  function updateSimpleIngestButtonState() {
    try {
      const mediaSel = document.getElementById('simpleIngest_media_type');
      const isWeb = mediaSel && mediaSel.value === 'web';
      const url = (document.getElementById('simpleIngest_url')?.value || '').trim();
      const fileChosen = !!(document.getElementById('simpleIngest_file')?.files?.length);
      const webUrl = (document.getElementById('simpleIngest_web_url')?.value || '').trim();
      const btn = document.getElementById('simpleIngest_submit');
      if (btn) btn.disabled = isWeb ? (!webUrl) : (!(url || fileChosen));
    } catch (_) {}
  }

  function updateSimpleChatButtonState() {
    try {
      const msg = (document.getElementById('simpleChat_input')?.value || '').trim();
      const btn = document.getElementById('simpleChat_send');
      if (btn) btn.disabled = !msg;
    } catch (_) {}
  }

  function updateSimpleSearchButtonState() {
    try {
      const q = (document.getElementById('simpleSearch_q')?.value || '').trim();
      const btn = document.getElementById('simpleSearch_run');
      if (btn) btn.disabled = !q;
    } catch (_) {}
  }

  function bindEnhancedInputs() {
    try {
      // Ingest: enable/disable submit
      const inputs = ['simpleIngest_media_type','simpleIngest_url','simpleIngest_file','simpleIngest_web_url'];
      inputs.forEach(id => {
        const el = document.getElementById(id);
        if (el && !el._uxBound) {
          const evt = (el.tagName === 'SELECT' || el.type === 'file') ? 'change' : 'input';
          el.addEventListener(evt, updateSimpleIngestButtonState);
          // Persist preferences for media and scrape method
          if (id === 'simpleIngest_media_type') el.addEventListener('change', () => { try { Utils.saveToStorage('simple-media-type', el.value); } catch(_){} });
          if (id === 'simpleIngest_scrape_method') el.addEventListener('change', () => { try { Utils.saveToStorage('simple-scrape-method', el.value); } catch(_){} });
          el._uxBound = true;
        }
      });
      updateSimpleIngestButtonState();

      // Auto-detect media type based on selected file(s) or URL extension
      const fileInput = document.getElementById('simpleIngest_file');
      if (fileInput && !fileInput._detectBound) {
        fileInput.addEventListener('change', () => {
          try {
            const files = Array.from(fileInput.files || []);
            renderIngestQueue(files);
            if (files.length > 0) {
              const mt = detectMediaTypeFromName(files[0].name || '');
              if (mt) { const sel = document.getElementById('simpleIngest_media_type'); if (sel) sel.value = mt; }
            }
          } catch (_) {}
        });
        fileInput._detectBound = true;
      }
      const urlInput = document.getElementById('simpleIngest_url');
      if (urlInput && !urlInput._detectBound) {
        urlInput.addEventListener('change', () => {
          try { const mt = detectMediaTypeFromName(urlInput.value || ''); if (mt) { const sel = document.getElementById('simpleIngest_media_type'); if (sel) sel.value = mt; } } catch(_){}
        });
        urlInput._detectBound = true;
      }
      const scrapeSel = document.getElementById('simpleIngest_scrape_method');
      if (scrapeSel && !scrapeSel._uxBound) {
        scrapeSel.addEventListener('change', () => {
          updateSimpleIngestUI();
          try { Utils.saveToStorage('simple-scrape-method', scrapeSel.value); } catch(_){}
        });
        scrapeSel._uxBound = true;
      }

      // Chat: enable/disable send, add Cmd/Ctrl+Enter shortcut
      const chatInput = document.getElementById('simpleChat_input');
      if (chatInput && !chatInput._uxBound) {
        chatInput.addEventListener('input', updateSimpleChatButtonState);
        chatInput.addEventListener('keydown', (e) => {
          if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
            e.preventDefault();
            simpleChatSend();
          }
        });
        chatInput._uxBound = true;
      }
      updateSimpleChatButtonState();

      // Persist stream toggle preference
      const streamToggle = document.getElementById('simpleChat_stream_toggle');
      if (streamToggle && !streamToggle._uxBound) {
        streamToggle.addEventListener('change', () => {
          try { Utils.saveToStorage('simple-chat-stream', !!streamToggle.checked); } catch(_){}
        });
        streamToggle._uxBound = true;
      }
      // Reset ephemeral chat thread
      const resetBtn = document.getElementById('simpleChat_reset');
      if (resetBtn && !resetBtn._bound) {
        resetBtn.addEventListener('click', (e) => {
          e.preventDefault();
          try { __simpleChatHistory = []; } catch (_) {}
          try { __simpleChatConversationId = null; } catch (_) {}
          try {
            const ans = document.getElementById('simpleChat_answer'); if (ans) ans.textContent = '';
            const out = document.getElementById('simpleChat_response'); if (out) out.textContent = '---';
          } catch (_) {}
          try { Toast && Toast.info ? Toast.info('Simple Chat thread reset') : 0; } catch (_) {}
        });
        resetBtn._bound = true;
      }

      // Search: enable/disable search, clear button
      const searchQ = document.getElementById('simpleSearch_q');
      if (searchQ && !searchQ._uxBound) {
        searchQ.addEventListener('input', updateSimpleSearchButtonState);
        searchQ._uxBound = true;
      }
      const clearBtn = document.getElementById('simpleSearch_clear');
      if (clearBtn && !clearBtn._bound) {
        clearBtn.addEventListener('click', () => {
          const el = document.getElementById('simpleSearch_q');
          if (el) el.value = '';
          updateSimpleSearchButtonState();
          const box = document.getElementById('simpleSearch_results');
          if (box) box.innerHTML = '';
          const info = document.getElementById('simpleSearch_pageinfo');
          if (info) info.textContent = '';
          const prevBtn = document.getElementById('simpleSearch_prev');
          const nextBtn = document.getElementById('simpleSearch_next');
          if (prevBtn) prevBtn.disabled = true;
          if (nextBtn) nextBtn.disabled = true;
        });
        clearBtn._bound = true;
      }
      updateSimpleSearchButtonState();

      // Persist RPP when changed
      const rppEl = document.getElementById('simpleSearch_rpp');
      if (rppEl && !rppEl._uxBound) {
        rppEl.addEventListener('change', () => {
          try { __simpleSearchState.rpp = Math.max(1, Math.min(100, parseInt(rppEl.value || '10', 10))); Utils.saveToStorage('simple-search-prefs', { page: __simpleSearchState.page, rpp: __simpleSearchState.rpp }); } catch(_){}
        });
        rppEl._uxBound = true;
      }

      // Paste-from-clipboard for ingest URLs
      const pasteBtn = document.getElementById('simpleIngest_paste_url');
      if (pasteBtn && !pasteBtn._bound) {
        pasteBtn.addEventListener('click', async (e) => {
          e.preventDefault();
          try {
            const text = await navigator.clipboard.readText();
            const el = document.getElementById('simpleIngest_url');
            if (el) { el.value = text || ''; el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); }
          } catch (_) {
            Toast && Toast.warning ? Toast.warning('Clipboard not available') : 0;
          }
        });
        pasteBtn._bound = true;
      }
      const pasteWebBtn = document.getElementById('simpleIngest_paste_web_url');
      if (pasteWebBtn && !pasteWebBtn._bound) {
        pasteWebBtn.addEventListener('click', async (e) => {
          e.preventDefault();
          try {
            const text = await navigator.clipboard.readText();
            const el = document.getElementById('simpleIngest_web_url');
            if (el) { el.value = text || ''; el.dispatchEvent(new Event('input')); el.dispatchEvent(new Event('change')); }
          } catch (_) {
            Toast && Toast.warning ? Toast.warning('Clipboard not available') : 0;
          }
        });
        pasteWebBtn._bound = true;
      }
    } catch (_) {}
  }

  function bindCurlToggles() {
    try {
      // Ingest cURL
      const btn = document.getElementById('simpleIngest_show_curl');
      if (btn && !btn._bound) {
        btn.addEventListener('click', () => {
          try {
            const mediaType = document.getElementById('simpleIngest_media_type')?.value || 'document';
            const url = (document.getElementById('simpleIngest_url')?.value || '').trim();
            const fileList = document.getElementById('simpleIngest_file')?.files || null;
            const model = document.getElementById('simpleIngest_model')?.value || '';
            const performAnalysis = !!document.getElementById('simpleIngest_perform_analysis')?.checked;
            const doChunk = !!document.getElementById('simpleIngest_chunking')?.checked;
            const isWeb = (mediaType === 'web');
            const webUrl = (document.getElementById('simpleIngest_web_url')?.value || '').trim();
            const seedPrompt = (document.getElementById('simpleIngest_seed')?.value || '').trim();
            const systemPrompt = (document.getElementById('simpleIngest_system')?.value || '').trim();
            let method = 'POST';
            let path = '/api/v1/media/add';
            let options = {};
            if (!isWeb) {
              const fd = new FormData();
              fd.append('media_type', mediaType);
              if (url) fd.append('urls', url);
              if (fileList && fileList.length) { Array.from(fileList).forEach(f => fd.append('files', f)); }
              if (model) fd.append('api_name', model);
              fd.append('perform_analysis', String(performAnalysis));
              fd.append('perform_chunking', String(doChunk));
              if (seedPrompt) fd.append('custom_prompt', seedPrompt);
              if (systemPrompt) fd.append('system_prompt', systemPrompt);
              fd.append('timestamp_option', 'true');
              fd.append('chunk_size', '500');
              fd.append('chunk_overlap', '200');
              options = { body: fd };
            } else {
              path = '/api/v1/media/ingest-web-content';
              const methodSel = document.getElementById('simpleIngest_scrape_method');
              const methodVal = methodSel ? methodSel.value : 'individual';
              const body = {
                urls: webUrl ? [webUrl] : [],
                scrape_method: methodVal,
                perform_analysis: performAnalysis,
                custom_prompt: seedPrompt || undefined,
                system_prompt: systemPrompt || undefined,
                api_name: model || undefined,
                perform_chunking: doChunk
              };
              if (methodVal === 'url_level') {
                const lvl = parseInt(document.getElementById('simpleIngest_url_level')?.value || '2', 10);
                if (!isNaN(lvl) && lvl > 0) body.url_level = lvl;
              } else if (methodVal === 'recursive_scraping') {
                const maxPages = parseInt(document.getElementById('simpleIngest_max_pages')?.value || '10', 10);
                const maxDepth = parseInt(document.getElementById('simpleIngest_max_depth')?.value || '3', 10);
                if (!isNaN(maxPages) && maxPages > 0) body.max_pages = maxPages;
                if (!isNaN(maxDepth) && maxDepth > 0) body.max_depth = maxDepth;
              }
              const includeExternal = !!document.getElementById('simpleIngest_include_external')?.checked;
              const crawlStrategy = (document.getElementById('simpleIngest_crawl_strategy')?.value || '').trim();
              if (includeExternal) body.include_external = true;
              if (crawlStrategy) body.crawl_strategy = crawlStrategy;
              options = { body };
            }
            const curl = (typeof apiClient.generateCurlV2 === 'function' ? apiClient.generateCurlV2(method, path, options) : apiClient.generateCurl(method, path, options));
            const curlEl = document.getElementById('simpleIngest_curl');
            if (curlEl) {
              curlEl.textContent = curl;
              curlEl.style.display = (curlEl.style.display === 'none') ? 'block' : 'none';
              ensureCurlCopyAndNote(curlEl, 'simpleIngest');
            }
          } catch (e) {
            const curlEl = document.getElementById('simpleIngest_curl');
            if (curlEl) { curlEl.textContent = `Error generating cURL: ${e.message}`; curlEl.style.display = 'block'; }
          }
        });
        btn._bound = true;
      }

      // Chat cURL
      const chatBtn = document.getElementById('simpleChat_show_curl');
      if (chatBtn && !chatBtn._bound) {
        chatBtn.addEventListener('click', () => {
          try {
            const model = document.getElementById('simpleChat_model')?.value || '';
            const msg = (document.getElementById('simpleChat_input')?.value || '').trim() || 'Hello';
            const body = { messages: [{ role: 'user', content: msg }] };
            if (model) body.model = model;
            // Include conversation_id if we have one (prevents creating new server threads)
            try { if (__simpleChatConversationId) body.conversation_id = __simpleChatConversationId; } catch (_) {}
            // Mirror Save to DB toggle to reflect persistence intent
            try { const saveEl = document.getElementById('simpleChat_save'); if (saveEl && saveEl.checked) body.save_to_db = true; } catch (_) {}
      const chatEp = (apiClient.endpoint('chat','completions') || '/api/v1/chat/completions');
      const curl = apiClient.generateCurlV2('POST', chatEp, { body });
            const curlEl = document.getElementById('simpleChat_curl');
            if (curlEl) {
              curlEl.textContent = curl;
              curlEl.style.display = (curlEl.style.display === 'none') ? 'block' : 'none';
              ensureCurlCopyAndNote(curlEl, 'simpleChat');
            }
          } catch (e) {
            const curlEl = document.getElementById('simpleChat_curl');
            if (curlEl) { curlEl.textContent = `Error generating cURL: ${e.message}`; curlEl.style.display = 'block'; }
          }
        });
        chatBtn._bound = true;
      }

      // Search cURL
      const searchBtn = document.getElementById('simpleSearch_show_curl');
      if (searchBtn && !searchBtn._bound) {
        searchBtn.addEventListener('click', () => {
          try {
            const q = (document.getElementById('simpleSearch_q')?.value || '').trim() || 'test';
            const rpp = Math.max(1, Math.min(100, parseInt((document.getElementById('simpleSearch_rpp')?.value || '10'), 10)));
            const page = __simpleSearchState.page || 1;
            const body = { query: q, fields: ['title','content'], sort_by: 'relevance' };
            const curl = apiClient.generateCurlV2('POST', '/api/v1/media/search', { body, query: { page, results_per_page: rpp } });
            const curlEl = document.getElementById('simpleSearch_curl');
            if (curlEl) {
              curlEl.textContent = curl;
              curlEl.style.display = (curlEl.style.display === 'none') ? 'block' : 'none';
              ensureCurlCopyAndNote(curlEl, 'simpleSearch');
            }
          } catch (e) {
            const curlEl = document.getElementById('simpleSearch_curl');
            if (curlEl) { curlEl.textContent = `Error generating cURL: ${e.message}`; curlEl.style.display = 'block'; }
          }
        });
        searchBtn._bound = true;
      }
    } catch (_) {}
  }

  function ensureCurlCopyAndNote(curlEl, prefix) {
    try {
      // Masking note behavior mirrors endpointHelper
      const noteId = `${prefix}_curl_note`;
      let note = document.getElementById(noteId);
      if (!note) {
        note = document.createElement('div');
        note.id = noteId;
        note.className = 'text-muted';
        note.style.fontSize = '0.85em';
        note.style.margin = '6px 0 0 0';
        curlEl.parentNode.insertBefore(note, curlEl.nextSibling);
      }
      if (apiClient && apiClient.token && !apiClient.includeTokenInCurl) {
        note.textContent = "Note: Token masked in cURL. Use Global Settings toggle to include it, or replace [REDACTED] with your token.";
        note.style.display = 'block';
      } else {
        note.textContent = '';
        note.style.display = 'none';
      }
      // Copy button
      if (!curlEl.nextElementSibling || !curlEl.nextElementSibling.classList.contains('copy-curl')) {
        const copyBtn = document.createElement('button');
        copyBtn.className = 'btn btn-sm btn-secondary copy-curl';
        copyBtn.textContent = 'Copy cURL';
        copyBtn.onclick = () => {
          Utils.copyToClipboard(curlEl.textContent || '');
          Toast && Toast.success ? Toast.success('cURL command copied to clipboard') : 0;
        };
        curlEl.parentNode.insertBefore(copyBtn, curlEl.nextSibling);
      }
    } catch (_) {}
  }

  // Helpers
  function detectMediaTypeFromName(name) {
    try {
      const lower = String(name || '').toLowerCase();
      if (/(\.pdf)(?:$|[?#])/.test(lower)) return 'pdf';
      if (/(\.epub)(?:$|[?#])/.test(lower)) return 'ebook';
      if (/(\.mp4|\.mov|\.mkv|\.webm)(?:$|[?#])/.test(lower)) return 'video';
      if (/(\.mp3|\.wav|\.m4a|\.flac|\.ogg)(?:$|[?#])/.test(lower)) return 'audio';
      if (/(\.html?|\.md|\.markdown|\.txt|\.docx?|\.rtf)(?:$|[?#])/.test(lower)) return 'document';
      return '';
    } catch (_) { return ''; }
  }

  function renderIngestQueue(files) {
    try {
      const box = document.getElementById('simpleIngest_queue');
      if (!box) return;
      const arr = Array.isArray(files) ? files : [];
      if (!arr.length) { box.style.display = 'none'; box.innerHTML = ''; return; }
      const items = arr.slice(0, 50).map((f) => {
        const safeName = escapeHtml(f && typeof f.name === 'string' ? f.name : String(f?.name ?? ''));
        return `<span class="chip" style="margin:2px;">${safeName}</span>`;
      }).join(' ');
      box.innerHTML = `<div><strong>Files:</strong> ${items}${arr.length > 50 ? ' …' : ''}</div>`;
      box.style.display = '';
    } catch (_) {}
  }

  function openJobsFiltered(domain, queue, jobType) {
    try {
      const btn = document.querySelector('.top-tab-button[data-toptab="admin"]');
      if (!btn || !window.webUI) return;
      window.webUI.activateTopTab(btn).then(() => {
        setTimeout(() => {
          const sub = document.querySelector('#admin-subtabs .sub-tab-button[data-content-id="tabAdminJobs"]');
          if (sub) {
            window.webUI.activateSubTab(sub).then(() => {
              setTimeout(() => { try { adminApplyJobsFilter(domain || '', queue || '', jobType || ''); } catch (_) {} }, 200);
            });
          }
        }, 150);
      });
    } catch (_) {}
  }

})();
