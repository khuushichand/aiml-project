// admin-advanced.js
// Externalized bindings for Admin advanced panels (virtual keys, orgs/teams, tool permissions, rate limits, tool catalog).

function esc(x) { return Utils.escapeHtml(String(x ?? '')); }

// ---------- User Registration (moved from inline) ----------
async function adminCreateUser() {
  const username = (document.getElementById('adminReg_username')?.value || '').trim();
  const email = (document.getElementById('adminReg_email')?.value || '').trim();
  const password = document.getElementById('adminReg_password')?.value || '';
  const registration_code = (document.getElementById('adminReg_code')?.value || '').trim() || null;
  if (!username || !email || !password) {
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Username, email, and password are required');
    return;
  }
  try {
    const res = await window.apiClient.post('/api/v1/auth/register', { username, email, password, registration_code });
    const out = document.getElementById('adminUserRegister_response'); if (out) out.textContent = JSON.stringify(res, null, 2);
    if (res && res.api_key) { if (typeof Toast !== 'undefined' && Toast) Toast.success('User created. API key returned below. Copy and store it securely.'); }
    else { if (typeof Toast !== 'undefined' && Toast) Toast.success('User created.'); }
  } catch (e) {
    const out = document.getElementById('adminUserRegister_response'); if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to create user');
  }
}

function bindAdminUsersBasics() {
  // List Users
  const listBtn = document.getElementById('btnAdminUsersList');
  if (listBtn) listBtn.addEventListener('click', () => window.makeRequest && window.makeRequest('adminUsersList', 'GET', '/api/v1/admin/users', 'query'));
  // Create User
  const createBtn = document.getElementById('btnAdminCreateUser');
  if (createBtn) createBtn.addEventListener('click', adminCreateUser);
}

// ---------- Virtual Keys (per user) ----------
async function admVKList() {
  const userId = parseInt(document.getElementById('admVK_userId')?.value || '0', 10);
  if (!userId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter user id'); return; }
  try {
    const items = await window.apiClient.get(`/api/v1/admin/users/${userId}/virtual-keys`);
    const c = document.getElementById('adminVirtualKeys_list');
    if (!c) return;
    if (!Array.isArray(items) || !items.length) { c.innerHTML = '<p>No virtual keys.</p>'; return; }
    let html = '<table class="simple-table"><thead><tr><th>ID</th><th>Prefix</th><th>Scope</th><th>Status</th><th>Created</th><th>Expires</th><th>Usage</th><th>Last Used IP</th><th>Actions</th></tr></thead><tbody>';
    for (const k of items) {
      html += `<tr>
        <td>${esc(k.id)}</td>
        <td>${esc(k.key_prefix)}</td>
        <td>${esc(k.scope)}</td>
        <td>${esc(k.status)}</td>
        <td>${esc(k.created_at)}</td>
        <td>${esc(k.expires_at)}</td>
        <td>${esc(k.usage_count)}</td>
        <td>${esc(k.last_used_ip)}</td>
        <td><button class="btn btn-danger admvk-revoke" data-uid="${esc(userId)}" data-kid="${esc(k.id)}">Revoke</button></td>
      </tr>`;
    }
    html += '</tbody></table>';
    c.innerHTML = html;
    const out = document.getElementById('adminVirtualKeys_result');
    if (out) out.textContent = 'Loaded';
  } catch (e) {
    const out = document.getElementById('adminVirtualKeys_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    const c = document.getElementById('adminVirtualKeys_list');
    if (c) c.innerHTML = '';
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to list virtual keys');
  }
}

// ---------- Registration Codes ----------
async function rcCreate() {
  try {
    const payload = {
      max_uses: parseInt(document.getElementById('regCode_maxUses')?.value || '1', 10),
      expires_in_days: parseInt(document.getElementById('regCode_expires')?.value || '30', 10),
      role_to_grant: document.getElementById('regCode_role')?.value || 'user',
      description: document.getElementById('regCode_desc')?.value || null,
    };
    const res = await window.apiClient.post('/api/v1/admin/registration-codes', payload);
    const out = document.getElementById('adminRegCodes_result');
    if (out) out.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Registration code created');
    await rcList();
  } catch (e) {
    const out = document.getElementById('adminRegCodes_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to create code');
  }
}

async function rcList() {
  try {
    const res = await window.apiClient.get('/api/v1/admin/registration-codes');
    const codes = Array.isArray(res.codes) ? res.codes : [];
    rcRenderList(codes);
    const out = document.getElementById('adminRegCodes_result');
    if (out) out.textContent = 'Loaded';
  } catch (e) {
    const out = document.getElementById('adminRegCodes_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to list codes');
  }
}

async function rcDelete(id) {
  try {
    if (!confirm('Delete this registration code?')) return;
    const res = await window.apiClient.delete(`/api/v1/admin/registration-codes/${id}`);
    const out = document.getElementById('adminRegCodes_result');
    if (out) out.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Registration code deleted');
    await rcList();
  } catch (e) {
    const out = document.getElementById('adminRegCodes_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to delete code');
  }
}

function rcRenderList(items) {
  const container = document.getElementById('adminRegCodes_list');
  if (!container) return;
  if (!items.length) { container.innerHTML = '<p>No registration codes found.</p>'; return; }
  let html = '<table class="simple-table"><thead><tr>' +
    '<th>ID</th><th>Code</th><th>Role</th><th>Uses</th><th>Max</th><th>Expires</th><th>Actions</th>' +
    '</tr></thead><tbody>';
  for (const c of items) {
    const id = esc(c.id);
    html += `
      <tr>
        <td>${id}</td>
        <td><code>${esc(c.code)}</code></td>
        <td>${esc(c.role_to_grant || '')}</td>
        <td>${esc(c.times_used ?? 0)}</td>
        <td>${esc(c.max_uses ?? '')}</td>
        <td>${esc(c.expires_at || '')}</td>
        <td><button class="btn btn-danger rc-delete" data-id="${id}">Delete</button></td>
      </tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

async function admVKCreate() {
  const userId = parseInt(document.getElementById('admVK_userId')?.value || '0', 10);
  if (!userId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter user id'); return; }
  const toList = (val) => (val || '').split(',').map(s => s.trim()).filter(Boolean);
  const payload = {
    name: (document.getElementById('admVK_name')?.value || '').trim() || null,
    description: (document.getElementById('admVK_desc')?.value || '').trim() || null,
    expires_in_days: parseInt(document.getElementById('admVK_expires')?.value || '30', 10),
    allowed_endpoints: toList(document.getElementById('admVK_endpoints')?.value),
    allowed_methods: toList(document.getElementById('admVK_methods')?.value),
    allowed_paths: toList(document.getElementById('admVK_paths')?.value),
    max_calls: document.getElementById('admVK_calls')?.value ? parseInt(document.getElementById('admVK_calls').value, 10) : null,
    max_runs: document.getElementById('admVK_runs')?.value ? parseInt(document.getElementById('admVK_runs').value, 10) : null,
  };
  try {
    const res = await window.apiClient.post(`/api/v1/admin/users/${userId}/virtual-keys`, payload);
    const out = document.getElementById('adminVirtualKeys_result');
    if (out) out.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Virtual key created');
    await admVKList();
  } catch (e) {
    const out = document.getElementById('adminVirtualKeys_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Create failed');
  }
}

async function admVKRevoke(userId, keyId) {
  try {
    if (!confirm('Revoke key #' + keyId + '?')) return;
    const res = await window.apiClient.delete(`/api/v1/admin/users/${userId}/api-keys/${keyId}`);
    const out = document.getElementById('adminVirtualKeys_result');
    if (out) out.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Key revoked');
    await admVKList();
  } catch (e) {
    const out = document.getElementById('adminVirtualKeys_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Revoke failed');
  }
}

// ---------- LLM Usage (list/export) ----------
function _llmUsageQueryParams() {
  const q = new URLSearchParams();
  const user_id = (document.getElementById('adminLLM_user_id')?.value || '').trim();
  const provider = (document.getElementById('adminLLM_provider')?.value || '').trim();
  const model = (document.getElementById('adminLLM_model')?.value || '').trim();
  const operation = (document.getElementById('adminLLM_operation')?.value || '').trim();
  const status = (document.getElementById('adminLLM_status')?.value || '').trim();
  const limit = (document.getElementById('adminLLM_limit')?.value || '').trim();
  const start = (document.getElementById('adminLLM_start')?.value || '').trim();
  const end = (document.getElementById('adminLLM_end')?.value || '').trim();
  if (user_id) q.append('user_id', user_id);
  if (provider) q.append('provider', provider);
  if (model) q.append('model', model);
  if (operation) q.append('operation', operation);
  if (status) q.append('status', status);
  if (limit) q.append('limit', limit);
  if (start) q.append('start', start);
  if (end) q.append('end', end);
  return q.toString();
}

async function adminQueryLLMUsage() {
  try {
    const q = _llmUsageQueryParams();
    const url = '/api/v1/admin/llm-usage' + (q ? ('?' + q) : '');
    const res = await window.apiClient.get(url);
    const pre = document.getElementById('adminLLMUsage_result');
    if (!res || !Array.isArray(res.items) || res.items.length === 0) pre.textContent = 'No data yet.';
    else pre.textContent = JSON.stringify(res, null, 2);
  } catch (e) {
    document.getElementById('adminLLMUsage_result').textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to fetch LLM usage');
  }
}

function adminDownloadLLMUsageCSV() {
  const q = _llmUsageQueryParams();
  const url = '/api/v1/admin/llm-usage/export.csv' + (q ? ('?' + q) : '');
  window.open(url, '_blank');
}

// ---------- Audit Export ----------
function _auditBuildQueryParams(overrides = {}) {
  const q = new URLSearchParams();
  const fmt = overrides.format ?? (document.getElementById('audit_format')?.value || 'json');
  q.append('format', fmt);
  const minRisk = overrides.min_risk_score ?? (document.getElementById('audit_min_risk')?.value || '').trim();
  const userId = overrides.user_id ?? (document.getElementById('audit_user_id')?.value || '').trim();
  const ev = overrides.event_type ?? (document.getElementById('audit_event_type')?.value || '').trim();
  const cat = overrides.category ?? (document.getElementById('audit_category')?.value || '').trim();
  const fname = overrides.filename ?? (document.getElementById('audit_filename')?.value || '').trim();
  const start = overrides.start_time ?? (document.getElementById('audit_start')?.value || '').trim();
  const end = overrides.end_time ?? (document.getElementById('audit_end')?.value || '').trim();
  if (minRisk) q.append('min_risk_score', minRisk);
  if (userId) q.append('user_id', userId);
  if (ev) q.append('event_type', ev);
  if (cat) q.append('category', cat);
  if (fname) q.append('filename', fname);
  if (start) q.append('start_time', start);
  if (end) q.append('end_time', end);
  return q.toString();
}

async function _auditFetchAndDownload(qs, format) {
  try {
    const url = `${window.apiClient.baseUrl}/api/v1/audit/export?${qs}`;
    const headers = {};
    const client = window.apiClient;
    if (client && client.token) {
      if (client.authMode === 'single-user' || (client.authMode === 'multi-user' && client.preferApiKeyInMultiUser)) headers['X-API-KEY'] = client.token;
      else if (client.authMode === 'multi-user') headers['Authorization'] = `Bearer ${client.token}`;
      else headers['X-API-KEY'] = client.token;
    }
    const res = await fetch(url, { headers });
    const text = await res.text();
    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
    const parsedQS = new URLSearchParams(qs);
    const fname = parsedQS.get('filename') || (format === 'csv' ? 'audit_export.csv' : 'audit_export.json');
    const mime = format === 'csv' ? 'text/csv;charset=utf-8' : 'application/json;charset=utf-8';
    Utils.downloadData(text, fname, mime);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Audit export downloaded');
  } catch (e) {
    console.error('Audit export failed:', e);
    if (typeof Toast !== 'undefined' && Toast) Toast.error(`Audit export failed: ${e.message || e}`);
  }
}

function adminAuditDownload() {
  const fmt = document.getElementById('audit_format')?.value || 'json';
  const qs = _auditBuildQueryParams({ format: fmt });
  _auditFetchAndDownload(qs, fmt);
}

function adminAuditDownloadLast24hHighRisk() {
  const now = new Date();
  const dayAgo = new Date(now.getTime() - 24 * 60 * 60 * 1000);
  const isoStart = dayAgo.toISOString().replace('Z', '+00:00');
  const overrides = { format: 'csv', min_risk_score: '70', start_time: isoStart, filename: 'audit_24h_high_risk.csv' };
  const qs = _auditBuildQueryParams(overrides);
  _auditFetchAndDownload(qs, 'csv');
}

function adminAuditDownloadApiEventsCSV() {
  const overrides = { format: 'csv', category: 'API_CALL', filename: 'audit_api_events.csv' };
  const qs = _auditBuildQueryParams(overrides);
  _auditFetchAndDownload(qs, 'csv');
}

async function adminAuditPreviewJSON() {
  try {
    const qs = _auditBuildQueryParams({ format: 'json' });
    const url = `${window.apiClient.baseUrl}/api/v1/audit/export?${qs}`;
    const headers = {};
    const client = window.apiClient;
    if (client && client.token) {
      if (client.authMode === 'single-user' || (client.authMode === 'multi-user' && client.preferApiKeyInMultiUser)) headers['X-API-KEY'] = client.token;
      else if (client.authMode === 'multi-user') headers['Authorization'] = `Bearer ${client.token}`;
      else headers['X-API-KEY'] = client.token;
    }
    const res = await fetch(url, { headers });
    const text = await res.text();
    if (!res.ok) throw new Error(text || `HTTP ${res.status}`);
    let display = text;
    try {
      const parsed = JSON.parse(text);
      display = JSON.stringify(parsed.slice ? parsed.slice(0, 20) : parsed, null, 2);
    } catch (_) {}
    const pre = document.getElementById('adminAuditPreview');
    if (pre) pre.textContent = display;
  } catch (e) {
    const pre = document.getElementById('adminAuditPreview');
    if (pre) pre.textContent = `Preview failed: ${e.message || e}`;
  }
}

// ---------- LLM Charts ----------
function _shadeFromHex(hex, lighten = 0, darken = 0) {
  const c = hex.replace('#', '');
  const num = parseInt(c, 16);
  let r = (num >> 16) & 0xff, g = (num >> 8) & 0xff, b = num & 0xff;
  const l = (x, p) => Math.min(255, Math.max(0, Math.round(x + (255 - x) * (p / 100))));
  const d = (x, p) => Math.min(255, Math.max(0, Math.round(x * (1 - p / 100))));
  const rl = l(r, lighten), gl = l(g, lighten), bl = l(b, lighten);
  const rd = d(r, darken), gd = d(g, darken), bd = d(b, darken);
  const toHex = (x) => x.toString(16).padStart(2, '0');
  return { base: `#${toHex(r)}${toHex(g)}${toHex(b)}`, light: `#${toHex(rl)}${toHex(gl)}${toHex(bl)}`, dark: `#${toHex(rd)}${toHex(gd)}${toHex(bd)}` };
}

// ==============================
// Moderation (migrated from inline)
// ==============================

// Settings
async function moderationLoadSettings() {
  try {
    const res = await window.apiClient.get('/api/v1/moderation/settings');
    const eff = res && res.effective ? res.effective : {};
    const cats = (eff.categories_enabled || []).join(',');
    const piiOverride = (res && Object.prototype.hasOwnProperty.call(res, 'pii_enabled')) ? res.pii_enabled : null;
    const piiVal = (piiOverride === null || piiOverride === undefined) ? '' : String(!!piiOverride);
    const setVal = (id, v) => { const el = document.getElementById(id); if (el) el.value = v; };
    setVal('modSettings_categories', cats);
    setVal('modSettings_pii', piiVal);
    const pre = document.getElementById('moderationSettings_status'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded settings');
  } catch (e) {
    const pre = document.getElementById('moderationSettings_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load settings');
  }
}

async function moderationSaveSettings() {
  try {
    const rawCats = (document.getElementById('modSettings_categories')?.value || '').trim();
    const cats = rawCats ? rawCats.split(',').map(x => x.trim()).filter(Boolean) : [];
    const piiVal = (document.getElementById('modSettings_pii')?.value || '');
    const body = {};
    if (piiVal !== '') body.pii_enabled = (piiVal === 'true');
    body.categories_enabled = cats;
    body.persist = !!document.getElementById('modSettings_persist')?.checked;
    const res = await window.apiClient.put('/api/v1/moderation/settings', body);
    const pre = document.getElementById('moderationSettings_status'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Saved settings');
  } catch (e) {
    const pre = document.getElementById('moderationSettings_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to save settings');
  }
}

// Managed Blocklist
window._moderationManaged = { version: '', items: [] };
window._moderationManagedLint = {}; // id -> lint item

function renderManagedBlocklist() {
  const container = document.getElementById('moderationManaged_table'); if (!container) return;
  const filter = (document.getElementById('moderationManaged_filter')?.value || '').toLowerCase();
  let items = (window._moderationManaged.items || []).filter(it => !filter || String(it.line).toLowerCase().includes(filter));
  const onlyInvalid = !!document.getElementById('moderationManaged_onlyInvalid')?.checked;
  if (onlyInvalid) {
    items = items.filter((it) => {
      const lint = window._moderationManagedLint[String(it.id)] || null;
      return lint && lint.ok === false;
    });
  }
  let html = '<table class="table"><thead><tr><th>ID</th><th>Pattern</th><th>Lint</th><th>Actions</th></tr></thead><tbody>';
  for (const it of items) {
    const lint = window._moderationManagedLint[String(it.id)] || null;
    const lintText = lint ? (lint.ok ? 'ok' : (lint.error || 'invalid')) : '';
    const lintClass = lint ? (lint.ok ? 'ok' : 'invalid') : '';
    const lintIcon = lint ? (lint.ok ? '✓' : '⚠') : '';
    html += `<tr>
      <td>${Utils.escapeHtml(String(it.id ?? ''))}</td>
      <td><code>${Utils.escapeHtml(String(it.line))}</code></td>
      <td><span class="lint-${lintClass}" title="${Utils.escapeHtml(lintText)}"><span class="lint-icon">${lintIcon}</span>${Utils.escapeHtml(lint ? (lint.pattern_type || '') : '')}</span></td>
      <td><button class="btn btn-danger mod-managed-del" data-id="${Utils.escapeHtml(String(it.id ?? ''))}">Delete</button></td>
    </tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
}

async function moderationLoadManaged() {
  try {
    const res = await window.apiClient.get('/api/v1/moderation/blocklist/managed');
    window._moderationManaged = res || { version: '', items: [] };
    await moderationLintManagedAll();
    renderManagedBlocklist();
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = `Loaded version: ${res.version}`;
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded managed blocklist');
  } catch (e) {
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load managed blocklist');
  }
}

async function moderationRefreshManaged() { return moderationLoadManaged(); }

async function moderationAppendManaged() {
  try {
    const line = (document.getElementById('moderationManaged_newLine')?.value || '').trim();
    if (!line) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter a line'); return; }
    const lint = await window.apiClient.post('/api/v1/moderation/blocklist/lint', { line });
    const invalid = (lint.items || []).filter(it => !it.ok);
    if (invalid.length > 0) {
      const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(lint, null, 2);
      if (typeof Toast !== 'undefined' && Toast) Toast.error('Lint failed: fix the line before append');
      return;
    }
    const res = await window.apiClient.post('/api/v1/moderation/blocklist/append', { line }, { headers: { 'If-Match': window._moderationManaged.version }});
    window._moderationManaged.version = res.version;
    await moderationLoadManaged();
    const input = document.getElementById('moderationManaged_newLine'); if (input) input.value = '';
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Appended');
  } catch (e) {
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to append');
  }
}

async function moderationDeleteManaged(id) {
  try {
    if (!confirm('Delete blocklist entry #' + id + '?')) return;
    const res = await window.apiClient.delete(`/api/v1/moderation/blocklist/${id}`, { headers: { 'If-Match': window._moderationManaged.version }});
    window._moderationManaged.version = res.version;
    await moderationLoadManaged();
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Deleted');
  } catch (e) {
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to delete');
  }
}

async function moderationLintManaged() {
  try {
    const line = (document.getElementById('moderationManaged_newLine')?.value || '').trim();
    if (!line) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter a line'); return; }
    const res = await window.apiClient.post('/api/v1/moderation/blocklist/lint', { line });
    const invalid = (res.items || []).filter(it => !it.ok);
    const msg = `Lint: ${res.valid_count} valid, ${res.invalid_count} invalid`;
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (invalid.length === 0) { if (typeof Toast !== 'undefined' && Toast) Toast.success(msg); } else { if (typeof Toast !== 'undefined' && Toast) Toast.error(msg); }
  } catch (e) {
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Lint failed');
  }
}

async function moderationLintManagedAll() {
  try {
    const lines = (window._moderationManaged.items || []).map(it => it.line);
    if (!lines.length) { window._moderationManagedLint = {}; return; }
    const res = await window.apiClient.post('/api/v1/moderation/blocklist/lint', { lines });
    const map = {};
    // Key lint results by blocklist entry ID instead of array index
    (res.items || []).forEach((it) => { map[String(it.id)] = it; });
    window._moderationManagedLint = map;
    renderManagedBlocklist();
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = 'Linted';
  } catch (e) {
    const pre = document.getElementById('moderationManaged_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
  }
}

// Raw Blocklist
window._moderationBlocklistLastLint = null;

async function moderationLoadBlocklist() {
  try {
    const lines = await window.apiClient.get('/api/v1/moderation/blocklist');
    const ta = document.getElementById('moderationBlocklist_text'); if (ta) ta.value = (lines || []).join('\n');
    const pre = document.getElementById('moderationBlocklist_status'); if (pre) pre.textContent = 'Loaded';
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded blocklist');
  } catch (e) {
    const pre = document.getElementById('moderationBlocklist_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load blocklist');
  }
}

async function moderationSaveBlocklist() {
  try {
    const raw = document.getElementById('moderationBlocklist_text')?.value || '';
    const lines = raw.split(/\r?\n/);
    const res = await window.apiClient.put('/api/v1/moderation/blocklist', { lines });
    const pre = document.getElementById('moderationBlocklist_status'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Blocklist saved');
  } catch (e) {
    const pre = document.getElementById('moderationBlocklist_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to save blocklist');
  }
}

async function moderationLintBlocklist() {
  try {
    const raw = document.getElementById('moderationBlocklist_text')?.value || '';
    const lines = raw.split(/\r?\n/);
    const res = await window.apiClient.post('/api/v1/moderation/blocklist/lint', { lines });
    const invalid = (res.items || []).filter(it => !it.ok);
    const msg = `Lint: ${res.valid_count} valid, ${res.invalid_count} invalid`;
    const pre = document.getElementById('moderationBlocklist_status'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    window._moderationBlocklistLastLint = res;
    renderBlocklistInvalidList();
    if (invalid.length === 0) { if (typeof Toast !== 'undefined' && Toast) Toast.success(msg); } else { if (typeof Toast !== 'undefined' && Toast) Toast.error(msg); }
  } catch (e) {
    const pre = document.getElementById('moderationBlocklist_status'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Lint failed');
  }
}

function renderBlocklistInvalidList() {
  const container = document.getElementById('moderationBlocklist_invalidList'); if (!container) return;
  const onlyInvalid = !!document.getElementById('moderationBlocklist_onlyInvalid')?.checked;
  const actions = document.getElementById('moderationBlocklist_invalidActions');
  if (!onlyInvalid) { container.innerHTML = ''; if (actions) actions.style.display = 'none'; return; }
  const res = window._moderationBlocklistLastLint;
  if (!res || !Array.isArray(res.items)) { container.innerHTML = '<em>No lint results yet</em>'; return; }
  const invalid = (res.items || []).filter(it => it && it.ok === false);
  if (!invalid.length) { container.innerHTML = '<em>No invalid items</em>'; if (actions) actions.style.display = 'none'; return; }
  let html = '<table class="simple-table"><thead><tr><th>#</th><th>Type</th><th>Error</th><th>Line</th></tr></thead><tbody>';
  for (const it of invalid) {
    const idx = typeof it.index === 'number' ? it.index : '';
    const type = it.pattern_type || '';
    const err = it.error || 'invalid';
    const line = (it.line || '').slice(0, 120);
    html += `<tr>
      <td>${idx}</td>
      <td>${Utils.escapeHtml(String(type))}</td>
      <td class="lint-invalid">${Utils.escapeHtml(String(err))}</td>
      <td><code>${Utils.escapeHtml(String(line))}</code></td>
    </tr>`;
  }
  html += '</tbody></table>';
  container.innerHTML = html;
  if (actions) actions.style.display = 'block';
}

async function moderationCopyInvalidBlocklist() {
  try {
    const res = window._moderationBlocklistLastLint ? (window._moderationBlocklistLastLint.items || []).filter(it => !it.ok).map(it => String(it.line || '')).join('\n') : '';
    if (!res) { if (typeof Toast !== 'undefined' && Toast) Toast.error('No invalid items to copy'); return; }
    const ok = await Utils.copyToClipboard(res);
    if (ok) { if (typeof Toast !== 'undefined' && Toast) Toast.success('Copied invalid lines'); } else { if (typeof Toast !== 'undefined' && Toast) Toast.error('Copy failed'); }
  } catch (_) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Copy failed'); }
}

// Overrides + Tester
function _buildOverridePayload() {
  const v = (id) => (document.getElementById(id)?.value ?? '').trim();
  const maybeBool = (x) => x === '' ? undefined : (x === 'true');
  const payload = {};
  const enabled = maybeBool(v('modEnabled'));
  const inp = maybeBool(v('modInputEnabled'));
  const outp = maybeBool(v('modOutputEnabled'));
  const ia = v('modInputAction');
  const oa = v('modOutputAction');
  const rr = v('modRedact');
  const cat = v('modUserCategories');
  if (enabled !== undefined) payload.enabled = enabled;
  if (inp !== undefined) payload.input_enabled = inp;
  if (outp !== undefined) payload.output_enabled = outp;
  if (ia) payload.input_action = ia;
  if (oa) payload.output_action = oa;
  if (rr) payload.redact_replacement = rr;
  if (cat) payload.categories_enabled = cat;
  return payload;
}

async function loadUserOverride() {
  try {
    const uid = (document.getElementById('modUserId')?.value || '').trim();
    if (!uid) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter a user ID'); return; }
    const res = await window.apiClient.get(`/api/v1/moderation/users/${uid}`);
    const pre = document.getElementById('moderationOverrides_result'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded override');
  } catch (e) {
    const pre = document.getElementById('moderationOverrides_result'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load override');
  }
}

async function saveUserOverride() {
  try {
    const uid = (document.getElementById('modUserId')?.value || '').trim();
    if (!uid) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter a user ID'); return; }
    const payload = _buildOverridePayload();
    const res = await window.apiClient.put(`/api/v1/moderation/users/${uid}`, payload);
    const pre = document.getElementById('moderationOverrides_result'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Saved override');
  } catch (e) {
    const pre = document.getElementById('moderationOverrides_result'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to save override');
  }
}

async function deleteUserOverride() {
  try {
    const uid = (document.getElementById('modUserId')?.value || '').trim();
    if (!uid) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter a user ID'); return; }
    if (!confirm('Delete override for user ' + uid + '?')) return;
    const res = await window.apiClient.delete(`/api/v1/moderation/users/${uid}`);
    const pre = document.getElementById('moderationOverrides_result'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Deleted override');
  } catch (e) {
    const pre = document.getElementById('moderationOverrides_result'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to delete override');
  }
}

async function moderationListOverrides() {
  try {
    const res = await window.apiClient.get('/api/v1/moderation/users');
    const overrides = (res && res.overrides) || {};
    const rows = Object.entries(overrides).map(([uid, o]) => ({ uid, ...o }));
    let html = '<table class="table"><thead><tr><th>User</th><th>enabled</th><th>input_enabled</th><th>output_enabled</th><th>input_action</th><th>output_action</th><th>redact_replacement</th><th>categories_enabled</th><th>Actions</th></tr></thead><tbody>';
    for (const r of rows) {
      html += `<tr>
        <td>${Utils.escapeHtml(String(r.uid))}</td>
        <td>${String(r.enabled ?? '')}</td>
        <td>${String(r.input_enabled ?? '')}</td>
        <td>${String(r.output_enabled ?? '')}</td>
        <td>${Utils.escapeHtml(String(r.input_action ?? ''))}</td>
        <td>${Utils.escapeHtml(String(r.output_action ?? ''))}</td>
        <td>${Utils.escapeHtml(String(r.redact_replacement ?? ''))}</td>
        <td>${Utils.escapeHtml(String(r.categories_enabled ?? ''))}</td>
        <td><button class="btn mod-load-editor" data-uid="${Utils.escapeHtml(String(r.uid))}">Load</button></td>
      </tr>`;
    }
    html += '</tbody></table>';
    const div = document.getElementById('moderationOverrides_table'); if (div) div.innerHTML = html;
  } catch (e) {
    const div = document.getElementById('moderationOverrides_table'); if (div) div.innerHTML = `<pre>${Utils.escapeHtml(JSON.stringify(e.response || e, null, 2))}</pre>`;
  }
}

function moderationLoadIntoEditor(uid) {
  const id = document.getElementById('modUserId'); if (id) id.value = uid;
  loadUserOverride();
  if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded override into editor');
}

async function moderationRunTest() {
  try {
    const user_id = (document.getElementById('modTest_user')?.value || '').trim() || null;
    const phase = document.getElementById('modTest_phase')?.value;
    const text = document.getElementById('modTest_text')?.value || '';
    const res = await window.apiClient.post('/api/v1/moderation/test', { user_id, phase, text });
    const pre = document.getElementById('moderationTester_result'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Test completed');
  } catch (e) {
    const pre = document.getElementById('moderationTester_result'); if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Test failed');
  }
}

// ==============================
// Security Alerts (migrated)
// ==============================
async function loadSecurityAlertStatus() {
  try {
    const resp = await window.apiClient.makeRequest('GET', '/api/v1/admin/security/alert-status');
    const pre = document.getElementById('adminSecurityAlerts_response'); if (pre) pre.textContent = JSON.stringify(resp, null, 2);
    const health = resp.health || 'unknown';
    const pill = document.getElementById('adminSecurityAlerts_health');
    if (pill) {
      pill.textContent = `Health: ${health}`;
      if (health === 'ok') { pill.style.backgroundColor = '#d1fae5'; pill.style.color = '#065f46'; }
      else if (health === 'degraded') { pill.style.backgroundColor = '#fef3c7'; pill.style.color = '#92400e'; }
      else { pill.style.backgroundColor = '#fee2e2'; pill.style.color = '#991b1b'; }
    }
    const tbody = document.querySelector('#adminSecurityAlerts_table tbody');
    if (tbody) {
      tbody.innerHTML = '';
      (resp.sinks || []).forEach(sink => {
        const row = document.createElement('tr');

        const tdSink = document.createElement('td');
        tdSink.textContent = String(sink?.sink ?? '');
        row.appendChild(tdSink);

        const tdConfigured = document.createElement('td');
        tdConfigured.textContent = sink && sink.configured ? 'Yes' : 'No';
        row.appendChild(tdConfigured);

        const tdMinSeverity = document.createElement('td');
        tdMinSeverity.textContent = String((sink && sink.min_severity) || resp.min_severity || '');
        row.appendChild(tdMinSeverity);

        const tdLastStatus = document.createElement('td');
        const lastStatus = sink && sink.last_status === true ? 'success' : (sink && sink.last_status === false ? 'failure' : 'n/a');
        tdLastStatus.textContent = lastStatus;
        row.appendChild(tdLastStatus);

        const tdLastError = document.createElement('td');
        tdLastError.textContent = String((sink && sink.last_error) || '');
        row.appendChild(tdLastError);

        const tdBackoff = document.createElement('td');
        tdBackoff.textContent = String((sink && sink.backoff_until) || '');
        row.appendChild(tdBackoff);

        tbody.appendChild(row);
      });
    }
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Security alert status refreshed');
  } catch (e) {
    const pre = document.getElementById('adminSecurityAlerts_response'); if (pre) pre.textContent = String(e?.message || e);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load security alert status: ' + (e?.message || e));
  }
}

// ==============================
// Usage (migrated)
// ==============================
function _usageQS() {
  const params = new URLSearchParams();
  const uid = parseInt(document.getElementById('usage_userId')?.value || '');
  const start = (document.getElementById('usage_start')?.value || '').trim();
  const end = (document.getElementById('usage_end')?.value || '').trim();
  const page = parseInt(document.getElementById('usage_page')?.value || '1', 10);
  const limit = parseInt(document.getElementById('usage_limit')?.value || '50', 10);
  if (!isNaN(uid)) params.set('user_id', String(uid));
  if (start) params.set('start', start);
  if (end) params.set('end', end);
  if (page) params.set('page', String(page));
  if (limit) params.set('limit', String(limit));
  return params.toString();
}

function _renderDailyTable(items) {
  if (!Array.isArray(items) || items.length === 0) return '<p>No data yet.</p>';
  const showIn = !!document.getElementById('usage_show_bytes_in')?.checked;
  let html = '<table class="simple-table"><thead><tr><th>User ID</th><th>Day</th><th>Requests</th><th>Errors</th><th>Bytes</th>' + (showIn ? '<th>Bytes In</th>' : '') + '<th>Avg Latency (ms)</th></tr></thead><tbody>';
  for (const r of items) {
    html += `<tr>
      <td>${r.user_id}</td>
      <td>${r.day}</td>
      <td>${r.requests}</td>
      <td>${r.errors}</td>
      <td>${r.bytes_total}</td>
      ${showIn ? `<td>${r.bytes_in_total || 0}</td>` : ''}
      <td>${r.avg_latency_ms || '-'}</td>
    </tr>`;
  }
  html += '</tbody></table>';
  return html;
}

async function adminLoadUsageDaily() {
  const qs = _usageQS();
  const url = '/api/v1/admin/usage/daily' + (qs ? ('?' + qs) : '');
  const res = await window.apiClient.get(url);
  const items = res && res.items ? res.items : [];
  const summary = document.getElementById('adminUsageDaily_summary'); if (summary) summary.textContent = `Items: ${items.length}`;
  const table = document.getElementById('adminUsageDaily_table'); if (table) table.innerHTML = _renderDailyTable(items);
  const raw = document.getElementById('adminUsageDaily_raw'); if (raw) raw.textContent = JSON.stringify(res, null, 2);
}

function adminDownloadUsageDailyCSV() {
  const qs = _usageQS();
  const url = `/api/v1/admin/usage/daily.csv${qs ? ('?' + qs) : ''}`;
  window.open(url, '_blank');
}

async function adminLoadUsageTop() {
  const metric = (document.getElementById('usage_top_metric')?.value || 'requests');
  const topLimit = parseInt(document.getElementById('usage_top_limit')?.value || '10', 10);
  const qsBase = _usageQS();
  const qs = new URLSearchParams(qsBase);
  qs.set('metric', metric);
  qs.set('top_limit', String(topLimit));
  const url = `/api/v1/admin/usage/top?${qs.toString()}`;
  const res = await window.apiClient.get(url);
  const items = res && res.items ? res.items : [];
  const summary = document.getElementById('adminUsageTop_summary'); if (summary) summary.textContent = `Items: ${items.length}`;
  let html = '<table class="simple-table"><thead><tr><th>User ID</th><th>Requests</th><th>Errors</th><th>Bytes Total</th></tr></thead><tbody>';
  for (const r of items) {
    html += `<tr><td>${r.user_id}</td><td>${r.requests}</td><td>${r.errors}</td><td>${r.bytes_total}</td></tr>`;
  }
  html += '</tbody></table>';
  const table = document.getElementById('adminUsageTop_table'); if (table) table.innerHTML = html;
  const raw = document.getElementById('adminUsageTop_raw'); if (raw) raw.textContent = JSON.stringify(res, null, 2);
}

function adminDownloadUsageTopCSV() {
  const metric = (document.getElementById('usage_top_metric')?.value || 'requests');
  const topLimit = parseInt(document.getElementById('usage_top_limit')?.value || '10', 10);
  const qsBase = _usageQS();
  const qs = new URLSearchParams(qsBase);
  qs.set('metric', metric);
  qs.set('top_limit', String(topLimit));
  const url = `/api/v1/admin/usage/top.csv?${qs.toString()}`;
  window.open(url, '_blank');
}

async function adminRunUsageAggregate() {
  const day = (document.getElementById('usage_agg_day')?.value || '').trim();
  if (!day) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter a day'); return; }
  const res = await window.apiClient.post('/api/v1/admin/usage/aggregate', { day });
  const pre = document.getElementById('adminUsageAgg_result'); if (pre) pre.textContent = JSON.stringify(res, null, 2);
}

function _colorFromLabel(label) {
  const h = Array.from(String(label || '')).reduce((a, c) => a + c.charCodeAt(0), 0) % 360;
  return { base: `hsl(${h}, 60%, 55%)`, light: `hsl(${h}, 65%, 75%)`, dark: `hsl(${h}, 55%, 40%)` };
}

function _colorForProvider(provider) {
  const p = String(provider || '').toLowerCase();
  const map = { openai: '#10a37f', anthropic: '#8e44ad', groq: '#e67e22', mistral: '#2980b9', google: '#4285f4', cohere: '#f39c12', qwen: '#2ecc71', deepseek: '#16a085', openrouter: '#34495e', xai: '#2c3e50', huggingface: '#ffcc4d' };
  const hex = map[p];
  return hex ? _shadeFromHex(hex, 10, 10) : null;
}

function _formatValue(val, unit) {
  const n = Number(val || 0);
  if (unit && unit.toLowerCase().includes('usd')) return `$${n.toFixed(2)}`;
  return n.toLocaleString();
}

let _chartTooltip = null;
function _ensureTooltip() {
  if (_chartTooltip) return _chartTooltip;
  _chartTooltip = document.createElement('div');
  _chartTooltip.className = 'chart-tooltip';
  document.body.appendChild(_chartTooltip);
  return _chartTooltip;
}

function _attachTooltips(containerId) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const tooltip = _ensureTooltip();
  container.querySelectorAll('.chart-bar').forEach(bar => {
    bar.addEventListener('mouseenter', (e) => {
      const label = bar.getAttribute('data-label') || '';
      const value = bar.getAttribute('data-value') || '';
      const unit = (container.dataset && container.dataset.unit) ? container.dataset.unit : 'USD';
      tooltip.innerHTML = `<strong>${esc(label)}</strong><br/>${_formatValue(value, unit)} ${unit}`;
      tooltip.style.display = 'block';
    });
    bar.addEventListener('mousemove', (e) => {
      tooltip.style.left = (e.clientX + 12) + 'px';
      tooltip.style.top = (e.clientY + 12) + 'px';
    });
    bar.addEventListener('mouseleave', () => { tooltip.style.display = 'none'; });
  });
}

function _renderBarChart(containerId, dataPairs, valueLabel, getColor) {
  const container = document.getElementById(containerId);
  if (!container) return;
  const maxVal = Math.max(...dataPairs.map(p => p.value), 1);
  container.innerHTML = `
    <div class="chart-placeholder">
      <div class="chart-bars">
        ${dataPairs.map(p => {
          const c = getColor ? getColor(p.label) : null;
          const style = c ? `background: linear-gradient(180deg, ${c.light} 0%, ${c.base} 100%); border-color: ${c.dark};` : '';
          const h = Math.max(5, (p.value / maxVal) * 100);
          const label = String(p.label);
          return `
            <div class="chart-bar" data-label="${esc(label)}" data-value="${esc(String(p.value))}" style="height:${h}%; ${style}">
              <span class="chart-bar-label" title="${esc(label)}">${esc(label)}</span>
              <span class="chart-bar-value">${_formatValue(p.value, valueLabel)} ${valueLabel || ''}</span>
            </div>`;
        }).join('')}
      </div>
    </div>`;
  try { container.dataset.unit = valueLabel || ''; } catch (_) {}
  _attachTooltips(containerId);
}

function _renderLegend(containerId, dataPairs, getColor) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.innerHTML = dataPairs.map(p => {
    const c = getColor ? getColor(p.label) : null;
    const style = c ? `background:${c.base}; border-color:${c.dark};` : '';
    return `<span class="legend-item"><span class="legend-swatch" style="${style}"></span>${esc(String(p.label))}</span>`;
  }).join('');
}

function _attachLegendToggle(legendId, chartId) {
  const legend = document.getElementById(legendId);
  const chart = document.getElementById(chartId);
  if (!legend || !chart) return;
  legend.querySelectorAll('.legend-item').forEach(item => {
    item.style.cursor = 'pointer';
    item.addEventListener('click', () => {
      const label = item.textContent.trim();
      const disabled = item.classList.toggle('disabled');
      chart.querySelectorAll(`.chart-bar[data-label="${label}"]`).forEach(bar => {
        if (disabled) bar.classList.add('hidden'); else bar.classList.remove('hidden');
      });
    });
  });
}

function _resetLegendVisibility(legendId, chartId) {
  const legend = document.getElementById(legendId);
  const chart = document.getElementById(chartId);
  if (!legend || !chart) return;
  legend.querySelectorAll('.legend-item').forEach(i => i.classList.remove('disabled'));
  chart.querySelectorAll('.chart-bar.hidden').forEach(b => b.classList.remove('hidden'));
}

const _providerMappingCache = {};
async function _fetchProviderMappingForModels(start, end, metric) {
  const cacheKey = `${start}|${end}|${metric}`;
  if (_providerMappingCache[cacheKey]) return _providerMappingCache[cacheKey];
  const qs = new URLSearchParams(); if (start) qs.append('start', start); if (end) qs.append('end', end); qs.append('limit', '1000');
  const url = '/api/v1/admin/llm-usage' + (qs.toString() ? ('?' + qs.toString()) : '');
  try {
    const res = await window.apiClient.get(url);
    const items = res.items || [];
    const scoreKey = metric === 'cost' ? 'total_cost_usd' : 'total_tokens';
    const acc = {};
    for (const row of items) {
      const model = String(row.model || '').toLowerCase();
      const prov = String(row.provider || '');
      const score = Number(row[scoreKey] || 0);
      if (!model) continue;
      acc[model] = acc[model] || {};
      acc[model][prov] = (acc[model][prov] || 0) + (score > 0 ? score : 1);
    }
    const mapping = {};
    for (const m in acc) {
      let bestProv = null, bestVal = -1;
      for (const p in acc[m]) { if (acc[m][p] > bestVal) { bestVal = acc[m][p]; bestProv = p; } }
      mapping[m] = bestProv || '';
    }
    const prox = new Proxy(mapping, { get: (t, k) => t[String(k).toLowerCase()] });
    _providerMappingCache[cacheKey] = prox;
    return prox;
  } catch (e) { return {}; }
}

async function adminLoadLLMCharts() {
  try {
    const start = (document.getElementById('adminLLMCharts_start')?.value || '').trim();
    const end = (document.getElementById('adminLLMCharts_end')?.value || '').trim();
    const qs = new URLSearchParams(); if (start) qs.append('start', start); if (end) qs.append('end', end);
    const topN = Math.max(3, Math.min(50, parseInt((document.getElementById('llmCharts_topN') || {}).value || '10', 10)));

    const topUrl = '/api/v1/admin/llm-usage/top-spenders' + (qs.toString() ? ('?' + qs.toString()) : '');
    const top = await window.apiClient.get(topUrl);
    let topPairs = (top.items || []).slice(0, topN).map(r => ({ label: String(r.user_id), value: Number(r.total_cost_usd || 0) }));
    if (!topPairs.length) {
      document.getElementById('llmChartTopSpenders').innerHTML = '<p>No data yet.</p>';
      document.getElementById('llmLegendTopSpenders').innerHTML = '';
    } else {
      _renderBarChart('llmChartTopSpenders', topPairs, 'USD', _colorFromLabel);
      _renderLegend('llmLegendTopSpenders', topPairs, _colorFromLabel);
      _attachLegendToggle('llmLegendTopSpenders', 'llmChartTopSpenders');
    }

    const mixUrl = '/api/v1/admin/llm-usage/summary' + (qs.toString() ? ('?' + qs.toString() + '&') : '?') + 'group_by=model';
    const mix = await window.apiClient.get(mixUrl);
    const modelMetric = (document.getElementById('llmCharts_model_metric')?.value || 'tokens');
    const valueKey = modelMetric === 'cost' ? 'total_cost_usd' : 'total_tokens';
    const valueLabel = modelMetric === 'cost' ? 'USD' : 'tokens';
    let mixPairs = (mix.items || []).map(r => ({ label: String(r.group_value), value: Number(r[valueKey] || 0) }));
    mixPairs.sort((a,b) => b.value - a.value); mixPairs = mixPairs.slice(0, topN);
    const palette = (document.getElementById('llmCharts_model_palette')?.value || 'distinct');
    let getColor = _colorFromLabel;
    if (palette === 'provider') {
      const mapping = await _fetchProviderMappingForModels(start, end, modelMetric);
      getColor = (label) => _colorForProvider(mapping[label]) || _colorFromLabel(mapping[label] || label);
    }
    if (!mixPairs.length) {
      document.getElementById('llmChartModelMix').innerHTML = '<p>No data yet.</p>';
      document.getElementById('llmLegendModelMix').innerHTML = '';
    } else {
      _renderBarChart('llmChartModelMix', mixPairs, valueLabel, getColor);
      _renderLegend('llmLegendModelMix', mixPairs, getColor);
      _attachLegendToggle('llmLegendModelMix', 'llmChartModelMix');
    }

    const provUrl = '/api/v1/admin/llm-usage/summary' + (qs.toString() ? ('?' + qs.toString() + '&') : '?') + 'group_by=provider';
    const prov = await window.apiClient.get(provUrl);
    const provMetric = (document.getElementById('llmCharts_provider_metric')?.value || 'cost');
    const provKey = provMetric === 'tokens' ? 'total_tokens' : 'total_cost_usd';
    const provLabel = provMetric === 'tokens' ? 'tokens' : 'USD';
    let provPairs = (prov.items || []).map(r => ({ label: String(r.group_value || 'unknown'), value: Number(r[provKey] || 0) }));
    provPairs.sort((a,b) => b.value - a.value); provPairs = provPairs.slice(0, topN);
    if (!provPairs.length) {
      document.getElementById('llmChartProviderMix').innerHTML = '<p>No data yet.</p>';
      document.getElementById('llmLegendProviderMix').innerHTML = '';
    } else {
      _renderBarChart('llmChartProviderMix', provPairs, provLabel, _colorForProvider);
      _renderLegend('llmLegendProviderMix', provPairs, _colorForProvider);
      _attachLegendToggle('llmLegendProviderMix', 'llmChartProviderMix');
    }
    if (typeof Toast !== 'undefined' && Toast) Toast.success('LLM charts loaded');
  } catch (e) {
    console.error('Failed to load LLM charts', e);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load LLM charts');
  }
}
// ---------- Admin Users API Keys (row actions) ----------
async function admUserKeyRotate(userId, keyId) {
  try {
    const res = await window.apiClient.post(`/api/v1/admin/users/${userId}/api-keys/${keyId}/rotate`, { expires_in_days: 365 });
    const out = document.getElementById('adminUserApiKeys_result');
    if (out) out.textContent = JSON.stringify(res, null, 2);
    if (res && res.key) { if (typeof Toast !== 'undefined' && Toast) Toast.success('API key rotated. Copy the new key now.'); }
    else { if (typeof Toast !== 'undefined' && Toast) Toast.success('API key rotated.'); }
    if (typeof window.adminListUserApiKeys === 'function') await window.adminListUserApiKeys();
  } catch (e) {
    const out = document.getElementById('adminUserApiKeys_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to rotate key');
  }
}

async function admUserKeyRevoke(userId, keyId) {
  try {
    if (!confirm('Revoke this key?')) return;
    const res = await window.apiClient.delete(`/api/v1/admin/users/${userId}/api-keys/${keyId}`);
    const out = document.getElementById('adminUserApiKeys_result');
    if (out) out.textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('API key revoked');
    if (typeof window.adminListUserApiKeys === 'function') await window.adminListUserApiKeys();
  } catch (e) {
    const out = document.getElementById('adminUserApiKeys_result');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to revoke key');
  }
}

// ---------- Orgs & Teams ----------
function tableHTML(rows, headers) {
  if (!Array.isArray(rows) || !rows.length) return '<p>None</p>';
  let html = '<table class="simple-table"><thead><tr>' + headers.map(h => `<th>${esc(h)}</th>`).join('') + '</tr></thead><tbody>';
  for (const r of rows) html += '<tr>' + headers.map(h => `<td>${esc(r[h])}</td>`).join('') + '</tr>';
  html += '</tbody></table>';
  return html;
}

async function admCreateOrg() {
  const name = (document.getElementById('org_name')?.value || '').trim(); if (!name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Name required'); return; }
  const payload = { name, slug: (document.getElementById('org_slug')?.value || '').trim() || null, owner_user_id: document.getElementById('org_owner')?.value ? parseInt(document.getElementById('org_owner').value, 10) : null };
  try {
    const res = await window.apiClient.post('/api/v1/admin/orgs', payload);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Org created');
    await admListOrgs();
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Create failed'); }
}

async function admListOrgs() {
  try {
    const res = await window.apiClient.get('/api/v1/admin/orgs');
    const items = Array.isArray(res) ? res : (res.items || []);
    const rows = items.map(x => ({ id: x.id, name: x.name, slug: x.slug, owner_user_id: x.owner_user_id }));
    document.getElementById('adminOrgs_list').innerHTML = tableHTML(rows, ['id','name','slug','owner_user_id']);
    document.getElementById('adminOrgsTeams_result').textContent = 'Loaded orgs';
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('List orgs failed'); }
}

async function admCreateTeam() {
  const orgId = parseInt(document.getElementById('team_org')?.value || '0', 10); if (!orgId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID required'); return; }
  const name = (document.getElementById('team_name')?.value || '').trim(); if (!name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Team name required'); return; }
  const payload = { name, slug: (document.getElementById('team_slug')?.value || '').trim() || null };
  try {
    const res = await window.apiClient.post(`/api/v1/admin/orgs/${orgId}/teams`, payload);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Team created');
    await admListTeams();
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Create team failed'); }
}

async function admListTeams() {
  const orgId = parseInt(document.getElementById('team_org')?.value || '0', 10); if (!orgId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID required'); return; }
  try {
    const rows = await window.apiClient.get(`/api/v1/admin/orgs/${orgId}/teams`);
    const items = Array.isArray(rows) ? rows : [];
    const mapped = items.map(x => ({ id: x.id, org_id: x.org_id, name: x.name, slug: x.slug }));
    document.getElementById('adminTeams_list').innerHTML = tableHTML(mapped, ['id','org_id','name','slug']);
    document.getElementById('adminOrgsTeams_result').textContent = 'Loaded teams';
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); Toast.error('List teams failed'); }
}

async function admAddTeamMember() {
  const teamId = parseInt(document.getElementById('m_team')?.value || '0', 10); const userId = parseInt(document.getElementById('m_user')?.value || '0', 10);
  if (!teamId || !userId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Team ID and User ID required'); return; }
  const role = (document.getElementById('m_role')?.value || '').trim() || 'member';
  try {
    const res = await window.apiClient.post(`/api/v1/admin/teams/${teamId}/members`, { user_id: userId, role });
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Added team member');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Add member failed'); }
}

async function admListTeamMembers() {
  const teamId = parseInt(document.getElementById('m_team')?.value || '0', 10); if (!teamId) { Toast.error('Team ID required'); return; }
  try {
    const rows = await window.apiClient.get(`/api/v1/admin/teams/${teamId}/members`);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(rows, null, 2);
    Toast.success('Listed team members');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); Toast.error('List team members failed'); }
}

async function admRemoveTeamMember() {
  const teamId = parseInt(document.getElementById('m_team')?.value || '0', 10); const userId = parseInt(document.getElementById('m_user')?.value || '0', 10);
  if (!teamId || !userId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Team ID and User ID required'); return; }
  if (!confirm('Remove user ' + userId + ' from team ' + teamId + '?')) return;
  try {
    const res = await window.apiClient.delete(`/api/v1/admin/teams/${teamId}/members/${userId}`);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Removed team member');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Remove failed'); }
}

async function admAddOrgMember() {
  const orgId = parseInt(document.getElementById('m_org')?.value || '0', 10); const userId = parseInt(document.getElementById('m_user')?.value || '0', 10);
  if (!orgId || !userId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID and User ID required'); return; }
  const role = (document.getElementById('m_role')?.value || '').trim() || 'member';
  try {
    const res = await window.apiClient.post(`/api/v1/admin/orgs/${orgId}/members`, { user_id: userId, role });
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Added org member');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Add org member failed'); }
}

async function admListOrgMembers() {
  const orgId = parseInt(document.getElementById('m_org')?.value || '0', 10); if (!orgId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID required'); return; }
  try {
    const rows = await window.apiClient.get(`/api/v1/admin/orgs/${orgId}/members`);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(rows, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Listed org members');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('List org members failed'); }
}

async function admUpdateOrgMemberRole() {
  const orgId = parseInt(document.getElementById('m_org')?.value || '0', 10); const userId = parseInt(document.getElementById('m_user')?.value || '0', 10);
  const role = (document.getElementById('m_role')?.value || '').trim();
  if (!orgId || !userId || !role) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID, User ID, and new role required'); return; }
  try {
    const res = await window.apiClient.patch(`/api/v1/admin/orgs/${orgId}/members/${userId}`, { role });
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Updated org member role');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Update role failed'); }
}

async function admRemoveOrgMember() {
  const orgId = parseInt(document.getElementById('m_org')?.value || '0', 10); const userId = parseInt(document.getElementById('m_user')?.value || '0', 10);
  if (!orgId || !userId) { Toast.error('Org ID and User ID required'); return; }
  if (!confirm('Remove user ' + userId + ' from org ' + orgId + '?')) return;
  try {
    const res = await window.apiClient.delete(`/api/v1/admin/orgs/${orgId}/members/${userId}`);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    Toast.success('Removed org member');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); Toast.error('Remove failed'); }
}

async function admGetOrgWatchCfg() {
  const orgId = parseInt(document.getElementById('m_org')?.value || '0', 10); if (!orgId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID required'); return; }
  try {
    const res = await window.apiClient.get(`/api/v1/admin/orgs/${orgId}/watchlists/settings`);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded org watchlists settings');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Get settings failed'); }
}

async function admSetOrgWatchCfg() {
  const orgId = parseInt(document.getElementById('m_org')?.value || '0', 10); if (!orgId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Org ID required'); return; }
  const val = document.getElementById('org_wl_require')?.value;
  const body = { require_include_default: val === '' ? null : (val === 'true') };
  try {
    const res = await window.apiClient.patch(`/api/v1/admin/orgs/${orgId}/watchlists/settings`, body);
    document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Updated org watchlists settings');
  } catch (e) { document.getElementById('adminOrgsTeams_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Update settings failed'); }
}

// ---------- Tool Permissions ----------
async function tpListPerms() {
  try {
    const rows = await window.apiClient.get('/api/v1/admin/permissions/tools');
    const list = Array.isArray(rows) ? rows : [];
    const html = (list.length ? '<ul>' + list.map(p => `<li><code>${esc(p.name)}</code> - ${esc(p.description || '')}</li>`).join('') + '</ul>' : '<p>None</p>');
    document.getElementById('adminToolPermissions_list').innerHTML = html;
    document.getElementById('adminToolPermissions_result').textContent = 'Loaded';
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('List failed'); }
}

async function tpCreatePerm() {
  const tool_name = (document.getElementById('tp_name')?.value || '').trim(); if (!tool_name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Tool name required'); return; }
  const description = (document.getElementById('tp_desc')?.value || '').trim() || null;
  try {
    const res = await window.apiClient.post('/api/v1/admin/permissions/tools', { tool_name, description });
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Permission created');
    await tpListPerms();
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Create failed'); }
}

async function tpDeletePerm() {
  const name = (document.getElementById('tp_name')?.value || '').trim(); if (!name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Enter permission name'); return; }
  if (!confirm('Delete ' + name + '?')) return;
  try {
    const res = await window.apiClient.delete(`/api/v1/admin/permissions/tools/${encodeURIComponent(name)}`);
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Permission deleted');
    await tpListPerms();
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Delete failed'); }
}

async function tpGrantToRole() {
  const roleId = parseInt(document.getElementById('tp_role')?.value || '0', 10); if (!roleId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Role ID required'); return; }
  const tool = (document.getElementById('tp_tool')?.value || '').trim(); if (!tool) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Tool required'); return; }
  try {
    const res = await window.apiClient.post(`/api/v1/admin/roles/${roleId}/permissions/tools`, { tool_name: tool });
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Granted');
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Grant failed'); }
}

async function tpRevokeFromRole() {
  const roleId = parseInt(document.getElementById('tp_role')?.value || '0', 10); if (!roleId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Role ID required'); return; }
  const tool = (document.getElementById('tp_tool')?.value || '').trim(); if (!tool) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Tool required'); return; }
  if (!confirm('Revoke ' + tool + ' from role ' + roleId + '?')) return;
  try {
    const res = await window.apiClient.delete(`/api/v1/admin/roles/${roleId}/permissions/tools/${encodeURIComponent(tool)}`);
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Revoked');
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Revoke failed'); }
}

async function tpListRoleToolPerms() {
  const roleId = parseInt(document.getElementById('tp_role')?.value || '0', 10); if (!roleId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Role ID required'); return; }
  try {
    const rows = await window.apiClient.get(`/api/v1/admin/roles/${roleId}/permissions/tools`);
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(rows || [], null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Listed role tool perms');
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('List failed'); }
}

async function tpGrantByPrefix() {
  const roleId = parseInt(document.getElementById('tp_role')?.value || '0', 10); const prefix = (document.getElementById('tp_prefix')?.value || '').trim();
  if (!roleId || !prefix) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Role ID and prefix required'); return; }
  try {
    const res = await window.apiClient.post(`/api/v1/admin/roles/${roleId}/permissions/tools/prefix/grant`, { prefix });
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(res || [], null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Granted by prefix');
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Grant by prefix failed'); }
}

async function tpRevokeByPrefix() {
  const roleId = parseInt(document.getElementById('tp_role')?.value || '0', 10); const prefix = (document.getElementById('tp_prefix')?.value || '').trim();
  if (!roleId || !prefix) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Role ID and prefix required'); return; }
  if (!confirm('Revoke all tool permissions by prefix from role ' + roleId + '?')) return;
  try {
    const res = await window.apiClient.post(`/api/v1/admin/roles/${roleId}/permissions/tools/prefix/revoke`, { prefix });
    document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(res || {}, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Revoked by prefix');
  } catch (e) { document.getElementById('adminToolPermissions_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Revoke by prefix failed'); }
}

// ---------- Rate Limits ----------
async function rlUpsertRole() {
  const roleId = parseInt(document.getElementById('rl_role')?.value || '0', 10); if (!roleId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Role ID required'); return; }
  const payload = { resource: (document.getElementById('rl_resource')?.value || '').trim(), limit_per_min: document.getElementById('rl_limit')?.value ? parseInt(document.getElementById('rl_limit').value, 10) : null, burst: document.getElementById('rl_burst')?.value ? parseInt(document.getElementById('rl_burst').value, 10) : null };
  if (!payload.resource) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Resource required'); return; }
  try {
    const res = await window.apiClient.post(`/api/v1/admin/roles/${roleId}/rate-limits`, payload);
    document.getElementById('adminRateLimits_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Role rate limit updated');
  } catch (e) { document.getElementById('adminRateLimits_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Upsert failed'); }
}

async function rlUpsertUser() {
  const userId = parseInt(document.getElementById('rl_user')?.value || '0', 10); if (!userId) { if (typeof Toast !== 'undefined' && Toast) Toast.error('User ID required'); return; }
  const payload = { resource: (document.getElementById('rl_u_resource')?.value || '').trim(), limit_per_min: document.getElementById('rl_u_limit')?.value ? parseInt(document.getElementById('rl_u_limit').value, 10) : null, burst: document.getElementById('rl_u_burst')?.value ? parseInt(document.getElementById('rl_u_burst').value, 10) : null };
  if (!payload.resource) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Resource required'); return; }
  try {
    const res = await window.apiClient.post(`/api/v1/admin/users/${userId}/rate-limits`, payload);
    document.getElementById('adminRateLimits_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('User rate limit updated');
  } catch (e) { document.getElementById('adminRateLimits_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Upsert failed'); }
}

async function rlReset() {
  const kind = document.getElementById('rl_kind')?.value || 'ip';
  const identifier = (document.getElementById('rl_identifier')?.value || '').trim();
  const endpoint = (document.getElementById('rl_endpoint')?.value || '').trim() || null;
  const dry_run = (document.getElementById('rl_dry')?.value === 'true');
  const payload = { kind, dry_run };
  if (kind === 'ip') payload.ip = identifier; else if (kind === 'user') payload.user_id = parseInt(identifier, 10); else if (kind === 'api') payload.api_key_hash = identifier; else if (kind === 'raw') payload.identifier = identifier;
  if (endpoint) payload.endpoint = endpoint;
  try {
    const res = await window.apiClient.post('/api/v1/admin/rate-limits/reset', payload);
    document.getElementById('adminRateLimits_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Rate limits reset');
  } catch (e) { document.getElementById('adminRateLimits_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Reset failed'); }
}

// ---------- Tool Catalog (UI placeholder; HTML added separately) ----------
async function tcList() {
  try {
    const rows = await window.apiClient.get('/api/v1/admin/mcp/tool_catalogs');
    const items = Array.isArray(rows) ? rows : [];
    const list = document.getElementById('adminToolCatalog_list');
    if (list) list.innerHTML = tableHTML(items.map(x => ({ id: x.id, name: x.name, org_id: x.org_id, team_id: x.team_id, is_active: x.is_active })), ['id','name','org_id','team_id','is_active']);
    document.getElementById('adminToolCatalog_result').textContent = 'Loaded catalogs';
  } catch (e) { document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('List catalogs failed'); }
}

async function tcCreate() {
  const name = (document.getElementById('tc_name')?.value || '').trim(); if (!name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Name required'); return; }
  const description = (document.getElementById('tc_desc')?.value || '').trim() || null;
  const org_id = document.getElementById('tc_org')?.value ? parseInt(document.getElementById('tc_org').value, 10) : null;
  const team_id = document.getElementById('tc_team')?.value ? parseInt(document.getElementById('tc_team').value, 10) : null;
  try {
    const res = await window.apiClient.post('/api/v1/admin/mcp/tool_catalogs', { name, description, org_id, team_id });
    document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Catalog created');
    await tcList();
  } catch (e) { document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Create catalog failed'); }
}

async function tcDelete() {
  const id = parseInt(document.getElementById('tc_catalog_id')?.value || '0', 10); if (!id) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Catalog id required'); return; }
  if (!confirm('Delete catalog #' + id + '?')) return;
  try {
    const res = await window.apiClient.delete(`/api/v1/admin/mcp/tool_catalogs/${id}`);
    document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Catalog deleted');
    await tcList();
  } catch (e) { document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Delete catalog failed'); }
}

async function tcListEntries() {
  const id = parseInt(document.getElementById('tc_catalog_id')?.value || '0', 10); if (!id) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Catalog id required'); return; }
  try {
    const rows = await window.apiClient.get(`/api/v1/admin/mcp/tool_catalogs/${id}/entries`);
    const items = Array.isArray(rows) ? rows : [];
    const entriesBox = document.getElementById('adminToolCatalog_entries');
    if (entriesBox) entriesBox.innerHTML = tableHTML(items.map(x => ({ tool_name: x.tool_name, module_id: x.module_id ?? '' })), ['tool_name','module_id']);
    document.getElementById('adminToolCatalog_result').textContent = 'Loaded entries';
  } catch (e) { document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('List entries failed'); }
}

async function tcAddEntry() {
  const id = parseInt(document.getElementById('tc_catalog_id')?.value || '0', 10); if (!id) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Catalog id required'); return; }
  const tool_name = (document.getElementById('tc_tool_name')?.value || '').trim(); if (!tool_name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('tool_name required'); return; }
  const module_id = (document.getElementById('tc_module_id')?.value || '').trim() || null;
  try {
    const res = await window.apiClient.post(`/api/v1/admin/mcp/tool_catalogs/${id}/entries`, { tool_name, module_id });
    document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Entry added');
    await tcListEntries();
  } catch (e) { document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Add entry failed'); }
}

async function tcDeleteEntry() {
  const id = parseInt(document.getElementById('tc_catalog_id')?.value || '0', 10); if (!id) { if (typeof Toast !== 'undefined' && Toast) Toast.error('Catalog id required'); return; }
  const tool_name = (document.getElementById('tc_tool_name')?.value || '').trim(); if (!tool_name) { if (typeof Toast !== 'undefined' && Toast) Toast.error('tool_name required'); return; }
  if (!confirm('Remove tool ' + tool_name + ' from catalog?')) return;
  try {
    const res = await window.apiClient.delete(`/api/v1/admin/mcp/tool_catalogs/${id}/entries/${encodeURIComponent(tool_name)}`);
    document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(res, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Entry deleted');
    await tcListEntries();
  } catch (e) { document.getElementById('adminToolCatalog_result').textContent = JSON.stringify(e.response || e, null, 2); if (typeof Toast !== 'undefined' && Toast) Toast.error('Delete entry failed'); }
}

// ---------- Ephemeral Cleanup Settings ----------
async function adminLoadCleanupSettings() {
  try {
    const resp = await window.apiClient.get('/api/v1/admin/cleanup-settings');
    const enabledEl = document.getElementById('adminCleanup_enabled');
    const intervalEl = document.getElementById('adminCleanup_interval');
    if (enabledEl) enabledEl.checked = !!resp.enabled;
    if (intervalEl) intervalEl.value = resp.interval_sec || 1800;
    const out = document.getElementById('adminCleanupSettings_response');
    if (out) out.textContent = JSON.stringify(resp, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Loaded cleanup settings');
  } catch (e) {
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to load cleanup settings: ' + (e?.message || e));
  }
}

async function adminSaveCleanupSettings() {
  try {
    const enabled = !!document.getElementById('adminCleanup_enabled')?.checked;
    const interval = parseInt(document.getElementById('adminCleanup_interval')?.value || '1800', 10);
    const body = { enabled, interval_sec: interval };
    const resp = await window.apiClient.post('/api/v1/admin/cleanup-settings', body);
    const out = document.getElementById('adminCleanupSettings_response');
    if (out) out.textContent = JSON.stringify(resp, null, 2);
    if (typeof Toast !== 'undefined' && Toast) Toast.success('Saved cleanup settings');
  } catch (e) {
    if (typeof Toast !== 'undefined' && Toast) Toast.error('Failed to save cleanup settings: ' + (e?.message || e));
  }
}

// ---------- Bindings ----------
function bindAdminAdvanced() {
  // Users: basic list/create in User Management section
  document.getElementById('btnAdminUsersList')?.addEventListener('click', () => window.makeRequest && window.makeRequest('adminUsersList', 'GET', '/api/v1/admin/users', 'query'));
  document.getElementById('btnAdminCreateUser')?.addEventListener('click', adminCreateUser);
  // Virtual keys
  document.getElementById('btnAdmVKList')?.addEventListener('click', admVKList);
  document.getElementById('btnAdmVKCreate')?.addEventListener('click', admVKCreate);
  document.getElementById('adminVirtualKeys_list')?.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.classList?.contains('admvk-revoke')) {
      const uid = t.getAttribute('data-uid');
      const kid = t.getAttribute('data-kid');
      if (uid && kid) admVKRevoke(parseInt(uid, 10), parseInt(kid, 10));
    }
  });

  // Orgs & Teams
  document.getElementById('btnAdmCreateOrg')?.addEventListener('click', admCreateOrg);
  document.getElementById('btnAdmListOrgs')?.addEventListener('click', admListOrgs);
  document.getElementById('btnAdmCreateTeam')?.addEventListener('click', admCreateTeam);
  document.getElementById('btnAdmListTeams')?.addEventListener('click', admListTeams);
  document.getElementById('btnAdmAddTeamMember')?.addEventListener('click', admAddTeamMember);
  document.getElementById('btnAdmListTeamMembers')?.addEventListener('click', admListTeamMembers);
  document.getElementById('btnAdmRemoveTeamMember')?.addEventListener('click', admRemoveTeamMember);
  document.getElementById('btnAdmAddOrgMember')?.addEventListener('click', admAddOrgMember);
  document.getElementById('btnAdmListOrgMembers')?.addEventListener('click', admListOrgMembers);
  document.getElementById('btnAdmUpdateOrgMemberRole')?.addEventListener('click', admUpdateOrgMemberRole);
  document.getElementById('btnAdmRemoveOrgMember')?.addEventListener('click', admRemoveOrgMember);
  document.getElementById('btnAdmGetOrgWatchCfg')?.addEventListener('click', admGetOrgWatchCfg);
  document.getElementById('btnAdmSetOrgWatchCfg')?.addEventListener('click', admSetOrgWatchCfg);

  // Tool permissions
  document.getElementById('btnTPList')?.addEventListener('click', tpListPerms);
  document.getElementById('btnTPCreate')?.addEventListener('click', tpCreatePerm);
  document.getElementById('btnTPDelete')?.addEventListener('click', tpDeletePerm);
  document.getElementById('btnTPGrant')?.addEventListener('click', tpGrantToRole);
  document.getElementById('btnTPRevoke')?.addEventListener('click', tpRevokeFromRole);
  document.getElementById('btnTPPrefixGrant')?.addEventListener('click', tpGrantByPrefix);
  document.getElementById('btnTPPrefixRevoke')?.addEventListener('click', tpRevokeByPrefix);
  document.getElementById('btnTPListRole')?.addEventListener('click', tpListRoleToolPerms);

  // Rate limits
  document.getElementById('btnRLUpsertRole')?.addEventListener('click', rlUpsertRole);
  document.getElementById('btnRLUpsertUser')?.addEventListener('click', rlUpsertUser);
  document.getElementById('btnRLReset')?.addEventListener('click', rlReset);

  // Legacy Admin Users API Keys (bind to global handlers without inline attributes)
  document.getElementById('btnAdmUserKeysList')?.addEventListener('click', () => window.adminListUserApiKeys && window.adminListUserApiKeys());
  document.getElementById('btnAdmUserKeysCreate')?.addEventListener('click', () => window.adminCreateUserApiKey && window.adminCreateUserApiKey());
  document.getElementById('btnAdmUserKeyUpdateLimits')?.addEventListener('click', () => window.adminUpdateKeyLimits && window.adminUpdateKeyLimits());
  document.getElementById('btnAdmUserKeyLoadAudit')?.addEventListener('click', () => window.adminLoadKeyAudit && window.adminLoadKeyAudit());

  // Delegated Users API Keys row actions
  document.getElementById('adminUserApiKeys_list')?.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.classList?.contains('adm-uk-rotate')) {
      const uid = parseInt(t.getAttribute('data-uid') || '0', 10);
      const kid = parseInt(t.getAttribute('data-kid') || '0', 10);
      if (uid && kid) admUserKeyRotate(uid, kid);
    } else if (t && t.classList?.contains('adm-uk-revoke')) {
      const uid = parseInt(t.getAttribute('data-uid') || '0', 10);
      const kid = parseInt(t.getAttribute('data-kid') || '0', 10);
      if (uid && kid) admUserKeyRevoke(uid, kid);
    }
  });

  // Registration Codes
  document.getElementById('btnRegCodeCreate')?.addEventListener('click', rcCreate);
  document.getElementById('btnRegCodeList')?.addEventListener('click', rcList);
  document.getElementById('adminRegCodes_list')?.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.classList?.contains('rc-delete')) {
      const id = parseInt(t.getAttribute('data-id') || '0', 10);
      if (id) rcDelete(id);
    }
  });

  // LLM Usage (query/download) controls
  document.getElementById('btnAdminLLMUsageQuery')?.addEventListener('click', adminQueryLLMUsage);
  document.getElementById('btnAdminLLMUsageCSV')?.addEventListener('click', adminDownloadLLMUsageCSV);

  // Audit Export controls
  document.getElementById('btnAdminAuditDownload')?.addEventListener('click', adminAuditDownload);
  document.getElementById('btnAdminAuditLast24h')?.addEventListener('click', adminAuditDownloadLast24hHighRisk);
  document.getElementById('btnAdminAuditApiEvents')?.addEventListener('click', adminAuditDownloadApiEventsCSV);
  document.getElementById('btnAdminAuditPreview')?.addEventListener('click', adminAuditPreviewJSON);

  // LLM Usage Charts controls
  document.getElementById('btnAdminLoadLLMCharts')?.addEventListener('click', adminLoadLLMCharts);
  document.getElementById('btnResetLegendTop')?.addEventListener('click', () => _resetLegendVisibility('llmLegendTopSpenders','llmChartTopSpenders'));
  document.getElementById('btnResetLegendModel')?.addEventListener('click', () => _resetLegendVisibility('llmLegendModelMix','llmChartModelMix'));
  document.getElementById('btnResetLegendProvider')?.addEventListener('click', () => _resetLegendVisibility('llmLegendProviderMix','llmChartProviderMix'));

  // Tool catalog (if present in HTML)
  document.getElementById('btnTCList')?.addEventListener('click', tcList);
  document.getElementById('btnTCCreate')?.addEventListener('click', tcCreate);
  document.getElementById('btnTCDelete')?.addEventListener('click', tcDelete);
  document.getElementById('btnTCEntries')?.addEventListener('click', tcListEntries);
  document.getElementById('btnTCAddEntry')?.addEventListener('click', tcAddEntry);
  document.getElementById('btnTCDeleteEntry')?.addEventListener('click', tcDeleteEntry);

  // Moderation: Settings
  document.getElementById('btnModSettingsLoad')?.addEventListener('click', moderationLoadSettings);
  document.getElementById('btnModSettingsSave')?.addEventListener('click', moderationSaveSettings);

  // Moderation: Managed
  document.getElementById('btnModerationLoadManaged')?.addEventListener('click', moderationLoadManaged);
  document.getElementById('btnModerationRefreshManaged')?.addEventListener('click', moderationRefreshManaged);
  document.getElementById('btnModerationAppendManaged')?.addEventListener('click', moderationAppendManaged);
  document.getElementById('btnModerationLintManaged')?.addEventListener('click', moderationLintManaged);
  document.getElementById('moderationManaged_filter')?.addEventListener('input', renderManagedBlocklist);
  document.getElementById('moderationManaged_onlyInvalid')?.addEventListener('change', renderManagedBlocklist);
  document.getElementById('moderationManaged_table')?.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.classList?.contains('mod-managed-del')) {
      const id = parseInt(t.getAttribute('data-id') || '0', 10);
      if (id) moderationDeleteManaged(id);
    }
  });

  // Moderation: Raw blocklist
  document.getElementById('btnModerationLoadBlocklist')?.addEventListener('click', moderationLoadBlocklist);
  document.getElementById('btnModerationLintBlocklist')?.addEventListener('click', moderationLintBlocklist);
  document.getElementById('btnModerationSaveBlocklist')?.addEventListener('click', moderationSaveBlocklist);
  document.getElementById('btnModerationCopyInvalidBlocklist')?.addEventListener('click', moderationCopyInvalidBlocklist);
  document.getElementById('moderationBlocklist_onlyInvalid')?.addEventListener('change', renderBlocklistInvalidList);

  // Moderation: Overrides + Tester
  document.getElementById('btnModOverrideLoad')?.addEventListener('click', loadUserOverride);
  document.getElementById('btnModOverrideSave')?.addEventListener('click', saveUserOverride);
  document.getElementById('btnModOverrideDelete')?.addEventListener('click', deleteUserOverride);
  document.getElementById('btnModerationListOverrides')?.addEventListener('click', moderationListOverrides);
  document.getElementById('btnModerationRunTest')?.addEventListener('click', moderationRunTest);
  document.getElementById('moderationOverrides_list')?.addEventListener('click', (e) => {
    const t = e.target;
    if (t && t.classList?.contains('mod-load-editor')) {
      const uid = t.getAttribute('data-uid');
      if (uid) moderationLoadIntoEditor(uid);
    }
  });

  // Health panel
  document.getElementById('btnHealthMain')?.addEventListener('click', () => window.makeRequest && window.makeRequest('healthMain','GET','/health','none'));
  document.getElementById('btnHealthRAG')?.addEventListener('click', () => window.makeRequest && window.makeRequest('healthRAG','GET','/api/v1/rag/health','none'));
  document.getElementById('btnHealthEmbeddings')?.addEventListener('click', () => window.makeRequest && window.makeRequest('healthEmbeddings','GET','/api/v1/embeddings/health','none'));
  document.getElementById('btnHealthWebScraping')?.addEventListener('click', () => window.makeRequest && window.makeRequest('healthWebScraping','GET','/api/v1/web-scraping/status','none'));

  // Ephemeral Cleanup Settings
  document.getElementById('btnAdminCleanupLoad')?.addEventListener('click', adminLoadCleanupSettings);
  document.getElementById('btnAdminCleanupSave')?.addEventListener('click', adminSaveCleanupSettings);

  // Security alerts
  document.getElementById('btnSecAlertRefresh')?.addEventListener('click', loadSecurityAlertStatus);
  setTimeout(() => { try { if (document.getElementById('btnSecAlertRefresh')) loadSecurityAlertStatus(); } catch (_) {} }, 300);

  // Usage
  document.getElementById('btnUsageLoadDaily')?.addEventListener('click', adminLoadUsageDaily);
  document.getElementById('btnUsageDownloadDailyCSV')?.addEventListener('click', adminDownloadUsageDailyCSV);
  document.getElementById('btnUsageTop')?.addEventListener('click', adminLoadUsageTop);
  document.getElementById('btnUsageDownloadTopCSV')?.addEventListener('click', adminDownloadUsageTopCSV);
  document.getElementById('btnUsageAggregate')?.addEventListener('click', adminRunUsageAggregate);

  // Admin user simple ops
  document.getElementById('btnAdminUserGet')?.addEventListener('click', () => window.makeRequest && window.makeRequest('adminUserGet', 'GET', '/api/v1/admin/users/{id}', 'none'));
  document.getElementById('btnAdminUserUpdate')?.addEventListener('click', () => window.makeRequest && window.makeRequest('adminUserUpdate', 'PUT', '/api/v1/admin/users/{id}', 'json'));
  document.getElementById('btnAdminUserDelete')?.addEventListener('click', () => { if (confirm('Are you sure you want to delete this user?')) window.makeRequest && window.makeRequest('adminUserDelete','DELETE','/api/v1/admin/users/{id}','none'); });
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindAdminAdvanced);
  else bindAdminAdvanced();
}

export default {
  // Expose for tests
  admVKList, admVKCreate, admVKRevoke,
  admCreateOrg, admListOrgs, admCreateTeam, admListTeams,
  admAddTeamMember, admListTeamMembers, admRemoveTeamMember,
  admAddOrgMember, admListOrgMembers, admUpdateOrgMemberRole, admRemoveOrgMember,
  admGetOrgWatchCfg, admSetOrgWatchCfg,
  tpListPerms, tpCreatePerm, tpDeletePerm, tpGrantToRole, tpRevokeFromRole, tpListRoleToolPerms, tpGrantByPrefix, tpRevokeByPrefix,
  rlUpsertRole, rlUpsertUser, rlReset,
  rcCreate, rcList, rcDelete, rcRenderList,
  adminQueryLLMUsage, adminDownloadLLMUsageCSV,
  adminAuditDownload, adminAuditDownloadLast24hHighRisk, adminAuditDownloadApiEventsCSV, adminAuditPreviewJSON,
  adminLoadLLMCharts,
  admUserKeyRotate, admUserKeyRevoke,
  adminLoadCleanupSettings: adminLoadCleanupSettings,
  adminSaveCleanupSettings: adminSaveCleanupSettings,
  tcList, tcCreate, tcDelete, tcListEntries, tcAddEntry, tcDeleteEntry,
  bindAdminAdvanced,
};
