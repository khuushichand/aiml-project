// Minimal headless smoke test for WebUI TTS voice selection sync
// - Exercises TTS.useCatalogVoice and TTS.useCustomVoice (TTS tab)
// - Exercises apiTTSUseVoice (Audio -> Text to Speech panel)
// - Verifies cross-tab sync of provider/voice selections

const fs = require('fs');
const vm = require('vm');

function makeSelect(initialOptions = []) {
  const el = {
    options: initialOptions.map(([value, text]) => ({ value, text, textContent: text })),
    value: '',
    appendChild(opt) {
      this.options.push({ value: opt.value, text: opt.textContent, textContent: opt.textContent });
    },
    dispatchEvent() {}
  };
  return el;
}

// Minimal fake DOM
const elements = {
  // TTS tab provider voice selects
  'openai-voice': makeSelect([
    ['alloy', 'Alloy'], ['echo', 'Echo'], ['fable', 'Fable'], ['onyx', 'Onyx'], ['nova', 'Nova'], ['shimmer', 'Shimmer']
  ]),
  'elevenlabs-voice': makeSelect([
    ['rachel', 'Rachel'], ['domi', 'Domi'], ['bella', 'Bella'], ['josh', 'Josh']
  ]),
  'kokoro-voice': makeSelect([
    ['af_bella', 'Bella'], ['am_adam', 'Adam']
  ]),
  'higgs-voice': makeSelect([
    ['default', 'Default']
  ]),
  'chatterbox-voice': makeSelect([
    ['default', 'Default']
  ]),
  'vibevoice-voice': makeSelect([
    ['speaker_1', 'Speaker 1'], ['speaker_2', 'Speaker 2']
  ]),
  'vibevoice-custom-voice': makeSelect([['', 'None']]),

  // API panel controls
  'audioTTS_provider': { value: 'openai' },
  'audioTTS_voice': makeSelect([
    ['alloy', 'Alloy'], ['echo', 'Echo']
  ]),

  // Status target
  'tts-status': { textContent: '', className: '' }
};

const documentStub = {
  getElementById(id) { return elements[id] || null; },
  querySelectorAll() { return []; },
  addEventListener() { /* no-op for smoke */ },
  createElement(tag) {
    if (tag === 'option') return { value: '', textContent: '' };
    return {};
  }
};

const context = {
  console,
  setTimeout,
  clearTimeout,
  window: {},
  document: documentStub,
  localStorage: {
    getItem() { return null; },
    setItem() {}
  },
  // Stubs used by TTS cross-sync
  updateTTSProviderOptions() {
    // Simulate provider voice reset based on provider selection
    const provider = elements['audioTTS_provider']?.value;
    const vs = elements['audioTTS_voice'];
    if (!vs) return;
    vs.options = [];
    if (provider === 'openai') {
      ['alloy','echo','fable','onyx','nova','shimmer'].forEach(v => vs.appendChild({ value: v, textContent: v }));
    } else if (provider === 'elevenlabs') {
      ['rachel','domi','bella','josh'].forEach(v => vs.appendChild({ value: v, textContent: v }));
    }
  },
  async loadProviderVoices() { /* no-op for smoke */ },
  apiClient: {
    async get(path, params) {
      if (path.includes('/audio/voices/catalog')) {
        const provider = params && (params.provider || params.Provider || '').toLowerCase();
        const catalog = {
          openai: [
            { id: 'alloy', name: 'Alloy' },
            { id: 'echo', name: 'Echo' },
            { id: 'fable', name: 'Fable' }
          ],
          elevenlabs: [
            { id: 'rachel', name: 'Rachel' },
            { id: 'domi', name: 'Domi' }
          ],
          vibevoice: [
            { id: 'speaker_1', name: 'Speaker 1' }
          ]
        };
        if (provider && catalog[provider]) return { [provider]: catalog[provider] };
        return catalog;
      }
      return {};
    }
  }
};

vm.createContext(context);

// Load and expose TTS into globalThis
let ttsSource = fs.readFileSync('tldw_Server_API/WebUI/js/tts.js', 'utf8');
ttsSource = ttsSource.replace(/const\s+TTS\s*=\s*\{/m, 'globalThis.TTS = {');
vm.runInContext(ttsSource, context, { filename: 'tts.js' });
// Expose to window for cross-tab sync checks
context.window.TTS = context.TTS;

// Load API tab helpers and expose functions globally (they are function declarations, so fine)
const tabFuncs = fs.readFileSync('tldw_Server_API/WebUI/js/tab-functions.js', 'utf8');
vm.runInContext(tabFuncs, context, { filename: 'tab-functions.js' });

// Basic checks
function assert(cond, msg) {
  if (!cond) throw new Error(`Assertion failed: ${msg}`);
}

(async () => {
  // Catalog voice selection from TTS tab
  await context.TTS.useCatalogVoice('openai', 'alloy', 'Alloy');
  assert(elements['openai-voice'].value === 'alloy', 'TTS tab openai voice should be alloy');
  assert(elements['audioTTS_provider'].value === 'openai', 'API panel provider should be openai');
  assert(elements['audioTTS_voice'].value === 'alloy', 'API panel voice should be alloy');

  // Custom voice selection from TTS tab (vibevoice)
  await context.TTS.useCustomVoice('vibevoice', 'custom123', 'My Voice');
  assert(elements['vibevoice-custom-voice'].value === 'custom:custom123', 'TTS tab vibevoice custom should be selected');
  assert(elements['audioTTS_provider'].value === 'vibevoice', 'API panel provider should sync to vibevoice');
  assert(elements['audioTTS_voice'].value === 'custom123', 'API panel voice should reflect custom id');

  // API panel Use Voice selection syncs back to TTS tab
  await context.apiTTSUseVoice('elevenlabs', 'rachel', 'Rachel');
  assert(elements['elevenlabs-voice'].value === 'rachel', 'TTS tab elevenlabs voice should be rachel');

  console.log('OK: WebUI TTS voice selection smoke test passed');
})().catch(err => {
  console.error('Smoke test failed:', err.message);
  process.exit(1);
});
