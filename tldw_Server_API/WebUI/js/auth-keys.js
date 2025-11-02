// auth-keys.js
// Manage current user's API keys without inline handlers; safe DOM rendering.

export async function listMyApiKeys() {
  try {
    const items = await window.apiClient.get('/api/v1/users/api-keys');
    renderKeys(Array.isArray(items) ? items : []);
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = 'Loaded';
  } catch (e) {
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to list API keys');
  }
}

export async function createMyApiKey() {
  try {
    const name = document.getElementById('apiKey_name')?.value || null;
    const scope = document.getElementById('apiKey_scope')?.value || 'write';
    const daysStr = document.getElementById('apiKey_expiry')?.value || '365';
    const expires_in_days = parseInt(daysStr, 10);
    const payload = { name, scope, expires_in_days };
    const res = await window.apiClient.post('/api/v1/users/api-keys', payload);
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(res || {}, null, 2);
    Toast.success('API key created. Copy it now; it is shown only once.');
    await listMyApiKeys();
  } catch (e) {
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to create API key');
  }
}

export async function rotateMyApiKey(id) {
  try {
    const res = await window.apiClient.post(`/api/v1/users/api-keys/${id}/rotate`, { expires_in_days: 365 });
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(res || {}, null, 2);
    Toast.success('API key rotated. Copy the new key now.');
    await listMyApiKeys();
  } catch (e) {
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to rotate API key');
  }
}

export async function revokeMyApiKey(id) {
  try {
    const res = await window.apiClient.delete(`/api/v1/users/api-keys/${id}`);
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(res || {}, null, 2);
    Toast.success('API key revoked');
    await listMyApiKeys();
  } catch (e) {
    const pre = document.getElementById('authApiKeys_response');
    if (pre) pre.textContent = JSON.stringify(e.response || e, null, 2);
    Toast.error('Failed to revoke API key');
  }
}

export function renderKeys(items) {
  const container = document.getElementById('authApiKeys_list');
  if (!container) return;
  container.innerHTML = '';

  if (!items.length) {
    const p = document.createElement('p');
    p.textContent = 'No API keys found.';
    container.appendChild(p);
    return;
  }

  const table = document.createElement('table');
  table.className = 'simple-table';
  const thead = document.createElement('thead');
  const trh = document.createElement('tr');
  ['ID','Name','Scope','Status','Created','Expires','Usage','Actions'].forEach(h => {
    const th = document.createElement('th'); th.textContent = h; trh.appendChild(th);
  });
  thead.appendChild(trh);
  table.appendChild(thead);

  const tbody = document.createElement('tbody');
  for (const k of items) {
    const tr = document.createElement('tr');
    const cells = [
      String(k.id ?? ''),
      String(k.name ?? ''),
      String(k.scope ?? ''),
      String(k.status ?? ''),
      String(k.created_at ?? ''),
      String(k.expires_at ?? ''),
      String(k.usage_count ?? 0),
    ];
    for (const txt of cells) { const td = document.createElement('td'); td.textContent = txt; tr.appendChild(td); }

    const actionsTd = document.createElement('td');
    const btnRotate = document.createElement('button');
    btnRotate.className = 'btn btn-sm btn-secondary btn-rotate';
    btnRotate.textContent = 'Rotate';
    btnRotate.dataset.id = String(k.id);
    const btnRevoke = document.createElement('button');
    btnRevoke.className = 'btn btn-sm btn-danger btn-revoke';
    btnRevoke.textContent = 'Revoke';
    btnRevoke.dataset.id = String(k.id);
    actionsTd.appendChild(btnRotate);
    actionsTd.appendChild(btnRevoke);
    tr.appendChild(actionsTd);

    tbody.appendChild(tr);
  }
  table.appendChild(tbody);
  container.appendChild(table);
}

function bindAuthKeys() {
  const listBtn = document.getElementById('btnMyApiKeysList');
  if (listBtn) listBtn.addEventListener('click', listMyApiKeys);
  const createBtn = document.getElementById('btnMyApiKeyCreate');
  if (createBtn) createBtn.addEventListener('click', createMyApiKey);

  const container = document.getElementById('authApiKeys_list');
  if (container) {
    container.addEventListener('click', (ev) => {
      const t = ev.target;
      if (!(t instanceof HTMLElement)) return;
      if (t.classList.contains('btn-rotate')) {
        const id = t.dataset.id; if (id) rotateMyApiKey(id);
      } else if (t.classList.contains('btn-revoke')) {
        const id = t.dataset.id; if (id) revokeMyApiKey(id);
      }
    });
  }
}

if (typeof document !== 'undefined') {
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', bindAuthKeys);
  } else {
    bindAuthKeys();
  }
}

export default { listMyApiKeys, createMyApiKey, rotateMyApiKey, revokeMyApiKey, renderKeys, bindAuthKeys };
