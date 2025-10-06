(() => {
  const API_BASE = '/api/v1/setup';
  const PLACEHOLDER_VALUES = new Set([
    '',
    'your_api_key_here',
    'YOUR_API_KEY_HERE',
    'default-secret-key-for-single-user',
    'CHANGE_ME_TO_SECURE_API_KEY',
    'ChangeMeStrong123!',
    'change-me-in-production',
  ]);
  const TEXTAREA_KEY_PATTERN = /(description|prompt|instructions|notes|template|path|url|uri)/i;
  const state = {
    dirty: {},
    sections: [],
    status: null,
    saving: false,
  };

  const elements = {};

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheElements();
    setLoading(true);

    try {
      const status = await fetchJson(`${API_BASE}/status`);
      state.status = status;

      if (!status.enabled) {
        renderDisabledState();
        return;
      }

      if (!status.needs_setup) {
        window.location.href = '/webui/';
        return;
      }

      renderStatus(status);
      await loadConfig();
      bindActions();
    } catch (error) {
      console.error('Setup initialisation failed', error);
      setMessage('error', `Failed to load setup data: ${error.message || error}`);
    } finally {
      setLoading(false);
    }
  }

  function cacheElements() {
    elements.configSections = document.getElementById('configSections');
    elements.configLoading = document.getElementById('configLoading');
    elements.setupRequired = document.getElementById('setupRequired');
    elements.configPath = document.getElementById('configPath');
    elements.placeholderNotice = document.getElementById('placeholderNotice');
    elements.saveButton = document.getElementById('saveChanges');
    elements.completeButton = document.getElementById('completeSetup');
    elements.disableToggle = document.getElementById('disableWizardToggle');
    elements.actionMessage = document.getElementById('actionMessage');
  }

  function hasPendingChanges() {
    return Object.keys(state.dirty).length > 0;
  }

  async function loadConfig() {
    try {
      const data = await fetchJson(`${API_BASE}/config`);
      state.sections = data.sections || [];
      renderSections(state.sections);
      updateSaveState();
    } catch (error) {
      console.error('Failed to fetch config snapshot', error);
      setMessage('error', `Unable to load configuration: ${error.message || error}`);
    }
  }

  function renderStatus(status) {
    elements.configPath.textContent = status.config_path;
    elements.setupRequired.textContent = status.needs_setup ? 'Yes' : 'No';
    elements.setupRequired.classList.toggle('badge-alert', !!status.needs_setup);
    elements.setupRequired.classList.toggle('badge-success', !status.needs_setup);

    if (status.placeholder_fields && status.placeholder_fields.length) {
      const uniquePlaceholders = status.placeholder_fields
        .map((item) => `${item.section} → ${item.key}`);

      elements.placeholderNotice.innerHTML = `
        <strong>${uniquePlaceholders.length} field(s)</strong> still use placeholder values.
        Focus on these sections first.
      `;
      elements.placeholderNotice.hidden = false;
    } else {
      elements.placeholderNotice.hidden = true;
    }
  }

  async function refreshStatus() {
    try {
      const status = await fetchJson(`${API_BASE}/status`);
      state.status = status;
      renderStatus(status);
    } catch (error) {
      console.error('Failed to refresh setup status', error);
    }
  }

  function renderDisabledState() {
    if (elements.configSections) {
      elements.configSections.innerHTML = `
        <div class="empty-state">
          Guided setup is disabled. Set <code>enable_first_time_setup = true</code> in config.txt to use this page.
        </div>
      `;
    }
    elements.saveButton.disabled = true;
    elements.completeButton.disabled = true;
    setMessage('info', 'Setup wizard disabled via config.txt.');
  }

  function renderSections(sections) {
    const container = elements.configSections;
    container.innerHTML = '';

    sections.forEach((section) => {
      const details = document.createElement('details');
      details.className = 'section-card';
      details.open = shouldExpandSection(section);

      const summary = document.createElement('summary');
      summary.className = 'section-summary';
      summary.innerHTML = `
        <span class="section-title">${escapeHtml(section.label || section.name)}</span>
        <span class="section-subtitle">${escapeHtml(section.description || '')}</span>
      `;
      details.appendChild(summary);

      const fieldsWrapper = document.createElement('div');
      fieldsWrapper.className = 'fields-wrapper';

      section.fields.forEach((field) => {
        fieldsWrapper.appendChild(renderField(section.name, field));
      });

      details.appendChild(fieldsWrapper);
      container.appendChild(details);
    });
  }

  function renderField(sectionName, field) {
    const wrapper = document.createElement('div');
    wrapper.className = 'field-card';
    if (field.placeholder) {
      wrapper.classList.add('placeholder');
    }

    if (shouldUseWideLayout(field)) {
      wrapper.classList.add('wide');
    }

    const label = document.createElement('label');
    label.className = 'field-label';
    label.textContent = field.key;

    const inputContainer = document.createElement('div');
    inputContainer.className = 'field-input';

    const input = createInputForField(field);
    input.dataset.section = sectionName;
    input.dataset.key = field.key;
    input.dataset.type = field.type;
    input.dataset.originalValue = initialDatasetValue(field);
    input.addEventListener('input', handleFieldInput);
    input.addEventListener('change', handleFieldInput);

    inputContainer.appendChild(input);

    if (field.is_secret && input.type === 'password') {
      const toggle = document.createElement('button');
      toggle.type = 'button';
      toggle.className = 'btn subtle reveal';
      toggle.textContent = 'Show';
      toggle.addEventListener('click', () => {
        if (input.type === 'password') {
          input.type = 'text';
          toggle.textContent = 'Hide';
        } else {
          input.type = 'password';
          toggle.textContent = 'Show';
        }
      });
      inputContainer.appendChild(toggle);
    }

    wrapper.appendChild(label);
    wrapper.appendChild(inputContainer);
    if (field.hint) {
      const hint = document.createElement('p');
      hint.className = 'field-hint';
      hint.textContent = field.hint;
      wrapper.appendChild(hint);
    }
    return wrapper;
  }

  function createInputForField(field) {
    const rawValue = field.value === undefined || field.value === null ? '' : field.value;
    const value = typeof rawValue === 'string' ? rawValue : String(rawValue);
    const isBoolean = field.type === 'boolean';
    const isNumeric = field.type === 'number' || field.type === 'integer';
    const isSecret = !!field.is_secret;

    if (isBoolean) {
      const input = document.createElement('input');
      input.type = 'checkbox';
      input.checked = toBoolean(value);
      return input;
    }

    if (shouldRenderTextarea(field, value)) {
      const textarea = document.createElement('textarea');
      const visibleLength = value.length;
      const computedRows = Math.ceil(visibleLength / 60);
      textarea.rows = Math.min(10, Math.max(4, computedRows || 4));
      textarea.value = value;
      textarea.spellcheck = false;
      return textarea;
    }

    const input = document.createElement('input');
    input.type = isSecret ? 'password' : (isNumeric ? 'number' : 'text');
    input.value = value;
    if (isNumeric) {
      input.step = field.type === 'integer' ? '1' : 'any';
    }
    return input;
  }

  function shouldUseWideLayout(field) {
    if (!field) {
      return false;
    }

    const type = field.type;
    if (type === 'boolean' || type === 'integer' || type === 'number') {
      return false;
    }

    if (field.is_secret) {
      return false;
    }

    const key = String(field.key || '');
    const heuristicMatch = TEXTAREA_KEY_PATTERN.test(key);
    const valueLength = String(field.value ?? '').length;
    return heuristicMatch || valueLength > 60;
  }

  function shouldRenderTextarea(field, value) {
    if (!field) {
      return false;
    }

    if (field.is_secret) {
      return false;
    }

    const type = field.type;
    if (type === 'boolean' || type === 'integer' || type === 'number') {
      return false;
    }

    if (typeof value === 'string') {
      if (value.includes('\n') || value.length > 80) {
        return true;
      }
    }

    const key = String(field.key || '');
    return TEXTAREA_KEY_PATTERN.test(key);
  }

  function initialDatasetValue(field) {
    if (field.type === 'boolean') {
      return toBoolean(field.value) ? 'true' : 'false';
    }

    if (field.type === 'number' || field.type === 'integer') {
      const numeric = field.value === undefined || field.value === null ? '' : field.value;
      return String(numeric).trim();
    }

    return field.value === undefined || field.value === null ? '' : String(field.value);
  }

  function handleFieldInput(event) {
    const input = event.target;
    const section = input.dataset.section;
    const key = input.dataset.key;
    const type = input.dataset.type;
    const original = input.dataset.originalValue !== undefined ? input.dataset.originalValue : '';
    const value = normaliseValue(input, type);

    if (!state.dirty[section]) {
      state.dirty[section] = {};
    }

    const parentCard = input.closest('.field-card');

    if (value === original) {
      delete state.dirty[section][key];
      if (Object.keys(state.dirty[section]).length === 0) {
        delete state.dirty[section];
      }
      if (parentCard) {
        parentCard.classList.remove('dirty');
      }
      if (parentCard) {
        parentCard.classList.toggle('placeholder', isPlaceholderValue(value));
      }
    } else {
      state.dirty[section][key] = value;
      if (parentCard) {
        parentCard.classList.add('dirty');
      }
      if (parentCard && !isPlaceholderValue(value)) {
        parentCard.classList.remove('placeholder');
      }
    }

    updateSaveState();
  }

  function updateSaveState() {
    const hasChanges = hasPendingChanges();

    if (elements.saveButton) {
      elements.saveButton.disabled = !hasChanges || state.saving;
    }

    if (elements.completeButton) {
      elements.completeButton.disabled = hasChanges || state.saving;
    }
  }

  function shouldExpandSection(section) {
    const placeholders = (section.fields || []).some((field) => field.placeholder);
    return placeholders;
  }

  async function persistDirtyChanges(options = {}) {
    const { silentSuccess = false } = options;

    if (!hasPendingChanges()) {
      if (!silentSuccess) {
        setMessage('info', 'No changes to save.');
      }
      return false;
    }

    try {
      const payload = { updates: state.dirty };
      const serialised = serialisePayload(payload);
      const response = await fetchJson(`${API_BASE}/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(serialised),
      });

      state.dirty = {};
      updateSaveState();
      await refreshStatus();
      await loadConfig();

      if (!silentSuccess) {
        setMessage('success', `Configuration saved. ${response.requires_restart ? 'Restart the server to apply changes.' : ''}`);
        if (response.backup_path) {
          appendMessage(`Backup created at ${response.backup_path}`);
        }
      }

      return true;
    } catch (error) {
      console.error('Failed to save configuration', error);
      setMessage('error', `Save failed: ${error.message || error}`);
      throw error;
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      await persistDirtyChanges();
    } catch {
      // Message handled in persistDirtyChanges
    } finally {
      setSaving(false);
    }
  }

  async function handleComplete() {
    if (hasPendingChanges()) {
      setMessage('info', 'Saving pending changes before completing setup…');
    }

    setSaving(true);
    try {
      if (hasPendingChanges()) {
        try {
          await persistDirtyChanges({ silentSuccess: true });
        } catch {
          return;
        }
      }

      const payload = { disable_first_time_setup: elements.disableToggle.checked };
      const response = await fetchJson(`${API_BASE}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      setMessage('success', `${response.message || 'Setup completed.'} Redirecting to Web UI…`);
      setTimeout(() => window.location.href = '/webui/', 2500);
    } catch (error) {
      console.error('Failed to mark setup complete', error);
      setMessage('error', `Unable to complete setup: ${error.message || error}`);
    } finally {
      setSaving(false);
    }
  }

  function normaliseValue(input, type) {
    if (type === 'boolean') {
      return input.checked ? 'true' : 'false';
    }

    if (type === 'number' || type === 'integer') {
      return input.value.trim();
    }

    return input.value;
  }

  function serialisePayload(payload) {
    const updates = {};
    for (const [section, fields] of Object.entries(payload.updates)) {
      updates[section] = {};
      for (const [key, value] of Object.entries(fields)) {
        updates[section][key] = value;
      }
    }
    return { updates };
  }

  function bindActions() {
    elements.saveButton.addEventListener('click', handleSave);
    elements.completeButton.addEventListener('click', handleComplete);
  }

  function setLoading(isLoading) {
    if (!elements.configLoading) return;
    elements.configLoading.style.display = isLoading ? 'flex' : 'none';
  }

  function setSaving(isSaving) {
    state.saving = isSaving;
    updateSaveState();
  }

  function setMessage(level, message) {
    if (!elements.actionMessage) return;
    elements.actionMessage.textContent = message;
    elements.actionMessage.className = `action-message ${level}`;
  }

  function appendMessage(additional) {
    if (!elements.actionMessage) return;
    elements.actionMessage.textContent += `\n${additional}`;
  }

  async function fetchJson(url, options) {
    const response = await fetch(url, options);
    if (!response.ok) {
      const text = await response.text();
      throw new Error(text || response.statusText);
    }
    return response.json();
  }

  function toBoolean(value) {
    const normalised = String(value).trim().toLowerCase();
    return ['true', '1', 'yes', 'on'].includes(normalised);
  }

  function isPlaceholderValue(value) {
    return PLACEHOLDER_VALUES.has(String(value).trim());
  }

  function escapeHtml(value) {
    return String(value || '')
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;');
  }
})();
