// Personalization tab bindings (CSP-safe)
(function () {
  function bind(container) {
    if (!container || container._persBound) return;
    container._persBound = true;
    const $ = (sel) => container.querySelector(sel);

    // View Profile
    const btnView = container.querySelector('[data-action="pers-view-profile"]');
    if (btnView && !btnView._b) {
      btnView._b = true;
      btnView.addEventListener('click', async () => {
        try {
          const j = await apiClient.makeRequest('GET', '/api/v1/personalization/profile');
          const pre = $('#persProfile');
          if (pre) pre.textContent = JSON.stringify(j, null, 2);
        } catch (e) {
          if (typeof Toast !== 'undefined' && Toast) Toast.error(e.message || 'Failed to load profile');
        }
      });
    }

    // Opt-In
    const btnOptIn = container.querySelector('[data-action="pers-opt-in"]');
    if (btnOptIn && !btnOptIn._b) {
      btnOptIn._b = true;
      btnOptIn.addEventListener('click', async () => {
        try {
          await apiClient.makeRequest('POST', '/api/v1/personalization/opt-in', { body: { enabled: true } });
          if (typeof Toast !== 'undefined' && Toast) Toast.success('Opted in'); else alert('Opted in');
        } catch (e) {
          if (typeof Toast !== 'undefined' && Toast) Toast.error(e.message || 'Opt-in failed');
        }
      });
    }

    // Purge
    const btnPurge = container.querySelector('[data-action="pers-purge"]');
    if (btnPurge && !btnPurge._b) {
      btnPurge._b = true;
      btnPurge.addEventListener('click', async () => {
        try {
          await apiClient.makeRequest('POST', '/api/v1/personalization/purge');
          if (typeof Toast !== 'undefined' && Toast) Toast.success('Purge requested'); else alert('Purge requested');
        } catch (e) {
          if (typeof Toast !== 'undefined' && Toast) Toast.error(e.message || 'Purge failed');
        }
      });
    }

    // Save weights
    const btnSave = container.querySelector('[data-action="pers-save"]');
    if (btnSave && !btnSave._b) {
      btnSave._b = true;
      btnSave.addEventListener('click', async () => {
        try {
          const alpha = parseFloat($('#persAlpha')?.value || '0.2');
          const beta = parseFloat($('#persBeta')?.value || '0.6');
          const gamma = parseFloat($('#persGamma')?.value || '0.2');
          const recency_half_life_days = parseInt($('#persHalf')?.value || '14', 10);
          const body = { alpha, beta, gamma, recency_half_life_days };
          await apiClient.makeRequest('POST', '/api/v1/personalization/preferences', { body });
          if (typeof Toast !== 'undefined' && Toast) Toast.success('Preferences updated'); else alert('Preferences updated');
        } catch (e) {
          if (typeof Toast !== 'undefined' && Toast) Toast.error(e.message || 'Save failed');
        }
      });
    }

    // Add memory
    const btnAdd = container.querySelector('[data-action="pers-add-memory"]');
    if (btnAdd && !btnAdd._b) {
      btnAdd._b = true;
      btnAdd.addEventListener('click', async () => {
        try {
          const memContent = $('#memContent')?.value || '';
          const tagsStr = $('#memTags')?.value || '';
          const tags = tagsStr.split(',').map(s => s.trim()).filter(Boolean);
          const pinned = !!$('#memPinned')?.checked;
          const payload = { id: 'tmp', type: 'semantic', content: memContent, pinned, tags: tags.length ? tags : null };
          const j = await apiClient.makeRequest('POST', '/api/v1/personalization/memories', { body: payload });
          if (typeof Toast !== 'undefined' && Toast) Toast.success(`Added memory: ${j?.id || ''}`); else alert(`Added memory: ${j?.id || ''}`);
        } catch (e) {
          if (typeof Toast !== 'undefined' && Toast) Toast.error(e.message || 'Add failed');
        }
      });
    }

    // List memories
    const btnList = container.querySelector('[data-action="pers-list-memories"]');
    if (btnList && !btnList._b) {
      btnList._b = true;
      btnList.addEventListener('click', async () => {
        try {
          const j = await apiClient.makeRequest('GET', '/api/v1/personalization/memories');
          const pre = $('#memList');
          if (pre) pre.textContent = JSON.stringify(j, null, 2);
        } catch (e) {
          if (typeof Toast !== 'undefined' && Toast) Toast.error(e.message || 'List failed');
        }
      });
    }
  }

  function initializePersonalizationTab() {
    try {
      const el = document.getElementById('tabPersonalization');
      if (el) bind(el);
    } catch (_) { /* ignore */ }
  }

  // Expose initializer
  window.initializePersonalizationTab = initializePersonalizationTab;
})();
