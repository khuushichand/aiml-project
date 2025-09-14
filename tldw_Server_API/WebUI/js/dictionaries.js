/**
 * Chat Dictionaries UI
 */

const DictionariesUI = (() => {
  let selected = null; // { id, name, is_active, entry_count, ... }
  let currentEntries = [];
  let entryFilterText = '';
  let entryFilterType = '';
  let groupBy = false;
  let selectedEntryIds = new Set();
  let groupFilter = '';

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
      window.__dictSelectedId = null;
      return;
    }
    if (nameSpan) nameSpan.textContent = `${selected.name} (#${selected.id})`;
    if (meta) meta.textContent = `Active: ${!!selected.is_active} • Entries: ${selected.entry_count ?? '-'} • Updated: ${selected.updated_at || 'n/a'}`;
    if (toggleBtn) toggleBtn.disabled = false;
    if (delBtn) delBtn.disabled = false;
    window.__dictSelectedId = selected.id;
  }

  async function refreshDictionaries(silent = false) {
    try {
      const data = await apiClient.get('/api/v1/chat/dictionaries', { include_inactive: true });
      const list = data?.dictionaries || [];
      renderDictionaries(list);
      // Update selected if exists
      if (selected) {
        const fresh = list.find(d => d.id === selected.id);
        if (fresh) { selected = fresh; updateSelectedMeta(); }
      }
      if (!silent && typeof Toast !== 'undefined') Toast.success('Dictionaries refreshed');
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
    currentEntries = Array.isArray(entries) ? entries.slice() : [];

    // Apply filters
    let filtered = currentEntries;
    if (entryFilterText) {
      const t = entryFilterText.toLowerCase();
      filtered = filtered.filter(e => String(e.pattern || '').toLowerCase().includes(t));
    }
    if (entryFilterType) {
      filtered = filtered.filter(e => (e.type || '') === entryFilterType);
    }
    if (groupFilter) {
      filtered = filtered.filter(e => (e.group || '') === groupFilter);
    }

    if (!filtered || filtered.length === 0) {
      listEl.innerHTML = '<div class="muted">No entries</div>';
      return;
    }
    const renderRow = (e) => `
      <div class="entry-row" data-id="${e.id}" style="display:flex; gap:8px; align-items:center; border-bottom:1px solid var(--color-border); padding:6px;">
        <input type="checkbox" class="entry-select" ${selectedEntryIds.has(e.id) ? 'checked' : ''} title="Select"/>
        <div style="display:flex; gap:8px; align-items:center; flex:1;">
          <input type="checkbox" class="entry-enabled" ${e.enabled ? 'checked' : ''} title="Enabled">
          <code class="entry-pattern" style="flex:1; overflow:auto;">${escapeHtml(e.pattern)}</code>
        </div>
        <div class="entry-replacement" style="flex:1; overflow:auto;">→ ${escapeHtml(e.replacement)}</div>
        <span class="badge">${e.type}</span>
        <div style="display:flex; gap:4px; align-items:center;">
          <label title="Case sensitive">
            <input type="checkbox" class="entry-case" ${e.case_sensitive ? 'checked' : ''}> Aa
          </label>
          <input type="number" min="0" max="1" step="0.05" class="entry-prob" value="${Number(e.probability).toFixed(2)}" title="Probability (0.0-1.0)" style="width:72px;">
        </div>
        <button class="btn btn-sm" data-edit="${e.id}">Edit</button>
        <button class="btn btn-danger btn-sm" data-del="${e.id}">Delete</button>
      </div>`;

    if (groupBy) {
      const byGroup = {};
      for (const e of filtered) {
        const g = e.group || '(no group)';
        (byGroup[g] ||= []).push(e);
      }
      let html = '';
      Object.keys(byGroup).sort().forEach(g => {
        html += `<div class="group-header" data-group="${escapeHtml(g)}" style="margin-top:6px; font-weight:600; display:flex; justify-content:space-between; align-items:center;">
          <span>Group: ${escapeHtml(g)}</span>
          <span style="display:flex; gap:6px; align-items:center;">
            <button class="btn btn-sm" data-gselect>Select</button>
            <button class="btn btn-sm" data-gact>Activate</button>
            <button class="btn btn-sm" data-gdeact>Deactivate</button>
            <button class="btn btn-sm" data-gclear>Clear Group</button>
            <button class="btn btn-sm" data-grename>Rename</button>
          </span>
        </div>`;
        html += byGroup[g].map(renderRow).join('');
      });
      listEl.innerHTML = html;
    } else {
      listEl.innerHTML = filtered.map(renderRow).join('');
    }
    listEl.querySelectorAll('button[data-del]').forEach(btn => {
      btn.addEventListener('click', async () => {
        const id = parseInt(btn.getAttribute('data-del'));
        if (!confirm('Delete entry?')) return;
        try {
          await apiClient.delete(`/api/v1/chat/dictionaries/entries/${id}`);
          await refreshEntries();
          if (typeof Toast !== 'undefined') Toast.success('Entry deleted');
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to delete entry');
        }
      });
    });

    // Selection
    listEl.querySelectorAll('.entry-select').forEach(cb => {
      cb.addEventListener('change', (ev) => {
        const row = ev.target.closest('.entry-row');
        const id = parseInt(row.getAttribute('data-id'));
        if (ev.target.checked) selectedEntryIds.add(id); else selectedEntryIds.delete(id);
      });
    });

    // Group header actions
    listEl.querySelectorAll('.group-header').forEach(header => {
      const groupName = header.getAttribute('data-group');
      const entriesInGroup = filtered.filter(e => (e.group || '(no group)') === groupName);
      header.querySelector('[data-gselect]')?.addEventListener('click', () => {
        for (const e of entriesInGroup) selectedEntryIds.add(e.id);
        renderEntries(currentEntries);
      });
      header.querySelector('[data-gact]')?.addEventListener('click', async () => {
        try {
          for (const e of entriesInGroup) await apiClient.put(`/api/v1/chat/dictionaries/entries/${e.id}`, { enabled: true });
          if (typeof Toast !== 'undefined') Toast.success(`Activated ${entriesInGroup.length} entries in group "${groupName}"`);
          await refreshEntries();
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to activate group');
        }
      });
      header.querySelector('[data-gdeact]')?.addEventListener('click', async () => {
        try {
          for (const e of entriesInGroup) await apiClient.put(`/api/v1/chat/dictionaries/entries/${e.id}`, { enabled: false });
          if (typeof Toast !== 'undefined') Toast.success(`Deactivated ${entriesInGroup.length} entries in group "${groupName}"`);
          await refreshEntries();
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to deactivate group');
        }
      });
      header.querySelector('[data-gclear]')?.addEventListener('click', async () => {
        try {
          for (const e of entriesInGroup) await apiClient.put(`/api/v1/chat/dictionaries/entries/${e.id}`, { group: null });
          if (typeof Toast !== 'undefined') Toast.success(`Cleared group from ${entriesInGroup.length} entries`);
          await refreshEntries();
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to clear group');
        }
      });
      header.querySelector('[data-grename]')?.addEventListener('click', async () => {
        const newName = prompt(`Rename group "${groupName}" to:`, groupName === '(no group)' ? '' : groupName);
        if (newName === null) return;
        const finalName = newName.trim();
        if (!finalName) { alert('Enter a non-empty group name'); return; }
        try {
          for (const e of entriesInGroup) await apiClient.put(`/api/v1/chat/dictionaries/entries/${e.id}`, { group: finalName });
          if (typeof Toast !== 'undefined') Toast.success(`Renamed group to "${finalName}"`);
          await refreshEntries();
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to rename group');
        }
      });
    });

    // Toggle enabled
    listEl.querySelectorAll('.entry-enabled').forEach(cb => {
      cb.addEventListener('change', async (ev) => {
        const row = ev.target.closest('.entry-row');
        const id = parseInt(row.getAttribute('data-id'));
        const enabled = !!ev.target.checked;
        try {
          await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { enabled });
          if (typeof Toast !== 'undefined') Toast.success(enabled ? 'Entry enabled' : 'Entry disabled');
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to toggle entry');
          // revert
          ev.target.checked = !enabled;
        }
      });
    });

    // Toggle case sensitivity
    listEl.querySelectorAll('.entry-case').forEach(cb => {
      cb.addEventListener('change', async (ev) => {
        const row = ev.target.closest('.entry-row');
        const id = parseInt(row.getAttribute('data-id'));
        const cs = !!ev.target.checked;
        try {
          await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { case_sensitive: cs });
          if (typeof Toast !== 'undefined') Toast.success(cs ? 'Case sensitive' : 'Case insensitive');
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to toggle case sensitivity');
          ev.target.checked = !cs;
        }
      });
    });

    // Probability inline edit
    listEl.querySelectorAll('.entry-prob').forEach(inp => {
      const handler = Utils?.debounce ? Utils.debounce : (f)=>f;
      const apply = async (ev) => {
        const row = ev.target.closest('.entry-row');
        const id = parseInt(row.getAttribute('data-id'));
        let p = parseFloat(ev.target.value);
        if (isNaN(p) || p < 0) p = 0; if (p > 1) p = 1;
        ev.target.value = p.toFixed(2);
        try {
          await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { probability: p });
          if (typeof Toast !== 'undefined') Toast.success('Probability updated');
        } catch (e) {
          console.error(e);
          if (typeof Toast !== 'undefined') Toast.error('Failed to update probability');
        }
      };
      inp.addEventListener('change', apply);
      inp.addEventListener('blur', apply);
    });

    // Edit inline
    listEl.querySelectorAll('button[data-edit]').forEach(btn => {
      btn.addEventListener('click', () => beginEditEntry(parseInt(btn.getAttribute('data-edit'))));
    });
  }

  async function refreshEntries() {
    if (!selected) return;
    try {
      const data = await apiClient.get(`/api/v1/chat/dictionaries/${selected.id}/entries`);
      renderEntries(data?.entries || []);
      populateGroupDropdown();
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
      if (typeof Toast !== 'undefined') Toast.success('Entry added');
      await refreshEntries();
      await refreshDictionaries();
    } catch (e) {
      if (status) status.textContent = `Error: ${e?.message || e}`;
      if (typeof Toast !== 'undefined') Toast.error('Failed to add entry');
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
      if (typeof Toast !== 'undefined') Toast.success(`Processed: ${res?.replacements ?? 0} replacements`);
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
      if (typeof Toast !== 'undefined') Toast.success('Dictionary imported');
    } catch (e) {
      if (status) status.textContent = `Error: ${e?.message || e}`;
      if (typeof Toast !== 'undefined') Toast.error('Import failed');
    }
  }

  async function exportMarkdown() {
    if (!selected) { alert('Select a dictionary first'); return; }
    try {
      const res = await apiClient.get(`/api/v1/chat/dictionaries/${selected.id}/export`);
      el('exp_content').value = res?.content || '';
      if (typeof Toast !== 'undefined') Toast.success('Exported');
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to export');
    }
  }

  async function importJSON() {
    const text = el('imp_json_content')?.value ?? '';
    const activate = !!el('imp_json_activate')?.checked;
    const status = el('imp_json_status');
    if (!text) { alert('Paste JSON data'); return; }
    let data;
    try { data = JSON.parse(text); } catch (e) { alert('Invalid JSON'); return; }
    try {
      const res = await apiClient.post('/api/v1/chat/dictionaries/import/json', { data, activate });
      if (status) status.textContent = `Imported #${res?.dictionary_id} (${res?.entries_imported} entries)`;
      await refreshDictionaries(true);
      if (typeof Toast !== 'undefined') Toast.success('Imported JSON dictionary');
    } catch (e) {
      if (status) status.textContent = `Error: ${e?.message || e}`;
      if (typeof Toast !== 'undefined') Toast.error('JSON import failed');
    }
  }

  async function exportJSON() {
    if (!selected) { alert('Select a dictionary first'); return; }
    try {
      const data = await apiClient.get(`/api/v1/chat/dictionaries/${selected.id}/export/json`);
      el('exp_json_content').value = JSON.stringify(data, null, 2);
      if (typeof Toast !== 'undefined') Toast.success('Exported JSON');
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('JSON export failed');
    }
  }

  // Download helpers
  function downloadText(filename, text, mime = 'text/plain;charset=utf-8') {
    try {
      const blob = new Blob([text ?? ''], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 0);
    } catch (e) {
      console.error('Download failed:', e);
      if (typeof Toast !== 'undefined') Toast.error('Download failed');
    }
  }

  async function downloadMarkdown() {
    if (!selected) { alert('Select a dictionary first'); return; }
    let content = el('exp_content')?.value || '';
    if (!content) {
      await exportMarkdown();
      content = el('exp_content')?.value || '';
    }
    if (!content) { alert('Nothing to download'); return; }
    const safe = (selected.name || 'dictionary').replace(/[^a-z0-9-_]+/gi,'_');
    downloadText(`${safe}.md`, content, 'text/markdown;charset=utf-8');
  }

  async function downloadJSON() {
    if (!selected) { alert('Select a dictionary first'); return; }
    let text = el('exp_json_content')?.value || '';
    if (!text) {
      await exportJSON();
      text = el('exp_json_content')?.value || '';
    }
    if (!text) { alert('Nothing to download'); return; }
    const safe = (selected.name || 'dictionary').replace(/[^a-z0-9-_]+/gi,'_');
    downloadText(`${safe}.json`, text, 'application/json;charset=utf-8');
  }

  async function downloadCSV() {
    if (!selected) { alert('Select a dictionary first'); return; }
    let text = el('exp_csv_content')?.value || '';
    if (!text) {
      await exportCSV();
      text = el('exp_csv_content')?.value || '';
    }
    if (!text) { alert('Nothing to download'); return; }
    const safe = (selected.name || 'dictionary').replace(/[^a-z0-9-_]+/gi,'_');
    downloadText(`${safe}.csv`, text, 'text/csv;charset=utf-8');
  }

  // Download helpers
  function downloadText(filename, text, mime = 'text/plain;charset=utf-8') {
    try {
      const blob = new Blob([text ?? ''], { type: mime });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      setTimeout(() => {
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      }, 0);
    } catch (e) {
      console.error('Download failed:', e);
      if (typeof Toast !== 'undefined') Toast.error('Download failed');
    }
  }

  async function downloadMarkdown() {
    if (!selected) { alert('Select a dictionary first'); return; }
    let content = el('exp_content')?.value || '';
    if (!content) {
      await exportMarkdown();
      content = el('exp_content')?.value || '';
    }
    if (!content) { alert('Nothing to download'); return; }
    const safe = (selected.name || 'dictionary').replace(/[^a-z0-9-_]+/gi,'_');
    downloadText(`${safe}.md`, content, 'text/markdown;charset=utf-8');
  }

  async function downloadJSON() {
    if (!selected) { alert('Select a dictionary first'); return; }
    let text = el('exp_json_content')?.value || '';
    if (!text) {
      await exportJSON();
      text = el('exp_json_content')?.value || '';
    }
    if (!text) { alert('Nothing to download'); return; }
    const safe = (selected.name || 'dictionary').replace(/[^a-z0-9-_]+/gi,'_');
    downloadText(`${safe}.json`, text, 'application/json;charset=utf-8');
  }

  async function downloadCSV() {
    if (!selected) { alert('Select a dictionary first'); return; }
    let text = el('exp_csv_content')?.value || '';
    if (!text) {
      await exportCSV();
      text = el('exp_csv_content')?.value || '';
    }
    if (!text) { alert('Nothing to download'); return; }
    const safe = (selected.name || 'dictionary').replace(/[^a-z0-9-_]+/gi,'_');
    downloadText(`${safe}.csv`, text, 'text/csv;charset=utf-8');
  }

  // CSV helpers
  function csvEscape(value) {
    if (value == null) return '';
    const s = String(value);
    if (/[",\n]/.test(s)) {
      return '"' + s.replace(/"/g, '""') + '"';
    }
    return s;
  }

  async function exportCSV() {
    if (!selected) { alert('Select a dictionary first'); return; }
    try {
      const data = await apiClient.get(`/api/v1/chat/dictionaries/${selected.id}/export/json`);
      const entries = data?.entries || [];
      const header = ['pattern','replacement','type','probability','enabled','case_sensitive','group','max_replacements'];
      const rows = [header.join(',')];
      for (const e of entries) {
        rows.push([
          csvEscape(e.pattern),
          csvEscape(e.replacement),
          csvEscape(e.type || 'literal'),
          csvEscape(e.probability ?? 1.0),
          csvEscape(e.enabled ?? true),
          csvEscape(e.case_sensitive ?? true),
          csvEscape(e.group ?? ''),
          csvEscape(e.max_replacements ?? 0),
        ].join(','));
      }
      el('exp_csv_content').value = rows.join('\n');
      if (typeof Toast !== 'undefined') Toast.success('Exported CSV');
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('CSV export failed');
    }
  }

  function parseCSV(text) {
    // Simple CSV parser for quoted/unquoted cells; split lines and parse quoted fields
    const lines = text.split(/\r?\n/).filter(l => l.trim().length > 0);
    if (lines.length === 0) return { header: [], rows: [] };
    const parseLine = (line) => {
      const result = [];
      let cur = '';
      let inQuotes = false;
      for (let i = 0; i < line.length; i++) {
        const ch = line[i];
        if (inQuotes) {
          if (ch === '"') {
            if (line[i+1] === '"') { cur += '"'; i++; } else { inQuotes = false; }
          } else {
            cur += ch;
          }
        } else {
          if (ch === ',') { result.push(cur); cur = ''; }
          else if (ch === '"') { inQuotes = true; }
          else { cur += ch; }
        }
      }
      result.push(cur);
      return result.map(c => c.trim());
    };
    const header = parseLine(lines[0]);
    const rows = lines.slice(1).map(parseLine);
    return { header, rows };
  }

  async function importCSV() {
    const name = el('imp_csv_name')?.value?.trim();
    const text = el('imp_csv_content')?.value ?? '';
    const activate = !!el('imp_csv_activate')?.checked;
    const status = el('imp_csv_status');
    if (!name) { alert('Enter a dictionary name'); return; }
    if (!text) { alert('Paste CSV content'); return; }
    try {
      const { header, rows } = parseCSV(text);
      const idx = (col) => header.findIndex(h => h.toLowerCase() === col);
      const map = {
        pattern: idx('pattern'),
        replacement: idx('replacement'),
        type: idx('type'),
        probability: idx('probability'),
        enabled: idx('enabled'),
        case_sensitive: idx('case_sensitive'),
        group: idx('group'),
        max_replacements: idx('max_replacements'),
      };
      const entries = [];
      for (const r of rows) {
        const get = (k) => (map[k] >= 0 ? r[map[k]] : undefined);
        const pat = get('pattern');
        const rep = get('replacement');
        if (!pat) continue;
        const typ = (get('type') || 'literal').toLowerCase();
        let prob = parseFloat(get('probability') ?? '1');
        if (isNaN(prob)) prob = 1.0;
        const enabled = String(get('enabled') ?? 'true').toLowerCase() !== 'false';
        const cs = String(get('case_sensitive') ?? 'true').toLowerCase() !== 'false';
        const group = get('group') || undefined;
        let mr = parseInt(get('max_replacements') ?? '0');
        if (isNaN(mr) || mr < 0) mr = 0;
        entries.push({ pattern: pat, replacement: rep ?? '', type: typ, probability: prob, enabled, case_sensitive: cs, group, max_replacements: mr });
      }
      const body = { data: { name, entries }, activate };
      const res = await apiClient.post('/api/v1/chat/dictionaries/import/json', body);
      if (status) status.textContent = `Imported #${res?.dictionary_id} (${res?.entries_imported} entries)`;
      await refreshDictionaries(true);
      if (typeof Toast !== 'undefined') Toast.success('CSV imported');
    } catch (e) {
      console.error(e);
      if (status) status.textContent = `Error: ${e?.message || e}`;
      if (typeof Toast !== 'undefined') Toast.error('CSV import failed');
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
    el('impJsonBtn')?.addEventListener('click', importJSON);
    el('expJsonBtn')?.addEventListener('click', exportJSON);
    el('impCsvBtn')?.addEventListener('click', importCSV);
    el('expCsvBtn')?.addEventListener('click', exportCSV);

    // Filters
    el('entriesFilter')?.addEventListener('input', (e) => {
      entryFilterText = e.target.value || '';
      renderEntries(currentEntries);
    });
    el('entriesTypeFilter')?.addEventListener('change', (e) => {
      entryFilterType = e.target.value || '';
      renderEntries(currentEntries);
    });
    el('entriesGroupFilter')?.addEventListener('change', (e) => {
      groupFilter = e.target.value || '';
      renderEntries(currentEntries);
    });
    el('entriesGroupBy')?.addEventListener('change', (e) => {
      groupBy = !!e.target.checked;
      renderEntries(currentEntries);
    });
    el('entriesSelectAll')?.addEventListener('change', (e) => {
      const check = !!e.target.checked;
      if (check) selectedEntryIds = new Set(currentEntries.map(e => e.id)); else selectedEntryIds.clear();
      renderEntries(currentEntries);
    });
    el('bulkAction')?.addEventListener('change', (e) => {
      const action = e.target.value || '';
      const groupInput = el('bulkGroupName');
      if (!groupInput) return;
      groupInput.style.display = (action === 'group' || action === 'rename_group') ? 'inline-block' : 'none';
    });
    el('bulkApplyBtn')?.addEventListener('click', applyBulkAction);

    // Downloads
    el('expDownloadMdBtn')?.addEventListener('click', downloadMarkdown);
    el('expJsonDownloadBtn')?.addEventListener('click', downloadJSON);
    el('expCsvDownloadBtn')?.addEventListener('click', downloadCSV);

    // Copy buttons
    el('expCopyMdBtn')?.addEventListener('click', async () => {
      const t = el('exp_content')?.value || '';
      if (!t) return;
      await Utils.copyToClipboard(t);
      if (typeof Toast !== 'undefined') Toast.success('Copied markdown');
    });
    el('expJsonCopyBtn')?.addEventListener('click', async () => {
      const t = el('exp_json_content')?.value || '';
      if (!t) return;
      await Utils.copyToClipboard(t);
      if (typeof Toast !== 'undefined') Toast.success('Copied JSON');
    });
    el('expCsvCopyBtn')?.addEventListener('click', async () => {
      const t = el('exp_csv_content')?.value || '';
      if (!t) return;
      await Utils.copyToClipboard(t);
      if (typeof Toast !== 'undefined') Toast.success('Copied CSV');
    });

    // Downloads
    el('expDownloadMdBtn')?.addEventListener('click', downloadMarkdown);
    el('expJsonDownloadBtn')?.addEventListener('click', downloadJSON);
    el('expCsvDownloadBtn')?.addEventListener('click', downloadCSV);
  }

  async function init() {
    // Ensure this tab is present
    if (!el('tabDictionaries')) return;
    bindEvents();
    await refreshDictionaries(true);
    // Attach drag-and-drop to import areas
    attachDropHandlers('imp_json_content', 'json');
    attachDropHandlers('imp_csv_content', 'csv');
  }

  function populateGroupDropdown() {
    const dd = el('entriesGroupFilter');
    if (!dd) return;
    const groups = Array.from(new Set(currentEntries.map(e => e.group || '').filter(Boolean))).sort();
    const cur = dd.value;
    dd.innerHTML = '<option value="">All groups</option>' + groups.map(g => `<option value="${escapeHtml(g)}">${escapeHtml(g)}</option>`).join('');
    if (groups.includes(cur)) dd.value = cur;
  }

  async function applyBulkAction() {
    if (!selected) { alert('Select a dictionary first'); return; }
    if (selectedEntryIds.size === 0) { alert('Select one or more entries'); return; }
    const action = el('bulkAction')?.value || '';
    if (!action) { alert('Choose a bulk action'); return; }
    const ids = Array.from(selectedEntryIds);
    try {
      if (action === 'delete') {
        for (const id of ids) { await apiClient.delete(`/api/v1/chat/dictionaries/entries/${id}`); }
        if (typeof Toast !== 'undefined') Toast.success(`Deleted ${ids.length} entr${ids.length>1?'ies':'y'}`);
      } else if (action === 'activate' || action === 'deactivate') {
        const enabled = action === 'activate';
        for (const id of ids) { await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { enabled }); }
        if (typeof Toast !== 'undefined') Toast.success(`${enabled ? 'Activated' : 'Deactivated'} ${ids.length} entr${ids.length>1?'ies':'y'}`);
      } else if (action === 'group') {
        const groupName = el('bulkGroupName')?.value?.trim();
        if (!groupName) { alert('Enter a group name'); return; }
        for (const id of ids) { await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { group: groupName }); }
        if (typeof Toast !== 'undefined') Toast.success(`Grouped ${ids.length} entr${ids.length>1?'ies':'y'} into "${groupName}"`);
      } else if (action === 'clear_group') {
        for (const id of ids) { await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { group: null }); }
        if (typeof Toast !== 'undefined') Toast.success(`Cleared group for ${ids.length} entr${ids.length>1?'ies':'y'}`);
      } else if (action === 'rename_group') {
        const newName = el('bulkGroupName')?.value?.trim();
        if (!newName) { alert('Enter a new group name'); return; }
        for (const id of ids) { await apiClient.put(`/api/v1/chat/dictionaries/entries/${id}`, { group: newName }); }
        if (typeof Toast !== 'undefined') Toast.success(`Renamed group for ${ids.length} entr${ids.length>1?'ies':'y'} to "${newName}"`);
      }
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Bulk operation failed');
    } finally {
      await refreshEntries();
      await refreshDictionaries(true);
      el('entriesSelectAll') && (el('entriesSelectAll').checked = false);
      selectedEntryIds.clear();
      renderEntries(currentEntries);
    }
  }

  return { init };
})();

// Hook into main loader
function initializeDictionariesTab() {
  DictionariesUI.init();
}

// Inline edit implementation
function beginEditEntry(entryId) {
  const row = document.querySelector(`.entry-row[data-id="${entryId}"]`);
  if (!row) return;
  const patternEl = row.querySelector('.entry-pattern');
  const replEl = row.querySelector('.entry-replacement');
  const originalPattern = patternEl?.textContent || '';
  const originalRepl = (replEl?.textContent || '').replace(/^\s*→\s*/, '');

  // Build editor inline
  row.dataset.mode = 'edit';
  patternEl.innerHTML = `<input type="text" class="entry-edit-pattern" value="${originalPattern.replace(/"/g,'&quot;')}">`;
  replEl.innerHTML = `→ <input type="text" class="entry-edit-replacement" value="${originalRepl.replace(/"/g,'&quot;')}">`;

  // Replace buttons
  const editBtn = row.querySelector('button[data-edit]');
  const delBtn = row.querySelector('button[data-del]');
  if (editBtn) editBtn.textContent = 'Save';
  if (delBtn) delBtn.textContent = 'Cancel';

  const saveHandler = async () => {
    const newPattern = row.querySelector('.entry-edit-pattern')?.value ?? originalPattern;
    const newRepl = row.querySelector('.entry-edit-replacement')?.value ?? originalRepl;
    try {
      await apiClient.put(`/api/v1/chat/dictionaries/entries/${entryId}`, { pattern: newPattern, replacement: newRepl });
      if (typeof Toast !== 'undefined') Toast.success('Entry updated');
      // refresh list
      const dictId = window.__dictSelectedId;
      if (!dictId) { renderEntries(currentEntries); return; }
      const entriesResp = await apiClient.get(`/api/v1/chat/dictionaries/${dictId}/entries`);
      currentEntries = entriesResp?.entries || [];
      renderEntries(currentEntries);
    } catch (e) {
      console.error(e);
      if (typeof Toast !== 'undefined') Toast.error('Failed to update entry');
    }
  };

  const cancelHandler = async () => {
    renderEntries(currentEntries);
  };

  editBtn?.addEventListener('click', saveHandler, { once: true });
  delBtn?.addEventListener('click', cancelHandler, { once: true });
}

// Drag & Drop file loader for import textareas
function attachDropHandlers(elementId, type) {
  const area = document.getElementById(elementId);
  if (!area) return;
  const onDragOver = (e) => { e.preventDefault(); area.classList.add('drag-over'); };
  const onDragLeave = (e) => { e.preventDefault(); area.classList.remove('drag-over'); };
  const onDrop = (e) => {
    e.preventDefault();
    area.classList.remove('drag-over');
    const file = e.dataTransfer?.files?.[0];
    if (!file) return;
    const reader = new FileReader();
    reader.onload = () => {
      try {
        const text = String(reader.result || '');
        if (type === 'json') {
          // Validate JSON structure
          const data = JSON.parse(text);
          if (typeof data !== 'object' || data === null) throw new Error('JSON must be an object');
          if (!('entries' in data) || !Array.isArray(data.entries)) {
            throw new Error("Missing 'entries' array in JSON");
          }
          // Pretty print
          area.value = JSON.stringify(data, null, 2);
          if (typeof Toast !== 'undefined') Toast.success(`Loaded JSON: ${file.name}`);
        } else if (type === 'csv') {
          // Validate CSV header
          const { header, rows } = parseCSV(text);
          const required = ['pattern','replacement'];
          const missing = required.filter(col => header.findIndex(h => h.toLowerCase() === col) < 0);
          if (missing.length) {
            throw new Error(`CSV missing required column(s): ${missing.join(', ')}`);
          }
          if (rows.length === 0) {
            throw new Error('CSV contains no data rows');
          }
          // Optional: check row widths
          const widths = rows.map(r => r.length);
          const expected = header.length;
          const badIndex = widths.findIndex(w => w !== expected);
          if (badIndex >= 0) {
            throw new Error(`Row ${badIndex + 2} has ${widths[badIndex]} columns; expected ${expected}`);
          }
          area.value = text;
          if (typeof Toast !== 'undefined') Toast.success(`Loaded CSV: ${file.name}`);
        } else {
          // Default: just load
          area.value = text;
          if (typeof Toast !== 'undefined') Toast.success(`Loaded ${file.name}`);
        }
      } catch (err) {
        console.error('Drop validation failed:', err);
        if (typeof Toast !== 'undefined') Toast.error(`Invalid ${type?.toUpperCase() || ''} file: ${err.message}`);
      }
    };
    reader.onerror = () => {
      if (typeof Toast !== 'undefined') Toast.error('Failed to read file');
    };
    reader.readAsText(file);
  };
  area.addEventListener('dragover', onDragOver);
  area.addEventListener('dragleave', onDragLeave);
  area.addEventListener('drop', onDrop);
}
