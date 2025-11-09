// Metrics tab logic (ported from inline scripts)
(function(){
  let metricsAutoRefresh = null;
  let jobsStatsTimer = null;
  let orchestratorTimer = null;
  let orchestratorPrev = null;
  let orchestratorSSEController = null;
  let orchestratorSSEEnabled = false;
  window.orchestratorHistory = window.orchestratorHistory || { chunking: [], embedding: [], storage: [] };

  async function refreshMetrics(){
    try{
      const base = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
      const res = await fetch(`${base}/api/v1/metrics`);
      const data = await res.json();
      const byId = (id, val, post='') => { const el = document.getElementById(id); if (el) el.textContent = (val ?? '--') + post; };
      byId('metric-api-health', data.health || 'Healthy');
      byId('metric-request-rate', data.request_rate || '0');
      byId('metric-response-time', data.response_time_p50 || '0');
      byId('metric-active-connections', data.active_connections || '0');
      byId('metric-error-rate', data.error_rate || '0');
      byId('metric-cpu-usage', ((data.cpu_usage||0).toFixed ? (data.cpu_usage||0).toFixed(1) : (data.cpu_usage||0)) + '%');
      byId('metric-memory-usage', (data.memory_mb||0).toFixed ? (data.memory_mb||0).toFixed(0) : (data.memory_mb||0));
      byId('metric-database-size', (data.database_mb||0).toFixed ? (data.database_mb||0).toFixed(1) : (data.database_mb||0));
    }catch(e){ console.debug('Failed to fetch metrics', e); }
    try { await refreshJobsOverview(); } catch(_){}
  }

  function startAutoRefresh(){
    try{ if (metricsAutoRefresh) clearInterval(metricsAutoRefresh); }catch(_){ }
    refreshMetrics();
    metricsAutoRefresh = setInterval(refreshMetrics, 5000);
    try { if (window.Toast) Toast.success('Auto-refresh enabled (5 seconds)'); } catch(_){ }
  }
  function stopAutoRefresh(){
    if (metricsAutoRefresh) { clearInterval(metricsAutoRefresh); metricsAutoRefresh = null; }
    try { if (window.Toast) Toast.info('Auto-refresh stopped'); } catch(_){ }
  }

  function setOrchestratorFallbackBadge(show, text){
    const el = document.getElementById('orchestrator_fallback_badge');
    const hint = document.getElementById('orchestrator_fallback_hint');
    if (!el) return;
    if (show){ if (text) el.textContent = text; el.style.display='inline-block'; if (hint) hint.style.display='inline-block'; }
    else { el.style.display='none'; if (hint) hint.style.display='none'; }
  }
  function setOrchestratorSSEStatus(connected){
    const el = document.getElementById('orchestrator_sse_status'); if (!el) return;
    if (connected){ el.classList.remove('badge-secondary'); el.classList.add('badge-success'); el.textContent='live'; }
    else { el.classList.remove('badge-success'); el.classList.add('badge-secondary'); el.textContent='disconnected'; }
  }
  function updateOrchestratorFromPayload(res){
    const q = (res && res.queues) || {}; const d = (res && res.dlq) || {}; const s = (res && res.stages) || {}; const flags=(res&&res.flags)||{}; const ages=(res&&res.ages)||{};
    const isZeroed = (!Object.keys(q).length && !Object.keys(d).length && !Object.keys(s).length && !Object.keys(flags).length && !Object.keys(ages).length);
    setOrchestratorFallbackBadge(isZeroed, 'fallback');
    const stages = ['chunking','embedding','storage'];
    const now = (res && res.ts) ? Number(res.ts) : (Date.now()/1000.0);
    const prev = orchestratorPrev;
    const rows = stages.map(st => {
      const qn = `embeddings:${st}`; const dq = `embeddings:${st}:dlq`;
      const qdepth = q[qn] || 0; const ddepth = d[dq] || 0;
      const ss = s[st] || { processed: 0, failed: 0 };
      let dlqRate = 0, procRate = 0, failRate = 0;
      if (prev && prev.stages && prev.stages[st]){
        const dt = Math.max(1, now - prev.ts);
        dlqRate = (ddepth - prev.stages[st].dlq) / dt;
        procRate = (ss.processed - prev.stages[st].processed) / dt;
        failRate = (ss.failed - prev.stages[st].failed) / dt;
      }
      // Short history for dlq sparkline
      try{
        const histKey = st; const h = window.orchestratorHistory[histKey] || []; h.push(ddepth); while (h.length > 40) h.shift(); window.orchestratorHistory[histKey] = h;
      }catch(_){ }
      return { st, qdepth, ddepth, ss, dlqRate, procRate, failRate };
    });
    const tb = document.getElementById('orchestrator_tableBody');
    if (!tb) return;
    tb.innerHTML = rows.map(({st,qdepth,ddepth,ss,dlqRate,procRate,failRate}) => `
      <tr>
        <td>${st}</td>
        <td>${qdepth}</td>
        <td>${ddepth}</td>
        <td><svg id="spark-${st}" width="120" height="24" viewBox="0 0 120 24"></svg></td>
        <td>${dlqRate.toFixed(2)}</td>
        <td>${ss.processed}</td>
        <td>${procRate.toFixed(2)}</td>
        <td>${ss.failed}</td>
        <td>${failRate.toFixed(2)}</td>
      </tr>`).join('') || '<tr><td colspan="8" class="text-muted">No data</td></tr>';
    // render sparklines
    try {
      const render = (elId, data) => { const svg = document.getElementById(elId); if (!svg || !data || data.length<2) return; const w=120,h=24,p=1; const min=Math.min.apply(null,data); const max=Math.max.apply(null,data); const range=Math.max(1,max-min); const step=(w-p*2)/(data.length-1); let dpath=''; data.forEach((v,i)=>{ const x=p+i*step; const y=h-p-((v-min)/range)*(h-p*2); dpath += (i===0?'M':'L') + x.toFixed(2) + ' ' + y.toFixed(2) + ' '; }); svg.innerHTML = `<path d="${dpath}" fill="none" stroke="currentColor" stroke-width="1" />`; };
      render('spark-chunking', window.orchestratorHistory.chunking);
      render('spark-embedding', window.orchestratorHistory.embedding);
      render('spark-storage', window.orchestratorHistory.storage);
    } catch(_){ }
    orchestratorPrev = { ts: now, stages: { chunking: { dlq: d['embeddings:chunking:dlq']||0, processed:(s['chunking']||{}).processed||0, failed:(s['chunking']||{}).failed||0 }, embedding: { dlq: d['embeddings:embedding:dlq']||0, processed:(s['embedding']||{}).processed||0, failed:(s['embedding']||{}).failed||0 }, storage: { dlq: d['embeddings:storage:dlq']||0, processed:(s['storage']||{}).processed||0, failed:(s['storage']||{}).failed||0 } } };
  }
  function startOrchestratorAutoRefresh(){ stopOrchestratorAutoRefresh(); fetchOrchestratorSummary(); orchestratorTimer = setInterval(fetchOrchestratorSummary, 10000); try{ localStorage.setItem('orchestrator-auto-refresh','true'); }catch(_){}}
  function stopOrchestratorAutoRefresh(){ if (orchestratorTimer){ clearInterval(orchestratorTimer); orchestratorTimer=null; } try{ localStorage.setItem('orchestrator-auto-refresh','false'); }catch(_){}}
  async function fetchOrchestratorSummary(){
    try{
      const res = await apiClient.makeRequest('GET','/api/v1/embeddings/orchestrator/summary');
      if (res) updateOrchestratorFromPayload(res);
    }catch(e){ const tb = document.getElementById('orchestrator_tableBody'); if (tb) tb.innerHTML = `<tr><td colspan="8">${Utils.escapeHtml(JSON.stringify(e.response || e))}</td></tr>`; }
  }
  async function startOrchestratorSSE(){
    try{
      const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
      const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';
      orchestratorSSEController = new AbortController();
      const res = await fetch(`${baseUrl}/api/v1/embeddings/orchestrator/events`, { method:'GET', headers: { ...(token?{ 'Authorization': `Bearer ${token}` }: {}) }, signal: orchestratorSSEController.signal });
      orchestratorSSEEnabled = true; setOrchestratorSSEStatus(true);
      await apiClient.handleStreamingResponse(res, (chunk) => { if (!orchestratorSSEEnabled) return; if (chunk && !chunk.error) updateOrchestratorFromPayload(chunk); });
    }catch(_){ /* ignore abort/network */ }
  }
  function stopOrchestratorSSE(){ orchestratorSSEEnabled=false; if (orchestratorSSEController){ try{ orchestratorSSEController.abort(); }catch(_){ } orchestratorSSEController=null; } setOrchestratorSSEStatus(false); }
  function toggleOrchestratorSSE(checked){ if (checked){ stopOrchestratorAutoRefresh(); startOrchestratorSSE(); } else { stopOrchestratorSSE(); } try{ localStorage.setItem('orchestrator-sse-enabled', checked? '1' : '0'); }catch(_){}}

  async function fetchJobsStats(){
    const domain = (document.getElementById('jobsStats_domain')||{}).value || '';
    const queue = (document.getElementById('jobsStats_queue')||{}).value || '';
    const jobType = (document.getElementById('jobsStats_jobType')||{}).value || '';
    const query = {}; if (domain) query.domain = domain; if (queue) query.queue = queue; if (jobType) query.job_type = jobType;
    const tbody = document.getElementById('jobsStats_tableBody'); if (!tbody) return;
    try{
      Loading.show(tbody.parentElement, 'Loading jobs stats...');
      const res = await apiClient.makeRequest('GET','/api/v1/jobs/stats',{ query });
      const data = Array.isArray(res) ? res : (res?.data || []);
      tbody.innerHTML = '';
      if (!data.length){ tbody.innerHTML = '<tr><td colspan="5" class="text-muted">No data</td></tr>'; return; }
      for (const row of data){ const tr = document.createElement('tr'); tr.innerHTML = `<td>${row.domain??''}</td><td>${row.queue??''}</td><td>${row.job_type??''}</td><td>${row.queued??0}</td><td>${row.processing??0}</td>`; tbody.appendChild(tr); }
    }catch(e){ tbody.innerHTML = `<tr><td colspan="5" class="text-error">${(e && e.message) || 'Failed to load'}</td></tr>`; }
    finally{ Loading.hide(tbody.parentElement); }
  }
  function startJobsStatsAutoRefresh(){ stopJobsStatsAutoRefresh(); jobsStatsTimer = setInterval(fetchJobsStats, 10000); fetchJobsStats(); }
  function stopJobsStatsAutoRefresh(){ if (jobsStatsTimer){ clearInterval(jobsStatsTimer); jobsStatsTimer = null; } }

  async function refreshJobsOverview(){
    try {
      const res = await apiClient.makeRequest('GET','/api/v1/jobs/stats',{ query:{} });
      const data = Array.isArray(res) ? res : (res?.data || []);
      const ul = document.getElementById('metric-jobs-overview'); if (!ul) return; ul.innerHTML = '';
      if (!data.length){ ul.innerHTML = '<li class="text-muted">No data</li>'; return; }
      const scored = data.map(r => ({ domain:r.domain||'', queue:r.queue||'', job_type:r.job_type||'', queued:r.queued||0, processing:r.processing||0 })).map(r => ({ ...r, score:(r.queued + r.processing) }));
      scored.sort((a,b)=>b.score-a.score); const top = scored.slice(0,3);
      for (const row of top){ const li=document.createElement('li'); const a=document.createElement('a'); a.href='#'; a.textContent=`${row.domain}/${row.queue}/${row.job_type} - queued: ${row.queued}, processing: ${row.processing}`; a.addEventListener('click',(ev)=>{ ev.preventDefault(); openAdminJobsWithFilter(row.domain,row.queue,row.job_type); }); li.appendChild(a); ul.appendChild(li); }
      if (!ul.children.length) ul.innerHTML = '<li class="text-muted">No active queues</li>';
    }catch(e){ const ul = document.getElementById('metric-jobs-overview'); if (ul) ul.innerHTML = '<li class="text-error">Jobs overview unavailable</li>'; }
  }
  function openAdminJobsWithFilter(domain, queue, jobType){
    try{ const topAdminBtn = document.querySelector('.top-tab-button[data-toptab="admin"]'); if (topAdminBtn) topAdminBtn.click(); setTimeout(()=>{ const adminJobsBtn = document.querySelector('#admin-subtabs .sub-tab-button[data-content-id="tabAdminJobs"]'); if (adminJobsBtn) adminJobsBtn.click(); let attempts=0; const tryApply=()=>{ const d=document.getElementById('adminJobs_domain'); const q=document.getElementById('adminJobs_queue'); const jt=document.getElementById('adminJobs_jobType'); if (d&&q&&jt){ d.value=domain||''; q.value=queue||''; jt.value=jobType||''; const topbar=document.getElementById('adminJobs_topbar'); if (topbar){ const desc=`${domain||'(any)'}/${queue||'(any)'}/${jobType||'(any)'}`; topbar.textContent = `Filter applied: ${desc}`; } try{ if (typeof adminJobsSaveFilters==='function') adminJobsSaveFilters(); }catch(_){ } try{ if (typeof updateSavedFiltersBadge==='function') updateSavedFiltersBadge({ domain, queue, job_type: jobType }); }catch(_){ } if (typeof adminFetchJobsStats==='function') adminFetchJobsStats(); return true; } return false; }; const interval=setInterval(()=>{ attempts += 1; if (tryApply() || attempts > 20) clearInterval(interval); }, 100); }, 100); }catch(e){ console.warn('Failed to navigate to Admin → Jobs with filter', e); }
  }

  function runMetricsAnalysis(){
    const timeRange = (document.getElementById('metricsAnalysis_timeRange')||{}).value || '';
    const metric = (document.getElementById('metricsAnalysis_metric')||{}).value || '';
    const aggregation = (document.getElementById('metricsAnalysis_aggregation')||{}).value || '';
    const chartContainer = document.getElementById('metricsAnalysis_chart'); if (chartContainer) chartContainer.innerHTML = `
      <div class="chart-placeholder">
        <p>Chart: ${metric} over ${timeRange} (${aggregation})</p>
        <div class="chart-bars">
          <div class="chart-bar" style="height: 60%;"></div>
          <div class="chart-bar" style="height: 80%;"></div>
          <div class="chart-bar" style="height: 45%;"></div>
          <div class="chart-bar" style="height: 90%;"></div>
          <div class="chart-bar" style="height: 70%;"></div>
          <div class="chart-bar" style="height: 85%;"></div>
          <div class="chart-bar" style="height: 50%;"></div>
        </div>
      </div>`;
    const insights = document.getElementById('metricsAnalysis_insights'); if (insights) insights.innerHTML = `
      <div class="insights">
        <h4>Analysis Insights</h4>
        <ul>
          <li>Peak ${metric} occurred at 14:30 UTC</li>
          <li>Average ${aggregation} value: 234ms</li>
          <li>Detected anomaly at 12:15 UTC (3σ deviation)</li>
          <li>Trend: Increasing by 12% over selected period</li>
        </ul>
      </div>`;
  }
  function saveMetricsAlerts(){ try{ if (window.Toast) Toast.success('Alerts configuration saved'); }catch(_){ } }
  function openMonitoringDocs(ev){ try{ if (ev && ev.preventDefault) ev.preventDefault(); }catch(_){ } const candidates=[ window.location.origin + '/monitoring/README.md', window.location.origin + '/webui/monitoring/README.md' ]; const gh='https://github.com/rmusser01/tldw_server/blob/main/monitoring/README.md'; try{ window.open(candidates[0],'_blank'); }catch(_){ } try{ alert('Monitoring docs are available at monitoring/README.md in the repo.\nIf browsing online, see: ' + gh + '\nPrometheus text metrics: /api/v1/metrics/text'); }catch(_){ } }

  function bindExecEndpointButtons(root){
    const scope = root || document;
    scope.querySelectorAll('button[data-action="exec-endpoint"]').forEach((btn)=>{
      if (btn._bound) return; btn._bound = true;
      btn.addEventListener('click', async (e)=>{
        e.preventDefault();
        const id = btn.getAttribute('data-id');
        const method = btn.getAttribute('data-method') || 'GET';
        const path = btn.getAttribute('data-path');
        const bodyType = btn.getAttribute('data-body') || 'none';
        const confirmMsg = btn.getAttribute('data-confirm') || '';
        if (confirmMsg && !confirm(confirmMsg)) return;
        const responseEl = document.getElementById(`${id}_response`);
        const curlEl = document.getElementById(`${id}_curl`);
        try{
          if (responseEl) responseEl.textContent = '';
          const { body, query, processedPath } = window.EndpointHelper && EndpointHelper.buildRequest ? EndpointHelper.buildRequest(id, path, bodyType) : (function(){
            const build = { body: null, query: {}, processedPath: path };
            if (bodyType === 'json'){ const ta = document.getElementById(`${id}_payload`); build.body = ta && ta.value ? JSON.parse(ta.value) : {}; }
            if (bodyType === 'query'){ /* collect known query inputs if present */ }
            return build;})()
          const resp = await apiClient.makeRequest(method, (processedPath || path), { body, query });
          if (responseEl) responseEl.textContent = (typeof resp === 'string') ? resp : JSON.stringify(resp,null,2);
          if (window.Toast) Toast.success('Request completed successfully');
        }catch(err){ if (responseEl) responseEl.textContent = `Error: ${err.message}`; if (window.Toast) Toast.error(`Request failed: ${err.message}`); }
      });
    });
  }

  function initializeMetricsTab(contentId){
    try{
      // Dashboard controls
      const r = document.getElementById('metrics-refresh'); if (r && !r._b){ r._b=true; r.addEventListener('click', refreshMetrics); }
      const as = document.getElementById('metrics-auto-start'); if (as && !as._b){ as._b=true; as.addEventListener('click', startAutoRefresh); }
      const ao = document.getElementById('metrics-auto-stop'); if (ao && !ao._b){ ao._b=true; ao.addEventListener('click', stopAutoRefresh); }

      // Orchestrator controls
      const or = document.getElementById('orchestrator-refresh'); if (or && !or._b){ or._b=true; or.addEventListener('click', fetchOrchestratorSummary); }
      const oas = document.getElementById('orchestrator-auto-start'); if (oas && !oas._b){ oas._b=true; oas.addEventListener('click', startOrchestratorAutoRefresh); }
      const oao = document.getElementById('orchestrator-auto-stop'); if (oao && !oao._b){ oao._b=true; oao.addEventListener('click', stopOrchestratorAutoRefresh); }
      const sse = document.getElementById('orchestrator_live_sse'); if (sse && !sse._b){ sse._b=true; sse.addEventListener('change', ()=> toggleOrchestratorSSE(!!sse.checked)); }
      const docLink = document.querySelector('[data-action="open-monitoring-docs"]'); if (docLink && !docLink._b){ docLink._b=true; docLink.addEventListener('click', openMonitoringDocs); }

      // Jobs controls
      const jr = document.getElementById('jobsStats_refresh'); if (jr && !jr._b){ jr._b=true; jr.addEventListener('click', fetchJobsStats); }
      const jas = document.getElementById('jobsStats_auto_start'); if (jas && !jas._b){ jas._b=true; jas.addEventListener('click', startJobsStatsAutoRefresh); }
      const jao = document.getElementById('jobsStats_auto_stop'); if (jao && !jao._b){ jao._b=true; jao.addEventListener('click', stopJobsStatsAutoRefresh); }

      // Analysis & alerts
      const runBtn = document.getElementById('metricsAnalysis_run'); if (runBtn && !runBtn._b){ runBtn._b=true; runBtn.addEventListener('click', runMetricsAnalysis); }
      const saveBtn = document.getElementById('metricsAlerts_save'); if (saveBtn && !saveBtn._b){ saveBtn._b=true; saveBtn.addEventListener('click', saveMetricsAlerts); }

      // Bind endpoint exec buttons
      bindExecEndpointButtons(document);

      // On first open of dashboard, do an initial refresh
      if (contentId === 'tabMetricsDashboard') refreshMetrics();
      // Restore Orchestrator prefs
      try{ const saved = String(localStorage.getItem('orchestrator-auto-refresh')||''); if (saved === 'true') startOrchestratorAutoRefresh(); }catch(_){ }
      try{ const savedSSE = String(localStorage.getItem('orchestrator-sse-enabled')||''); if (savedSSE === '1' && sse){ sse.checked = true; stopOrchestratorAutoRefresh(); startOrchestratorSSE(); } }catch(_){ }
    }catch(e){ console.debug('initializeMetricsTab failed', e); }
  }

  window.initializeMetricsTab = initializeMetricsTab;
  // expose functions for reuse if needed
  window.refreshMetrics = refreshMetrics;
  window.startAutoRefresh = startAutoRefresh;
  window.stopAutoRefresh = stopAutoRefresh;
})();

