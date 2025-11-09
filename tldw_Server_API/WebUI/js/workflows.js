// Workflows tab: bind UI without inline handlers
(function(){
  function callIf(fnName, ...args){ try{ if (typeof window[fnName] === 'function') return window[fnName](...args); }catch(_){ } console.warn(`[workflows] Missing handler: ${fnName}`); }

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
    }catch(e){ console.debug('initializeWorkflowsTab failed', e); }
  }

  window.initializeWorkflowsTab = initializeWorkflowsTab;
})();

