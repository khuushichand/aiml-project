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
  };

  function waitForWebUI() {
    if (window.webUI) return Promise.resolve();
    return new Promise((resolve) => {
      document.addEventListener('webui-ready', () => resolve(), { once: true });
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
        }
        el = document.querySelector('[data-shared-chat-ui]');
      }

      state.sharedEl = el || null;

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
    return state.sharedEl;
  }

  async function mount(hostName) {
    if (!hostName) return;
    const host = document.querySelector(`[data-chat-host="${hostName}"]`);
    if (!host) return;

    const shared = await ensureSharedElement();
    if (!shared) {
      togglePlaceholder(host, true);
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
    togglePlaceholder(host, false);
    state.currentHost = hostName;
  }

  window.SharedChatPortal = {
    mount,
    ensureReady: ensureSharedElement,
  };
})();
