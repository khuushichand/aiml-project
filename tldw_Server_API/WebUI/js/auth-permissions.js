// auth-permissions.js
// Renders a self-scoped permissions matrix for the Auth → Permissions Matrix subtab.
// Uses /api/v1/privileges/self and provides a boolean grid by scope plus a detailed list.

/* global Toast */

const AUTH_PERM_CACHE = {
  self: null,
  lastLoadedAt: null,
};

function _ap_escape(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text ?? '').replace(/[&<>"']/g, m => map[m]);
}

function _ap_summarize(items) {
  const total = items.length;
  let allowed = 0, blocked = 0;
  for (const it of items) {
    if ((it.status || '').toLowerCase() === 'allowed') allowed++; else blocked++;
  }
  return { total, allowed, blocked };
}

function _ap_matches(item, query) {
  if (!query) return true;
  const q = query.toLowerCase();
  const fields = [item.endpoint, item.method, item.privilege_scope_id, item.feature_flag_id, (item.sensitivity_tier || '')].map(v => String(v || '').toLowerCase());
  return fields.some(f => f.includes(q));
}

function _ap_filteredItems() {
  const q = (document.getElementById('authPermSearch')?.value || '').trim();
  const items = Array.isArray(AUTH_PERM_CACHE.self?.items) ? AUTH_PERM_CACHE.self.items : [];
  if (!q) return items;
  return items.filter(it => _ap_matches(it, q));
}

function _ap_renderSummary() {
  const el = document.getElementById('authPermSummary');
  if (!el) return;
  const items = _ap_filteredItems();
  const { total, allowed, blocked } = _ap_summarize(items);
  const ts = AUTH_PERM_CACHE.lastLoadedAt ? new Date(AUTH_PERM_CACHE.lastLoadedAt).toLocaleString() : '-';
  el.innerHTML = `Items: <strong>${total}</strong> · Allowed: <strong>${allowed}</strong> · Blocked: <strong>${blocked}</strong> · Loaded: ${_ap_escape(ts)}`;
}

function _ap_renderMatrixByScope() {
  const container = document.getElementById('authPermMatrixByScope');
  if (!container) return;
  const items = _ap_filteredItems();
  if (!items.length) { container.innerHTML = '<p>No data. Click Refresh to load.</p>'; return; }
  // Build unique sets
  const scopes = Array.from(new Set(items.map(it => it.privilege_scope_id))).sort();
  const endpoints = Array.from(new Set(items.map(it => `${(it.method || '').toUpperCase()} ${it.endpoint}`))).sort();
  // Map of endpoint -> scope -> allowed bool
  const grid = new Map();
  for (const ep of endpoints) grid.set(ep, new Map());
  for (const it of items) {
    const ep = `${(it.method || '').toUpperCase()} ${it.endpoint}`;
    const sc = it.privilege_scope_id;
    const allowed = (it.status || '').toLowerCase() === 'allowed';
    const row = grid.get(ep) || new Map();
    row.set(sc, allowed);
    grid.set(ep, row);
  }
  // Render simple boolean grid
  let html = '<div class="scroll-x"><table class="simple-table small-table">';
  html += '<thead><tr><th class="rbac-sticky-left header">Endpoint \\ Scope</th>' + scopes.map(s => `<th>${_ap_escape(s)}</th>`).join('') + '</tr></thead>';
  html += '<tbody>';
  for (const ep of endpoints) {
    html += `<tr><td class="rbac-sticky-left"><strong>${_ap_escape(ep)}</strong></td>`;
    const row = grid.get(ep) || new Map();
    for (const sc of scopes) {
      const v = !!row.get(sc);
      html += `<td style="text-align:center;">${v ? '✓' : ''}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table></div>';
  container.innerHTML = html;
}

function _ap_renderList() {
  const container = document.getElementById('authPermList');
  if (!container) return;
  const items = _ap_filteredItems();
  if (!items.length) { container.innerHTML = '<p>No permission entries.</p>'; return; }
  let html = '<div class="scroll-y"><table class="simple-table small-table">';
  html += '<thead><tr>' +
    '<th>Method</th><th>Endpoint</th><th>Scope</th><th>Status</th><th>Sensitivity</th><th>Feature Flag</th><th>Rate Class</th>' +
    '</tr></thead>';
  html += '<tbody>';
  for (const it of items) {
    html += '<tr>' +
      `<td>${_ap_escape((it.method || '').toUpperCase())}</td>` +
      `<td>${_ap_escape(it.endpoint)}</td>` +
      `<td>${_ap_escape(it.privilege_scope_id)}</td>` +
      `<td>${_ap_escape(it.status)}</td>` +
      `<td>${_ap_escape(it.sensitivity_tier || '')}</td>` +
      `<td>${_ap_escape(it.feature_flag_id || '')}</td>` +
      `<td>${_ap_escape(it.rate_limit_class || '')}</td>` +
      '</tr>';
  }
  html += '</tbody></table></div>';
  container.innerHTML = html;
}

function _ap_renderAll() {
  _ap_renderSummary();
  _ap_renderMatrixByScope();
  _ap_renderList();
}

async function loadSelfPermissions() {
  try {
    const summary = document.getElementById('authPermSummary');
    if (summary) summary.textContent = 'Loading…';
    const data = await window.apiClient.get('/api/v1/privileges/self');
    AUTH_PERM_CACHE.self = data || { items: [] };
    AUTH_PERM_CACHE.lastLoadedAt = new Date().toISOString();
    _ap_renderAll();
    Toast?.success && Toast.success('Loaded permissions');
  } catch (e) {
    const container = document.getElementById('authPermList');
    if (container) container.innerHTML = `<pre>${_ap_escape(JSON.stringify(e.response || e, null, 2))}</pre>`;
    const matrix = document.getElementById('authPermMatrixByScope');
    if (matrix) matrix.innerHTML = '';
    const summary = document.getElementById('authPermSummary');
    if (summary) summary.textContent = 'Failed to load permissions';
    Toast?.error && Toast.error('Failed to load permissions');
  }
}

function exportSelfPermissionsCsv() {
  const items = _ap_filteredItems();
  const fields = ['method','endpoint','privilege_scope_id','status','sensitivity_tier','feature_flag_id','rate_limit_class'];
  const csvEsc = (v) => '"' + String(v ?? '').replace(/"/g, '""') + '"';
  let csv = '';
  csv += fields.map(csvEsc).join(',') + '\n';
  for (const it of items) {
    const row = [
      (it.method || '').toUpperCase(),
      it.endpoint,
      it.privilege_scope_id,
      it.status,
      it.sensitivity_tier || '',
      it.feature_flag_id || '',
      it.rate_limit_class || '',
    ];
    csv += row.map(csvEsc).join(',') + '\n';
  }
  const blob = new Blob([csv], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'my-permissions.csv';
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

function _ap_bindHandlers() {
  const refreshBtn = document.getElementById('btnAuthPermRefresh');
  refreshBtn && refreshBtn.addEventListener('click', loadSelfPermissions);
  const exportBtn = document.getElementById('btnAuthPermExport');
  exportBtn && exportBtn.addEventListener('click', exportSelfPermissionsCsv);
  const search = document.getElementById('authPermSearch');
  search && search.addEventListener('input', () => _ap_renderAll());
}

// Bind when the subtab content is present in DOM
document.addEventListener('DOMContentLoaded', () => {
  _ap_bindHandlers();
});

// In case the content is dynamically injected later, use a MutationObserver to bind once present
const _ap_observer = new MutationObserver(() => {
  if (document.getElementById('tabAuthPermissionsMatrix')) {
    _ap_bindHandlers();
  }
});
_ap_observer.observe(document.documentElement || document.body, { childList: true, subtree: true });
