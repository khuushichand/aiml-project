/**
 * Chat Dictionaries UI
 */

const DictionariesUI = (() => {
  let selected = null; // { id, name, is_active, entry_count, ... }

  function el(id) { return document.getElementById(id); }

  function renderDictionaries(list) {
    const container = el('dictsList');
    if (!container) return;
    if (!Array.isArray(list) || list.length === 0) {
      container.innerHTML = '<div class="muted">No dictionaries found.</div>';
      return;
    }
    const rows = list.map(d => {
      const activeBadge = d.is_active ? '<span class="badge success">active</span>' : '<span class="badge">inactive</span>';
      return `<div class="list-item" data-id="${d.id}" style="display:flex; justify-content:space-between; align-items:center; padding:6px; border-bottom:1px solid var(--color-border); cursor:pointer;">
        <div>
          <div><strong>${escapeHtml(d.name)}</strong> ${activeBadge}</div>
          <div class="muted" style="font-size:12px;">${escapeHtml(d.description || '')}</div>
        </div>
        <div class="muted" style="font-size:12px;">entries: ${d.entry_count ?? '-'}</div>
      </div>`;
    }).join('');
    container.innerHTML = rows;
    // click handlers
    container.querySelectorAll('.list-item').forEach(item => {
      item.addEventListener('click', async () => {
        const id = parseInt(item.getAttribute('data-id'));
        const dict = list.find(x => x.id === id);
        if (dict) {
          selected = dict;
          updateSelectedMeta();
          await refreshEntries();
        }
      });
    });
  }

  function updateSelectedMeta() {
    const nameSpan = el('selectedDictName');
    const meta = el('selectedDictMeta');
    const toggleBtn = el('dictToggleActiveBtn');
    const delBtn = el('dictDeleteBtn');
    if (!selected) {
      if (nameSpan) nameSpan.textContent = 'None';
      if (meta) meta.textContent = '';
      if (toggleBtn) toggleBtn.disabled = true;
      if (delBtn) delBtn.disabled = true;
      return;
    }
    if (nameSpan) nameSpan.textContent = `${selected.name} (#${selected.id})`;
    if (meta) meta.textContent = `Active: ${!!selected.is_active} • Entries: ${selected.entry_count ?? '-'} • Updated: ${selected.updated_at || 'n/a'}`;
    if (toggleBtn) toggleBtn.disabled = false;
    if (delBtn) delBtn.disabled = false;
  }

  async function refreshDictionaries() {
    try {
      const data = await apiClient.get('/api/v1/chat/dictionaries', { include_inactive: true });
      const list = data?.dictionaries || [];
      renderDictionaries(list);
      // Update selected if exists
      if (selected) {
        const fresh = list.find(d => d.id === selected.id);
        if (fresh) { selected = fresh; updateSelectedMeta(); }
      }
    } catch (e) {
      console.error('Failed to load dictionaries:', e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to load dictionaries');
    }
  }

  async function createDictionary() {
    const name = el('dictCreate_name')?.value?.trim();
    const description = el('dictCreate_description')?.value?.trim();
    const status = el('dictCreate_status');
    if (!name) { alert('Enter a name'); return; }
    try {
      const res = await apiClient.post('/api/v1/chat/dictionaries', { name, description });
      if (status) status.textContent = `Created: ${res?.name || name} (#${res?.id})`;
      await refreshDictionaries();
      if (typeof Toast !== 'undefined') Toast.success('Dictionary created');
    } catch (e) {
      if (status) status.textContent = `Error: ${e?.message || e}`;
    }
  }

  async function toggleActive() {
    if (!selected) return;
    const desired = !selected.is_active;
    try {
      const res = await apiClient.put(`/api/v1/chat/dictionaries/${selected.id}`, { is_active: desired });
      selected = res;
      updateSelectedMeta();
      await refreshDictionaries();
      if (typeof Toast !== 'undefined') Toast.success(`Dictionary ${desired ? 'activated' : 'deactivated'}`);
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to toggle active');
    }
  }

  async function deleteDictionary() {
    if (!selected) return;
    if (!confirm(`Delete dictionary "${selected.name}"?`)) return;
    try {
      await apiClient.delete(`/api/v1/chat/dictionaries/${selected.id}`);
      selected = null;
      updateSelectedMeta();
      el('entriesList').innerHTML = '';
      await refreshDictionaries();
      if (typeof Toast !== 'undefined') Toast.success('Dictionary deleted');
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to delete dictionary');
    }
  }

  function renderEntries(entries) {
    const listEl = el('entriesList');
    if (!listEl) return;
    if (!entries || entries.length === 0) {
      listEl.innerHTML = '<div class="muted">No entries</div>';
      return;
    }
    const rows = entries.map(e => `
      <div class="entry-row" style="display:flex; gap:8px; align-items:center; border-bottom:1px solid var(--color-border); padding:6px;">
        <code style="flex:1; overflow:auto;">${escapeHtml(e.pattern)}</code>
        <div style="flex:1; overflow:auto;">→ ${escapeHtml(e.replacement)}</div>
        <span class="badge">${e.type}</span>
        <span class="badge">p=${Number(e.probability).toFixed(2)}</span>
        <button class="btn btn-danger btn-sm" data-del="${e.id}">Delete</button>
      </div>
    `).join('');
    listEl.innerHTML = rows;
    listEl.querySelectorAll('button[data-del]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = parseInt(btn.getAttribute('data-del'));
        if (!confirm('Delete entry?')) return;
        try {
          await apiClient.delete(`/api/v1/chat/dictionaries/entries/${id}`);
          await refreshEntries();
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to delete entry');
        }
      });
    });
  }

  async function refreshEntries() {
    if (!selected) return;
    try {
      const data = await apiClient.get(`/api/v1/chat/dictionaries/${selected.id}/entries`);
      renderEntries(data?.entries || []);
    } catch (e) {
      console.error('Failed to load entries:', e);
    }
  }

  async function addEntry() {
    if (!selected) { alert('Select a dictionary first'); return; }
    const pattern = el('entry_pattern')?.value?.trim();
    const replacement = el('entry_replacement')?.value ?? '';
    const type = el('entry_type')?.value || 'literal';
    const probability = parseFloat(el('entry_probability')?.value || '1');
    const group = el('entry_group')?.value?.trim() || undefined;
    const max_replacements = parseInt(el('entry_max_replacements')?.value || '0');
    const enabled = !!el('entry_enabled')?.checked;
    const case_sensitive = !!el('entry_case_sensitive')?.checked;
    const status = el('entryAdd_status');
    if (!pattern) { alert('Enter a pattern'); return; }
    try {
      const body = { pattern, replacement, type, probability, group, max_replacements, enabled, case_sensitive };
      await apiClient.post(`/api/v1/chat/dictionaries/${selected.id}/entries`, body);
      if (status) status.textContent = 'Entry added';
      await refreshEntries();
      await refreshDictionaries();
    } catch (e) {
      if (status) status.textContent = `Error: ${e?.message || e}`;
    }
  }

  async function processText() {
    if (!selected) { alert('Select a dictionary first'); return; }
    const text = el('proc_text')?.value ?? '';
    const max_tokens_raw = el('proc_max_tokens')?.value?.trim();
    const group = el('proc_group')?.value?.trim();
    const body = { text, dictionary_id: selected.id };
    if (group) body.group = group;
    if (max_tokens_raw) body.token_budget = parseInt(max_tokens_raw);
    try {
      const res = await apiClient.post('/api/v1/chat/dictionaries/process', body);
      el('proc_output').textContent = res?.processed_text ?? '';
      el('proc_stats').textContent = `replacements=${res?.replacements ?? 0}, iterations=${res?.iterations ?? 0}, token_budget_exceeded=${!!res?.token_budget_exceeded}`;
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to process text');
    }
  }

  async function importMarkdown() {
    const name = el('imp_name')?.value?.trim();
    const content = el('imp_content')?.value ?? '';
    const activate = !!el('imp_activate')?.checked;
    const status = el('imp_status');
    if (!name) { alert('Enter a name'); return; }
    if (!content) { alert('Paste markdown content'); return; }
    try {
      const res = await apiClient.post('/api/v1/chat/dictionaries/import', { name, content, activate });
      if (status) status.textContent = `Imported #${res?.dictionary_id} (${res?.entries_imported} entries)`;
      await refreshDictionaries();
    } catch (e) {
      if (status) status.textContent = `Error: ${e?.message || e}`;
    }
  }

  async function exportMarkdown() {
    if (!selected) { alert('Select a dictionary first'); return; }
    try {
      const res = await apiClient.get(`/api/v1/chat/dictionaries/${selected.id}/export`);
      el('exp_content').value = res?.content || '';
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to export');
    }
  }

  function escapeHtml(str) {
    if (str == null) return '';
    return String(str)
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#39;');
  }

  function bindEvents() {
    el('dictsRefreshBtn')?.addEventListener('click', refreshDictionaries);
    el('dictCreateBtn')?.addEventListener('click', createDictionary);
    el('dictToggleActiveBtn')?.addEventListener('click', toggleActive);
    el('dictDeleteBtn')?.addEventListener('click', deleteDictionary);
    el('entryAddBtn')?.addEventListener('click', addEntry);
    el('procRunBtn')?.addEventListener('click', processText);
    el('impRunBtn')?.addEventListener('click', importMarkdown);
    el('expRunBtn')?.addEventListener('click', exportMarkdown);
  }

  async function init() {
    // Ensure this tab is present
    if (!el('tabDictionaries')) return;
    bindEvents();
    await refreshDictionaries();
  }

  return { init };
})();

// Hook into main loader
function initializeDictionariesTab() {
  DictionariesUI.init();
}

