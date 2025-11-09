/**
 * Shared Chat Portal
 * Moves the single full chat interface between the Simple landing page and the
 * Chat tab so we never duplicate stateful DOM with identical IDs.
 */

(function shareChatPortal() {
  const state = {
    sharedEl: null,
    loadingPromise: null,
    currentHost: null,
    notifiedFailure: false,
  };

  function waitForWebUI() {
    if (typeof window !== 'undefined' && window.webUI) return Promise.resolve();
    // Fallback: resolve after DOM is ready if webUI was already constructed
    if (document && (document.readyState === 'complete' || document.readyState === 'interactive')) {
      if (typeof window !== 'undefined' && window.webUI) return Promise.resolve();
    }
    return new Promise((resolve) => {
      const onReady = () => resolve();
      document.addEventListener('webui-ready', onReady, { once: true });
      // Safety timeout in case the event fired before we attached the listener
      setTimeout(() => { if (typeof window !== 'undefined' && window.webUI) resolve(); }, 1500);
    });
  }

  function togglePlaceholder(host, visible) {
    if (!host) return;
    host.querySelectorAll('[data-chat-placeholder]').forEach((el) => {
      if (!el) return;
      if (visible) el.style.removeProperty('display');
      else el.style.display = 'none';
    });
  }

  async function ensureSharedElement() {
    if (state.sharedEl && state.sharedEl.isConnected) return state.sharedEl;
    if (state.loadingPromise) {
      await state.loadingPromise;
      return state.sharedEl;
    }

    state.loadingPromise = (async () => {
      await waitForWebUI();

      let el = document.querySelector('[data-shared-chat-ui]');
      if (!el && window.webUI && typeof window.webUI.loadContentGroup === 'function') {
        const groups = window.webUI.loadedContentGroups;
        const hasChat = groups && typeof groups.has === 'function' ? groups.has('chat') : false;
        try {
          if (!hasChat) {
            await window.webUI.loadContentGroup('chat');
            if (groups && typeof groups.add === 'function') {
              groups.add('chat');
            }
          }
        } catch (err) {
          console.error('SharedChatPortal: failed to load chat group', err);
          // Surface a user-visible hint to diagnose tab HTML/script load failures
          if (!state.notifiedFailure) {
            state.notifiedFailure = true;
            try {
              const msg = 'Failed to load Chat UI (tabs/chat_content.html). See console/network tab.';
              if (typeof Toast !== 'undefined' && Toast && typeof Toast.error === 'function') {
                Toast.error(msg);
              }
            } catch (_) { /* no-op */ }
            try {
              // Update any visible chat placeholders with a brief error note
              document.querySelectorAll('[data-chat-placeholder]').forEach((ph) => {
                if (!ph) return;
                const note = 'Chat interface failed to load. Check server logs and /webui/tabs/chat_content.html.';
                ph.textContent = note;
                ph.style.removeProperty('display');
              });
            } catch (_) { /* ignore */ }
          }
        }
        el = document.querySelector('[data-shared-chat-ui]');
      }

      state.sharedEl = el || null;

      // Fallback: if chat group loaded but markup not found, fetch and extract just the shared UI subtree
      if (!state.sharedEl) {
        try {
          const url = new URL('tabs/chat_content.html', window.location.href).toString();
          const resp = await fetch(url, { cache: 'no-cache' });
          if (resp && resp.ok) {
            const html = await resp.text();
            // Sanitize before parsing so CSP never sees inline handlers
            const sanitize = (s) => {
              try {
                if (window.webUI && typeof window.webUI.sanitizeInlineHandlersAndScripts === 'function') {
                  return window.webUI.sanitizeInlineHandlersAndScripts(s);
                }
              } catch (_) {}
              try {
                const input = String(s);
                let doc = null;
                try {
                  if (typeof DOMParser !== 'undefined') {
                    const parser = new DOMParser();
                    doc = parser.parseFromString(input, 'text/html');
                  }
                } catch (_) { doc = null; }
                if (!doc) {
                  try {
                    doc = document.implementation.createHTMLDocument('');
                    doc.body.innerHTML = input;
                  } catch (_) { return input; }
                }
                try { doc.querySelectorAll('script').forEach((n) => { try { n.remove(); } catch (_) {} }); } catch (_) {}
                try {
                  const all = doc.querySelectorAll('*');
                  all.forEach((el) => {
                    if (!el || !el.attributes) return;
                    const toRemove = [];
                    const toAdd = [];
                    for (const attr of Array.from(el.attributes)) {
                      const rawName = attr && attr.name ? String(attr.name) : '';
                      if (!rawName) continue;
                      const name = rawName.toLowerCase();
                      if (name.startsWith('on') && /^[a-z0-9_-]+$/.test(name.slice(2) || '')) {
                        const val = attr.value || '';
                        let b64 = '';
                        try { b64 = btoa(val); } catch (_) { b64 = ''; }
                        const dataName = `data-${name}-b64`;
                        toAdd.push([dataName, b64]);
                        toRemove.push(rawName);
                      }
                    }
                    toAdd.forEach(([n, v]) => { try { el.setAttribute(n, v); } catch (_) {} });
                    toRemove.forEach((n) => { try { el.removeAttribute(n); } catch (_) {} });
                  });
                } catch (_) {}
                try {
                  if (doc.body) return doc.body.innerHTML;
                  if (doc.documentElement) return doc.documentElement.outerHTML;
                } catch (_) {}
                return input;
              } catch (_) { return s; }
            };
            const tmp = document.createElement('div');
            tmp.innerHTML = sanitize(html);
            const shared = tmp.querySelector('[data-shared-chat-ui]');
            if (shared) {
              // Adopt into current document by cloning
              state.sharedEl = shared.cloneNode(true);
            } else {
              console.warn('SharedChatPortal: fallback fetch succeeded but no [data-shared-chat-ui] present');
            }
          } else {
            console.warn('SharedChatPortal: fallback fetch for chat_content.html failed', resp && resp.status);
          }
        } catch (e) {
          console.debug('SharedChatPortal: fallback fetch error', e);
        }
      }

      if (el && window.ModuleLoader && typeof window.ModuleLoader.ensureGroupScriptsLoaded === 'function') {
        try {
          await window.ModuleLoader.ensureGroupScriptsLoaded('chat');
        } catch (err) {
          console.debug('SharedChatPortal: unable to load chat module scripts', err);
        }
      }

      state.loadingPromise = null;
    })();

    await state.loadingPromise;
    if (!state.sharedEl) {
      // Element still not present after load — surface a clear hint
      if (!state.notifiedFailure) {
        state.notifiedFailure = true;
        try {
          const msg = 'Chat UI markup not found after load. Verify /webui/tabs/chat_content.html loads.';
          if (typeof Toast !== 'undefined' && Toast && typeof Toast.error === 'function') {
            Toast.error(msg);
          }
        } catch (_) {}
        try {
          document.querySelectorAll('[data-chat-placeholder]').forEach((ph) => {
            if (!ph) return;
            ph.textContent = 'Chat interface unavailable (missing markup). Open Chat tab once or check network.';
            ph.style.removeProperty('display');
          });
        } catch (_) {}
      }
    }
    return state.sharedEl;
  }

  async function mount(hostName) {
    if (!hostName) return;
    const host = document.querySelector(`[data-chat-host="${hostName}"]`);
    if (!host) return;

    const shared = await ensureSharedElement();
    if (!shared) {
      togglePlaceholder(host, true);
      // Minimal inline hint on the host where it failed to mount
      try {
        const ph = host.querySelector('[data-chat-placeholder]');
        if (ph) {
          ph.textContent = 'Unable to mount Chat UI. See console/network for tabs/chat_content.html.';
        }
      } catch (_) {}
      return;
    }

    if (shared.parentElement === host) {
      togglePlaceholder(host, false);
      state.currentHost = hostName;
      return;
    }

    const previousHost = shared.closest('[data-chat-host]');
    if (previousHost && previousHost !== host) {
      togglePlaceholder(previousHost, true);
    }

    host.appendChild(shared);
    // Bind inline handlers safely for the newly inserted subtree
    try { if (window.webUI && typeof window.webUI.migrateInlineHandlers === 'function') { window.webUI.migrateInlineHandlers(host); } } catch (_) {}
    // Ensure chat module scripts are present for any dynamic behavior
    try { if (window.ModuleLoader && typeof window.ModuleLoader.ensureGroupScriptsLoaded === 'function') { window.ModuleLoader.ensureGroupScriptsLoaded('chat'); } } catch (_) {}
    // Populate model dropdowns and ensure a default model is selected if none is chosen
    try {
      const pop = (window.apiClient && typeof window.apiClient.populateModelDropdowns === 'function')
        ? window.apiClient.populateModelDropdowns()
        : (typeof window.populateModelDropdowns === 'function' ? window.populateModelDropdowns() : null);
      if (pop && typeof pop.then === 'function') {
        await pop;
      }
      try {
        const sel = document.getElementById('chatCompletions_model');
        if (sel && (!sel.value || sel.value === '')) {
          const providersInfo = (window.apiClient && window.apiClient.cachedProviders) ? window.apiClient.cachedProviders : null;
          if (providersInfo && providersInfo.default_provider && Array.isArray(providersInfo.providers)) {
            const dp = providersInfo.default_provider;
            const p = providersInfo.providers.find(x => x && x.name === dp);
            const dm = p && p.default_model ? `${p.name}/${p.default_model}` : null;
            if (dm) sel.value = dm;
          }
        }
      } catch (_) { /* ignore */ }
    } catch (_) { /* ignore */ }
    togglePlaceholder(host, false);
    state.currentHost = hostName;
  }

  window.SharedChatPortal = {
    mount,
    ensureReady: ensureSharedElement,
  };
})();
