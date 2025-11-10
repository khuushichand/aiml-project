// Lightweight per-group script loader to reduce initial payload
// Uses simple script tag injection and avoids duplicate loads.

(function () {
  const loaded = new Set();
  const inflight = new Map();

  const groupToScripts = {
    // Core heavy groups
    audio: [
      'js/tts.js',
      'js/tts-loader.js',
      'js/streaming-transcription.js',
    ],
    chat: [
      'js/chat-ui.js',
      'js/dictionaries.js',
    ],
    prompts: [
      'js/components_explain.js',
      'js/prompts.js',
    ],
    rag: ['js/rag.js'],
    evaluations: ['js/evals.js'],
    jobs: ['js/jobs.js'],
    chatbooks: ['js/jobs.js'],
    keywords: ['js/keywords.js'],
    admin: [
      'js/admin-advanced.js',
      'js/admin-rbac.js',
      'js/admin-user-permissions.js',
      'js/admin-rbac-monitoring.js',
    ],
    media: ['js/media-analysis.js'],
    maintenance: ['js/maintenance.js'],
    auth: [
      'js/auth-basic.js',
      'js/auth-keys.js',
      'js/auth-advanced.js',
      'js/auth-permissions.js',
    ],
    simple: ['js/simple-mode.js'],
    // Vector stores loads its own module
    vector_stores: ['js/vector-stores.js'],
    // Additional groups
    webscraping: ['js/webscraping.js'],
    workflows: ['js/workflows.js'],
    // Placeholders (documenting groups that intentionally load no extra scripts)
    flashcards: [],
    llamacpp: [],
    health: [],
    mcp: [],
    sync: [],
    // other groups can be added as needed
  };

  function loadScript(src) {
    if (loaded.has(src)) return Promise.resolve();
    if (inflight.has(src)) return inflight.get(src);
    const p = new Promise((resolve, reject) => {
      const s = document.createElement('script');
      s.src = src;
      s.async = true;
      s.onload = () => { loaded.add(src); inflight.delete(src); resolve(); };
      s.onerror = (e) => { inflight.delete(src); reject(new Error(`Failed to load ${src}`)); };
      document.body.appendChild(s);
    });
    inflight.set(src, p);
    return p;
  }

  async function ensureGroupScriptsLoaded(groupName) {
    if (!groupName) return;
    const list = groupToScripts[groupName];
    if (!list || !list.length) return;
    for (const src of list) {
      // eslint-disable-next-line no-await-in-loop
      await loadScript(src);
    }
  }

  window.ModuleLoader = {
    ensureGroupScriptsLoaded,
  };
})();
