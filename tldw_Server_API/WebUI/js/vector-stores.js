// Vector Stores module (migrated from inline <script> in vector_stores_content.html)
// Uses addEventListener bindings and avoids inline event attributes.

(function () {
  function initializeVectorStoresTab() {
    const root = document.getElementById('tabVectorStores');
    if (!root || root._vsBound) return;
    root._vsBound = true;

    // Click bindings via delegation
    root.addEventListener('click', async (ev) => {
      const btn = ev.target && ev.target.closest('button[data-action]');
      if (!btn) return;
      const action = btn.getAttribute('data-action');
      try {
        if (action === 'vs-create') return vsCreate();
        if (action === 'vs-list') return vsList();
        if (action === 'vs-duplicate') return vsDuplicateSelected();
        if (action === 'vs-rename-from-panel') return vsRenameSelectedFromPanel();
        if (action === 'vs-load') return vsLoadStore();
        if (action === 'vs-save') return vsSaveStore();
        if (action === 'vs-delete') return vsDeleteStore();
        if (action === 'vs-create-from-media') return uiCreateStoreFromMedia();
        if (action === 'vs-load-stores') return uiLoadExistingStores();
        if (action === 'vs-update-from-media') return uiUpdateStoreFromMedia();
        if (action === 'vs-rename-selected') return uiRenameSelectedStore();
        if (action === 'vs-refresh-badge') return vsUpdateIndexBadgeFromId();
        if (action === 'vs-upsert') return vsUpsertVector();
        if (action === 'vs-list-vectors') return vsListVectors();
        if (action === 'vs-prev') return vsPrevPage();
        if (action === 'vs-next') return vsNextPage();
        if (action === 'vs-query') return vsQuery();
        if (action === 'vs-bulk-upsert') return vsBulkUpsert();
        if (action === 'vs-delete-vector') return vsDeleteVector();
        if (action === 'vs-delete-by-filter') return vsDeleteByFilter();
        if (action === 'vs-admin-index-info') return vsAdminIndexInfo();
        if (action === 'vs-admin-set-ef') return vsAdminSetEfSearch();
        if (action === 'vs-admin-rebuild') return vsAdminRebuildIndex();
        if (action === 'vb-load-users') return vbLoadUsers();
        if (action === 'vb-refresh') return vbList();
      } catch (e) {
        console.error('Vector stores action failed:', action, e);
      }
    });

    // Blur bindings for badges
    const bindBlur = (id) => {
      const el = document.getElementById(id);
      if (el && !el._vsBlur) { el._vsBlur = true; el.addEventListener('blur', () => { try { vsUpdateIndexBadgeFromId(); } catch {} }); }
    };
    bindBlur('vs_id');
    bindBlur('vs_admin_id');

    // Optional initial list to populate selects
    try { uiLoadExistingStores(); } catch {}
  }
  async function vsCreate() {
    const name = document.getElementById('vs_name')?.value.trim();
    const dim = parseInt(document.getElementById('vs_dimensions')?.value || '1536');
    const model = document.getElementById('vs_model')?.value.trim();
    const body = { dimensions: dim };
    if (name) body.name = name;
    if (model) body.embedding_model = model;
    const res = await apiClient.post('/api/v1/vector_stores', body);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  async function vsList() {
    const res = await apiClient.get('/api/v1/vector_stores');
    const ul = document.getElementById('vs_list');
    if (!ul) return;
    ul.innerHTML = '';
    (res.data || []).forEach((s) => {
      const li = document.createElement('li');
      li.setAttribute('tabindex', '0');
      const nameSpan = document.createElement('span');
      // Safely compose: name (code(id)) - dim=dimensions
      const nameText = document.createTextNode(String(s.name || ''));
      const openParen = document.createTextNode(' (');
      const codeEl = document.createElement('code');
      codeEl.textContent = String(s.id || '');
      const closeText = document.createTextNode(`) - dim=${String(s.dimensions)}`);
      nameSpan.appendChild(nameText);
      nameSpan.appendChild(openParen);
      nameSpan.appendChild(codeEl);
      nameSpan.appendChild(closeText);
      li.appendChild(nameSpan);
      const space = document.createTextNode(' ');
      li.appendChild(space);
      // Quick copy ID button
      const copyBtn = document.createElement('button');
      copyBtn.className = 'btn-small';
      copyBtn.title = 'Copy Store ID';
      copyBtn.textContent = 'Copy ID';
      copyBtn.addEventListener('click', async (ev) => {
        ev.stopPropagation();
        const ok = await Utils.copyToClipboard(String(s.id || ''));
        if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied store id');
      });
      li.appendChild(copyBtn);
      const btnRename = document.createElement('button');
      btnRename.className = 'btn-small';
      btnRename.textContent = 'Rename';
      btnRename.addEventListener('click', (ev) => { ev.stopPropagation(); vsRenameQuick(s.id); });
      li.appendChild(btnRename);
      const btnSelect = document.createElement('button');
      btnSelect.className = 'btn-small';
      btnSelect.style.marginLeft = '6px';
      btnSelect.textContent = 'Select';
      btnSelect.addEventListener('click', (ev) => { ev.stopPropagation(); vsSelect(s.id, s.name || ''); });
      li.appendChild(btnSelect);

      // Row badge and refresh
      try {
        const rowBadge = document.createElement('span');
        rowBadge.id = `vs_row_badge_${s.id}`;
        rowBadge.className = 'vs-row-badge';
        rowBadge.style.cssText = 'margin-left:6px; padding:2px 6px; border-radius:10px; font-size:12px; background:#eee; color:#444;';
        rowBadge.textContent = 'index: …';
        li.appendChild(rowBadge);
        const refreshBtn = document.createElement('button');
        refreshBtn.className = 'btn-small';
        refreshBtn.style.marginLeft = '6px';
        refreshBtn.textContent = 'Refresh';
        refreshBtn.addEventListener('click', (ev) => { ev.stopPropagation(); vsRefreshRowBadge(s.id); });
        li.appendChild(refreshBtn);
        li.addEventListener('mouseenter', () => {
          const badgeEl = document.getElementById(`vs_row_badge_${s.id}`);
          if (badgeEl && !badgeEl.dataset.loaded) {
            vsFetchIndexBadgeForStore(s.id, badgeEl).catch(() => {});
          }
        }, { once: true });
      } catch {}

      li.style.cursor = 'pointer';
      li.addEventListener('click', () => {
        const idEl = document.getElementById('vs_edit_id'); if (idEl) idEl.value = s.id;
        const nmEl = document.getElementById('vs_edit_name'); if (nmEl) nmEl.value = s.name || '';
        const mdEl = document.getElementById('vs_edit_metadata'); if (mdEl) mdEl.value = JSON.stringify(s.metadata || {}, null, 2);
        const id2 = document.getElementById('vs_id'); if (id2) id2.value = s.id;
      });
      // Keyboard shortcuts on focused row
      li.addEventListener('keydown', async (e) => {
        if (e.key === 'Enter') { e.preventDefault(); vsSelect(s.id, s.name || ''); }
        if (e.key.toLowerCase() === 'c') { e.preventDefault(); const ok = await Utils.copyToClipboard(String(s.id || '')); if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied store id'); }
        if (e.key.toLowerCase() === 'n') { e.preventDefault(); const ok = await Utils.copyToClipboard(String(s.name || '')); if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied store name'); }
      });
      // Context menu for copy actions
      li.addEventListener('contextmenu', (e) => {
        e.preventDefault();
        showVsContextMenu(e.pageX, e.pageY, s);
      });
      ul.appendChild(li);
    });
  }

  // Minimal context menu for vector stores list
  function ensureVsContextMenu() {
    let menu = document.getElementById('vs_context_menu');
    if (menu) return menu;
    menu = document.createElement('div');
    menu.id = 'vs_context_menu';
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-hidden', 'true');
    menu.style.cssText = 'position:absolute; z-index:2000; background: var(--color-surface); border:1px solid var(--color-border); border-radius:6px; box-shadow: var(--shadow-md); display:none; min-width:160px;';
    const mkItem = (label, handler) => {
      const it = document.createElement('div');
      it.textContent = label;
      it.style.cssText = 'padding:8px 12px; cursor:pointer;';
      it.addEventListener('mouseenter', () => it.style.background = 'var(--color-surface-alt)');
      it.addEventListener('mouseleave', () => it.style.background = 'transparent');
      it.addEventListener('click', handler);
      return it;
    };
    // Items are created dynamically on show to capture current store
    document.body.appendChild(menu);
    // Hide on outside click
    document.addEventListener('click', () => { menu.style.display = 'none'; });
    window.addEventListener('resize', () => { menu.style.display = 'none'; });
    window.addEventListener('scroll', () => { menu.style.display = 'none'; }, true);
    return menu;
  }

  function showVsContextMenu(x, y, store) {
    const menu = ensureVsContextMenu();
    menu.innerHTML = '';
    const add = (label, fn) => menu.appendChild((() => { const it = document.createElement('div'); it.textContent = label; it.setAttribute('role','menuitem'); it.tabIndex = 0; it.style.cssText = 'padding:8px 12px; cursor:pointer;'; it.addEventListener('mouseenter', () => it.style.background = 'var(--color-surface-alt)'); it.addEventListener('mouseleave', () => it.style.background = 'transparent'); it.addEventListener('click', async (e) => { e.stopPropagation(); hideVsContextMenu(); await fn(); }); it.addEventListener('keydown', async (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); hideVsContextMenu(); await fn(); } }); return it; })());
    add('Copy Store ID', async () => { const ok = await Utils.copyToClipboard(String(store.id || '')); if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied store id'); });
    add('Copy Name', async () => { const ok = await Utils.copyToClipboard(String(store.name || '')); if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied store name'); });
    add('Copy JSON', async () => { const ok = await Utils.copyToClipboard(JSON.stringify(store, null, 2)); if (ok && typeof Toast !== 'undefined' && Toast) Toast.success('Copied store JSON'); });
    menu.style.left = x + 'px';
    menu.style.top = y + 'px';
    menu.style.display = 'block';
    menu.setAttribute('aria-hidden','false');
  }

  function hideVsContextMenu() {
    const menu = document.getElementById('vs_context_menu');
    if (!menu) return;
    menu.style.display = 'none';
    menu.setAttribute('aria-hidden','true');
  }

  // Close on Escape
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') hideVsContextMenu(); });

  async function vsLoadStore() {
    const id = document.getElementById('vs_edit_id')?.value.trim();
    if (!id) { alert('Enter store id'); return; }
    const res = await apiClient.get(`/api/v1/vector_stores/${encodeURIComponent(id)}`);
    const nm = document.getElementById('vs_edit_name'); if (nm) nm.value = res.name || '';
    const md = document.getElementById('vs_edit_metadata'); if (md) md.value = JSON.stringify(res.metadata || {}, null, 2);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function vsSaveStore() {
    const id = document.getElementById('vs_edit_id')?.value.trim();
    if (!id) { alert('Enter store id'); return; }
    let md = {};
    const name = document.getElementById('vs_edit_name')?.value.trim();
    const mdText = document.getElementById('vs_edit_metadata')?.value.trim();
    if (mdText) { try { md = JSON.parse(mdText); } catch (e) { alert('Invalid metadata JSON'); return; } }
    const payload = {}; if (name) payload.name = name; payload.metadata = md;
    const res = await apiClient.patch(`/api/v1/vector_stores/${encodeURIComponent(id)}`, payload);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  async function vsDeleteStore() {
    const id = document.getElementById('vs_edit_id')?.value.trim();
    if (!id) { alert('Enter store id'); return; }
    if (!confirm('Delete this vector store?')) return;
    const res = await apiClient.delete(`/api/v1/vector_stores/${encodeURIComponent(id)}`);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  async function vsUpsertVector() {
    const id = document.getElementById('vs_id')?.value.trim();
    if (!id) { alert('Enter vector store id'); return; }
    const text = document.getElementById('vec_text')?.value.trim();
    const valsStr = document.getElementById('vec_values')?.value.trim();
    let record = {};
    if (text) record.content = text;
    else if (valsStr) { try { record.values = JSON.parse(valsStr); } catch (e) { alert('Invalid values JSON'); return; } }
    else { alert('Provide content or values'); return; }
    const res = await apiClient.post(`/api/v1/vector_stores/${encodeURIComponent(id)}/vectors`, { records: [record] });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function vsListVectors() {
    const id = document.getElementById('vs_id')?.value.trim();
    if (!id) { alert('Enter vector store id'); return; }
    const limit = parseInt(document.getElementById('vs_limit')?.value || '50');
    const offset = window.__vs_offset || 0;
    const query = { limit, offset };
    const filterText = (document.getElementById('vs_filter')?.value || '').trim();
    if (filterText) { try { query.filter = JSON.parse(filterText); } catch (e) { alert('Invalid filter JSON'); return; } }
    const orderBy = (document.getElementById('vs_order_by')?.value || '').trim();
    const orderDir = (document.getElementById('vs_order_dir')?.value || '').trim();
    if (orderBy) query.order_by = orderBy;
    if (orderDir) query.order_dir = orderDir;
    const res = await apiClient.get(`/api/v1/vector_stores/${encodeURIComponent(id)}/vectors`, query);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    const items = (res.data || []);
    renderVectorList(items, id);
  }

  function renderVectorList(items, storeId) {
    const container = document.getElementById('vs_vector_list');
    if (!container) return;
    if (!items.length) { container.innerHTML = '<div class="muted">No vectors on this page.</div>'; return; }
    container.innerHTML = '';
    const wrapper = document.createElement('div');
    wrapper.style.marginTop = '8px';
    items.forEach((it) => {
      const row = document.createElement('div');
      row.className = 'list-row';
      row.style.cssText = 'display:flex; gap:8px; align-items:center; border-bottom:1px solid var(--color-border); padding:6px 0;';
      const code = document.createElement('code');
      code.style.cssText = 'flex:0 0 260px; overflow:hidden; text-overflow:ellipsis;';
      code.textContent = it.id;
      const content = document.createElement('span');
      content.style.cssText = 'flex:1 1 auto; color: var(--color-text-muted);';
      // Avoid XSS by assigning plain text instead of HTML
      content.textContent = (it.content || '').slice(0, 100);
      const md = document.createElement('span');
      md.style.cssText = 'flex:0 0 200px; color: var(--color-text-muted);';
      md.textContent = (it.metadata && Object.keys(it.metadata).length) ? JSON.stringify(it.metadata) : '';
      const del = document.createElement('button');
      del.className = 'btn-small btn-danger';
      del.textContent = 'Delete';
      del.addEventListener('click', async () => {
        await vsDeleteVectorInline(encodeURIComponent(storeId), encodeURIComponent(it.id));
      });
      row.appendChild(code); row.appendChild(content); row.appendChild(md); row.appendChild(del);
      wrapper.appendChild(row);
    });
    container.appendChild(wrapper);
  }

  async function vsDeleteVectorInline(encStoreId, encVecId) {
    const storeId = decodeURIComponent(encStoreId);
    const vecId = decodeURIComponent(encVecId);
    if (!confirm(`Delete vector ${vecId}?`)) return;
    const res = await apiClient.delete(`/api/v1/vector_stores/${encodeURIComponent(storeId)}/vectors/${encodeURIComponent(vecId)}`);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsListVectors();
  }

  async function vsPrevPage() {
    const current = window.__vs_offset || 0;
    const limit = parseInt(document.getElementById('vs_limit')?.value || '50');
    window.__vs_offset = Math.max(0, current - limit);
    await vsListVectors();
  }

  async function vsNextPage() {
    const limit = parseInt(document.getElementById('vs_limit')?.value || '50');
    const offset = window.__vs_offset || 0;
    window.__vs_offset = offset + limit;
    await vsListVectors();
  }

  async function vsQuery() {
    await vsListVectors();
  }

  async function vsAdminIndexInfo() {
    const id = document.getElementById('vs_admin_id')?.value.trim();
    if (!id) { alert('Enter store id'); return; }
    const res = await apiClient.get(`/api/v1/vector_stores/${encodeURIComponent(id)}/admin/index`);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    // Update badge in admin row
    await vsFetchIndexBadgeForStore(id, document.getElementById('vs_row_badge_' + id));
  }

  async function vsAdminSetEfSearch() {
    const id = document.getElementById('vs_admin_id')?.value.trim();
    const ef = parseInt(document.getElementById('vs_ef_search')?.value || '64');
    if (!id) { alert('Enter store id'); return; }
    const res = await apiClient.patch(`/api/v1/vector_stores/${encodeURIComponent(id)}/admin/index`, { ef_search: ef });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function vsAdminRebuildIndex() {
    const id = document.getElementById('vs_admin_id')?.value.trim();
    const type = document.getElementById('vs_index_type')?.value;
    const metric = document.getElementById('vs_index_metric')?.value;
    const m = parseInt(document.getElementById('vs_index_m')?.value || '16');
    const efc = parseInt(document.getElementById('vs_index_efc')?.value || '200');
    const lists = parseInt(document.getElementById('vs_index_lists')?.value || '100');
    if (!id) { alert('Enter store id'); return; }
    const payload = { type, metric, m, ef_construction: efc, lists };
    const res = await apiClient.post(`/api/v1/vector_stores/${encodeURIComponent(id)}/admin/index/rebuild`, payload);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  async function vsUpdateIndexBadgeFromId() {
    const id = document.getElementById('vs_admin_id')?.value.trim();
    if (!id) return;
    const badge = document.getElementById(`vs_row_badge_${id}`);
    await vsFetchIndexBadgeForStore(id, badge);
  }

  function vsRenderIndexBadge(info) {
    if (!info) return 'index: -';
    if (info.type === 'hnsw') return `index: hnsw/${info.metric || '-'}`;
    if (info.type === 'ivfflat') return `index: ivfflat/${info.metric || '-'}`;
    if (info.type === 'none') return 'index: none';
    return `index: ${info.type || '-'}`;
  }

  async function vsFetchIndexBadgeForStore(storeId, badgeEl) {
    if (!badgeEl) return;
    try {
      const info = await apiClient.get(`/api/v1/vector_stores/${encodeURIComponent(storeId)}/admin/index`);
      badgeEl.textContent = vsRenderIndexBadge(info);
      badgeEl.dataset.loaded = '1';
    } catch (e) {
      badgeEl.textContent = 'index: ?';
    }
  }

  function vsRefreshRowBadge(storeId) {
    const badge = document.getElementById(`vs_row_badge_${storeId}`);
    if (badge) {
      badge.dataset.loaded = '';
      badge.textContent = 'index: …';
      vsFetchIndexBadgeForStore(storeId, badge).catch(() => {});
    }
  }

  async function vsBulkUpsert() {
    const id = document.getElementById('vs_id')?.value.trim();
    if (!id) { alert('Enter vector store id'); return; }
    const text = document.getElementById('vs_bulk')?.value || '';
    let records = [];
    try {
      if (text.trim().startsWith('[')) {
        records = JSON.parse(text);
      } else {
        records = text.split(/\n+/).map((line) => ({ content: line.trim() })).filter((r) => r.content);
      }
    } catch (e) { alert('Invalid bulk payload'); return; }
    const res = await apiClient.post(`/api/v1/vector_stores/${encodeURIComponent(id)}/vectors`, { records });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function vsDeleteVector() {
    const id = document.getElementById('vs_id')?.value.trim();
    const vec = document.getElementById('vec_delete_id')?.value.trim();
    if (!id || !vec) { alert('Enter store and vector id'); return; }
    const res = await apiClient.delete(`/api/v1/vector_stores/${encodeURIComponent(id)}/vectors/${encodeURIComponent(vec)}`);
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function vsDeleteByFilter() {
    const id = document.getElementById('vs_id')?.value.trim();
    const filt = document.getElementById('vs_delete_filter')?.value.trim();
    if (!id || !filt) { alert('Enter store id and filter'); return; }
    let filter = {};
    try { filter = JSON.parse(filt); } catch (e) { alert('Invalid filter JSON'); return; }
    const res = await apiClient.delete(`/api/v1/vector_stores/${encodeURIComponent(id)}/vectors`, { filter });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function vsRenameQuick(id) {
    const name = prompt('New name for store', '');
    if (name === null) return;
    const res = await apiClient.patch(`/api/v1/vector_stores/${encodeURIComponent(id)}`, { name });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  function vsSelect(id, name) {
    const idInput = document.getElementById('vs_id'); if (idInput) idInput.value = id;
    const existingSel = document.getElementById('vs_media_existing_store_select');
    const existingId = document.getElementById('vs_media_existing_store_id');
    if (existingSel) existingSel.value = id;
    if (existingId) existingId.value = id;
    const dupName = document.getElementById('vs_duplicate_name');
    if (dupName) dupName.value = `${name}-copy`;
  }

  async function vsDuplicateSelected() {
    const id = document.getElementById('vs_id')?.value.trim();
    if (!id) { alert('Select a store first (click on list item or use Select button)'); return; }
    const new_name = document.getElementById('vs_duplicate_name')?.value.trim();
    if (!new_name) { alert('Enter a name for the duplicate'); return; }
    const res = await apiClient.post(`/api/v1/vector_stores/${encodeURIComponent(id)}/duplicate`, { new_name });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  async function vsRenameSelectedFromPanel() {
    const id = document.getElementById('vs_id')?.value.trim();
    if (!id) { alert('Select a store first'); return; }
    const new_name = document.getElementById('vs_rename_name')?.value.trim();
    if (!new_name) { alert('Enter a new name'); return; }
    const res = await apiClient.patch(`/api/v1/vector_stores/${encodeURIComponent(id)}`, { name: new_name });
    const out = document.getElementById('vs_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    await vsList();
  }

  async function uiCreateStoreFromMedia() {
    const name = document.getElementById('vs_media_store_name')?.value.trim();
    if (!name) { alert('Enter store name'); return; }
    const dimensions = parseInt(document.getElementById('vs_media_dimensions')?.value || '1536');
    const model = document.getElementById('vs_media_model')?.value.trim();
    const ids = (document.getElementById('vs_media_ids')?.value || '').split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
    const kws = (document.getElementById('vs_media_keywords')?.value || '').split(',').map(s => s.trim()).filter(Boolean);
    const kwMatch = (document.getElementById('vs_media_keyword_match')?.value || 'any');
    const chunk_size = parseInt(document.getElementById('vs_media_chunk_size')?.value || '500');
    const chunk_overlap = parseInt(document.getElementById('vs_media_chunk_overlap')?.value || '100');
    const chunk_method = (document.getElementById('vs_media_chunk_method')?.value || 'words');
    const use_existing_embeddings = document.getElementById('vs_media_use_existing')?.checked || false;
    const language = (document.getElementById('vs_media_language')?.value || '').trim() || undefined;
    const body = { store_name: name, dimensions, embedding_model: model || undefined, media_ids: ids.length ? ids : undefined, keywords: kws.length ? kws : undefined, keyword_match: kwMatch, chunk_size, chunk_overlap, chunk_method, language, use_existing_embeddings };
    const res = await apiClient.post('/api/v1/vector_stores/create_from_media', body);
    const out = document.getElementById('vs_media_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function uiUpdateStoreFromMedia() {
    let existing = document.getElementById('vs_media_existing_store_id')?.value.trim();
    const sel = document.getElementById('vs_media_existing_store_select');
    if (!existing && sel && sel.value) existing = sel.value;
    if (!existing) { alert('Enter existing store id'); return; }
    const name = document.getElementById('vs_media_store_name')?.value.trim();
    const dimensions = parseInt(document.getElementById('vs_media_dimensions')?.value || '1536');
    const model = document.getElementById('vs_media_model')?.value.trim();
    const ids = (document.getElementById('vs_media_ids')?.value || '').split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
    const kws = (document.getElementById('vs_media_keywords')?.value || '').split(',').map(s => s.trim()).filter(Boolean);
    const kwMatch = (document.getElementById('vs_media_keyword_match')?.value || 'any');
    const chunk_size = parseInt(document.getElementById('vs_media_chunk_size')?.value || '500');
    const chunk_overlap = parseInt(document.getElementById('vs_media_chunk_overlap')?.value || '100');
    const chunk_method = (document.getElementById('vs_media_chunk_method')?.value || 'words');
    const use_existing_embeddings = document.getElementById('vs_media_use_existing')?.checked || false;
    const language = (document.getElementById('vs_media_language')?.value || '').trim() || undefined;
    const body = { store_name: name || existing, dimensions, embedding_model: model || undefined, media_ids: ids.length ? ids : undefined, keywords: kws.length ? kws : undefined, keyword_match: kwMatch, chunk_size, chunk_overlap, chunk_method, language, use_existing_embeddings, update_existing_store_id: existing };
    const res = await apiClient.post('/api/v1/vector_stores/create_from_media', body);
    const out = document.getElementById('vs_media_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
  }

  async function uiLoadExistingStores() {
    const sel = document.getElementById('vs_media_existing_store_select');
    if (!sel) return;
    const res = await apiClient.get('/api/v1/vector_stores');
    const list = (res.data || []);
    // Rebuild options safely without injecting HTML
    sel.innerHTML = '';
    const def = document.createElement('option');
    def.value = '';
    def.textContent = '-- Select Existing Store --';
    sel.appendChild(def);
    list.forEach((s) => {
      const opt = document.createElement('option');
      opt.value = String(s.id || '');
      opt.textContent = `${String(s.name || '')} (${String(s.id || '')})`;
      sel.appendChild(opt);
    });
  }

  async function uiRenameSelectedStore() {
    let existing = document.getElementById('vs_media_existing_store_id')?.value.trim();
    const sel = document.getElementById('vs_media_existing_store_select');
    if (!existing && sel && sel.value) existing = sel.value;
    if (!existing) { alert('Select existing store'); return; }
    const newName = (document.getElementById('vs_media_store_name')?.value || '').trim();
    if (!newName) { alert('Enter a new store name in the Store Name field'); return; }
    const res = await apiClient.patch(`/api/v1/vector_stores/${encodeURIComponent(existing)}`, { name: newName });
    alert('Renamed successfully');
    try { await uiLoadExistingStores(); } catch (e) {}
  }

  async function vbList() {
    const status = document.getElementById('vb_status')?.value;
    const limit = parseInt(document.getElementById('vb_limit')?.value || '50');
    const offset = parseInt(document.getElementById('vb_offset')?.value || '0');
    const user = document.getElementById('vb_user')?.value.trim();
    const query = {};
    if (status) query.status = status;
    query.limit = limit; query.offset = offset;
    const res = await apiClient.get('/api/v1/vector_stores/batches', query);
    const out = document.getElementById('vb_result'); if (out) out.textContent = JSON.stringify(res, null, 2);
    const list = document.getElementById('vb_list');
    const rows = (res.data || []).map(r => {
      const safeError = r.error ? Utils.escapeHtml(String(r.error).slice(0, 120)) : '';
      const err = safeError ? `<span style='color:var(--color-danger-emphasis)'>${safeError}</span>` : '';
      const safeId = Utils.escapeHtml(String(r.id ?? '').slice(0, 120));
      const safeStoreId = Utils.escapeHtml(String(r.store_id ?? '').slice(0, 120));
      const safeStatus = Utils.escapeHtml(String(r.status ?? '').slice(0, 120));
      const safeUpserted = Utils.escapeHtml(String(r.upserted ?? '').slice(0, 120));
      return `<div class='list-row' style='display:flex; gap:8px; border-bottom:1px solid var(--color-border); padding:6px 0;'>
      <code style='flex:0 0 220px;'>${safeId}</code>
      <code style='flex:0 0 220px;'>${safeStoreId}</code>
      <span style='flex:0 0 80px;'>${safeStatus}</span>
      <span style='flex:0 0 80px;'>${safeUpserted}</span>
      <span style='flex:1 1 auto; color:var(--color-text-muted);'>${err}</span>
    </div>`;
    }).join('');
    if (list) list.innerHTML = `<div style='margin-top:8px;'>${rows || '<div class="muted">No batches found</div>'}</div>`;
  }

  async function vbLoadUsers() {
    const info = document.getElementById('vb_users_info');
    const sel = document.getElementById('vb_user_select');
    try {
      const res = await apiClient.get('/api/v1/vector_stores/admin/users');
      const rows = res.data || [];
      if (!rows.length) { if (info) info.textContent = 'No users found.'; return; }
      if (sel) {
        // Safely rebuild user options without injecting raw HTML
        sel.innerHTML = '';
        const def = document.createElement('option');
        def.value = '';
        def.textContent = '-- Select User --';
        sel.appendChild(def);
        rows.forEach((u) => {
          const opt = document.createElement('option');
          opt.value = String(u.user_id ?? '');
          const stores = String(u.store_count ?? 0);
          const batches = String(u.batch_count ?? 0);
          opt.textContent = `${String(u.user_id ?? '')} (stores: ${stores}, batches: ${batches})`;
          sel.appendChild(opt);
        });
      }
      if (sel) sel.addEventListener('change', () => {
        const val = sel.value; const vbUser = document.getElementById('vb_user'); if (vbUser) vbUser.value = val;
      });
      if (info) info.textContent = `Loaded ${rows.length} users.`;
    } catch (e) { if (info) info.textContent = `Failed to load users: ${e.message || e}`; }
  }

  // Expose globals for existing buttons (migrated by main.js without eval)
  Object.assign(window, {
    vsCreate, vsList, vsLoadStore, vsSaveStore, vsDeleteStore, vsUpsertVector,
    vsListVectors, vsPrevPage, vsNextPage, vsQuery, vsBulkUpsert, vsDeleteVector,
    vsDeleteByFilter, vsAdminIndexInfo, vsAdminSetEfSearch, vsAdminRebuildIndex,
    vsUpdateIndexBadgeFromId, vsRenderIndexBadge, vsFetchIndexBadgeForStore,
    vsRefreshRowBadge, vsRenameQuick, vsSelect, vsDuplicateSelected,
    vsRenameSelectedFromPanel, uiCreateStoreFromMedia, uiUpdateStoreFromMedia,
    uiLoadExistingStores, uiRenameSelectedStore, vbList, vbLoadUsers,
    initializeVectorStoresTab,
  });
})();
