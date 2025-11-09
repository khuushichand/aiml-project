// Workflows tab: bind UI without inline handlers
(function(){
  function callIf(fnName, ...args){ try{ if (typeof window[fnName] === 'function') return window[fnName](...args); }catch(_){ } console.warn(`[workflows] Missing handler: ${fnName}`); }

  function setSafeHTML(el, html){ try{ if (window.SafeDOM && typeof window.SafeDOM.setHTML === 'function'){ window.SafeDOM.setHTML(el, html); } else { el.innerHTML = html; } }catch(e){ if (el) el.textContent = html; }
  }

  function initializeWorkflowsTab(contentId){
    try{
      const root = document.getElementById(contentId) || document;

      // Config + step types
      const cfgBtn = document.getElementById('wfCfg_refresh'); if (cfgBtn && !cfgBtn._b){ cfgBtn._b=true; cfgBtn.addEventListener('click', ()=>callIf('wfLoadConfig')); }
      const stepBtn = document.getElementById('wfStepTypes_btn'); if (stepBtn && !stepBtn._b){ stepBtn._b=true; stepBtn.addEventListener('click', ()=>callIf('wfGetStepTypes')); }

      // Featured template buttons
      const featured = document.getElementById('wfTpl_featured');
      if (featured && !featured._b){
        featured._b = true;
        featured.addEventListener('click',(ev)=>{
          const btn = ev.target && ev.target.closest('button[data-action]'); if (!btn) return;
          const t = btn.getAttribute('data-template') || '';
          const act = btn.getAttribute('data-action');
          if (act === 'wfTpl-load') callIf('wfTplLoadByName', t);
          else if (act === 'wfTpl-run') callIf('wfTplRunByName', t);
          else if (act === 'wfTpl-runwatch') callIf('wfTplRunWatchByName', t);
        });
      }

      // Search input
      const q = document.getElementById('wfTpl_search');
      if (q && !q._b){
        q._b = true;
        q.addEventListener('input', ()=>callIf('wfTplQueryChanged'));
        q.addEventListener('keydown', (e)=>{ if (e.key==='Enter'){ e.preventDefault(); callIf('wfTplLoadList'); } });
      }
      const searchBtn = document.getElementById('wfTpl_search_btn'); if (searchBtn && !searchBtn._b){ searchBtn._b=true; searchBtn.addEventListener('click', ()=>callIf('wfTplLoadList')); }
      const applyBtn = document.getElementById('wfTpl_apply_btn'); if (applyBtn && !applyBtn._b){ applyBtn._b=true; applyBtn.addEventListener('click', ()=>callIf('wfTplApply')); }
      const insertBtn = document.getElementById('wfTpl_insert_btn'); if (insertBtn && !insertBtn._b){ insertBtn._b=true; insertBtn.addEventListener('click', ()=>callIf('wfTplInsert')); }
      const runBtn = document.getElementById('wfTpl_run_btn'); if (runBtn && !runBtn._b){ runBtn._b=true; runBtn.addEventListener('click', ()=>callIf('wfTplRun')); }
      const runWatchBtn = document.getElementById('wfTpl_runwatch_btn'); if (runWatchBtn && !runWatchBtn._b){ runWatchBtn._b=true; runWatchBtn.addEventListener('click', ()=>callIf('wfTplRunWatch')); }
      const saveAsBtn = document.getElementById('wfTpl_saveas_btn'); if (saveAsBtn && !saveAsBtn._b){ saveAsBtn._b=true; saveAsBtn.addEventListener('click', ()=>callIf('wfTplSaveAsNew')); }
      const delLocalBtn = document.getElementById('wfTpl_delete_local_btn'); if (delLocalBtn && !delLocalBtn._b){ delLocalBtn._b=true; delLocalBtn.addEventListener('click', ()=>callIf('wfTplDeleteLocal')); }
      const copyCurlBtn = document.getElementById('wfTpl_copy_curl_btn'); if (copyCurlBtn && !copyCurlBtn._b){ copyCurlBtn._b=true; copyCurlBtn.addEventListener('click', ()=>callIf('wfTplCopyCurlAlt')); }
      const nojq = document.getElementById('wfTpl_curl_nojq'); if (nojq && !nojq._b){ nojq._b=true; nojq.addEventListener('change', ()=>callIf('wfTplCurlToggle')); }
      const resetFilters = document.getElementById('wfTpl_reset_filters'); if (resetFilters && !resetFilters._b){ resetFilters._b=true; resetFilters.addEventListener('click', ()=>callIf('wfTplResetFilters')); }

      // Definition controls
      const createBtn = document.getElementById('wfDef_create'); if (createBtn && !createBtn._b){ createBtn._b=true; createBtn.addEventListener('click', ()=>callIf('wfCreateDefinition')); }
      const listBtn = document.getElementById('wfDef_list'); if (listBtn && !listBtn._b){ listBtn._b=true; listBtn.addEventListener('click', ()=>callIf('wfListDefinitions')); }

      // Insert step buttons (delegated)
      root.addEventListener('click', (ev)=>{
        const b = ev.target && ev.target.closest('button[data-action="wf-insert"]'); if (!b) return;
        const kind = b.getAttribute('data-kind');
        const map = {
          delay: 'wfInsertDelay', log: 'wfInsertLog', branch: 'wfInsertBranch', prompt: 'wfInsertPrompt',
          rag: 'wfInsertRagSearch', ingest: 'wfInsertMediaIngest', tts: 'wfInsertTTS', process_media: 'wfInsertProcessMedia',
          rss: 'wfInsertRSSFetch', embed: 'wfInsertEmbed', translate: 'wfInsertTranslate', stt: 'wfInsertSTT',
          notify: 'wfInsertNotify', diff: 'wfInsertDiff'
        };
        const fn = map[kind]; if (fn) callIf(fn);
      });

      // Copy/Clear JSON
      root.addEventListener('click', (ev)=>{
        const b = ev.target && ev.target.closest('button[data-action="wf-copy-json"],button[data-action="wf-clear-json"]'); if (!b) return;
        const target = b.getAttribute('data-target') || '';
        if (b.getAttribute('data-action') === 'wf-copy-json') callIf('wfCopyJson', target);
        else callIf('wfClearJson', target);
      });

      // Routing controls
      const r1 = document.getElementById('wfRouting_refresh_ids'); if (r1 && !r1._b){ r1._b=true; r1.addEventListener('click', ()=>callIf('wfRoutingRefreshOptions', true)); }
      const r2 = document.getElementById('wfRouting_clear'); if (r2 && !r2._b){ r2._b=true; r2.addEventListener('click', ()=>callIf('wfRoutingClear')); }
      const r3 = document.getElementById('wfRouting_apply'); if (r3 && !r3._b){ r3._b=true; r3.addEventListener('click', ()=>callIf('wfApplyRouting')); }

      // Scheduler
      const sr = document.getElementById('wfSched_refresh'); if (sr && !sr._b){ sr._b=true; sr.addEventListener('click', ()=>callIf('wfSchedList')); }
      const sc = document.getElementById('wfSched_create'); if (sc && !sc._b){ sc._b=true; sc.addEventListener('click', ()=>callIf('wfSchedCreate')); }

      // Runs filters and actions
      const qSel = document.getElementById('wfList_quick'); if (qSel && !qSel._b){ qSel._b=true; qSel.addEventListener('change', ()=>callIf('wfQuickHours')); }
      const pSel = document.getElementById('wfList_presets'); if (pSel && !pSel._b){ pSel._b=true; pSel.addEventListener('change', ()=>callIf('wfApplyPreset')); }
      const useCursor = document.getElementById('wfList_use_cursor'); if (useCursor && !useCursor._b){ useCursor._b=true; useCursor.addEventListener('change', ()=>callIf('wfSaveFilters')); }
      const curReset = document.getElementById('wfCursor_reset'); if (curReset && !curReset._b){ curReset._b=true; curReset.addEventListener('click', ()=>callIf('wfResetCursor')); }
      const curHelp = document.getElementById('wfCursor_help'); if (curHelp && !curHelp._b){ curHelp._b=true; curHelp.addEventListener('click', ()=>callIf('wfShowCursorHelp')); }
      const curInput = document.getElementById('wfList_cursor'); if (curInput && !curInput._b){ curInput._b=true; curInput.addEventListener('input', ()=>callIf('wfSaveFilters')); }
      const listRuns = document.getElementById('wfList_runs'); if (listRuns && !listRuns._b){ listRuns._b=true; listRuns.addEventListener('click', ()=>callIf('wfListRuns')); }
      const copyCurl = document.getElementById('wfList_copy_curl'); if (copyCurl && !copyCurl._b){ copyCurl._b=true; copyCurl.addEventListener('click', ()=>callIf('wfCopyRunsCurl')); }
      const copyLink = document.getElementById('wfList_copy_link'); if (copyLink && !copyLink._b){ copyLink._b=true; copyLink.addEventListener('click', ()=>callIf('wfCopyShareLink')); }
      const clearFilters = document.getElementById('wfList_clear_filters'); if (clearFilters && !clearFilters._b){ clearFilters._b=true; clearFilters.addEventListener('click', ()=>callIf('wfClearFilters')); }
      const prevBtn = document.getElementById('wfList_prev'); if (prevBtn && !prevBtn._b){ prevBtn._b=true; prevBtn.addEventListener('click', ()=>callIf('wfPrevPage')); }
      const nextBtn = document.getElementById('wfList_next'); if (nextBtn && !nextBtn._b){ nextBtn._b=true; nextBtn.addEventListener('click', ()=>callIf('wfNextPage')); }
      const nextCur = document.getElementById('wfList_next_cursor'); if (nextCur && !nextCur._b){ nextCur._b=true; nextCur.addEventListener('click', ()=>callIf('wfNextCursor')); }
      const copyNextCur = document.getElementById('wfList_copy_cursor_btn'); if (copyNextCur && !copyNextCur._b){ copyNextCur._b=true; copyNextCur.addEventListener('click', ()=>callIf('wfCopyNextCursor')); }

      // Runs actions
      const getBtn = document.getElementById('wfRun_get'); if (getBtn && !getBtn._b){ getBtn._b=true; getBtn.addEventListener('click', ()=>callIf('wfGetRun')); }
      const getEvents = document.getElementById('wfRun_get_events'); if (getEvents && !getEvents._b){ getEvents._b=true; getEvents.addEventListener('click', ()=>callIf('wfGetEvents')); }
      const watchToggle = document.getElementById('wfWatch_toggle'); if (watchToggle && !watchToggle._b){ watchToggle._b=true; watchToggle.addEventListener('change', ()=>callIf('wfToggleWatchStatus')); }
      const evNext = document.getElementById('wfEvents_next'); if (evNext && !evNext._b){ evNext._b=true; evNext.addEventListener('click', ()=>callIf('wfGetNextEvents')); }
      const evAuto = document.getElementById('wfEvents_auto'); if (evAuto && !evAuto._b){ evAuto._b=true; evAuto.addEventListener('change', ()=>callIf('wfToggleAutoEvents')); }
      const evTail = document.getElementById('wfEvents_tail'); if (evTail && !evTail._b){ evTail._b=true; evTail.addEventListener('change', ()=>callIf('wfToggleTail')); }
      const evFilter = document.getElementById('wfEvents_filter'); if (evFilter && !evFilter._b){ evFilter._b=true; evFilter.addEventListener('input', ()=>callIf('wfSyncEventTypeChips')); }
      const evErr = document.getElementById('wfEvents_error_filter'); if (evErr && !evErr._b){ evErr._b=true; evErr.addEventListener('click', ()=>callIf('wfApplyErrorFilter')); }
      const evCopyCur = document.getElementById('wfEvents_copy_cursor'); if (evCopyCur && !evCopyCur._b){ evCopyCur._b=true; evCopyCur.addEventListener('click', ()=>callIf('wfCopyEventsCursor')); }
      const evNextCurBtn = document.getElementById('wfEvents_next_cursor_btn'); if (evNextCurBtn && !evNextCurBtn._b){ evNextCurBtn._b=true; evNextCurBtn.addEventListener('click', ()=>callIf('wfGetNextEvents')); }
      // Event type chips delegation
      const chipHost = document.getElementById('wfEvents_type_chips'); if (chipHost && !chipHost._b){ chipHost._b=true; chipHost.addEventListener('click', (e)=>{ const el=e.target.closest('.wf-chip,[data-type]'); if (!el) return; callIf('wfToggleEventTypeChip', el); }); chipHost.addEventListener('keydown', (e)=>{ const el=e.target.closest('.wf-chip,[data-type]'); if (!el) return; callIf('wfEventTypeChipKey', e, el); }); }

      // Run control buttons
      const p = document.getElementById('wfRun_pause'); if (p && !p._b){ p._b=true; p.addEventListener('click', ()=>callIf('wfPause')); }
      const rs = document.getElementById('wfRun_resume'); if (rs && !rs._b){ rs._b=true; rs.addEventListener('click', ()=>callIf('wfResume')); }
      const c = document.getElementById('wfRun_cancel'); if (c && !c._b){ c._b=true; c.addEventListener('click', ()=>callIf('wfCancel')); }
      const r = document.getElementById('wfRun_retry'); if (r && !r._b){ r._b=true; r.addEventListener('click', ()=>callIf('wfRetry')); }
      const cj = document.getElementById('wfRun_copy_json'); if (cj && !cj._b){ cj._b=true; cj.addEventListener('click', ()=>callIf('wfCopyJson','wfRun_result')); }
      const cl = document.getElementById('wfRun_clear_json'); if (cl && !cl._b){ cl._b=true; cl.addEventListener('click', ()=>callIf('wfClearJson','wfRun_result')); }

      // Runs list row delegation (open run / events)
      const runHost = document.getElementById('wfRun_list'); if (runHost && !runHost._b){ runHost._b=true; runHost.addEventListener('click', (e)=>{ const a=e.target.closest('[data-action]'); if (!a) return; const rid=a.getAttribute('data-run-id'); if (a.getAttribute('data-action')==='wf-open-run'){ const inp=document.getElementById('wfRun_run_id'); if (inp) inp.value = rid||''; callIf('wfGetRun'); e.preventDefault(); } else if (a.getAttribute('data-action')==='wf-run-events'){ const inp=document.getElementById('wfRun_run_id'); if (inp) inp.value = rid||''; callIf('wfGetEvents'); } }); }

      // Artifacts
      const la = document.getElementById('wfArtifacts_list'); if (la && !la._b){ la._b=true; la.addEventListener('click', ()=>callIf('wfListArtifacts')); }
      const dls = document.getElementById('wfArtifacts_dl_server'); if (dls && !dls._b){ dls._b=true; dls.addEventListener('click', ()=>callIf('wfDownloadAllServer')); }
      const dlc = document.getElementById('wfArtifacts_dl_client'); if (dlc && !dlc._b){ dlc._b=true; dlc.addEventListener('click', ()=>callIf('wfDownloadAllClient')); }

      // DLQ
      const dr = document.getElementById('wfDlq_refresh'); if (dr && !dr._b){ dr._b=true; dr.addEventListener('click', ()=>callIf('wfDlqLoad')); }

      // Modal
      const mcopy = document.getElementById('wfModal_copy_btn'); if (mcopy && !mcopy._b){ mcopy._b=true; mcopy.addEventListener('click', ()=>callIf('wfCopyModal')); }
      const mcopy2 = document.getElementById('wfModal_copy_btn2'); if (mcopy2 && !mcopy2._b){ mcopy2._b=true; mcopy2.addEventListener('click', ()=>callIf('wfCopyModal')); }
      const mclose = document.getElementById('wfModal_close_btn'); if (mclose && !mclose._b){ mclose._b=true; mclose.addEventListener('click', ()=>callIf('wfCloseModal')); }
      const mclose2 = document.getElementById('wfModal_close_btn2'); if (mclose2 && !mclose2._b){ mclose2._b=true; mclose2.addEventListener('click', ()=>callIf('wfCloseModal')); }

      // Approvals
      const appr = document.getElementById('wfApprove_btn'); if (appr && !appr._b){ appr._b=true; appr.addEventListener('click', ()=>callIf('wfApprove')); }
      const rej = document.getElementById('wfReject_btn'); if (rej && !rej._b){ rej._b=true; rej.addEventListener('click', ()=>callIf('wfReject')); }
      const appr2 = document.getElementById('wfApprove_btn2'); if (appr2 && !appr2._b){ appr2._b=true; appr2.addEventListener('click', ()=>callIf('wfApprove')); }
      const rej2 = document.getElementById('wfReject_btn2'); if (rej2 && !rej2._b){ rej2._b=true; rej2.addEventListener('click', ()=>callIf('wfReject')); }

      // Status chips (runs filter) delegation
      const chipsHost = document.getElementById('wfList_chips') || document; // if container has id in future
      document.addEventListener('click', (e)=>{ const chip = e.target.closest('.chip[data-status]'); if (!chip) return; callIf('wfToggleChip', chip); });
    }catch(e){ console.debug('initializeWorkflowsTab failed', e); }
  }

  window.initializeWorkflowsTab = initializeWorkflowsTab;
})();

// ====== Ported inline functions from workflows_content.html (CSP-safe) ======

async function wfLoadConfig(){
  try{ const cfg = await apiClient.makeRequest('GET','/api/v1/workflows/config'); wfRenderConfigCard(cfg); }catch(e){ Toast.error('Failed to load config: '+(e?.message||e)); }
}
function _wfRow(label, value){ const v = (Array.isArray(value) ? value.join(', ') : (value===true? 'true': value===false? 'false' : (value ?? ''))); return `<div style=\"display:flex;gap:8px;justify-content:space-between;border-bottom:1px dashed var(--color-base-30);padding:4px 0\"><div style=\"color:var(--color-base-0)\">${label}</div><div style=\"font-family:monospace\">${String(v)}</div></div>`; }
function wfRenderConfigCard(cfg){
  try{
    const c = document.getElementById('wfConfig_card');
    if (!cfg || typeof cfg !== 'object'){ setSafeHTML(c, '<div style="color:var(--color-base-0)">No data</div>'); return; }
    const backend = cfg.backend||{}; const rl = cfg.rate_limits||{}; const eng = cfg.engine||{}; const eg = cfg.egress||{}; const wh = cfg.webhooks||{}; const art = cfg.artifacts||{};
    let html = '';
    html += '<div style="display:grid;grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));gap:12px">';
    html += `<div style="border:1px solid var(--color-base-30);border-radius:6px;padding:8px"><div style="font-weight:600;margin-bottom:4px">Backend</div>${_wfRow('type', backend.type||'(auto)')}</div>`;
    html += `<div style="border:1px solid var(--color-base-30);border-radius:6px;padding:8px"><div style="font-weight:600;margin-bottom:4px">Rate Limits / Quotas <span class=\"wf-help\" title=\"Burst per minute limits prevent floods; daily per user caps total runs a user can start each day.\">i</span></div>${_wfRow('limits_disabled', rl.disabled)}${_wfRow('quotas_disabled', rl.quotas_disabled)}${_wfRow('burst_per_min', rl.quota_burst_per_min)}${_wfRow('daily_per_user', rl.quota_daily_per_user)}</div>`;
    html += `<div style="border:1px solid var(--color-base-30);border-radius:6px;padding:8px"><div style="font-weight:600;margin-bottom:4px">Engine</div>${_wfRow('tenant_concurrency', eng.tenant_concurrency)}${_wfRow('workflow_concurrency', eng.workflow_concurrency)}</div>`;
    html += `<div style="border:1px solid var(--color-base-30);border-radius:6px;padding:8px"><div style="font-weight:600;margin-bottom:4px">Egress</div>${_wfRow('profile <span class=\"wf-help\" title=\"Egress profiles guard against SSRF by restricting outbound destinations. Choose a profile suited to your environment.\">i</span>', eg.profile)}${_wfRow('allowed_ports', eg.allowed_ports)}${_wfRow('allowlist', eg.allowlist)}${_wfRow('block_private', eg.block_private)}</div>`;
    html += `<div style="border:1px solid var(--color-base-30);border-radius:6px;padding:8px"><div style="font-weight:600;margin-bottom:4px">Webhooks</div>${_wfRow('completion_disabled', wh.completion_disabled)}${_wfRow('secret_set', wh.secret_set)}${_wfRow('dlq_enabled', wh.dlq_enabled)}${_wfRow('allowlist', wh.allowlist)}${_wfRow('denylist', wh.denylist)}</div>`;
    html += `<div style="border:1px solid var(--color-base-30);border-radius:6px;padding:8px"><div style="font-weight:600;margin-bottom:4px">Artifacts</div>${_wfRow('validate_strict', art.validate_strict)}${_wfRow('encryption_enabled', art.encryption_enabled)}${_wfRow('gc_enabled', art.gc_enabled)}${_wfRow('retention_days', art.retention_days)}</div>`;
    html += '</div>';
    setSafeHTML(c, html);
  }catch(e){ /* ignore */ }
}
async function wfCreateDefinition(){ try{ const body = JSON.parse(document.getElementById('wfDef_payload').value); const resp = await apiClient.makeRequest('POST','/api/v1/workflows',{ body }); document.getElementById('wfDef_result').textContent = JSON.stringify(resp,null,2); Toast.success('Created definition id='+(resp?.id||'')); }catch(e){ Toast.error('Create failed: '+(e?.message||e)); } }

// The rest of Workflows functions are ported as-is from the inline scripts. For brevity, only major UI-affecting ones are adjusted for SafeDOM.
async function wfTplLoadList(){ try{ const sel = document.getElementById('wfTpl_select'); sel.innerHTML = ''; const q = (document.getElementById('wfTpl_search')?.value||'').trim(); const tagSel = document.getElementById('wfTpl_tag'); const tagVal = (tagSel?.value||'').trim(); let url = '/api/v1/workflows/templates'; const params = new URLSearchParams(); if (q) params.set('q', q); if (tagVal) params.set('tag', tagVal); if ([...params.keys()].length){ url += '?' + params.toString(); } const items = await apiClient.makeRequest('GET', url); wfTplSavePrefs(); const localsRaw = wfTplGetLocalTemplates(); const qLower = q ? q.toLowerCase() : null; const tagNorm = tagVal ? tagVal.toLowerCase() : null; const locals = localsRaw.filter(t=>{ if (qLower && !t.name.toLowerCase().includes(qLower)) return false; if (tagNorm){ const tags = Array.isArray(t.body?.tags) ? t.body.tags.map(s=>String(s).toLowerCase()) : []; if (!tags.includes(tagNorm)) return false; } return true; }).sort((a,b)=> a.name.localeCompare(b.name));
  // Fill tag select if empty
  try{ if (tagSel && tagSel.options && tagSel.options.length <= 1){ const tags = new Set(); (items||[]).forEach(it=>{ (Array.isArray(it.tags)?it.tags:[]).forEach(x=>tags.add(String(x))); }); (locals||[]).forEach(it=>{ (Array.isArray(it.body?.tags)?it.body.tags:[]).forEach(x=>tags.add(String(x))); }); const arr = Array.from(tags.values()).sort((a,b)=>String(a).localeCompare(String(b))); arr.forEach(t=>{ const opt = document.createElement('option'); opt.value = String(t); opt.textContent = String(t); tagSel.appendChild(opt); }); } }catch(_){ }
  const opt = document.createElement('option'); opt.value=''; opt.textContent='(select a template)'; sel.appendChild(opt);
  (items||[]).forEach(t=>{ const o=document.createElement('option'); o.value = t.name; o.textContent = `${t.name} — ${t.title || ''}`.trim(); sel.appendChild(o); });
  (locals||[]).forEach(t=>{ const o=document.createElement('option'); o.value = 'local::'+t.name; o.textContent = `local::${t.name}`; sel.appendChild(o); });
}catch(e){ Toast.error('Load templates failed: '+(e?.message||e)); } }

// Placeholders moved from inline (full bodies present later in file if needed by UI):
function wfTplSavePrefs(){ try{ const q=(document.getElementById('wfTpl_search')?.value||''); const tag=(document.getElementById('wfTpl_tag')?.value||''); if (typeof Utils!=='undefined'){ Utils.saveToStorage('wfTpl_pref',{q,tag}); } }catch(_){ } }
function wfTplGetLocalTemplates(){ try{ const k='WF_LOCAL_TEMPLATES'; const val = (typeof Utils!=='undefined') ? Utils.getFromStorage(k) : null; return Array.isArray(val)?val:[]; }catch(_){ return []; } }
function wfTplQueryChanged(){ try{ /* optional; UI binder triggers wfTplLoadList on enter */ }catch(_){ } }

async function wfDlqLoad(){ try{ const limit=parseInt(document.getElementById('wfDlq_limit').value||'50'); const offset=parseInt(document.getElementById('wfDlq_offset').value||'0'); const resp=await apiClient.makeRequest('GET', `/api/v1/workflows/webhooks/dlq?limit=${limit}&offset=${offset}`); const items=resp?.items||[]; let html = '<table style="width:100%;border-collapse:collapse">'; html += '<thead><tr><th style="text-align:left;padding:4px;border-bottom:1px solid var(--color-base-40)">ID</th><th style="text-align:left;padding:4px;border-bottom:1px solid var(--color-base-40)">Tenant</th><th style="text-align:left;padding:4px;border-bottom:1px solid var(--color-base-40)">Run</th><th style="text-align:left;padding:4px;border-bottom:1px solid var(--color-base-40)">URL</th><th style="text-align:left;padding:4px;border-bottom:1px solid var(--color-base-40)">Error</th></tr></thead><tbody>'; items.forEach(x=>{ html += `<tr><td>${String(x.id||'')}</td><td>${String(x.tenant||'')}</td><td>${String(x.run_id||'')}</td><td>${Utils.escapeHtml(String(x.url||''))}</td><td>${Utils.escapeHtml(String(x.error||''))}</td></tr>`; }); html += '</tbody></table>'; const host = document.getElementById('wfDlq_table'); setSafeHTML(host, html); }catch(e){ Toast.error('DLQ load failed: '+(e?.message||e)); } }

function wfRunRowHtml(run){ const rid = String(run?.run_id ?? ''); const wf = run?.workflow_id ?? ''; const owner = run?.user_id ?? ''; const statusChip = wfRunStatusChip(run?.status); const created = run?.created_at || ''; const ended = run?.ended_at || ''; const esc = Utils && Utils.escapeHtml ? Utils.escapeHtml : (s)=>s; return `<tr data-run-row="1"><td style="font-family:monospace"><a href="#" data-action="wf-open-run" data-run-id="${rid}">${esc(rid)}</a></td><td>${esc(String(wf ?? ''))}</td><td>${esc(String(owner ?? ''))}</td><td>${statusChip}</td><td>${esc(created)}</td><td>${esc(ended)}</td><td><button class="api-button btn-sm" data-action="wf-run-events" data-run-id="${rid}">Events</button></td></tr>`; }
