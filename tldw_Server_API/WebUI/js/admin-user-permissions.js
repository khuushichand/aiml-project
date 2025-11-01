// admin-user-permissions.js
// Admin subtab: interactive editor to manage a user's roles and permission overrides.

/* global Toast */

const UP_STATE = {
  selectedUser: null, // { id, username, email, role, ... }
  roles: [], // [{id,name,description,is_system}]
  userRoles: new Set(),
  permissions: [], // [{id,name,category,description}]
  overrides: new Map(), // permission_id -> { permission_id, permission_name, granted, expires_at }
  effective: new Set(), // set of permission names
  categories: [],
};

function _esc(x) {
  const m = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(x ?? '').replace(/[&<>"']/g, c => m[c]);
}

async function _apiGet(path) { return await window.apiClient.get(path); }
async function _apiPost(path, body) { return await window.apiClient.post(path, body ?? {}); }
async function _apiDelete(path) { return await window.apiClient.delete(path); }

function _setSelectedUser(user) {
  UP_STATE.selectedUser = user ? { ...user } : null;
  const info = document.getElementById('userPermSelected');
  if (!info) return;
  if (!user) info.textContent = 'No user selected';
  else info.innerHTML = `User: <strong>${_esc(user.username || user.email || user.id)}</strong> (id=${_esc(user.id)})`;
}

function _renderSearchResults(list) {
  const box = document.getElementById('userPermSearchResults');
  if (!box) return;
  if (!Array.isArray(list) || !list.length) { box.style.display = 'none'; box.innerHTML = ''; return; }
  let html = '<div><strong>Select a user:</strong></div>';
  html += '<ul class="simple-list">';
  for (const u of list) {
    const label = `${u.username || '(no-username)'} · ${u.email || ''} · id=${u.id}`;
    html += `<li><button class="btn btn-secondary btn-compact user-select" data-userid="${_esc(u.id)}" title="Select ${_esc(label)}">${_esc(label)}</button></li>`;
  }
  html += '</ul>';
  box.innerHTML = html;
  box.style.display = 'block';
}

async function searchUsers() {
  try {
    const q = (document.getElementById('userPermSearch')?.value || '').trim();
    const query = q ? `?search=${encodeURIComponent(q)}` : '';
    const res = await _apiGet(`/api/v1/admin/users${query}`);
    const list = Array.isArray(res?.users) ? res.users : [];
    _renderSearchResults(list);
  } catch (e) {
    document.getElementById('userPermSearchResults').innerHTML = `<pre>${_esc(JSON.stringify(e.response || e, null, 2))}</pre>`;
    document.getElementById('userPermSearchResults').style.display = 'block';
    Toast?.error && Toast.error('Failed to search users');
  }
}

async function loadRolesAndAssignments(userId) {
  const [rolesRes, userRolesRes] = await Promise.all([
    _apiGet('/api/v1/admin/roles'),
    _apiGet(`/api/v1/admin/users/${userId}/roles`),
  ]);
  UP_STATE.roles = Array.isArray(rolesRes) ? rolesRes : [];
  const roles = Array.isArray(userRolesRes?.roles) ? userRolesRes.roles : [];
  UP_STATE.userRoles = new Set(roles.map(r => r.id));
}

async function loadPermissionsAndOverrides(userId) {
  const [permsRes, overridesRes, effRes] = await Promise.all([
    _apiGet('/api/v1/admin/permissions'),
    _apiGet(`/api/v1/admin/users/${userId}/overrides`),
    _apiGet(`/api/v1/admin/users/${userId}/effective-permissions`),
  ]);
  UP_STATE.permissions = Array.isArray(permsRes) ? permsRes : [];
  const cats = new Set();
  for (const p of UP_STATE.permissions) if (p.category) cats.add(p.category);
  UP_STATE.categories = Array.from(cats).sort();
  const entries = Array.isArray(overridesRes?.overrides) ? overridesRes.overrides : [];
  UP_STATE.overrides = new Map(entries.map(e => [e.permission_id, e]));
  const eff = new Set(Array.isArray(effRes?.permissions) ? effRes.permissions : []);
  UP_STATE.effective = eff;
}

function renderRoleCheckboxes() {
  const container = document.getElementById('userPermRolesList');
  if (!container) return;
  if (!UP_STATE.selectedUser) { container.innerHTML = '<p>Select a user above.</p>'; return; }
  let html = '';
  for (const r of UP_STATE.roles) {
    const checked = UP_STATE.userRoles.has(r.id) ? 'checked' : '';
    html += `<label style="display:block; margin:4px 0;">
      <input type="checkbox" class="user-role-toggle" data-roleid="${_esc(r.id)}" ${checked}/> ${_esc(r.name)}
      ${r.is_system ? '<span class="tag" title="system role">system</span>' : ''}
    </label>`;
  }
  container.innerHTML = html || '<p>No roles defined.</p>';
}

function _overrideStateForPid(pid) {
  const o = UP_STATE.overrides.get(pid);
  if (!o) return 'inherit';
  return o.granted ? 'allow' : 'deny';
}

function _visiblePermissions() {
  const search = (document.getElementById('permFilterSearch')?.value || '').trim().toLowerCase();
  const cat = (document.getElementById('permFilterCategory')?.value || '').trim();
  let list = [...UP_STATE.permissions];
  if (cat) list = list.filter(p => (p.category || '') === cat);
  if (search) list = list.filter(p => (p.name || '').toLowerCase().includes(search));
  return list;
}

function _splitVisibleByTool() {
  const ALL = _visiblePermissions();
  const toolPrefix = 'tools.execute:';
  const tools = [];
  const std = [];
  for (const p of ALL) {
    if ((p.name || '').startsWith(toolPrefix)) tools.push(p); else std.push(p);
  }
  return { tools, std };
}

function renderOverridesTable() {
  const toolsBody = document.getElementById('userPermOverridesTableTools');
  const stdBody = document.getElementById('userPermOverridesTableStd');
  const catSel = document.getElementById('permFilterCategory');
  if (catSel && !catSel._applied) {
    let opt = '<option value="">All</option>';
    for (const c of UP_STATE.categories) opt += `<option value="${_esc(c)}">${_esc(c)}</option>`;
    catSel.innerHTML = opt; catSel._applied = true;
  }
  if (!toolsBody || !stdBody) return;
  if (!UP_STATE.selectedUser) {
    toolsBody.innerHTML = '<tr><td colspan="4">Select a user.</td></tr>';
    stdBody.innerHTML = '<tr><td colspan="4">Select a user.</td></tr>';
    return;
  }
  const { tools, std } = _splitVisibleByTool();
  const renderRows = (rows) => {
    if (!rows.length) return '<tr><td colspan="4">No permissions.</td></tr>';
    let html = '';
    for (const p of rows) {
      const st = _overrideStateForPid(p.id);
      const eff = UP_STATE.effective.has(p.name);
      const name = `ovr-${p.id}`;
      html += `<tr>
        <td>${_esc(p.name)}</td>
        <td>${_esc(p.category || '')}</td>
        <td style="text-align:center;">${eff ? '✓' : ''}</td>
        <td>
          <label class="inline"><input type="radio" name="${name}" value="inherit" ${st === 'inherit' ? 'checked' : ''}/> Inherit</label>
          <label class="inline" style="margin-left:8px;"><input type="radio" name="${name}" value="allow" ${st === 'allow' ? 'checked' : ''}/> Allow</label>
          <label class="inline" style="margin-left:8px;"><input type="radio" name="${name}" value="deny" ${st === 'deny' ? 'checked' : ''}/> Deny</label>
        </td>
      </tr>`;
    }
    return html;
  };
  toolsBody.innerHTML = renderRows(tools);
  stdBody.innerHTML = renderRows(std);
}

async function _applyRoleToggle(roleId, checked) {
  const uid = UP_STATE.selectedUser?.id;
  if (!uid) return;
  try {
    if (checked) await _apiPost(`/api/v1/admin/users/${uid}/roles/${roleId}`, {});
    else await _apiDelete(`/api/v1/admin/users/${uid}/roles/${roleId}`);
    if (checked) UP_STATE.userRoles.add(roleId); else UP_STATE.userRoles.delete(roleId);
    Toast?.success && Toast.success(checked ? 'Role assigned' : 'Role removed');
  } catch (e) {
    Toast?.error && Toast.error('Failed to update role');
  }
}

async function _applyOverrideChange(pid, action, opts = {}) {
  const uid = UP_STATE.selectedUser?.id;
  if (!uid) return;
  try {
    if (action === 'inherit') {
      if (UP_STATE.overrides.has(pid)) await _apiDelete(`/api/v1/admin/users/${uid}/overrides/${pid}`);
      UP_STATE.overrides.delete(pid);
    } else {
      const effect = action === 'allow' ? 'allow' : 'deny';
      const res = await _apiPost(`/api/v1/admin/users/${uid}/overrides`, { permission_id: pid, effect });
      // Refresh override entry
      UP_STATE.overrides.set(pid, { permission_id: pid, permission_name: (UP_STATE.permissions.find(p => p.id === pid)?.name || ''), granted: (effect === 'allow'), expires_at: null });
    }
    if (!opts.deferRefresh) {
      // Refresh effective perms after override change
      const effRes = await _apiGet(`/api/v1/admin/users/${uid}/effective-permissions`);
      UP_STATE.effective = new Set(Array.isArray(effRes?.permissions) ? effRes.permissions : []);
      renderOverridesTable();
      renderEffectiveOut();
    }
    if (!opts.silent) Toast?.success && Toast.success('Override updated');
  } catch (e) {
    Toast?.error && Toast.error('Failed to update override');
  }
}

async function bulkApplyOverrides(action, which = 'all') {
  if (!UP_STATE.selectedUser) return;
  const { tools, std } = _splitVisibleByTool();
  let all;
  if (which === 'tools') all = tools; else if (which === 'std') all = std; else all = [...tools, ...std];
  if (!all.length) return Toast?.error && Toast.error('No filtered permissions to update');
  const actionLabel = action === 'allow' ? 'Allow' : action === 'deny' ? 'Deny' : 'Inherit';
  const sectionLabel = which === 'tools' ? 'tool permissions' : which === 'std' ? 'standard permissions' : 'filtered permissions';
  const confirmed = window.confirm(`${actionLabel} ${all.length} ${sectionLabel}?`);
  if (!confirmed) return;
  try {
    const container = document.getElementById('adminUserPerms') || document.getElementById('tabAdminUserPermissions');
    let loaderId = null;
    const useOverlay = (all.length > 10);
    if (useOverlay && typeof Loading !== 'undefined' && container) {
      loaderId = Loading.show(container, `${actionLabel} 0/${all.length}…`);
    }
    // Apply without refreshing each time; update progress text
    for (let i = 0; i < all.length; i++) {
      const p = all[i];
      await _applyOverrideChange(p.id, action, { deferRefresh: true, silent: true });
      try {
        if (loaderId) {
          const overlay = document.getElementById(loaderId);
          const msg = overlay && overlay.querySelector('.loading-message');
          if (msg) msg.textContent = `${actionLabel} ${i + 1}/${all.length}…`;
        }
      } catch (_) { /* ignore */ }
    }
    // Single refresh
    const uid = UP_STATE.selectedUser.id;
    const effRes = await _apiGet(`/api/v1/admin/users/${uid}/effective-permissions`);
    UP_STATE.effective = new Set(Array.isArray(effRes?.permissions) ? effRes.permissions : []);
    renderOverridesTable();
    renderEffectiveOut();
    Toast?.success && Toast.success(`Applied '${action}' to ${all.length} ${sectionLabel}`);
    try { if (loaderId && container) Loading.hide(container); } catch (_) { /* ignore */ }
  } catch (e) {
    Toast?.error && Toast.error('Bulk update failed');
  }
}

function renderEffectiveOut() {
  const el = document.getElementById('userPermEffectiveOut');
  if (!el) return;
  if (!UP_STATE.selectedUser) { el.textContent = '-'; return; }
  el.textContent = JSON.stringify({ user_id: UP_STATE.selectedUser.id, permissions: Array.from(UP_STATE.effective).sort() }, null, 2);
}

async function loadUserPermissionsEditor(user) {
  _setSelectedUser(user);
  if (!user) return;
  try {
    await loadRolesAndAssignments(user.id);
    renderRoleCheckboxes();
    await loadPermissionsAndOverrides(user.id);
    renderOverridesTable();
    renderEffectiveOut();
  } catch (e) {
    Toast?.error && Toast.error('Failed to load user data');
  }
}

function bindHandlers() {
  document.getElementById('btnUserPermSearch')?.addEventListener('click', searchUsers);
  document.getElementById('btnUserPermReload')?.addEventListener('click', async () => {
    if (UP_STATE.selectedUser) await loadUserPermissionsEditor(UP_STATE.selectedUser);
  });
  document.getElementById('btnUserPermRefreshEffective')?.addEventListener('click', async () => {
    if (!UP_STATE.selectedUser) return;
    try { const effRes = await _apiGet(`/api/v1/admin/users/${UP_STATE.selectedUser.id}/effective-permissions`);
      UP_STATE.effective = new Set(Array.isArray(effRes?.permissions) ? effRes.permissions : []);
      renderEffectiveOut();
      renderOverridesTable();
    } catch (e) { /* ignore */ }
  });
  document.getElementById('permFilterSearch')?.addEventListener('input', renderOverridesTable);
  document.getElementById('permFilterCategory')?.addEventListener('change', renderOverridesTable);
  document.getElementById('btnPermBulkAllowTools')?.addEventListener('click', () => bulkApplyOverrides('allow', 'tools'));
  document.getElementById('btnPermBulkDenyTools')?.addEventListener('click', () => bulkApplyOverrides('deny', 'tools'));
  document.getElementById('btnPermBulkInheritTools')?.addEventListener('click', () => bulkApplyOverrides('inherit', 'tools'));
  document.getElementById('btnPermBulkAllowStd')?.addEventListener('click', () => bulkApplyOverrides('allow', 'std'));
  document.getElementById('btnPermBulkDenyStd')?.addEventListener('click', () => bulkApplyOverrides('deny', 'std'));
  document.getElementById('btnPermBulkInheritStd')?.addEventListener('click', () => bulkApplyOverrides('inherit', 'std'));

  // Delegated: pick a user from search results
  document.getElementById('userPermSearchResults')?.addEventListener('click', async (e) => {
    const t = e.target;
    if (t && t.classList?.contains('user-select')) {
      const id = parseInt(t.getAttribute('data-userid') || 'NaN', 10);
      if (!isNaN(id)) {
        // Compose a minimal user object to display while we fetch full lists
        await loadUserPermissionsEditor({ id, username: t.textContent.split(' · ')[0] || String(id) });
      }
    }
  });

  // Delegated: toggle role assignment
  document.getElementById('userPermRolesList')?.addEventListener('change', (e) => {
    const t = e.target;
    if (t && t.classList?.contains('user-role-toggle')) {
      const rid = parseInt(t.getAttribute('data-roleid') || 'NaN', 10);
      if (!isNaN(rid)) _applyRoleToggle(rid, !!t.checked);
    }
  });

  // Delegated: override choice change
  const _onOvrChange = (e) => {
    const t = e.target;
    if (t && t.name && t.name.startsWith('ovr-')) {
      const pid = parseInt(t.name.substring(4), 10);
      const action = t.value; // inherit | allow | deny
      if (!isNaN(pid)) _applyOverrideChange(pid, action);
    }
  };
  document.getElementById('userPermOverridesTableTools')?.addEventListener('change', _onOvrChange);
  document.getElementById('userPermOverridesTableStd')?.addEventListener('change', _onOvrChange);
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindHandlers);
  else bindHandlers();
}

export default {
  searchUsers, loadUserPermissionsEditor,
};
