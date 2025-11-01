// Extracted Jobs Admin tab logic from inline script
// This module defines global functions used by Jobs tab buttons and initializes the tab on load.

let adminJobsTimer = null;

async function adminFetchJobsStats() {
  const domain = document.getElementById('adminJobs_domain')?.value?.trim() || '';
  const queue = document.getElementById('adminJobs_queue')?.value?.trim() || '';
  const jobType = document.getElementById('adminJobs_jobType')?.value?.trim() || '';
  const query = {};
  if (domain) query.domain = domain;
  if (queue) query.queue = queue;
  if (jobType) query.job_type = jobType;
  const tbody = document.getElementById('adminJobs_tableBody');
  if (!tbody) return;
  try {
    Loading.show(tbody.parentElement, 'Loading jobs stats...');
    const res = await apiClient.makeRequest('GET', '/api/v1/jobs/stats', { query });
    const data = Array.isArray(res) ? res : (res?.data || []);
    tbody.innerHTML = '';
    if (!data.length) {
      const tr = document.createElement('tr');
      const td = document.createElement('td');
      td.colSpan = 7;
      td.className = 'text-muted';
      td.textContent = 'No data';
      tr.appendChild(td);
      tbody.appendChild(tr);
      return;
    }
    for (const row of data) {
      const tr = document.createElement('tr');
      const values = [
        row.domain ?? '',
        row.queue ?? '',
        row.job_type ?? '',
        row.queued ?? 0,
        row.scheduled ?? 0,
        row.processing ?? 0,
        row.quarantined ?? 0,
      ];
      for (const v of values) {
        const td = document.createElement('td');
        td.textContent = String(v);
        tr.appendChild(td);
      }
      // Make rows clickable to apply filter
      tr.style.cursor = 'pointer';
      tr.title = 'Click to filter Admin → Jobs';
      tr.setAttribute('role', 'button');
      tr.setAttribute('tabindex', '0');
      tr.addEventListener('click', () => {
        adminApplyJobsFilter(row.domain || '', row.queue || '', row.job_type || '');
      });
      tr.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          adminApplyJobsFilter(row.domain || '', row.queue || '', row.job_type || '');
        }
      });
      tbody.appendChild(tr);
    }
  } catch (e) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 7;
    td.className = 'text-error';
    td.textContent = (e && e.message) ? String(e.message) : 'Failed to load';
    tr.appendChild(td);
    tbody.innerHTML = '';
    tbody.appendChild(tr);
  } finally {
    Loading.hide(tbody.parentElement);
  }
}

function adminStartJobsAutoRefresh() {
  adminStopJobsAutoRefresh();
  adminJobsTimer = setInterval(adminFetchJobsStats, 10000);
  adminFetchJobsStats();
}

function adminStopJobsAutoRefresh() {
  if (adminJobsTimer) {
    clearInterval(adminJobsTimer);
    adminJobsTimer = null;
  }
}

// Mini warning banners for destructive actions when Dry Run is unchecked
function adminInitJobsWarnings() {
  try {
    const pruneCb = document.getElementById('adminJobs_dryRun');
    const pruneWarn = document.getElementById('adminJobsPrune_warning');
    if (pruneCb && pruneWarn) {
      const syncPrune = () => { pruneWarn.style.display = pruneCb.checked ? 'none' : 'block'; };
      pruneCb.addEventListener('change', syncPrune);
      syncPrune();
    }
  } catch (e) { /* no-op */ }
  try {
    const rqCb = document.getElementById('adminJobsRequeue_dryRun');
    const rqWarn = document.getElementById('adminJobsRequeue_warning');
    if (rqCb && rqWarn) {
      const syncRq = () => { rqWarn.style.display = rqCb.checked ? 'none' : 'block'; };
      rqCb.addEventListener('change', syncRq);
      syncRq();
    }
  } catch (e) { /* no-op */ }
}

async function adminJobsQueueControl() {
  const domain = document.getElementById('adminJobs_ctrl_domain')?.value?.trim();
  const queue = document.getElementById('adminJobs_ctrl_queue')?.value?.trim();
  const action = document.getElementById('adminJobs_ctrl_action')?.value;
  const el = document.getElementById('adminJobs_ctrl_status');
  if (!domain || !queue || !action) { el && (el.textContent = 'Missing domain/queue/action'); return; }
  try {
    const res = await apiClient.makeRequest('POST', '/api/v1/jobs/queue/control', { body: { domain, queue, action } });
    el && (el.textContent = `paused=${!!res.paused} drain=${!!res.drain}`);
  } catch (e) {
    el && (el.textContent = (e && e.message) ? String(e.message) : 'Failed');
  }
}

async function adminJobsQueueStatus() {
  const domain = document.getElementById('adminJobs_ctrl_domain')?.value?.trim();
  const queue = document.getElementById('adminJobs_ctrl_queue')?.value?.trim();
  const el = document.getElementById('adminJobs_ctrl_status');
  if (!domain || !queue) { el && (el.textContent = 'Missing domain/queue'); return; }
  try {
    const res = await apiClient.makeRequest('GET', '/api/v1/jobs/queue/status', { query: { domain, queue } });
    el && (el.textContent = `paused=${!!res.paused} drain=${!!res.drain}`);
  } catch (e) {
    el && (el.textContent = (e && e.message) ? String(e.message) : 'Failed');
  }
}

async function adminJobsAddAttachment() {
  const jid = document.getElementById('adminJobs_attach_jobId')?.value;
  const text = document.getElementById('adminJobs_attach_text')?.value;
  const kind = document.getElementById('adminJobs_attach_kind')?.value || 'log';
  if (!jid) return;
  const body = { kind };
  if (kind === 'artifact') body.url = text; else body.content_text = text;
  await apiClient.makeRequest('POST', `/api/v1/jobs/${jid}/attachments`, { body });
  await adminJobsListAttachments();
}

async function adminJobsListAttachments() {
  const jid = document.getElementById('adminJobs_attach_jobId')?.value;
  const pre = document.getElementById('adminJobs_attach_list');
  if (!jid || !pre) return;
  const res = await apiClient.makeRequest('GET', `/api/v1/jobs/${jid}/attachments`);
  pre.textContent = JSON.stringify(res, null, 2);
}

async function adminJobsUpsertSla() {
  const domain = document.getElementById('adminJobs_sla_domain')?.value?.trim();
  const queue = document.getElementById('adminJobs_sla_queue')?.value?.trim();
  const job_type = document.getElementById('adminJobs_sla_jobType')?.value?.trim();
  const max_queue_latency_seconds = parseInt(document.getElementById('adminJobs_sla_queueLat')?.value || '0', 10);
  const max_duration_seconds = parseInt(document.getElementById('adminJobs_sla_duration')?.value || '0', 10);
  const enabled = !!document.getElementById('adminJobs_sla_enabled')?.checked;
  const body = { domain, queue, job_type, max_queue_latency_seconds, max_duration_seconds, enabled };
  const res = await apiClient.makeRequest('POST', '/api/v1/jobs/sla/policy', { body });
  const el = document.getElementById('adminJobs_sla_result');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function adminJobsListSla() {
  const domain = document.getElementById('adminJobs_sla_domain')?.value?.trim();
  const queue = document.getElementById('adminJobs_sla_queue')?.value?.trim();
  const job_type = document.getElementById('adminJobs_sla_jobType')?.value?.trim();
  const res = await apiClient.makeRequest('GET', '/api/v1/jobs/sla/policies', { query: { domain, queue, job_type } });
  const el = document.getElementById('adminJobs_sla_result');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

function _collectCryptoRotateBody(showErrors = true) {
  const domain = document.getElementById('adminJobs_crypto_domain')?.value?.trim();
  const queue = document.getElementById('adminJobs_crypto_queue')?.value?.trim();
  const job_type = document.getElementById('adminJobs_crypto_type')?.value?.trim();
  const old_key_b64 = document.getElementById('adminJobs_crypto_old')?.value?.trim();
  const new_key_b64 = document.getElementById('adminJobs_crypto_new')?.value?.trim();
  const limit = parseInt(document.getElementById('adminJobs_crypto_limit')?.value || '1000', 10);
  const fields = [];
  if (document.getElementById('adminJobs_crypto_payload')?.checked) fields.push('payload');
  if (document.getElementById('adminJobs_crypto_result')?.checked) fields.push('result');
  const body = { old_key_b64, new_key_b64, fields, limit };
  if (domain) body.domain = domain;
  if (queue) body.queue = queue;
  if (job_type) body.job_type = job_type;
  // inline validation
  const errs = [];
  if (!old_key_b64) errs.push('Old key is required.');
  if (!new_key_b64) errs.push('New key is required.');
  if (!fields.length) errs.push('Select at least one field (payload/result).');
  const box = document.getElementById('adminJobs_crypto_errors');
  if (box && showErrors) box.textContent = errs.join(' ');
  body.__errors = errs;
  return body;
}

async function adminJobsCryptoRotateDryRun() {
  const pre = document.getElementById('adminJobs_crypto_result');
  const body = _collectCryptoRotateBody(true);
  if (body.__errors?.length) return;
  body.dry_run = true;
  const res = await apiClient.makeRequest('POST', '/api/v1/jobs/crypto/rotate', { body });
  if (pre) pre.textContent = JSON.stringify(res, null, 2);
}

async function adminJobsCryptoRotateExecute() {
  const pre = document.getElementById('adminJobs_crypto_result');
  const body = _collectCryptoRotateBody(true);
  if (body.__errors?.length) return;
  body.dry_run = false;
  const res = await apiClient.makeRequest('POST', '/api/v1/jobs/crypto/rotate', { body, headers: { 'X-Confirm': 'true' } });
  if (pre) pre.textContent = JSON.stringify(res, null, 2);
}

function adminOpenRotateKeysModal() {
  try {
    const content = `
      <div class="form-grid">
        <div class="form-group"><label>Domain</label><input type="text" id="rk_domain" placeholder="(optional)"></div>
        <div class="form-group"><label>Queue</label><input type="text" id="rk_queue" placeholder="(optional)"></div>
        <div class="form-group"><label>Job Type</label><input type="text" id="rk_type" placeholder="(optional)"></div>
        <div class="form-group"><label>Old Key (base64)</label><input type="text" id="rk_old" placeholder="base64-encoded key"></div>
        <div class="form-group"><label>New Key (base64)</label><input type="text" id="rk_new" placeholder="base64-encoded key"></div>
        <div class="form-group"><label>Fields</label>
          <label style="margin-right:8px;"><input type="checkbox" id="rk_payload" checked> payload</label>
          <label><input type="checkbox" id="rk_result"> result</label>
        </div>
        <div class="form-group"><label>Limit</label><input type="number" id="rk_limit" value="500" min="1"></div>
        <div class="form-group"><label>Type 'rotate' to confirm</label><input type="text" id="rk_confirm" placeholder="rotate"></div>
        <div id="rk_errors" class="text-error" style="min-height:18px;"></div>
        <pre id="rk_result" style="max-height:200px; overflow:auto;">-</pre>
      </div>
    `;
    const footer = `
      <button class="btn btn-secondary" id="rk_dry">Dry Run</button>
      <button class="btn btn-danger" id="rk_exec" disabled>Execute (X-Confirm)</button>
    `;
    const modal = new Modal({ title: 'Rotate Keys', content, footer, size: 'medium' });
    modal.show();
    const $ = (id) => modal.modal.querySelector(id);
    const collect = () => {
      const domain = $('#rk_domain').value.trim();
      const queue = $('#rk_queue').value.trim();
      const job_type = $('#rk_type').value.trim();
      const old_key_b64 = $('#rk_old').value.trim();
      const new_key_b64 = $('#rk_new').value.trim();
      const limit = parseInt($('#rk_limit').value || '500', 10);
      const fields = [];
      if ($('#rk_payload').checked) fields.push('payload');
      if ($('#rk_result').checked) fields.push('result');
      const errs = [];
      if (!old_key_b64) errs.push('Old key is required.');
      if (!new_key_b64) errs.push('New key is required.');
      if (!fields.length) errs.push('Select at least one field.');
      const confirmText = $('#rk_confirm').value.trim().toLowerCase();
      if (confirmText !== 'rotate') errs.push("Type 'rotate' to enable Execute.");
      $('#rk_errors').textContent = errs.join(' ');
      const body = { old_key_b64, new_key_b64, fields, limit };
      if (domain) body.domain = domain;
      if (queue) body.queue = queue;
      if (job_type) body.job_type = job_type;
      body.__errors = errs;
      return body;
    };
    // Enable/disable Execute button based on confirmation input
    const updateExecEnabled = () => {
      const ok = ($('#rk_confirm').value.trim().toLowerCase() === 'rotate');
      const execBtn = $('#rk_exec');
      if (execBtn) execBtn.disabled = !ok;
    };
    $('#rk_confirm').addEventListener('input', updateExecEnabled);
    updateExecEnabled();
    $('#rk_dry').onclick = async () => {
      const body = collect();
      if (body.__errors.length) return;
      body.dry_run = true;
      const res = await apiClient.makeRequest('POST', '/api/v1/jobs/crypto/rotate', { body });
      $('#rk_result').textContent = JSON.stringify(res, null, 2);
    };
    $('#rk_exec').onclick = async () => {
      const body = collect();
      if (body.__errors.length) return;
      body.dry_run = false;
      const res = await apiClient.makeRequest('POST', '/api/v1/jobs/crypto/rotate', { body, headers: { 'X-Confirm': 'true' } });
      $('#rk_result').textContent = JSON.stringify(res, null, 2);
    };
  } catch (e) { console.warn('Rotate Keys modal failed:', e); }
}

function adminJobsSaveFilters() {
  try {
    const d = document.getElementById('adminJobs_domain');
    const q = document.getElementById('adminJobs_queue');
    const jt = document.getElementById('adminJobs_jobType');
    const payload = { domain: d ? d.value.trim() : '', queue: q ? q.value.trim() : '', job_type: jt ? jt.value.trim() : '' };
    if (typeof Utils !== 'undefined') Utils.saveToStorage('admin-jobs-filters', payload);
    updateSavedFiltersBadge(payload);
  } catch (e) { /* ignore */ }
}

function adminApplyJobsFilter(domain, queue, jobType) {
  try {
    const d = document.getElementById('adminJobs_domain');
    const q = document.getElementById('adminJobs_queue');
    const jt = document.getElementById('adminJobs_jobType');
    if (d) d.value = domain || '';
    if (q) q.value = queue || '';
    if (jt) jt.value = jobType || '';
    const topbar = document.getElementById('adminJobs_topbar');
    if (topbar) {
      const desc = `${domain || '(any)'}/${queue || '(any)'}/${jobType || '(any)'}`;
      topbar.textContent = `Filter applied: ${desc}`;
    }
    updateSavedFiltersBadge({ domain, queue, job_type: jobType });
    adminJobsSaveFilters();
    adminFetchJobsStats();
  } catch (e) { /* ignore */ }
}

async function adminJobsLoadQueues() {
  try {
    const sel = document.getElementById('adminJobs_queue');
    if (!sel) return;
    // Remove existing dynamic options (keep first (any))
    while (sel.options.length > 1) sel.remove(1);
    const res = await apiClient.makeRequest('GET', '/api/v1/config/jobs', {});
    const queues = (res && res.standard_queues && Array.isArray(res.standard_queues)) ? res.standard_queues : ['default','high','low'];
    queues.forEach(q => {
      const opt = document.createElement('option');
      opt.value = q;
      opt.textContent = q;
      sel.appendChild(opt);
    });
  } catch (e) {
    // Silent fallback to defaults
  }
}

function adminJobsRestoreFilters() {
  try {
    const saved = (typeof Utils !== 'undefined') ? Utils.getFromStorage('admin-jobs-filters') : null;
    if (!saved) return;
    const d = document.getElementById('adminJobs_domain');
    const q = document.getElementById('adminJobs_queue');
    const jt = document.getElementById('adminJobs_jobType');
    if (d) d.value = saved.domain || '';
    if (jt) jt.value = saved.job_type || '';
    if (q) {
      // Ensure saved option exists before selecting
      const found = Array.from(q.options).some(o => o.value === (saved.queue || ''));
      if (!found && saved.queue) {
        const opt = document.createElement('option');
        opt.value = saved.queue;
        opt.textContent = saved.queue;
        q.appendChild(opt);
      }
      q.value = saved.queue || '';
    }
    updateSavedFiltersBadge(saved);
  } catch (e) { /* ignore */ }
}

function adminJobsBindPersist() {
  try {
    const ids = ['adminJobs_domain','adminJobs_queue','adminJobs_jobType'];
    ids.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.addEventListener('change', adminJobsSaveFilters);
    });
  } catch (e) { /* ignore */ }
}

async function adminJobsInit() {
  await adminJobsLoadQueues();
  adminJobsRestoreFilters();
  adminJobsBindPersist();
  adminInitJobsWarnings();
  // Bind buttons for this tab (removes need for inline handlers)
  try {
    const byId = (id) => document.getElementById(id);
    byId('btnAdminOpenRotateKeys')?.addEventListener('click', adminOpenRotateKeysModal);
    byId('btnAdminJobsRefresh')?.addEventListener('click', adminFetchJobsStats);
    byId('btnAdminJobsAutoRefresh')?.addEventListener('click', adminStartJobsAutoRefresh);
    byId('btnAdminJobsStop')?.addEventListener('click', adminStopJobsAutoRefresh);
    byId('adminJobs_resetFilters')?.addEventListener('click', adminJobsResetFilters);
    byId('adminJobsPrune_btn')?.addEventListener('click', adminPruneJobs);
    byId('adminJobsTTL_btn')?.addEventListener('click', adminRunTTLSweep);
    byId('adminJobsRequeue_btn')?.addEventListener('click', adminRequeueQuarantined);
    byId('btnAdminJobsQueueControl')?.addEventListener('click', adminJobsQueueControl);
    byId('btnAdminJobsQueueStatus')?.addEventListener('click', adminJobsQueueStatus);
    byId('btnAdminJobsAddAttachment')?.addEventListener('click', adminJobsAddAttachment);
    byId('btnAdminJobsListAttachments')?.addEventListener('click', adminJobsListAttachments);
    byId('btnAdminJobsUpsertSla')?.addEventListener('click', adminJobsUpsertSla);
    byId('btnAdminJobsListSla')?.addEventListener('click', adminJobsListSla);
    byId('btnAdminJobsCryptoDryRun')?.addEventListener('click', adminJobsCryptoRotateDryRun);
    byId('btnAdminJobsCryptoExec')?.addEventListener('click', adminJobsCryptoRotateExecute);
    byId('adminJobsEvents_start')?.addEventListener('click', adminStartJobsEvents);
    byId('adminJobsEvents_stop')?.addEventListener('click', adminStopJobsEvents);
    // Optional: user-configurable max events buffer
    const maxEl = byId('adminJobsEvents_max');
    if (maxEl) {
      // Initialize from storage if empty
      try {
        if (!maxEl.value) {
          let saved = null;
          if (typeof Utils !== 'undefined') saved = Utils.getFromStorage('admin-jobs-events-max');
          else if (typeof localStorage !== 'undefined') saved = localStorage.getItem('admin-jobs-events-max');
          if (saved) maxEl.value = String(parseInt(saved, 10) || 100);
        }
      } catch (_) {}
      maxEl.addEventListener('change', () => {
        const v = parseInt(maxEl.value, 10);
        const val = (Number.isFinite(v) && v > 0) ? v : 100;
        maxEl.value = String(val);
        try {
          if (typeof Utils !== 'undefined') Utils.saveToStorage('admin-jobs-events-max', val);
          else if (typeof localStorage !== 'undefined') localStorage.setItem('admin-jobs-events-max', String(val));
        } catch (_) {}
      });
    }
  } catch (_) {}
  try { await adminFetchJobsStats(); } catch (e) { /* ignore */ }
}

function updateSavedFiltersBadge(values) {
  try {
    const badge = document.getElementById('adminJobs_savedFiltersBadge');
    if (!badge) return;
    const saved = values || (typeof Utils !== 'undefined' ? Utils.getFromStorage('admin-jobs-filters') : null) || { domain: '', queue: '', job_type: '' };
    const domain = saved.domain || '(any)';
    const queue = saved.queue || '(any)';
    const jobType = saved.job_type || '(any)';
    badge.textContent = `Saved Filters: domain=${domain}, queue=${queue}, job_type=${jobType}`;
  } catch (e) { /* ignore */ }
}

function adminJobsResetFilters() {
  try {
    if (typeof Utils !== 'undefined') Utils.saveToStorage('admin-jobs-filters', { domain: '', queue: '', job_type: '' });
    const d = document.getElementById('adminJobs_domain');
    const q = document.getElementById('adminJobs_queue');
    const jt = document.getElementById('adminJobs_jobType');
    if (d) d.value = '';
    if (q) q.value = '';
    if (jt) jt.value = '';
    updateSavedFiltersBadge({ domain: '', queue: '', job_type: '' });
    adminFetchJobsStats();
    Toast.info('Filters reset');
  } catch (e) { /* ignore */ }
}

async function adminPruneJobs() {
  const btn = document.getElementById('adminJobsPrune_btn');
  const statuses = Array.from(document.querySelectorAll('.adminJobs_status:checked')).map(cb => cb.value);
  const olderDaysEl = document.getElementById('adminJobs_olderDays');
  const olderThanDays = Math.max(1, parseInt(olderDaysEl && olderDaysEl.value ? olderDaysEl.value : '30', 10));
  const dryRun = !!(document.getElementById('adminJobs_dryRun') && document.getElementById('adminJobs_dryRun').checked);
  const domain = (document.getElementById('adminJobs_domain')?.value || '').trim();
  const queue = (document.getElementById('adminJobs_queue')?.value || '').trim();
  const jobType = (document.getElementById('adminJobs_jobType')?.value || '').trim();
  const resultEl = document.getElementById('adminJobsPrune_result');
  const summaryEl = document.getElementById('adminJobsPrune_summary');
  if (!statuses.length) {
    Toast.error('Select at least one status to prune');
    return;
  }
  const scope = [domain && `domain=${domain}`, queue && `queue=${queue}`, jobType && `job_type=${jobType}`].filter(Boolean).join(', ');
  const preview = dryRun ? ' (dry run)' : '';
  const confirmed = confirm(`Prune${preview} jobs with statuses [${statuses.join(', ')}] older than ${olderThanDays} days${scope ? `, scoped to [${scope}]` : ''}?`);
  if (!confirmed) return;
  try {
    if (btn) btn.disabled = true;
    Loading.show(resultEl, 'Pruning jobs...');
    if (summaryEl) summaryEl.textContent = dryRun ? 'Dry run: counting matching jobs…' : 'Deleting matching jobs…';
    const body = { statuses, older_than_days: olderThanDays, dry_run: dryRun };
    if (domain) body.domain = domain;
    if (queue) body.queue = queue;
    if (jobType) body.job_type = jobType;
    const res = await apiClient.makeRequest('POST', '/api/v1/jobs/prune', { body });
    const deleted = (res && typeof res.deleted === 'number') ? res.deleted : (res?.data?.deleted || 0);
    resultEl.textContent = JSON.stringify(res, null, 2);
    Toast.success(`${dryRun ? 'Would prune' : 'Pruned'} ${deleted} job(s)`);
    const topbar = document.getElementById('adminJobs_topbar');
    if (topbar) {
      const ts = new Date().toLocaleString();
      topbar.textContent = `${dryRun ? 'Dry run:' : 'Pruned'} ${deleted} job(s) [${statuses.join(', ')} older than ${olderThanDays} days${scope ? `, ${scope}` : ''}] - ${ts}`;
    }
    if (summaryEl) summaryEl.textContent = dryRun
      ? `Dry run: would prune ${deleted} job(s) matching filters`
      : `Deleted ${deleted} job(s)`;
    // Refresh stats after prune
    if (typeof adminFetchJobsStats === 'function') adminFetchJobsStats();
  } catch (e) {
    const err = e && (e.response || e);
    resultEl.textContent = JSON.stringify(err, null, 2);
    Toast.error('Prune failed');
    if (summaryEl) summaryEl.textContent = '-';
  } finally {
    if (btn) btn.disabled = false;
    Loading.hide(resultEl);
  }
}

async function adminRunTTLSweep() {
  const btn = document.getElementById('adminJobsTTL_btn');
  const resultEl = document.getElementById('adminJobsTTL_result');
  const summaryEl = document.getElementById('adminJobsTTL_summary');
  const domain = (document.getElementById('adminJobs_domain')?.value || '').trim();
  const queue = (document.getElementById('adminJobs_queue')?.value || '').trim();
  const jobType = (document.getElementById('adminJobs_jobType')?.value || '').trim();
  const ageSecondsStr = (document.getElementById('adminJobs_ttl_age')?.value || '').trim();
  const runtimeSecondsStr = (document.getElementById('adminJobs_ttl_runtime')?.value || '').trim();
  const action = (document.getElementById('adminJobs_ttl_action')?.value || 'cancel');
  const body = { action };
  const ageSeconds = parseInt(ageSecondsStr || '0', 10);
  const runtimeSeconds = parseInt(runtimeSecondsStr || '0', 10);
  if (ageSeconds > 0) body.age_seconds = ageSeconds;
  if (runtimeSeconds > 0) body.runtime_seconds = runtimeSeconds;
  if (domain) body.domain = domain;
  if (queue) body.queue = queue;
  if (jobType) body.job_type = jobType;
  if (!body.age_seconds && !body.runtime_seconds) {
    Toast.error('Provide age_seconds and/or runtime_seconds');
    return;
  }
  try {
    if (btn) btn.disabled = true;
    Loading.show(resultEl, 'Sweeping TTL…');
    if (summaryEl) summaryEl.textContent = 'Running TTL sweep…';
    const res = await apiClient.makeRequest('POST', '/api/v1/jobs/ttl/sweep', { body });
    resultEl.textContent = JSON.stringify(res, null, 2);
    const affected = (res && typeof res.affected === 'number') ? res.affected : (res?.data?.affected || 0);
    Toast.success(`TTL sweep affected ${affected} job(s)`);
    const ts = new Date().toLocaleString();
    const scope = [domain && `domain=${domain}`, queue && `queue=${queue}`, jobType && `job_type=${jobType}`].filter(Boolean).join(', ');
    if (summaryEl) summaryEl.textContent = `TTL ${action} sweep affected ${affected} job(s) [${scope || 'unscoped'}] - ${ts}`;
    if (typeof adminFetchJobsStats === 'function') adminFetchJobsStats();
  } catch (e) {
    const err = e && (e.response || e);
    resultEl.textContent = JSON.stringify(err, null, 2);
    Toast.error('TTL sweep failed');
    if (summaryEl) summaryEl.textContent = '-';
  } finally {
    if (btn) btn.disabled = false;
    Loading.hide(resultEl);
  }
}

async function adminRequeueQuarantined() {
  const btn = document.getElementById('adminJobsRequeue_btn');
  const resultEl = document.getElementById('adminJobsRequeue_result');
  const summaryEl = document.getElementById('adminJobsRequeue_summary');
  const domain = (document.getElementById('adminJobs_domain')?.value || '').trim();
  const queue = (document.getElementById('adminJobs_queue')?.value || '').trim();
  const jobType = (document.getElementById('adminJobs_jobType')?.value || '').trim();
  const dryRun = !!document.getElementById('adminJobsRequeue_dryRun')?.checked;
  if (!domain) {
    Toast.error('Provide a domain to scope requeue');
    return;
  }
  try {
    if (btn) btn.disabled = true;
    Loading.show(resultEl, 'Requeuing quarantined…');
    if (summaryEl) summaryEl.textContent = 'Running requeue…';
    const body = { domain, dry_run: dryRun };
    if (queue) body.queue = queue;
    if (jobType) body.job_type = jobType;
    const headers = dryRun ? {} : { 'X-Confirm': 'true' };
    const res = await apiClient.makeRequest('POST', '/api/v1/jobs/batch/requeue_quarantined', { body, headers });
    resultEl.textContent = JSON.stringify(res, null, 2);
    const affected = (res && typeof res.affected === 'number') ? res.affected : (res?.data?.affected || 0);
    Toast.success(`${dryRun ? 'Would requeue' : 'Requeued'} ${affected} job(s)`);
    const ts = new Date().toLocaleString();
    const scope = [domain && `domain=${domain}`, queue && `queue=${queue}`, jobType && `job_type=${jobType}`].filter(Boolean).join(', ');
    if (summaryEl) summaryEl.textContent = `${dryRun ? 'Dry run' : 'Requeued'} ${affected} quarantined job(s) [${scope || 'unscoped'}] - ${ts}`;
    if (typeof adminFetchJobsStats === 'function') adminFetchJobsStats();
  } catch (e) {
    const err = e && (e.response || e);
    resultEl.textContent = JSON.stringify(err, null, 2);
    Toast.error('Requeue failed');
    if (summaryEl) summaryEl.textContent = '-';
  } finally {
    if (btn) btn.disabled = false;
    Loading.hide(resultEl);
  }
}

// ---- Live Events stream helpers ----
let adminJobsEventsAbort = null;
let adminJobsEventsCursor = 0;
const adminJobsFailureTimelines = {}; // job_id -> [retry_backoff...]

function renderSparkline(vals) {
  if (!vals || !vals.length) return '';
  const ticks = ['▁','▂','▃','▄','▅','▆','▇','█'];
  const max = Math.max(...vals);
  if (max <= 0) return '▁'.repeat(Math.min(vals.length, 20));
  return vals.slice(-20).map(v => {
    const idx = Math.min(ticks.length - 1, Math.floor((v / max) * (ticks.length - 1)));
    return ticks[idx];
  }).join('');
}

// auth headers now handled by apiClient.streamSSE

function adminStopJobsEvents() {
  try { if (adminJobsEventsAbort) adminJobsEventsAbort.abort(); } catch (e) {}
  adminJobsEventsAbort = null;
}

async function adminStartJobsEvents() {
  adminStopJobsEvents();
  // Create streaming SSE via apiClient
  adminJobsEventsAbort = null;
  const tbody = document.getElementById('adminJobsEvents_tableBody');
  if (tbody) {
    const tr = document.createElement('tr');
    const td = document.createElement('td');
    td.colSpan = 6;
    td.className = 'text-muted';
    td.textContent = 'Connecting…';
    tr.appendChild(td);
    tbody.innerHTML = '';
    tbody.appendChild(tr);
  }
  // Keep a bounded buffer of recent events to avoid unbounded growth
  // Allow user-configured cap via input #adminJobsEvents_max or local storage key 'admin-jobs-events-max'
  const EVENTS_MAX = (() => {
    try {
      const input = document.getElementById('adminJobsEvents_max');
      const readStored = () => {
        try {
          if (typeof Utils !== 'undefined') {
            return Utils.getFromStorage('admin-jobs-events-max');
          }
          return (typeof localStorage !== 'undefined') ? localStorage.getItem('admin-jobs-events-max') : null;
        } catch (_) { return null; }
      };
      let v = NaN;
      if (input && input.value) {
        v = parseInt(input.value, 10);
      } else {
        const saved = readStored();
        if (saved != null) v = parseInt(saved, 10);
      }
      if (!Number.isFinite(v) || v <= 0) v = 100; // default
      if (input) input.value = String(v);
      try {
        if (typeof Utils !== 'undefined') Utils.saveToStorage('admin-jobs-events-max', v);
        else if (typeof localStorage !== 'undefined') localStorage.setItem('admin-jobs-events-max', String(v));
      } catch (_) {}
      return v;
    } catch (_) {
      return 100;
    }
  })();
  const events = [];
  const handle = apiClient.streamSSE('/api/v1/jobs/events/stream', {
    method: 'GET',
    query: { after_id: String(adminJobsEventsCursor || 0) },
    timeout: 600000,
    onEvent: (obj) => {
      try {
        adminJobsEventsCursor += 1;
        const jid = obj.job_id || obj.attrs?.job_id;
        const backoff = obj.attrs?.retry_backoff;
        if (jid && typeof backoff === 'number') {
          const arr = adminJobsFailureTimelines[jid] || [];
          arr.push(backoff);
          adminJobsFailureTimelines[jid] = arr.slice(-20);
        }
        events.push(obj);
        // Trim to the last EVENTS_MAX items to cap memory
        if (events.length > EVENTS_MAX) {
          events.splice(0, events.length - EVENTS_MAX);
        }
      } catch (_) {}
      if (tbody) {
        tbody.innerHTML = '';
        const last = events.slice(-20);
        for (const ev of last) {
          const tr = document.createElement('tr');
          const jid = ev.job_id || '';
          const tl = adminJobsFailureTimelines[jid] || [];
          const cells = [];
          const tdId = document.createElement('td');
          tdId.textContent = String(jid || ''); cells.push(tdId);
          const tdEvent = document.createElement('td');
          tdEvent.textContent = String(ev.event || ''); cells.push(tdEvent);
          const tdDqt = document.createElement('td');
          const dqt = [ev.domain, ev.queue, ev.job_type].filter(Boolean).join('/');
          tdDqt.textContent = dqt || ''; cells.push(tdDqt);
          const tdFail = document.createElement('td');
          tdFail.textContent = renderSparkline(tl); cells.push(tdFail);
          const tdCorr = document.createElement('td');
          if (ev.request_id) { const s = document.createElement('span'); s.className = 'chip'; s.textContent = `req:${String(ev.request_id)}`; tdCorr.appendChild(s); }
          if (ev.trace_id) { const s = document.createElement('span'); s.className = 'chip'; s.textContent = `trace:${String(ev.trace_id)}`; tdCorr.appendChild(s); }
          cells.push(tdCorr);
          const tdAttrs = document.createElement('td');
          const code = document.createElement('code'); code.style.fontSize = '11px'; code.textContent = JSON.stringify(ev.attrs || {});
          tdAttrs.appendChild(code); cells.push(tdAttrs);
          for (const td of cells) tr.appendChild(td);
          tbody.appendChild(tr);
        }
        if (!last.length) {
          const tr = document.createElement('tr');
          const td = document.createElement('td'); td.colSpan = 6; td.className = 'text-muted'; td.textContent = 'No events yet';
          tr.appendChild(td); tbody.appendChild(tr);
        }
      }
    }
  });
  adminJobsEventsAbort = handle;
}

// Initialize on load for the Jobs tab content
(function () {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', adminJobsInit);
  } else {
    adminJobsInit();
  }
})();

// Test-friendly export
if (typeof module !== 'undefined' && module.exports) {
  module.exports = {
    adminFetchJobsStats,
    adminStartJobsEvents,
    adminStopJobsEvents,
    renderSparkline,
  };
}
