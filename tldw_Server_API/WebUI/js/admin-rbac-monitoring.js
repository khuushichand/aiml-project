// admin-rbac-monitoring.js
// Move Admin Monitoring bindings + helpers off inline handlers.
// RBAC: for now, only bind ID-based events to existing inline functions if present.

function esc(x) {
  const str = String(x ?? '');
  if (typeof Utils !== 'undefined' && Utils.escapeHtml) return Utils.escapeHtml(str);
  // Safe fallback: escape critical HTML characters
  return str
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;')
    .replace(/\//g, '&#x2F;');
}

// -------- Monitoring: Watchlists --------
async function monListWatchlists() {
  try {
    const res = await window.apiClient.get('/api/v1/monitoring/watchlists');
    const listEl = document.getElementById('monitoringWatchlists_list');
    let wls = (res && res.watchlists) || [];
    const fScope = (document.getElementById('monWl_filter_scope_type')?.value || '').trim();
    const fId = (document.getElementById('monWl_filter_scope_id')?.value || '').trim();
    if (fScope) wls = wls.filter(w => (w.scope_type || '') === fScope);
    if (fId) wls = wls.filter(w => String(w.scope_id || '') === fId);
    const showId = !!document.getElementById('monWl_col_id')?.checked;
    const showScope = !!document.getElementById('monWl_col_scope')?.checked;
    const showRules = !!document.getElementById('monWl_col_rules')?.checked;
    let html = '<table class="api-table"><thead><tr>';
    if (showId) html += '<th>ID</th>';
    html += '<th>Name</th>';
    if (showScope) html += '<th>Scope</th>';
    html += '<th>Enabled</th>';
    if (showRules) html += '<th>Rules</th>';
    html += '<th>Actions</th></tr></thead><tbody>';
    for (const wl of wls) {
      html += '<tr>';
      if (showId) html += `<td>${esc(wl.id || '')}</td>`;
      html += `<td>${esc(wl.name || '')}</td>`;
      if (showScope) html += `<td>${esc(wl.scope_type || '')}:${esc(wl.scope_id || '')}</td>`;
      html += `<td>${esc(String(wl.enabled))}</td>`;
      if (showRules) html += `<td>${esc(String((wl.rules||[]).length))}</td>`;
      if (wl.scope_type === 'team' || wl.scope_type === 'org') {
        html += `<td><button class="btn mon-apply-scope" data-st="${esc(wl.scope_type)}" data-sid="${esc(wl.scope_id)}">Apply Defaults to Scope</button></td>`;
      } else {
        html += '<td></td>';
      }
      html += '</tr>';
    }
    html += '</tbody></table>';
    listEl.innerHTML = html;
  } catch (e) {
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to list watchlists');
  }
}

async function monApplyDefaultsToScope(scopeType, scopeId) {
  try {
    if (!scopeType || !scopeId) { Toast.error('Missing scope'); return; }
    const listed = await window.apiClient.get('/api/v1/monitoring/watchlists');
    const wls = (listed && listed.watchlists) || [];
    const defaults = wls.filter(w => (w.scope_type === 'global' || w.scope_type === 'all') && ((w.name || '').startsWith('Kid-Safe Defaults')));
    if (defaults.length === 0) { Toast.error('No default watchlists found'); return; }
    let created = 0;
    for (const wl of defaults) {
      const payload = { id: null, name: `${wl.name} [${scopeType}:${scopeId}]`, description: wl.description || '', enabled: true, scope_type: scopeType, scope_id: scopeId, rules: wl.rules || [] };
      try { await window.apiClient.post('/api/v1/monitoring/watchlists', payload); created += 1; } catch (_) {}
    }
    Toast.success(`Applied ${created} default watchlists to ${scopeType}:${scopeId}`);
    await monListWatchlists();
  } catch (e) {
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to apply defaults');
  }
}

async function monReloadWatchlists() {
  try {
    const res = await window.apiClient.post('/api/v1/monitoring/reload');
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(res, null, 2);
    await monListWatchlists();
  } catch (e) {
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to reload');
  }
}

async function monUpsertWatchlist() {
  try {
    const id = (document.getElementById('monWl_id')?.value || '').trim() || null;
    const name = (document.getElementById('monWl_name')?.value || '').trim();
    const description = (document.getElementById('monWl_desc')?.value || '').trim() || '';
    const enabled = (document.getElementById('monWl_enabled')?.value === 'true');
    const scope_type = (document.getElementById('monWl_scope_type')?.value || 'global');
    const scope_id = (document.getElementById('monWl_scope_id')?.value || '') || null;
    const rules_raw = document.getElementById('monWl_rules')?.value || '[]';
    let rules;
    try { rules = JSON.parse(rules_raw); } catch (e) { Toast.error('Rules must be JSON'); return; }
    const body = { id, name, description, enabled, scope_type, scope_id, rules };
    const res = await window.apiClient.post('/api/v1/monitoring/watchlists', body);
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(res, null, 2);
    Toast.success('Saved');
    await monListWatchlists();
  } catch (e) {
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to save watchlist');
  }
}

async function monDeleteWatchlist() {
  try {
    const id = (document.getElementById('monWl_id')?.value || '').trim();
    if (!id) { Toast.error('Enter watchlist ID to delete'); return; }
    if (!confirm('Delete watchlist ' + id + '?')) return;
    const res = await window.apiClient.delete(`/api/v1/monitoring/watchlists/${encodeURIComponent(id)}`);
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(res, null, 2);
    Toast.success('Deleted');
    await monListWatchlists();
  } catch (e) {
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to delete watchlist');
  }
}

async function monQuickApplyDefaults(scopeType) {
  const id = (scopeType === 'team') ? (document.getElementById('monQuick_team')?.value || '').trim() : (document.getElementById('monQuick_org')?.value || '').trim();
  if (!id) { Toast.error(`Enter a ${scopeType} id`); return; }
  await monApplyDefaultsToScope(scopeType, id);
}

async function monBulkApplyDefaults() {
  try {
    const scopeType = document.getElementById('monBulk_scope')?.value || 'team';
    const raw = (document.getElementById('monBulk_ids')?.value || '').trim();
    if (!raw) { Toast.error('Enter at least one ID'); return; }
    const parts = raw.split(/\n|,/).map(s => s.trim()).filter(Boolean);
    if (parts.length === 0) { Toast.error('No valid IDs found'); return; }
    const listed = await window.apiClient.get('/api/v1/monitoring/watchlists');
    const wls = (listed && listed.watchlists) || [];
    const defaults = wls.filter(w => (w.scope_type === 'global' || w.scope_type === 'all') && ((w.name || '').startsWith('Kid-Safe Defaults')));
    if (defaults.length === 0) { Toast.error('No default watchlists found'); return; }
    let totalCreated = 0;
    for (const sid of parts) {
      for (const wl of defaults) {
        const payload = { id: null, name: `${wl.name} [${scopeType}:${sid}]`, description: wl.description || '', enabled: true, scope_type: scopeType, scope_id: sid, rules: wl.rules || [] };
        try { await window.apiClient.post('/api/v1/monitoring/watchlists', payload); totalCreated += 1; } catch (_) {}
      }
    }
    Toast.success(`Applied ${totalCreated} watchlists to ${parts.length} ${scopeType} id(s)`);
  } catch (e) {
    document.getElementById('monitoringWatchlists_result').textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Bulk apply failed');
  }
}

// -------- Monitoring: Alerts --------
async function monListAlerts() {
  try {
    const params = new URLSearchParams();
    const uid = (document.getElementById('monAlerts_user')?.value || '').trim();
    const since = (document.getElementById('monAlerts_since')?.value || '').trim();
    const unread = (document.getElementById('monAlerts_unread')?.value || 'false');
    const limit = (document.getElementById('monAlerts_limit')?.value || '').trim();
    if (uid) params.append('user_id', uid);
    if (since) params.append('since', since);
    if (unread) params.append('unread_only', unread);
    if (limit) params.append('limit', limit);
    const res = await window.apiClient.get('/api/v1/monitoring/alerts' + (params.toString() ? ('?' + params.toString()) : ''));
    const list = Array.isArray(res.items) ? res.items : (res.alerts || []);
    const box = document.getElementById('monitoringAlerts_list');
    if (!list.length) { box.innerHTML = '<p>No alerts.</p>'; return; }
    let html = '<table class="simple-table"><thead><tr><th>Time</th><th>User</th><th>Source</th><th>Category</th><th>Severity</th><th>Pattern</th><th>Text Snippet</th><th>Actions</th></tr></thead><tbody>';
    for (const a of list) {
      html += `<tr>
        <td>${esc(a.created_at || '')}</td>
        <td>${esc(a.user_id ?? '')}</td>
        <td>${esc(a.source || '')}</td>
        <td>${esc(a.rule_category || '')}</td>
        <td>${esc(a.rule_severity || '')}</td>
        <td>${esc(a.pattern || '')}</td>
        <td>${esc(a.text_snippet || '')}</td>
        <td>${a.id ? `<button class="btn mon-alert-mark" data-id="${esc(a.id)}">Mark read</button>` : ''}</td>
      </tr>`;
    }
    html += '</tbody></table>';
    box.innerHTML = html;
  } catch (e) {
    document.getElementById('monitoringAlerts_list').innerHTML = `<pre>${esc(JSON.stringify(e.response || e, null, 2))}</pre>`;
    Toast.error('Failed to list alerts');
  }
}

async function monMarkAlertRead(id) {
  try {
    if (!id) return;
    const safeId = encodeURIComponent(id);
    await window.apiClient.post(`/api/v1/monitoring/alerts/${safeId}/read`, {});
    Toast.success('Marked read');
    await monListAlerts();
  } catch (e) { Toast.error('Mark read failed'); }
}

async function monLoadRecentAlerts() {
  try {
    const limit = parseInt(document.getElementById('monAlerts_recent_limit')?.value || '10', 10);
    const unreadOnly = (document.getElementById('monAlerts_recent_unread')?.value === 'true');
    const qs = new URLSearchParams({ limit: String(limit) });
    if (unreadOnly) qs.set('unread_only','true');
    const res = await window.apiClient.get(`/api/v1/monitoring/alerts?${qs.toString()}`);
    const list = Array.isArray(res.items) ? res.items : (res.alerts || []);
    const box = document.getElementById('monitoringAlerts_recent');
    if (!list.length) { box.innerHTML = '<p>No recent alerts.</p>'; return; }
    box.innerHTML = '<ul>' + list.map(a => (
      `<li><strong>${esc(a.rule_severity || '')}</strong> [${esc(a.rule_category || '')}] ${esc(String((a.text_snippet || '')).slice(0,100))} <em>${esc(a.created_at || '')}</em></li>`
    )).join('') + '</ul>';
    const ts = new Date().toISOString();
    const label = document.getElementById('monAlerts_last_update'); if (label) label.textContent = ts;
  } catch (e) { document.getElementById('monitoringAlerts_recent').innerHTML = `<pre>${esc(JSON.stringify(e.response || e, null, 2))}</pre>`; }
}

// -------- Monitoring: Notifications --------
async function monLoadNotifSettings() {
  try {
    const s = await window.apiClient.get('/api/v1/monitoring/notifications/settings');
    document.getElementById('monNotif_enabled').value = String(!!s.enabled);
    document.getElementById('monNotif_min_sev').value = s.min_severity || 'critical';
    document.getElementById('monNotif_file').value = s.file || '';
    document.getElementById('monNotif_webhook').value = s.webhook_url || '';
    document.getElementById('monNotif_email_to').value = s.email_to || '';
    document.getElementById('monNotif_smtp_host').value = s.smtp_host || '';
    document.getElementById('monNotif_smtp_port').value = s.smtp_port || 587;
    document.getElementById('monNotif_smtp_starttls').value = String(!!s.smtp_starttls);
    document.getElementById('monNotif_smtp_user').value = s.smtp_user || '';
    document.getElementById('monNotif_email_from').value = s.email_from || '';
    document.getElementById('monitoringNotif_result').textContent = JSON.stringify(s, null, 2);
  } catch (e) { document.getElementById('monitoringNotif_result').textContent = JSON.stringify(e.response || e, null, 2); Toast.error('Failed to load settings'); }
}

async function monSaveNotifSettings() {
  try {
    const body = {
      enabled: (document.getElementById('monNotif_enabled')?.value === 'true'),
      min_severity: document.getElementById('monNotif_min_sev')?.value || 'critical',
      file: document.getElementById('monNotif_file')?.value || '',
      webhook_url: document.getElementById('monNotif_webhook')?.value || '',
      email_to: document.getElementById('monNotif_email_to')?.value || '',
      email_from: document.getElementById('monNotif_email_from')?.value || '',
      smtp_host: document.getElementById('monNotif_smtp_host')?.value || '',
      smtp_port: parseInt(document.getElementById('monNotif_smtp_port')?.value || '587', 10),
      smtp_starttls: (document.getElementById('monNotif_smtp_starttls')?.value === 'true'),
      smtp_user: document.getElementById('monNotif_smtp_user')?.value || '',
      smtp_password: document.getElementById('monNotif_smtp_pass')?.value || '',
    };
    const res = await window.apiClient.put('/api/v1/monitoring/notifications/settings', body);
    document.getElementById('monitoringNotif_result').textContent = JSON.stringify(res, null, 2);
    Toast.success('Saved');
  } catch (e) { document.getElementById('monitoringNotif_result').textContent = JSON.stringify(e.response || e, null, 2); Toast.error('Failed to save settings'); }
}

function monClearNotifDrafts() {
  const ids = ['monNotif_enabled','monNotif_min_sev','monNotif_file','monNotif_webhook','monNotif_email_to','monNotif_smtp_host','monNotif_smtp_port','monNotif_smtp_starttls','monNotif_smtp_user','monNotif_email_from','monNotif_smtp_pass'];
  for (const id of ids) { try { localStorage.removeItem(id); } catch (_) {} }
  // Reset UI fields to sane defaults so the form matches cleared state
  try {
    const setVal = (id, val) => { const el = document.getElementById(id); if (el) el.value = String(val); };
    setVal('monNotif_enabled', 'false');
    setVal('monNotif_min_sev', 'critical');
    setVal('monNotif_file', '');
    setVal('monNotif_webhook', '');
    setVal('monNotif_email_to', '');
    setVal('monNotif_email_from', '');
    setVal('monNotif_smtp_host', '');
    setVal('monNotif_smtp_port', 587);
    setVal('monNotif_smtp_starttls', 'false');
    setVal('monNotif_smtp_user', '');
    setVal('monNotif_smtp_pass', '');
  } catch (_) { /* ignore */ }
  Toast.success('Drafts cleared');
}

async function monRestoreNotifDefaults() {
  await monLoadNotifSettings();
  Toast.success('Defaults loaded');
}

async function monSendNotifTest() {
  try {
    const severity = document.getElementById('monNotif_test_sev')?.value || 'info';
    const message = document.getElementById('monNotif_test_msg')?.value || 'Test notification';
    const res = await window.apiClient.post('/api/v1/monitoring/notifications/test', { severity, message });
    document.getElementById('monitoringNotif_result').textContent = JSON.stringify(res, null, 2);
    Toast.success('Sent test');
  } catch (e) { document.getElementById('monitoringNotif_result').textContent = JSON.stringify(e.response || e, null, 2); Toast.error('Test failed'); }
}

async function monLoadRecentNotifications() {
  try {
    const limit = parseInt(document.getElementById('monNotif_recent_limit')?.value || '50', 10);
    const res = await window.apiClient.get(`/api/v1/monitoring/notifications/recent?limit=${limit}`);
    const items = Array.isArray(res.items) ? res.items : (res.notifications || []);
    const box = document.getElementById('monitoringNotif_recent');
    if (!items.length) { box.innerHTML = '<p>No recent notifications.</p>'; return; }
    box.innerHTML = '<ul>' + items.map(n => (
      `<li>[${esc(n.rule_severity || '')}] (${esc(n.rule_category || '')}) ${esc(n.source || '')} user:${esc(n.user_id ?? '')} - ${esc(n.snippet || '')} <em>${esc(n.ts || '')}</em></li>`
    )).join('') + '</ul>';
    const ts = new Date().toISOString();
    const last = document.getElementById('monNotif_last_update'); if (last) last.textContent = ts;
    const upd = document.getElementById('monNotif_updated'); if (upd) { upd.textContent = '✓'; setTimeout(() => upd.textContent = '', 1000); }
  } catch (e) { document.getElementById('monitoringNotif_recent').innerHTML = `<pre>${esc(JSON.stringify(e.response || e, null, 2))}</pre>`; }
}

function monResetAllMonitoringUI() {
  try {
    const ids = ['monWl_filter_scope_type','monWl_filter_scope_id','monWl_col_id','monWl_col_scope','monWl_col_rules','monWl_id','monWl_name','monWl_desc','monWl_scope_id','monWl_rules'];
    ids.forEach((id) => {
      const el = document.getElementById(id);
      if (!el) return;
      if (el.type === 'checkbox') {
        el.checked = false;
        return;
      }
      if (el.tagName === 'INPUT' || el.tagName === 'TEXTAREA') {
        el.value = '';
      } else if (el.tagName === 'SELECT') {
        el.selectedIndex = 0;
      }
    });
  } catch (_) {}
  document.getElementById('monitoringWatchlists_list')?.replaceChildren();
  document.getElementById('monitoringWatchlists_result')?.replaceChildren();
  document.getElementById('monitoringAlerts_list')?.replaceChildren();
  document.getElementById('monitoringAlerts_recent')?.replaceChildren();
  document.getElementById('monitoringNotif_recent')?.replaceChildren();
  Toast.success('Monitoring UI reset');
}

// -------- RBAC: Bindings (call inline impl if present) --------
function bindRbacHandlers() {
  // Replace critical inline handlers with IDs and bindings if elements exist
  const bind = (id, fnName) => { const el = document.getElementById(id); if (el) el.addEventListener('click', () => { if (typeof window[fnName] === 'function') window[fnName](); }); };
  // Examples: load matrices, export, copy, reload
  bind('btnRbacLoadList', 'loadRbacMatrixList');
  bind('btnRbacLoadBoolean', 'loadRbacMatrixBoolean');
  bind('btnRbacReload', 'reloadRbacMatrices');
  bind('btnRbacExportMatrix', 'exportRbacMatrixCsv');
  bind('btnRbacExportList', 'exportRbacListCsv');
  bind('btnRbacCopySummary', 'copyRbacSummary');
  bind('btnRbacClearFilters', 'clearRbacFilters');
  // Pagination
  const prev = document.getElementById('rbacPrevBtn'); if (prev) prev.addEventListener('click', () => { if (typeof window.rbacPrevPage === 'function') window.rbacPrevPage(); });
  const next = document.getElementById('rbacNextBtn'); if (next) next.addEventListener('click', () => { if (typeof window.rbacNextPage === 'function') window.rbacNextPage(); });
  // Select/Clear role names
  bind('btnRbacSelectAllRoles', 'rbacSelectAllRoleNames');
  bind('btnRbacClearRoles', 'rbacClearRoleNames');
  // Category filters on inputs
  const cat = document.getElementById('rbacMatrixCategory'); if (cat) cat.addEventListener('change', () => { if (window.RBAC_CACHE && window.RBAC_CACHE.boolean && typeof window.renderRbacMatrixBoolean === 'function') window.renderRbacMatrixBoolean(); if (window.RBAC_CACHE && window.RBAC_CACHE.list && typeof window.renderRbacMatrixList === 'function') window.renderRbacMatrixList(); });
  const search = document.getElementById('rbacMatrixSearch'); if (search) search.addEventListener('input', () => { if (window.RBAC_CACHE && window.RBAC_CACHE.boolean && typeof window.renderRbacMatrixBoolean === 'function') window.renderRbacMatrixBoolean(); if (window.RBAC_CACHE && window.RBAC_CACHE.list && typeof window.renderRbacMatrixList === 'function') window.renderRbacMatrixList(); });
  const pinned = document.getElementById('rbacMatrixPinned'); if (pinned) pinned.addEventListener('input', () => { if (window.RBAC_CACHE && window.RBAC_CACHE.boolean && typeof window.renderRbacMatrixBoolean === 'function') window.renderRbacMatrixBoolean(); if (window.RBAC_CACHE && window.RBAC_CACHE.list && typeof window.renderRbacMatrixList === 'function') window.renderRbacMatrixList(); });
  const vis = document.getElementById('rbacVisibleCats'); if (vis) vis.addEventListener('change', () => { if (window.RBAC_CACHE && window.RBAC_CACHE.boolean && typeof window.renderRbacMatrixBoolean === 'function') window.renderRbacMatrixBoolean(); if (typeof window._saveRbacFilterState === 'function') window._saveRbacFilterState(); });
}

function bindMonitoringHandlers() {
  document.getElementById('btnMonResetUI')?.addEventListener('click', monResetAllMonitoringUI);
  document.getElementById('btnMonWlList')?.addEventListener('click', monListWatchlists);
  document.getElementById('btnMonWlReload')?.addEventListener('click', monReloadWatchlists);
  document.getElementById('btnMonWlSave')?.addEventListener('click', monUpsertWatchlist);
  document.getElementById('btnMonWlDelete')?.addEventListener('click', monDeleteWatchlist);
  document.getElementById('btnMonQuickTeam')?.addEventListener('click', () => monQuickApplyDefaults('team'));
  document.getElementById('btnMonQuickOrg')?.addEventListener('click', () => monQuickApplyDefaults('org'));
  document.getElementById('btnMonBulkApply')?.addEventListener('click', monBulkApplyDefaults);
  // Delegated click for Apply Defaults to Scope buttons
  document.getElementById('monitoringWatchlists_list')?.addEventListener('click', (e) => {
    const t = e.target; if (t && t.classList?.contains('mon-apply-scope')) { const st = t.getAttribute('data-st'); const sid = t.getAttribute('data-sid'); if (st && sid) monApplyDefaultsToScope(st, sid); }
  });
  // Alerts
  document.getElementById('btnMonAlertsList')?.addEventListener('click', monListAlerts);
  document.getElementById('monitoringAlerts_list')?.addEventListener('click', (e) => { const t = e.target; if (t && t.classList?.contains('mon-alert-mark')) { const id = t.getAttribute('data-id'); if (id) monMarkAlertRead(id); } });
  document.getElementById('btnMonAlertsLoadRecent')?.addEventListener('click', monLoadRecentAlerts);
  // Notifications
  document.getElementById('btnMonNotifLoad')?.addEventListener('click', monLoadNotifSettings);
  document.getElementById('btnMonNotifSave')?.addEventListener('click', monSaveNotifSettings);
  document.getElementById('btnMonNotifClearDrafts')?.addEventListener('click', monClearNotifDrafts);
  document.getElementById('btnMonNotifRestoreDefaults')?.addEventListener('click', monRestoreNotifDefaults);
  document.getElementById('btnMonNotifSendTest')?.addEventListener('click', monSendNotifTest);
  document.getElementById('btnMonNotifLoadRecent')?.addEventListener('click', monLoadRecentNotifications);
}

function bindAdminRbacMonitoring() {
  bindRbacHandlers();
  bindMonitoringHandlers();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindAdminRbacMonitoring);
  else bindAdminRbacMonitoring();
}

export default {
  monListWatchlists, monApplyDefaultsToScope, monReloadWatchlists, monUpsertWatchlist, monDeleteWatchlist, monQuickApplyDefaults, monBulkApplyDefaults,
  monListAlerts, monMarkAlertRead, monLoadRecentAlerts,
  monLoadNotifSettings, monSaveNotifSettings, monClearNotifDrafts, monRestoreNotifDefaults, monSendNotifTest, monLoadRecentNotifications,
  monResetAllMonitoringUI,
  bindAdminRbacMonitoring,
};
