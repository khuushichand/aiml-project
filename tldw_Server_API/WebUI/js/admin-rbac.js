// admin-rbac.js
// RBAC logic migrated from inline <script> blocks in admin_content.html.
// Exposes the same function names on window for compatibility, and binds
// events to replace inline onclick handlers. Also renders RBAC matrix without
// inline event attributes (delegated handlers instead).

/* global Utils, Toast */

const RBAC_CACHE = { list: null, boolean: null, categoriesLoaded: false };
const RBAC_META = { categories: [], permCategoryByName: {} };

function _escapeHtml(text) {
  const map = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;' };
  return String(text).replace(/[&<>"']/g, m => map[m]);
}

function _setLoading(targetId, isLoading) {
  try {
    const target = document.getElementById(targetId);
    if (!target) return;
    if (isLoading) {
      target.innerHTML = '<div class="spinner" aria-label="Loading"></div>';
    }
  } catch (_) { /* ignore */ }
}

function _filters() {
  const category = document.getElementById('rbacMatrixCategory')?.value || '';
  const search = (document.getElementById('rbacMatrixSearch')?.value || '').trim();
  const pinned = (document.getElementById('rbacMatrixPinned')?.value || '')
    .split(',').map(s => s.trim()).filter(Boolean);
  return { category, search, pinned };
}

async function _ensurePermissionCategories() {
  if (RBAC_CACHE.categoriesLoaded) return;
  try {
    const cats = await window.apiClient.get('/api/v1/admin/permissions/categories');
    RBAC_META.categories = Array.isArray(cats) ? cats : [];
  } catch (_) {
    RBAC_META.categories = [];
  }
  const sel = document.getElementById('rbacMatrixCategory');
  if (sel) {
    const current = sel.value;
    let html = '<option value="">All</option>';
    for (const c of RBAC_META.categories) html += `<option value="${_escapeHtml(c)}">${_escapeHtml(c)}</option>`;
    sel.innerHTML = html;
    if (RBAC_META.categories.includes(current)) sel.value = current;
  }
  // Populate quick pin category select if present
  try {
    const pinSel = document.getElementById('rbacPinCategory');
    if (pinSel) {
      let ph = '';
      for (const c of RBAC_META.categories) ph += `<option value="${_escapeHtml(c)}">${_escapeHtml(c)}</option>`;
      pinSel.innerHTML = ph;
    }
  } catch (_) { /* ignore */ }
  RBAC_CACHE.categoriesLoaded = true;
}

async function _ensureRolesList() {
  // We reuse the existing endpoint via loadRbacMatrixList which will set RBAC_CACHE.list
  if (!RBAC_CACHE.list) return;
}

function _rebuildPermCategoryByName() {
  try {
    const list = RBAC_CACHE.list;
    const perms = Array.isArray(list?.permissions) ? list.permissions : [];
    const map = {};
    for (const p of perms) { map[p.name] = p.category || ''; }
    RBAC_META.permCategoryByName = map;
  } catch (_) { /* ignore */ }
}

function _updateRbacRolesInfo(count) {
  try {
    const total = RBAC_CACHE.total_roles || 0;
    const info = document.getElementById('rbacRolesInfo');
    const note = document.getElementById('rbacRolesNote');
    if (info) info.textContent = `Roles: ${count}${total && total !== count ? ` (showing ${count} of ${total})` : ''}`;
    if (note) note.textContent = total && total !== count ? 'Use Next/Prev or filters to page.' : '';
  } catch (_) { /* ignore */ }
}

function _saveRbacFilterState() {
  try {
    const data = {
      category: document.getElementById('rbacMatrixCategory')?.value || '',
      search: document.getElementById('rbacMatrixSearch')?.value || '',
      pinned: document.getElementById('rbacMatrixPinned')?.value || '',
      roleSearch: document.getElementById('rbacRoleSearch')?.value || '',
      rolesLimit: document.getElementById('rbacRolesLimit')?.value || '100',
      rolesOffset: document.getElementById('rbacRolesOffset')?.value || '0',
      roleNames: Array.from(document.getElementById('rbacRoleNames')?.selectedOptions || []).map(o => o.value),
      visibleCats: Array.from(document.getElementById('rbacVisibleCats')?.selectedOptions || []).map(o => o.value),
    };
    localStorage.setItem('rbacFilters', JSON.stringify(data));
  } catch (_) { /* ignore */ }
}

function _loadRbacFilterState() {
  try {
    const raw = localStorage.getItem('rbacFilters');
    if (!raw) return null;
    const data = JSON.parse(raw);
    document.getElementById('rbacMatrixCategory') && (document.getElementById('rbacMatrixCategory').value = data.category || '');
    document.getElementById('rbacMatrixSearch') && (document.getElementById('rbacMatrixSearch').value = data.search || '');
    document.getElementById('rbacMatrixPinned') && (document.getElementById('rbacMatrixPinned').value = data.pinned || '');
    document.getElementById('rbacRoleSearch') && (document.getElementById('rbacRoleSearch').value = data.roleSearch || '');
    document.getElementById('rbacRolesLimit') && (document.getElementById('rbacRolesLimit').value = data.rolesLimit || '100');
    document.getElementById('rbacRolesOffset') && (document.getElementById('rbacRolesOffset').value = data.rolesOffset || '0');
    RBAC_CACHE.savedRoleNames = Array.isArray(data.roleNames) ? data.roleNames : [];
    RBAC_CACHE.savedVisibleCats = Array.isArray(data.visibleCats) ? data.visibleCats : [];
    return data;
  } catch (_) { return null; }
}

function _applySavedRoleNamesSelection() {
  try {
    const saved = RBAC_CACHE.savedRoleNames || [];
    if (!saved.length) return;
    const sel = document.getElementById('rbacRoleNames');
    const options = Array.from(sel?.options || []);
    for (const opt of options) opt.selected = saved.includes(opt.value);
  } catch (_) { /* ignore */ }
}

function _applySavedVisibleCatsSelection() {
  try {
    const saved = RBAC_CACHE.savedVisibleCats || [];
    if (!saved.length) return;
    const sel = document.getElementById('rbacVisibleCats');
    const options = Array.from(sel?.options || []);
    for (const opt of options) opt.selected = saved.includes(opt.value);
  } catch (_) { /* ignore */ }
}

async function loadRbacMatrixList() {
  try {
    await _ensurePermissionCategories();
    _setLoading('rbacMatrixList', true);
    const { category, search } = _filters();
    const qs = new URLSearchParams();
    if (category) qs.set('category', category);
    if (search) qs.set('search', search);
    const roleSearch = (document.getElementById('rbacRoleSearch')?.value || '').trim();
    const rolesLimit = parseInt(document.getElementById('rbacRolesLimit')?.value || '100', 10);
    const rolesOffset = parseInt(document.getElementById('rbacRolesOffset')?.value || '0', 10);
    if (roleSearch) qs.set('role_search', roleSearch);
    if (!isNaN(rolesLimit)) qs.set('roles_limit', String(rolesLimit));
    if (!isNaN(rolesOffset)) qs.set('roles_offset', String(rolesOffset));
    const roleNamesSel = document.getElementById('rbacRoleNames');
    const selectedNames = Array.from(roleNamesSel?.selectedOptions || []).map(o => o.value);
    for (const n of selectedNames) qs.append('role_names', n);
    const path = qs.toString() ? `/api/v1/admin/roles/matrix?${qs.toString()}` : '/api/v1/admin/roles/matrix';
    const data = await window.apiClient.get(path);
    RBAC_CACHE.list = data;
    _rebuildPermCategoryByName();
    RBAC_CACHE.total_roles = typeof data.total_roles === 'number' ? data.total_roles : undefined;
    renderRbacMatrixList();
    _updateRbacRolesInfo(Array.isArray(data.roles) ? data.roles.length : 0);
    _saveRbacFilterState();
    Toast?.success && Toast.success('Loaded RBAC role→permissions list');
  } catch (e) {
    const el = document.getElementById('rbacMatrixList');
    if (el) el.innerHTML = `<pre>${_escapeHtml(JSON.stringify(e.response || e, null, 2))}</pre>`;
    Toast?.error && Toast.error('Failed to load matrix');
  }
}

async function loadRbacMatrixBoolean() {
  try {
    await _ensurePermissionCategories();
    _setLoading('rbacMatrixBoolean', true);
    if (!RBAC_CACHE.list) {
      await loadRbacMatrixList();
    }
    const { category, search } = _filters();
    const qs = new URLSearchParams();
    if (category) qs.set('category', category);
    if (search) qs.set('search', search);
    const roleSearch = (document.getElementById('rbacRoleSearch')?.value || '').trim();
    const rolesLimit = parseInt(document.getElementById('rbacRolesLimit')?.value || '100', 10);
    const rolesOffset = parseInt(document.getElementById('rbacRolesOffset')?.value || '0', 10);
    if (roleSearch) qs.set('role_search', roleSearch);
    if (!isNaN(rolesLimit)) qs.set('roles_limit', String(rolesLimit));
    if (!isNaN(rolesOffset)) qs.set('roles_offset', String(rolesOffset));
    const roleNamesSel = document.getElementById('rbacRoleNames');
    const selectedNames = Array.from(roleNamesSel?.selectedOptions || []).map(o => o.value);
    for (const n of selectedNames) qs.append('role_names', n);
    const path = qs.toString() ? `/api/v1/admin/roles/matrix/boolean?${qs.toString()}` : '/api/v1/admin/roles/matrix/boolean';
    const data = await window.apiClient.get(path);
    RBAC_CACHE.boolean = data;
    RBAC_CACHE.total_roles = typeof data.total_roles === 'number' ? data.total_roles : RBAC_CACHE.total_roles;
    renderRbacMatrixBoolean();
    _updateRbacRolesInfo(Array.isArray(data.roles) ? data.roles.length : 0);
    _saveRbacFilterState();
    Toast?.success && Toast.success('Loaded RBAC boolean grid');
  } catch (e) {
    const el = document.getElementById('rbacMatrixBoolean');
    if (el) el.innerHTML = `<pre>${_escapeHtml(JSON.stringify(e.response || e, null, 2))}</pre>`;
    Toast?.error && Toast.error('Failed to load boolean grid');
  }
}

function reloadRbacMatrices() {
  RBAC_CACHE.list = null;
  RBAC_CACHE.boolean = null;
  RBAC_CACHE.categoriesLoaded = false;
  RBAC_META.permCategoryByName = {};
  loadRbacMatrixList();
  loadRbacMatrixBoolean();
}

function rbacSelectAllRoleNames() {
  try {
    const sel = document.getElementById('rbacRoleNames');
    Array.from(sel?.options || []).forEach(opt => (opt.selected = true));
    _saveRbacFilterState();
  } catch (_) { /* ignore */ }
}

function rbacClearRoleNames() {
  try {
    const sel = document.getElementById('rbacRoleNames');
    Array.from(sel?.options || []).forEach(opt => (opt.selected = false));
    _saveRbacFilterState();
  } catch (_) { /* ignore */ }
}

function rbacPrevPage() {
  try {
    const offEl = document.getElementById('rbacRolesOffset');
    const lim = parseInt(document.getElementById('rbacRolesLimit')?.value || '100', 10) || 100;
    let off = parseInt(offEl?.value || '0', 10) || 0;
    off = Math.max(0, off - lim);
    if (offEl) offEl.value = String(off);
    _saveRbacFilterState();
    loadRbacMatrixList();
    loadRbacMatrixBoolean();
  } catch (_) { /* ignore */ }
}

function rbacNextPage() {
  try {
    const lim = parseInt(document.getElementById('rbacRolesLimit')?.value || '100', 10) || 100;
    const offEl = document.getElementById('rbacRolesOffset');
    let off = parseInt(offEl?.value || '0', 10) || 0;
    const total = RBAC_CACHE.total_roles || 0;
    off = Math.min(total ? Math.max(off + lim, 0) : off + lim, total ? Math.max(total - lim, 0) : off + lim);
    if (offEl) offEl.value = String(off);
    _saveRbacFilterState();
    loadRbacMatrixList();
    loadRbacMatrixBoolean();
  } catch (_) { /* ignore */ }
}

async function exportRbacMatrixCsv() {
  try {
    if (!RBAC_CACHE.boolean) {
      await loadRbacMatrixBoolean();
      if (!RBAC_CACHE.boolean) return;
    }
    const data = RBAC_CACHE.boolean;
    const roles = Array.isArray(data.roles) ? data.roles : [];
    let permNames = Array.isArray(data.permission_names) ? data.permission_names.slice() : [];
    const matrix = Array.isArray(data.matrix) ? data.matrix : [];
    const { category, search, pinned } = _filters();
    const visSel = document.getElementById('rbacVisibleCats');
    const vis = visSel ? Array.from(visSel.selectedOptions || []).map(o => o.value) : [];
    if (vis && vis.length && RBAC_META.permCategoryByName) {
      permNames = permNames.filter(n => vis.includes(RBAC_META.permCategoryByName[n] || ''));
    }
    if (category && RBAC_META.permCategoryByName) permNames = permNames.filter(n => (RBAC_META.permCategoryByName[n] || '') === category);
    if (search) {
      const s = search.toLowerCase();
      permNames = permNames.filter(n => n.toLowerCase().includes(s));
    }
    if (pinned.length) {
      const isPinned = (name) => pinned.some(p => name.startsWith(p));
      const left = permNames.filter(isPinned);
      const right = permNames.filter(n => !isPinned(n));
      permNames = [...left, ...right];
    }
    const nameToIndex = new Map();
    for (let i = 0; i < permNames.length; i++) nameToIndex.set(permNames[i], i);
    const csvEscape = (v) => '"' + String(v).replace(/"/g, '""') + '"';
    let csv = '';
    csv += [csvEscape('Role \\ Permission'), ...permNames.map(csvEscape)].join(',') + '\n';
    for (let r = 0; r < roles.length; r++) {
      const role = roles[r];
      const fullRow = matrix[r] || [];
      const cells = [csvEscape(role.name || '')];
      for (const pn of permNames) {
        const idx = nameToIndex.get(pn);
        const v = idx != null ? !!fullRow[idx] : false;
        cells.push(v ? '1' : '0');
      }
      csv += cells.join(',') + '\n';
    }
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'rbac_matrix.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    Toast?.success && Toast.success('Matrix CSV downloaded');
  } catch (e) { console.error(e); Toast?.error && Toast.error('Failed to export CSV'); }
}

async function exportRbacListCsv() {
  try {
    if (!RBAC_CACHE.list) {
      await loadRbacMatrixList();
      if (!RBAC_CACHE.list) return;
    }
    const data = RBAC_CACHE.list;
    const roles = Array.isArray(data.roles) ? data.roles : [];
    const perms = Array.isArray(data.permissions) ? data.permissions : [];
    const grants = new Set((data.grants || []).map(g => `${g.role_id}:${g.permission_id}`));
    if (!roles.length) { Toast?.error && Toast.error('No roles to export'); return; }
    const permIdToName = {}; for (const p of perms) permIdToName[p.id] = p.name;
    const csvEscape = (v) => '"' + String(v).replace(/"/g, '""') + '"';
    let csv = '';
    csv += [csvEscape('Role'), csvEscape('Permissions')].join(',') + '\n';
    for (const role of roles) {
      const names = [];
      for (const p of perms) { if (grants.has(`${role.id}:${p.id}`)) names.push(permIdToName[p.id] || p.name); }
      csv += [csvEscape(role.name || ''), csvEscape(names.join('; '))].join(',') + '\n';
    }
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8;' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = 'rbac_list.csv';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
    Toast?.success && Toast.success('List CSV downloaded');
  } catch (e) { console.error(e); Toast?.error && Toast.error('Failed to export list CSV'); }
}

async function copyRbacSummary() {
  try {
    if (!RBAC_CACHE.list) {
      await loadRbacMatrixList();
      if (!RBAC_CACHE.list) return;
    }
    const data = RBAC_CACHE.list;
    const roles = Array.isArray(data.roles) ? data.roles : [];
    const perms = Array.isArray(data.permissions) ? data.permissions : [];
    const grants = new Set((data.grants || []).map(g => `${g.role_id}:${g.permission_id}`));
    const permIdToName = {}; for (const p of perms) permIdToName[p.id] = p.name;
    let text = '';
    for (const role of roles) {
      const names = [];
      for (const p of perms) { if (grants.has(`${role.id}:${p.id}`)) names.push(permIdToName[p.id] || p.name); }
      text += `${role.name}: ${names.join(', ')}` + '\n';
    }
    await navigator.clipboard.writeText(text);
    Toast?.success && Toast.success('Summary copied to clipboard');
  } catch (e) { console.error(e); Toast?.error && Toast.error('Failed to copy summary'); }
}

// Rendering
function renderRbacMatrixBoolean() {
  const data = RBAC_CACHE.boolean;
  const container = document.getElementById('rbacMatrixBoolean');
  const roles = Array.isArray(data?.roles) ? data.roles : [];
  let permNames = Array.isArray(data?.permission_names) ? data.permission_names.slice() : [];
  const matrix = Array.isArray(data?.matrix) ? data.matrix : [];
  if (!roles.length || !permNames.length) { if (container) container.innerHTML = '<p>No roles or permissions.</p>'; return; }
  const { category, search, pinned } = _filters();
  try {
    const visSel = document.getElementById('rbacVisibleCats');
    const vis = visSel ? Array.from(visSel.selectedOptions || []).map(o => o.value) : [];
    if (vis && vis.length && RBAC_META.permCategoryByName) {
      permNames = permNames.filter(n => vis.includes(RBAC_META.permCategoryByName[n] || ''));
    }
  } catch (_) { /* ignore */ }
  if (category && RBAC_META.permCategoryByName) permNames = permNames.filter(n => (RBAC_META.permCategoryByName[n] || '') === category);
  if (search) { const s = search.toLowerCase(); permNames = permNames.filter(n => n.toLowerCase().includes(s)); }
  if (pinned.length) {
    const isPinned = (name) => pinned.some(p => name.startsWith(p));
    const left = permNames.filter(isPinned);
    const right = permNames.filter(n => !isPinned(n));
    permNames = [...left, ...right];
  }
  let html = '<div class="scroll-x"><table class="simple-table small-table">';
  html += '<thead><tr><th class="rbac-sticky-left header">Role \\ Permission</th>' + permNames.map(n => `<th>${_escapeHtml(n)}</th>`).join('') + '</tr></thead>';
  html += '<tbody>';
  for (let r = 0; r < roles.length; r++) {
    const role = roles[r];
    const fullRow = matrix[r] || [];
    const nameToIndex = new Map();
    const originalNames = RBAC_CACHE.boolean.permission_names;
    for (let i = 0; i < originalNames.length; i++) nameToIndex.set(originalNames[i], i);
    html += `<tr><td class="rbac-sticky-left"><strong>${_escapeHtml(role.name)}</strong> <button class="btn btn-secondary btn-compact rbac-eff" title="View effective permissions" aria-label="View effective permissions for role ${_escapeHtml(role.name)}" data-role="${role.id}">Eff</button></td>`;
    for (let c = 0; c < permNames.length; c++) {
      const idx = nameToIndex.get(permNames[c]);
      const v = idx != null ? !!fullRow[idx] : false;
      html += `<td style="text-align:center;">${v ? '✓' : ''}</td>`;
    }
    html += '</tr>';
  }
  html += '</tbody></table></div>';
  if (container) container.innerHTML = html;
}

function renderRbacMatrixList() {
  const data = RBAC_CACHE.list;
  const container = document.getElementById('rbacMatrixList');
  const roles = Array.isArray(data?.roles) ? data.roles : [];
  let perms = Array.isArray(data?.permissions) ? data.permissions.slice() : [];
  const grants = new Set((data?.grants || []).map(g => `${g.role_id}:${g.permission_id}`));
  if (!roles.length || !perms.length) { if (container) container.innerHTML = '<p>No roles or permissions.</p>'; return; }
  const { category, search, pinned } = _filters();
  if (category) perms = perms.filter(p => (p.category || '') === category);
  if (search) { const s = search.toLowerCase(); perms = perms.filter(p => p.name.toLowerCase().includes(s)); }
  if (pinned.length) {
    const isPinned = (name) => pinned.some(p => name.startsWith(p));
    const left = perms.filter(p => isPinned(p.name));
    const right = perms.filter(p => !isPinned(p.name));
    perms = [...left, ...right];
  }
  const permIdToName = {}; for (const p of perms) permIdToName[p.id] = p.name;
  let html = '<div class="scroll-y" style="max-height:360px">';
  for (const role of roles) {
    const names = [];
    for (const p of perms) { if (grants.has(`${role.id}:${p.id}`)) names.push(p.name); }
    html += `<div class="card"><div class="card-header"><strong>${_escapeHtml(role.name)}</strong> <button class="btn btn-secondary btn-compact rbac-eff" title="View effective permissions" aria-label="View effective permissions for role ${_escapeHtml(role.name)}" data-role="${role.id}">Eff</button></div>`;
    html += `<div class="card-body"><div>${names.length ? names.map(_escapeHtml).join(', ') : '<em>No permissions</em>'}</div></div></div>`;
  }
  html += '</div>';
  if (container) container.innerHTML = html;
}

// RBAC API operations
function _rbacUserId() {
  const v = parseInt(document.getElementById('rbacUserId')?.value, 10);
  if (!v) throw new Error('User ID required');
  return v;
}

async function rbacGetRoleEffective() {
  const roleIdRaw = (document.getElementById('rbacEffRoleId')?.value || '').trim();
  if (!roleIdRaw) return Toast?.error && Toast.error('Role ID is required');
  const roleId = parseInt(roleIdRaw, 10);
  if (isNaN(roleId) || roleId <= 0) return Toast?.error && Toast.error('Enter a valid Role ID');
  try {
    const data = await window.apiClient.get(`/api/v1/admin/roles/${roleId}/permissions/effective`);
    const out = document.getElementById('rbacRoleEffOut');
    if (out) out.textContent = JSON.stringify(data, null, 2);
    Toast?.success && Toast.success('Loaded role effective permissions');
  } catch (e) {
    const out = document.getElementById('rbacRoleEffOut');
    if (out) out.textContent = JSON.stringify(e.response || e, null, 2);
    Toast?.error && Toast.error('Failed to load role effective permissions');
  }
}

function rbacViewEffectiveForRole(roleId) {
  try {
    const input = document.getElementById('rbacEffRoleId');
    if (input) input.value = String(roleId);
    rbacGetRoleEffective();
    const out = document.getElementById('rbacRoleEffOut');
    if (out && out.scrollIntoView) out.scrollIntoView({ behavior: 'smooth', block: 'start' });
  } catch (_) { /* no-op */ }
}

async function rbacListRoles() {
  const res = await window.apiClient.get('/api/v1/admin/roles');
  const el = document.getElementById('rbacRolesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacCreateRole() {
  const name = (document.getElementById('rbacRoleName')?.value || '').trim();
  const description = (document.getElementById('rbacRoleDesc')?.value || '').trim() || null;
  if (!name) return Toast?.error && Toast.error('Role name required');
  const res = await window.apiClient.post('/api/v1/admin/roles', { name, description });
  Toast?.success && Toast.success('Role created');
  const el = document.getElementById('rbacRolesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacListPermissions() {
  const res = await window.apiClient.get('/api/v1/admin/permissions');
  const el = document.getElementById('rbacPermsOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacCreatePermission() {
  const name = (document.getElementById('rbacPermName')?.value || '').trim();
  const category = (document.getElementById('rbacPermCat')?.value || '').trim() || null;
  if (!name) return Toast?.error && Toast.error('Permission name required');
  const res = await window.apiClient.post('/api/v1/admin/permissions', { name, category });
  Toast?.success && Toast.success('Permission created');
  const el = document.getElementById('rbacPermsOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacGetUserRoles() {
  const uid = _rbacUserId();
  const res = await window.apiClient.get(`/api/v1/admin/users/${uid}/roles`);
  const el = document.getElementById('rbacUserRolesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacAssignRole() {
  const uid = _rbacUserId();
  const rid = parseInt(document.getElementById('rbacAssignRoleId')?.value || 'NaN', 10);
  if (!rid) return Toast?.error && Toast.error('Role ID required');
  const res = await window.apiClient.post(`/api/v1/admin/users/${uid}/roles/${rid}`, {});
  Toast?.success && Toast.success('Role assigned');
  const el = document.getElementById('rbacUserRolesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacRemoveRole() {
  const uid = _rbacUserId();
  const rid = parseInt(document.getElementById('rbacAssignRoleId')?.value || 'NaN', 10);
  if (!rid) return Toast?.error && Toast.error('Role ID required');
  const res = await window.apiClient.delete(`/api/v1/admin/users/${uid}/roles/${rid}`);
  Toast?.success && Toast.success('Role removed');
  const el = document.getElementById('rbacUserRolesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacListOverrides() {
  const uid = _rbacUserId();
  const res = await window.apiClient.get(`/api/v1/admin/users/${uid}/overrides`);
  const el = document.getElementById('rbacOverridesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacUpsertOverride() {
  const uid = _rbacUserId();
  const permField = (document.getElementById('rbacOverridePerm')?.value || '').trim();
  const effect = document.getElementById('rbacOverrideEffect')?.value;
  if (!permField) return Toast?.error && Toast.error('Permission required');
  let body = { effect };
  if (/^\d+$/.test(permField)) body.permission_id = parseInt(permField, 10);
  else body.permission_name = permField;
  const res = await window.apiClient.post(`/api/v1/admin/users/${uid}/overrides`, body);
  Toast?.success && Toast.success('Override saved');
  const el = document.getElementById('rbacOverridesOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

async function rbacGetEffectivePerms() {
  const uid = _rbacUserId();
  const res = await window.apiClient.get(`/api/v1/admin/users/${uid}/effective-permissions`);
  const el = document.getElementById('rbacUserEffPermsOut');
  if (el) el.textContent = JSON.stringify(res, null, 2);
}

// Bind events (replace inline handlers)
function bindRbacModuleHandlers() {
  // Action buttons
  document.getElementById('btnRbacCreateRole')?.addEventListener('click', rbacCreateRole);
  document.getElementById('btnRbacListRoles')?.addEventListener('click', rbacListRoles);
  document.getElementById('btnRbacCreatePermission')?.addEventListener('click', rbacCreatePermission);
  document.getElementById('btnRbacListPermissions')?.addEventListener('click', rbacListPermissions);
  document.getElementById('btnRbacGetRoleEffective')?.addEventListener('click', rbacGetRoleEffective);
  document.getElementById('btnRbacGetUserRoles')?.addEventListener('click', rbacGetUserRoles);
  document.getElementById('btnRbacGetEffectivePerms')?.addEventListener('click', rbacGetEffectivePerms);
  document.getElementById('btnRbacAssignRole')?.addEventListener('click', rbacAssignRole);
  document.getElementById('btnRbacRemoveRole')?.addEventListener('click', rbacRemoveRole);
  document.getElementById('btnRbacUpsertOverride')?.addEventListener('click', rbacUpsertOverride);
  document.getElementById('btnRbacListOverrides')?.addEventListener('click', rbacListOverrides);

  // Matrix controls (IDs already present in HTML)
  document.getElementById('btnRbacLoadList')?.addEventListener('click', loadRbacMatrixList);
  document.getElementById('btnRbacLoadBoolean')?.addEventListener('click', loadRbacMatrixBoolean);
  document.getElementById('btnRbacReload')?.addEventListener('click', reloadRbacMatrices);
  document.getElementById('btnRbacExportMatrix')?.addEventListener('click', exportRbacMatrixCsv);
  document.getElementById('btnRbacExportList')?.addEventListener('click', exportRbacListCsv);
  document.getElementById('btnRbacCopySummary')?.addEventListener('click', copyRbacSummary);
  document.getElementById('btnRbacClearFilters')?.addEventListener('click', () => {
    try {
      const ids = ['rbacMatrixCategory','rbacMatrixSearch','rbacMatrixPinned','rbacRoleSearch','rbacRolesLimit','rbacRolesOffset'];
      for (const id of ids) { const el = document.getElementById(id); if (el) el.value = (id === 'rbacRolesLimit') ? '100' : '0'; }
    } catch (_) { /* ignore */ }
    _saveRbacFilterState();
    if (RBAC_CACHE.boolean) renderRbacMatrixBoolean();
    if (RBAC_CACHE.list) renderRbacMatrixList();
  });
  document.getElementById('rbacPrevBtn')?.addEventListener('click', rbacPrevPage);
  document.getElementById('rbacNextBtn')?.addEventListener('click', rbacNextPage);

  // Filters persistence
  (function initRbacFilters() {
    _loadRbacFilterState();
    try {
      const ids = ['rbacMatrixCategory','rbacMatrixSearch','rbacMatrixPinned','rbacRoleSearch','rbacRolesLimit','rbacRolesOffset','rbacRoleNames'];
      for (const id of ids) {
        const el = document.getElementById(id);
        if (!el) continue;
        const ev = (id === 'rbacRoleNames' || id === 'rbacMatrixCategory') ? 'change' : 'input';
        el.addEventListener(ev, () => _saveRbacFilterState());
      }
      const vis = document.getElementById('rbacVisibleCats');
      if (vis) vis.addEventListener('change', () => _saveRbacFilterState());
    } catch (_) { /* ignore */ }
  })();

  // Delegated click for "Eff" buttons in matrix/list
  document.getElementById('rbacMatrixBoolean')?.addEventListener('click', (e) => {
    const t = e.target; if (t && t.classList?.contains('rbac-eff')) { const rid = t.getAttribute('data-role'); if (rid) rbacViewEffectiveForRole(parseInt(rid, 10)); }
  });
  document.getElementById('rbacMatrixList')?.addEventListener('click', (e) => {
    const t = e.target; if (t && t.classList?.contains('rbac-eff')) { const rid = t.getAttribute('data-role'); if (rid) rbacViewEffectiveForRole(parseInt(rid, 10)); }
  });

  // Ensure saved selections applied after options load
  _applySavedRoleNamesSelection();
  _applySavedVisibleCatsSelection();
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', bindRbacModuleHandlers);
  else bindRbacModuleHandlers();
}

// Expose for compatibility with other modules that call these by name
Object.assign(window, {
  RBAC_CACHE, RBAC_META,
  loadRbacMatrixList, loadRbacMatrixBoolean, reloadRbacMatrices,
  exportRbacMatrixCsv, exportRbacListCsv, copyRbacSummary,
  renderRbacMatrixBoolean, renderRbacMatrixList,
  rbacSelectAllRoleNames, rbacClearRoleNames, rbacPrevPage, rbacNextPage,
  rbacGetRoleEffective, rbacViewEffectiveForRole,
  rbacListRoles, rbacCreateRole, rbacListPermissions, rbacCreatePermission,
  rbacGetUserRoles, rbacGetEffectivePerms, rbacAssignRole, rbacRemoveRole,
  rbacListOverrides, rbacUpsertOverride,
});

export default {
  RBAC_CACHE, RBAC_META,
  loadRbacMatrixList, loadRbacMatrixBoolean, reloadRbacMatrices,
  exportRbacMatrixCsv, exportRbacListCsv, copyRbacSummary,
  renderRbacMatrixBoolean, renderRbacMatrixList,
  rbacSelectAllRoleNames, rbacClearRoleNames, rbacPrevPage, rbacNextPage,
  rbacGetRoleEffective, rbacViewEffectiveForRole,
  rbacListRoles, rbacCreateRole, rbacListPermissions, rbacCreatePermission,
  rbacGetUserRoles, rbacGetEffectivePerms, rbacAssignRole, rbacRemoveRole,
  rbacListOverrides, rbacUpsertOverride,
  bindRbacModuleHandlers,
};
