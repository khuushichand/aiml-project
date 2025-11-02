// maintenance.js - migrate inline handlers to module

function parseMediaIds(text) {
  if (!text) return [];
  const parts = String(text).split(/[\s,]+/).map(s => s.trim()).filter(Boolean);
  const out = new Set();
  for (const p of parts) {
    if (/^\d+$/.test(p)) { out.add(parseInt(p,10)); continue; }
    const m = p.match(/^(\d+)\-(\d+)$/);
    if (m) {
      let a = parseInt(m[1],10), b=parseInt(m[2],10);
      if (a>b) [a,b]=[b,a];
      for (let i=a;i<=b;i++) out.add(i);
    }
  }
  return Array.from(out);
}

function updateBatchFields() {
  const operation = document.getElementById('batchOperation')?.value;
  const fieldsDiv = document.getElementById('batchFields');
  if (!fieldsDiv) return;
  let html = '';
  switch(operation) {
    case 'delete_media':
      html = `
        <div class="form-group">
          <label for="batch_media_ids">Media IDs (comma-separated or range):</label>
          <textarea id="batch_media_ids" rows="4" placeholder="1,2,3 or 1-100 or combination"></textarea>
          <small>Examples: "1,2,3" or "1-10" or "1-5,10,15-20"</small>
        </div>
        <div class="form-group">
          <label>
            <input type="checkbox" id="batch_permanent_delete"> Permanent delete (bypass trash)
          </label>
        </div>`;
      break;
    case 'cleanup_orphans':
      html = `
        <div class="form-group">
          <p>This will find and remove:</p>
          <ul>
            <li>Embeddings without media items</li>
            <li>Transcripts without media items</li>
            <li>Versions without parent media</li>
          </ul>
        </div>`;
      break;
    case 'export_data':
      html = `
        <div class="form-group">
          <label for="batch_export_type">Export Type:</label>
          <select id="batch_export_type">
            <option value="all">All Data</option>
            <option value="media">Media Items</option>
            <option value="prompts">Prompts</option>
            <option value="notes">Notes</option>
          </select>
        </div>
        <div class="form-group">
          <label for="batch_export_format">Format:</label>
          <select id="batch_export_format">
            <option value="json">JSON</option>
            <option value="csv">CSV</option>
            <option value="sql">SQL</option>
          </select>
        </div>`;
      break;
  }
  fieldsDiv.innerHTML = html;
}

async function performBatchOperation() {
  const operation = document.getElementById('batchOperation')?.value;
  const resultEl = document.getElementById('batchResult');
  const progressDiv = document.getElementById('batchProgress');
  const progressBar = document.getElementById('batchProgressBar');
  const progressText = document.getElementById('batchProgressText');
  if (!operation) return;
  progressDiv.style.display = 'block';
  resultEl.textContent='';
  try {
    let endpoint = '/api/v1/maintenance/batch';
    let payload = { operation };
    if (operation === 'delete_media') {
      const idsText = document.getElementById('batch_media_ids')?.value || '';
      payload.media_ids = parseMediaIds(idsText);
      payload.permanent = !!document.getElementById('batch_permanent_delete')?.checked;
    } else if (operation === 'export_data') {
      payload.export_type = document.getElementById('batch_export_type')?.value || 'all';
      payload.format = document.getElementById('batch_export_format')?.value || 'json';
      endpoint = '/api/v1/maintenance/export';
    }
    let progress = 0;
    const intv = setInterval(()=>{
      progress = Math.min(progress+10,90);
      progressBar.style.width = progress + '%';
      progressText.textContent = `Processing... ${progress}%`;
    },200);
    const response = await window.apiClient.post(endpoint, payload);
    progressBar.style.width = '100%';
    progressText.textContent = 'Complete';
    resultEl.textContent = JSON.stringify(response, null, 2);
    if (window.Toast) Toast.success('Batch operation complete');
  } catch (e) {
    resultEl.textContent = `Error: ${e.message}`;
    if (window.Toast) Toast.error(`Batch failed: ${e.message}`);
  } finally {
    clearInterval(intv);
  }
}

function previewBatchOperation() {
  const operation = document.getElementById('batchOperation')?.value;
  const resultEl = document.getElementById('batchResult');
  if (!operation) return;
  let endpoint = '/api/v1/maintenance/batch';
  let payload = { operation };
  if (operation === 'delete_media') {
    const idsText = document.getElementById('batch_media_ids')?.value || '';
    payload.media_ids = parseMediaIds(idsText);
    payload.permanent = !!document.getElementById('batch_permanent_delete')?.checked;
  } else if (operation === 'export_data') {
    payload.export_type = document.getElementById('batch_export_type')?.value || 'all';
    payload.format = document.getElementById('batch_export_format')?.value || 'json';
    endpoint = '/api/v1/maintenance/export';
  }
  resultEl.textContent = `Preview:\nPOST ${endpoint}\n${JSON.stringify(payload,null,2)}`;
}

async function performDatabaseCleanup() {
  const resultEl = document.getElementById('cleanupResult');
  const options = {
    temp_files: !!document.getElementById('cleanup_temp_files')?.checked,
    orphaned_embeddings: !!document.getElementById('cleanup_orphaned_embeddings')?.checked,
    old_versions: !!document.getElementById('cleanup_old_versions')?.checked,
    error_logs: !!document.getElementById('cleanup_error_logs')?.checked,
    expired_sessions: !!document.getElementById('cleanup_expired_sessions')?.checked,
    dry_run: !!document.getElementById('cleanup_dry_run')?.checked,
  };
  try {
    const response = await window.apiClient.post('/api/v1/maintenance/cleanup', options);
    resultEl.textContent = JSON.stringify(response, null, 2);
    if (window.Toast) Toast.success('Cleanup requested');
  } catch (e) { resultEl.textContent = `Error: ${e.message}`; if (window.Toast) Toast.error(`Cleanup failed: ${e.message}`); }
}

async function exportConfiguration() {
  const resultEl = document.getElementById('exportResult');
  const options = {
    config: !!document.getElementById('export_config')?.checked,
    prompts: !!document.getElementById('export_prompts')?.checked,
    characters: !!document.getElementById('export_characters')?.checked,
    api_keys: !!document.getElementById('export_api_keys')?.checked,
    custom_settings: !!document.getElementById('export_custom_settings')?.checked,
    format: document.getElementById('export_format')?.value || 'json',
  };
  try {
    const expectZip = options.format === 'zip';
    const response = await window.apiClient.post(
      '/api/v1/maintenance/export-config',
      options,
      expectZip ? { responseType: 'blob' } : {}
    );
    if (expectZip) {
      const blob = (typeof Blob !== 'undefined' && response instanceof Blob)
        ? response
        : new Blob([response], { type: 'application/zip' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `tldw_config_${Date.now()}.zip`;
      document.body.appendChild(a);
      a.click();
      // Defer revocation to allow download to start
      setTimeout(() => {
        try { document.body.removeChild(a); } catch (_) {}
        try { URL.revokeObjectURL(url); } catch (_) {}
      }, 100);
      resultEl.textContent = 'Configuration exported successfully';
    } else {
      resultEl.textContent = typeof response === 'string'
        ? response
        : JSON.stringify(response, null, 2);
    }
    if (window.Toast) Toast.success('Configuration exported');
  } catch (e) { resultEl.textContent = `Error: ${e.message}`; if (window.Toast) Toast.error(`Export failed: ${e.message}`); }
}

async function importConfiguration() {
  const resultEl = document.getElementById('importResult');
  const fileInput = document.getElementById('importFile');
  if (!fileInput?.files?.length) { if (window.Toast) Toast.error('Please select a file to import'); return; }
  const formData = new FormData();
  formData.append('file', fileInput.files[0]);
  formData.append('backup', !!document.getElementById('import_backup')?.checked);
  formData.append('merge', !!document.getElementById('import_merge')?.checked);
  formData.append('validate', !!document.getElementById('import_validate')?.checked);
  try {
    if (window.Loading) Loading.show(resultEl.parentElement, 'Importing configuration...');
    const response = await window.apiClient.post('/api/v1/maintenance/import-config', formData);
    resultEl.textContent = JSON.stringify(response, null, 2);
    if (window.Toast) Toast.success('Configuration imported successfully');
  } catch (e) { resultEl.textContent = `Error: ${e.message}`; if (window.Toast) Toast.error(`Import failed: ${e.message}`); }
  finally { if (window.Loading) Loading.hide(resultEl.parentElement); }
}

async function createBackup() {
  const resultEl = document.getElementById('backupResult');
  const options = {
    name: document.getElementById('backup_name')?.value || undefined,
    media_db: !!document.getElementById('backup_media_db')?.checked,
    vector_db: !!document.getElementById('backup_vector_db')?.checked,
    notes_db: !!document.getElementById('backup_notes_db')?.checked,
    compress: !!document.getElementById('backup_compress')?.checked,
  };
  try {
    if (window.Loading) Loading.show(resultEl.parentElement, 'Creating backup...');
    const response = await window.apiClient.post('/api/v1/maintenance/backup', options, { timeout: 300000 });
    resultEl.textContent = JSON.stringify(response, null, 2);
    if (window.Toast) Toast.success('Backup created successfully');
  } catch (e) { resultEl.textContent = `Error: ${e.message}`; if (window.Toast) Toast.error(`Backup failed: ${e.message}`); }
  finally { if (window.Loading) Loading.hide(resultEl.parentElement); }
}

async function restoreBackup() {
  const resultEl = document.getElementById('restoreResult');
  const fileInput = document.getElementById('restore_file');
  if (!fileInput?.files?.length) { if (window.Toast) Toast.error('Please select a backup file'); return; }
  if (!confirm('This will overwrite your existing data. Are you absolutely sure?')) return;
  const formData = new FormData(); formData.append('backup_file', fileInput.files[0]);
  try {
    if (window.Loading) Loading.show(resultEl.parentElement, 'Restoring backup...');
    const response = await window.apiClient.post('/api/v1/maintenance/restore', formData, { timeout: 600000 });
    resultEl.textContent = JSON.stringify(response, null, 2);
    if (window.Toast) Toast.success('Backup restored successfully');
  } catch (e) { resultEl.textContent = `Error: ${e.message}`; if (window.Toast) Toast.error(`Restore failed: ${e.message}`); }
  finally { if (window.Loading) Loading.hide(resultEl.parentElement); }
}

async function uiClaimsLoad() {
  const out = document.getElementById('claims_output');
  const mid = parseInt(document.getElementById('claims_media_id')?.value || '0', 10);
  if (!mid) { out.textContent = 'Enter a valid media_id'; return; }
  try { const resp = await fetch(`/api/v1/claims/${mid}`); if (!resp.ok) throw new Error(await resp.text()); const data = await resp.json(); out.textContent = JSON.stringify(data, null, 2);} catch (e) { out.textContent = 'Error: ' + e; }
}
async function uiClaimsRebuildOne() {
  const out = document.getElementById('claims_output');
  const mid = parseInt(document.getElementById('claims_media_id')?.value || '0', 10);
  if (!mid) { out.textContent = 'Enter a valid media_id'; return; }
  try { const resp = await fetch(`/api/v1/claims/${mid}/rebuild`, { method: 'POST' }); if (!resp.ok) throw new Error(await resp.text()); const data = await resp.json(); out.textContent = 'Rebuild queued: ' + JSON.stringify(data);} catch (e) { out.textContent = 'Error: ' + e; }
}
async function uiClaimsRebuildAll() {
  const out = document.getElementById('claims_output'); const pol = document.getElementById('claims_rebuild_policy')?.value || 'missing';
  try { const resp = await fetch(`/api/v1/claims/rebuild/all?policy=${encodeURIComponent(pol)}`, { method: 'POST' }); if (!resp.ok) throw new Error(await resp.text()); const data = await resp.json(); out.textContent = 'Rebuild all queued: ' + JSON.stringify(data);} catch (e) { out.textContent = 'Error: ' + e; }
}
async function uiClaimsRebuildFTS() {
  const out = document.getElementById('claims_output');
  try { const resp = await fetch(`/api/v1/claims/rebuild_fts`, { method: 'POST' }); if (!resp.ok) throw new Error(await resp.text()); const data = await resp.json(); out.textContent = 'FTS index rebuilt: ' + JSON.stringify(data);} catch (e) { out.textContent = 'Error: ' + e; }
}

function bindMaintenance() {
  document.getElementById('restore_confirm')?.addEventListener('change', (e) => {
    const tgt = document.getElementById('restoreBtn'); if (tgt) tgt.disabled = !e.target.checked;
  });
  document.getElementById('batchOperation')?.addEventListener('change', updateBatchFields);
  document.getElementById('btnBatchExecute')?.addEventListener('click', performBatchOperation);
  document.getElementById('btnBatchPreview')?.addEventListener('click', previewBatchOperation);
  document.getElementById('btnCleanupRun')?.addEventListener('click', performDatabaseCleanup);
  document.getElementById('btnExportConfig')?.addEventListener('click', exportConfiguration);
  document.getElementById('btnImportConfig')?.addEventListener('click', importConfiguration);
  document.getElementById('btnCreateBackup')?.addEventListener('click', createBackup);
  document.getElementById('restoreBtn')?.addEventListener('click', restoreBackup);
  // Claims
  document.getElementById('btnClaimsLoad')?.addEventListener('click', uiClaimsLoad);
  document.getElementById('btnClaimsRebuildOne')?.addEventListener('click', uiClaimsRebuildOne);
  document.getElementById('btnClaimsRebuildAll')?.addEventListener('click', uiClaimsRebuildAll);
  document.getElementById('btnClaimsRebuildFTS')?.addEventListener('click', uiClaimsRebuildFTS);
  // initial
  updateBatchFields();
}

if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindMaintenance);
else bindMaintenance();

export default { bindMaintenance };
