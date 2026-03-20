(() => {
  const API_BASE = '/api/v1/setup';
  const QUICKSTART_URL = '/api/v1/config/quickstart';
  const PLACEHOLDER_VALUES = new Set([
    '',
    'your_api_key_here',
    'YOUR_API_KEY_HERE',
    'default-secret-key-for-single-user',
    'CHANGE_ME_TO_SECURE_API_KEY',
    'TestPassword123!',
    'change-me-in-production',
  ]);
  const TEXTAREA_KEY_PATTERN = /(description|prompt|instructions|notes|template|path|url|uri)/i;
  const DEFAULT_AUDIO_RESOURCE_PROFILE = 'balanced';
  const AUDIO_RESOURCE_PROFILE_ORDER = ['light', 'balanced', 'performance'];
  const AUDIO_RESOURCE_PROFILE_LABELS = {
    light: 'Light',
    balanced: 'Balanced',
    performance: 'Performance',
  };
  function humaniseKey(value) {
    if (!value) {
      return '';
    }
    return String(value)
      .split(/[_-]+/)
      .filter(Boolean)
      .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
      .join(' ');
  }
  const FEATURE_OPTIONS = [
    {
      value: 'chat',
      label: 'Chat & Conversations',
      hint: 'Configure chat behaviour, fallbacks, and persona tooling.',
      sections: ['API', 'Chat-Module', 'Character-Chat', 'Settings'],
    },
    {
      value: 'rag',
      label: 'Retrieval (RAG)',
      hint: 'Tune retrieval pipelines, hybrid search, and augmentation.',
      sections: ['RAG', 'Embeddings', 'Chunking'],
    },
    {
      value: 'chunking',
      label: 'Chunking & Ingestion',
      hint: 'Control how documents are chunked and normalised when ingested.',
      sections: ['Chunking', 'Processing', 'Media-Processing'],
    },
    {
      value: 'embeddings',
      label: 'Embeddings Service',
      hint: 'Manage embedding providers, context strategies, and caching.',
      sections: ['Embeddings', 'RAG', 'API'],
    },
    {
      value: 'audio',
      label: 'Speech (STT & TTS)',
      hint: 'Highlight transcription, streaming audio, and voice synthesis.',
      sections: ['STT-Settings', 'TTS-Settings'],
    },
    {
      value: 'media',
      label: 'Media & Downloads',
      hint: 'Adjust file limits, conversions, and yt-dlp ingestion defaults.',
      sections: ['Processing', 'Media-Processing', 'Settings'],
    },
    {
      value: 'mcp',
      label: 'MCP Integrations',
      hint: 'Surface Model Context Protocol tools, auth, and service hosts.',
      sections: ['MCP', 'MCP-Unified', 'AuthNZ', 'API'],
    },
    {
      value: 'extensions',
      label: 'Automation & Extras',
      hint: 'Expose optional modules like Prompt Studio or search providers.',
      sections: ['Prompts', 'Search-Engines', 'Auto-Save'],
    },
  ];
  const FEATURE_SECTION_MAP = FEATURE_OPTIONS.reduce((accumulator, option) => {
  accumulator[option.value] = option.sections;
  return accumulator;
}, {});
  const BACKEND_CATEGORY_OPTIONS = [
  {
    value: 'stt',
    label: 'Speech-to-text engines',
    hint: 'Install transcription backends and checkpoints so audio uploads work right away.',
    sections: ['STT-Settings', 'Processing'],
  },
  {
    value: 'tts',
    label: 'Text-to-speech engines',
    hint: 'Download voice synthesis models for offline and low-latency playback.',
    sections: ['TTS-Settings', 'Processing'],
  },
  {
    value: 'embeddings',
    label: 'Embedding models',
    hint: 'Pre-fetch dense retrievers for RAG so search works without extra setup.',
    sections: ['Embeddings', 'RAG'],
  },
];
  const BACKEND_SECTION_MAP = BACKEND_CATEGORY_OPTIONS.reduce((accumulator, option) => {
  accumulator[option.value] = option.sections;
  return accumulator;
}, {});
  const DATASTORE_SECTION_MAP = {
  sqlite: ['Database'],
  postgres: ['Database'],
};
  const INSTALL_TARGETS = {
  stt: {
    label: 'Speech-to-text engines',
    description: 'Choose which transcription engines and checkpoints to install after setup completes.',
    options: [
      {
        id: 'faster_whisper',
        label: 'Faster Whisper',
        hint: 'Optimised Whisper inference with CPU/GPU support. Downloads checkpoints into models/whisper/.',
        variantsLabel: 'Checkpoints to download',
        variants: [
          { id: 'small', label: 'small (≈1.0GB, good quality)', default: true },
          { id: 'medium', label: 'medium (≈2.4GB, balanced)' },
          { id: 'large-v3', label: 'large-v3 (≈5.8GB, highest accuracy)' },
          { id: 'distil-large-v3', label: 'distil-large-v3 (≈3.2GB, fast + accurate)' },
        ],
      },
      {
        id: 'qwen2_audio',
        label: 'Qwen2Audio 7B',
        hint: 'Multilingual streaming-ready ASR. ~14GB download, GPU recommended but CPU works for batch jobs.',
      },
      {
        id: 'nemo_parakeet_standard',
        label: 'NVIDIA NeMo Parakeet (standard)',
        hint: 'High quality NeMo transcription via nemo_toolkit. Downloads nvidia/parakeet-tdt-0.6b-v3.',
      },
      {
        id: 'nemo_parakeet_onnx',
        label: 'NVIDIA NeMo Parakeet (ONNX)',
        hint: 'CPU-optimised ONNX export of Parakeet. Great for production servers without GPUs.',
      },
      {
        id: 'nemo_parakeet_mlx',
        label: 'NVIDIA NeMo Parakeet (MLX)',
        hint: 'Apple Silicon accelerated transcription. Requires MLX runtime, downloads native variant.',
      },
      {
        id: 'nemo_canary',
        label: 'NVIDIA NeMo Canary',
        hint: 'Streaming-friendly multilingual Canary-1B for diarisation-ready pipelines.',
      },
    ],
  },
  tts: {
    label: 'Text-to-speech engines',
    description: 'Pick the voice providers to provision so chat responses can be spoken immediately.',
    options: [
      {
        id: 'kokoro',
        label: 'Kokoro (v1.0 ONNX)',
        hint: 'Lightweight expressive voices. Downloads onnx/model.onnx and voices/ (requires espeak-ng; set PHONEMIZER_ESPEAK_LIBRARY if needed).',
        variantsLabel: 'Assets',
        variants: [
          { id: 'onnx', label: 'ONNX runtime assets', default: true },
          { id: 'voices', label: 'Voice embeddings' },
        ],
      },
      {
        id: 'kitten_tts',
        label: 'KittenTTS',
        hint: 'Small English ONNX voices with first-use Hugging Face downloads. Requires espeak-ng plus phonemizer-fork/espeakng_loader.',
        variantsLabel: 'Model variants',
        variants: [
          { id: 'nano', label: 'Nano 0.8', default: true },
          { id: 'nano-int8', label: 'Nano 0.8 INT8' },
          { id: 'micro', label: 'Micro 0.8' },
          { id: 'mini', label: 'Mini 0.8' },
        ],
      },
      {
        id: 'dia',
        label: 'Dia dialogue TTS',
        hint: 'Conversational PyTorch voices with automatic speaker detection. Downloads nari-labs/dia.',
      },
      {
        id: 'higgs',
        label: 'Higgs Audio V2',
        hint: 'Multi-lingual diffusion voices (BosonAI). Downloads higgs-audio-v2 3B base + tokenizer.',
      },
      {
        id: 'vibevoice',
        label: 'Microsoft VibeVoice',
        hint: 'Expressive multi-speaker synthesis with singing/background music. Installs Git repo + model snapshot.',
        variantsLabel: 'Model variants',
        variants: [
          { id: '1.5B', label: '1.5B (≈3GB, 64K context)', default: true },
          { id: '7B', label: '7B preview (≈14GB, 32K context)' },
        ],
      },
    ],
  },
  embeddings: {
    label: 'Embedding models',
    description: 'Download dense retrievers now so RAG, search, and evals work out of the box.',
    options: [
      {
        id: 'huggingface',
        label: 'Trusted HuggingFace models',
        hint: 'Pre-download the allowlisted embedding models configured in config.txt.',
      },
      {
        id: 'custom_trusted',
        label: 'Custom trusted models',
        hint: 'Add additional HuggingFace repo IDs to the trusted list and download them now.',
      },
    ],
  },
};
  const DEFAULT_TRUSTED_EMBEDDING_MODELS = [
  'sentence-transformers/all-MiniLM-L6-v2',
  'sentence-transformers/all-mpnet-base-v2',
  'BAAI/bge-large-en-v1.5',
  'intfloat/e5-large-v2',
  'jinaai/jina-embeddings-v2-base-en',
  'nomic-ai/nomic-embed-text-v1.5',
];
  const INSTALL_STATUS_POLL_INTERVAL = 6000;
  const SECTION_INFO_DESCRIPTIONS = {
    Setup: 'Controls the guided setup flow that appears on first launch and handles completion flags.',
    AuthNZ: 'Configure authentication mode, API keys, and multi-user security policies.',
    API: 'Provide credentials for external LLMs and services used by chat, RAG, and tooling.',
    Processing: 'Set global ingestion defaults like concurrency, temporary storage, and file validation.',
    'Media-Processing': 'Fine-tune how videos, audio, and documents are chunked, converted, and analyzed.',
    'Chat-Module': 'Adjust chat behaviour, default providers, streaming responses, and moderation settings.',
    'Character-Chat': 'Manage persona chat options, character cards, and session persistence.',
    'Chat-Dictionaries': 'Control dictionary-driven replacements and prompt snippets used in chat flows.',
    Settings: 'General server preferences covering UI, rate limiting, and miscellaneous toggles.',
    'Auto-Save': 'Control how frequently notes, chats, and prompts are saved and versioned.',
    Server: 'Toggle deployment-wide behaviours like CORS, feature guards, and server defaults.',
    Database: 'Set database engines and file paths for auth, media content, and per-user data.',
    Embeddings: 'Choose embedding providers, models, and batching options for retrieval.',
    RAG: 'Tune retrieval parameters, hybrid search weights, and reranking behaviour.',
    Chunking: 'Define chunk sizes, overlap, and adaptive options for each media type.',
    'STT-Settings': 'Pick speech-to-text models, diarization, and streaming transcription preferences.',
    'TTS-Settings': 'Configure text-to-speech voices, codecs, and streaming output.',
    Prompts: 'Manage system prompts and templates for summarisation, chat, and automation.',
    'Search-Engines': 'Configure web search providers, query budgets, and language defaults.',
    'Local-API': 'Point to locally hosted model servers such as Ollama, Kobold, or vLLM.',
    Claims: 'Enable claim extraction workflows and related LLM providers.',
    MCP: 'Manage Model Context Protocol host settings, tokens, and exposed tools.',
    'MCP-Unified': 'Unified MCP service configuration including tool registry and RBAC.',
    Logging: 'Direct logs to files or services, adjust verbosity, and enable observability hooks.',
    Moderation: 'Configure chat guardrails: enablement, input/output actions, redact replacement, blocklist path, and per-user overrides file. Managed blocklist uses ETag/If-Match headers to protect concurrent edits.',
  };
  const MODULE_WALKTHROUGHS = {
    chat: {
      title: 'API & Chat Providers',
      intro: 'Make sure the chat pipeline knows which providers and defaults to use.',
      steps: [
        {
          title: 'Collect provider credentials',
          description: 'Confirm which remote providers you will use and store their API keys in your environment (.env or config helpers).',
          points: [
            'Open the API section to review which providers are enabled by default.',
            'Record which keys you still need to add before going live.',
          ],
          focus: [{ section: 'API' }],
        },
        {
          title: 'Set default chat providers',
          description: 'Pick the primary and backup chat providers to fall back on when requests do not specify one.',
          points: [
            'Use default_api for the primary provider and default_api_for_tasks for bulk/utility work.',
            'Match these defaults to the providers you have valid credentials for.',
          ],
          focus: [
            { section: 'API', key: 'default_api' },
            { section: 'API', key: 'default_api_for_tasks' },
          ],
        },
        {
          title: 'Tune chat behaviour',
          description: 'Adjust chat-module fallbacks, persistence, and rate limits to suit your deployment.',
          points: [
            'Enable provider fallback if you want automatic retries across providers.',
            'Configure chat_save_default and rate limits according to your storage and quota plans.',
          ],
          focus: [
            { section: 'Chat-Module', key: 'enable_provider_fallback' },
            { section: 'Chat-Module', key: 'chat_save_default' },
            { section: 'Chat-Module', key: 'rate_limit_per_minute' },
          ],
        },
        {
          title: 'Review moderation & guardrails',
          description: 'Enable moderation and set how violations are handled globally (block, redact, or warn). You can also provide a blocklist file and per-user overrides file.',
          points: [
            'Toggle Moderation.enabled on to enforce guardrails.',
            'Choose input_action and output_action (block, redact, warn).',
            'Set redact_replacement and point to your blocklist file.',
            'Blocklist supports /regex/flags (i, m, s, x); use \\# to include a literal #; categories suffix requires a space before # (e.g., "... -> redact:[X] #pii").',
          ],
          focus: [
            { section: 'Moderation', key: 'enabled' },
            { section: 'Moderation', key: 'input_action' },
            { section: 'Moderation', key: 'output_action' },
            { section: 'Moderation', key: 'blocklist_file' },
            { section: 'Moderation', key: 'user_overrides_file' },
          ],
        },
      ],
    },
    embeddings: {
      title: 'Embeddings & Retrieval',
      intro: 'Configure the vector pipeline so RAG and search behave the way you expect.',
      steps: [
        {
          title: 'Choose embedding provider & model',
          description: 'Select the embedding service (remote or local) and the default model that matches your retrieval budget.',
          points: [
            'Remote APIs (OpenAI, Cohere) require credentials in your environment.',
            'Local backends (sentence-transformers, ONNX) need the model path available on disk.',
          ],
          focus: [
            { section: 'Embeddings', key: 'embedding_provider' },
            { section: 'Embeddings', key: 'embedding_model' },
          ],
        },
        {
          title: 'Balance throughput vs. quality',
          description: 'Tune batching, context strategy, and caching so requests remain fast without sacrificing recall.',
          points: [
            'Adjust chunk_size/overlap for your document length and provider token budget.',
            'Context strategy controls how much document context to send with each embedding request.',
          ],
          focus: [
            { section: 'Embeddings', key: 'chunk_size' },
            { section: 'Embeddings', key: 'overlap' },
            { section: 'Embeddings', key: 'context_strategy' },
          ],
        },
        {
          title: 'Review chunking interplay',
          description: 'Align global chunking defaults with the embeddings pipeline so documents are segmented consistently.',
          points: [
            'Ensure chunk_max_size/overlap in the Chunking section matches the expectations you configured above.',
            'Enable adaptive chunking only if your workloads benefit from dynamic sizes.',
          ],
          focus: [
            { section: 'Chunking', key: 'chunking_method' },
            { section: 'Chunking', key: 'chunk_max_size' },
            { section: 'Chunking', key: 'chunk_overlap' },
          ],
        },
      ],
    },
    audio: {
      title: 'Speech (STT/TTS)',
      intro: 'Pick the transcription and voice synthesis backends you actually plan to run.',
      steps: [
        {
          title: 'Select the default transcriber',
          description: 'Choose the speech-to-text engine that is installed on this machine (faster-whisper, nemo, qwen2audio, etc.).',
          points: [
            'Set default_transcriber to the engine you have binaries/models for.',
            'Decide whether to keep streaming_fallback_to_whisper enabled for resilience.',
          ],
          focus: [
            { section: 'STT-Settings', key: 'default_transcriber' },
            { section: 'STT-Settings', key: 'streaming_fallback_to_whisper' },
          ],
        },
        {
          title: 'Configure STT performance knobs',
          description: 'Match model variants (MLX vs CUDA), chunk durations, and buffering to your hardware.',
          points: [
            'Nemo model variants require the matching device and cache directory.',
            'Tune chunk durations if you see latency spikes or memory pressure.',
          ],
          focus: [
            { section: 'STT-Settings', key: 'nemo_model_variant' },
            { section: 'STT-Settings', key: 'nemo_device' },
            { section: 'STT-Settings', key: 'buffered_chunk_duration' },
          ],
        },
        {
          title: 'Pick TTS backends you will run',
          description: 'Decide which voice provider(s) to enable so you avoid installing everything at once.',
          points: [
            'Set default_tts_provider to the engine you plan to run (e.g. kokoro, kitten_tts, openai, elevenlabs).',
            'Update default_tts_voice and any provider-specific model settings to match the assets you installed.',
          ],
          focus: [
            { section: 'TTS-Settings', key: 'default_tts_provider' },
            { section: 'TTS-Settings', key: 'default_tts_voice' },
            { section: 'TTS-Settings', key: 'default_openai_tts_model' },
            { section: 'TTS-Settings', key: 'default_kokoro_tts_model' },
          ],
        },
      ],
    },
    mcp: {
      title: 'Model Context Protocol',
      intro: 'Wire up MCP hosts and the unified registry if you plan to expose tools through the protocol.',
      steps: [
        {
          title: 'Review MCP host settings',
          description: 'Confirm the MCP base URLs, authentication tokens, and tool discovery defaults.',
          points: [
            'Ensure hosts are reachable from your deployment environment.',
            'Decide whether to enable tool auto-registration or restrict manually.',
          ],
          focus: [{ section: 'MCP' }],
        },
        {
          title: 'Configure unified MCP service',
          description: 'Set up the unified MCP server, including RBAC policies and JWT secrets if you are exposing it externally.',
          points: [
            'Review token lifetimes and signing keys before enabling remote access.',
            'Add or remove tool modules from the registry to match your environment.',
          ],
          focus: [{ section: 'MCP-Unified' }],
        },
      ],
    },
  };
  const WIZARD_STEPS = [
    {
      id: 'auth',
      type: 'single',
      title: 'Who will use this server?',
      description: 'Pick the option that best matches your deployment so we can configure authentication.',
      options: [
        {
          value: 'single_user',
          label: 'Just me on this machine',
          hint: 'Simple API key authentication (recommended for local or personal installs).',
          sections: ['AuthNZ', 'Setup'],
        },
        {
          value: 'multi_user',
          label: 'Multiple teammates or remote access',
          hint: 'Enables JWT auth, user management, and database configuration.',
          sections: ['AuthNZ', 'Setup', 'Database'],
        },
      ],
    },
    {
      id: 'features',
      type: 'multi',
      title: 'Which capabilities do you plan to use first?',
      description: 'We will surface the settings that unlock these features right away.',
      options: FEATURE_OPTIONS.map(({ value, label, hint }) => ({ value, label, hint })),
    },
    {
      id: 'backends',
      type: 'multi',
      optional: true,
      title: 'Which backend modules will you install next?',
      description: 'Call out the engines you plan to add so we can point you to the right configuration and assets.',
      options: BACKEND_CATEGORY_OPTIONS,
    },
    {
      id: 'backend_config',
      type: 'module',
      optional: true,
      title: 'Choose your audio bundle and installable modules',
      description: 'Start with the recommended curated audio bundle, then open advanced mode only if you need individual engine control.',
    },
    {
      id: 'datastore',
      type: 'single',
      title: 'Where will your primary data live?',
      description: 'Base installs ship with SQLite. Switch to PostgreSQL when you are ready for multi-user or scaled storage.',
      options: [
        {
          value: 'sqlite',
          label: 'SQLite (default)',
          hint: 'Lightweight, file-based, perfect for local or single-user deployments.',
          sections: ['Database'],
        },
        {
          value: 'postgres',
          label: 'PostgreSQL',
          hint: 'Production-ready relational database. Configure connection URLs and migrations under Database.',
          sections: ['Database'],
        },
      ],
    },
    {
      id: 'depth',
      type: 'single',
      title: 'How much configuration do you want to see now?',
      description: 'You can always reveal every section later.',
      options: [
        {
          value: 'guided',
          label: 'Show the recommended sections only',
          hint: 'Keeps advanced settings tucked away until you need them.',
        },
        {
          value: 'all',
          label: 'Show everything from config.txt',
          hint: 'Ideal if you already know which values you want to change.',
        },
      ],
    },
    {
      id: 'summary',
      type: 'summary',
      title: 'All set! Let’s review.',
      description: '',
    },
  ];
  const QUESTION_STEPS = WIZARD_STEPS.filter((step) => step.type !== 'summary');
  const TOTAL_GUIDED_STEPS = QUESTION_STEPS.length;
  const state = {
    dirty: {},
    sections: [],
    status: null,
    saving: false,
    configLoaded: false,
    visibleSections: null,
    showHiddenSections: false,
    hiddenSections: [],
    recommendedSections: new Set(),
    wizard: {
      active: false,
      currentStep: 0,
      answers: {},
      completed: false,
      skipped: false,
    },
    assistant: {
      open: false,
      sending: false,
      greeted: false,
      history: [],
      initialised: false,
    },
    walkthrough: {
      active: false,
      module: null,
      stepIndex: 0,
      returnFocus: null,
    },
    install: {
      stt: {},
      tts: {},
      embeddings: {
        huggingface: [],
        custom: [],
        customInput: '',
        onnx: [],
      },
    },
    installStatus: {
      data: null,
      active: false,
      polling: false,
      redirectOnComplete: false,
    },
    audio: createAudioSetupState(),
  };
  state.walkthroughCompleted = new Set();

  function createAudioSetupState(overrides = {}) {
    return {
      loading: false,
      loaded: false,
      error: '',
      machineProfile: null,
      recommendations: [],
      excluded: [],
      catalog: {},
      selectedBundleId: null,
      selectedResourceProfile: DEFAULT_AUDIO_RESOURCE_PROFILE,
      showAlternatives: false,
      showAdvancedInstaller: false,
      showReadiness: false,
      provisioning: false,
      verifying: false,
      readinessLoading: false,
      readinessLoaded: false,
      readiness: null,
      lastProvisionResult: null,
      lastVerificationResult: null,
      ...overrides,
    };
  }

  function resetAudioSetupState(options = {}) {
    const { preserveReadiness = false } = options;
    const readiness = preserveReadiness ? state.audio?.readiness || null : null;
    const readinessLoaded = preserveReadiness ? Boolean(state.audio?.readinessLoaded) : false;
    const selectedBundleId = preserveReadiness
      ? state.audio?.selectedBundleId || readiness?.selected_bundle_id || null
      : null;
    const selectedResourceProfile = preserveReadiness
      ? state.audio?.selectedResourceProfile || readiness?.selected_resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE
      : DEFAULT_AUDIO_RESOURCE_PROFILE;

    state.audio = createAudioSetupState({
      readiness,
      readinessLoaded,
      selectedBundleId,
      selectedResourceProfile,
      showReadiness: preserveReadiness && Boolean(readiness),
    });
  }

  function ensureAudioSetupState() {
    if (!state.audio) {
      resetAudioSetupState();
    }
  }

  function resetInstallSelections() {
    state.install = {
      stt: {},
      tts: {},
      embeddings: {
        huggingface: [],
        custom: [],
        customInput: '',
        onnx: [],
      },
    };
  }

  function ensureInstallState() {
    if (!state.install) {
      resetInstallSelections();
      return;
    }

    state.install.stt = state.install.stt || {};
    state.install.tts = state.install.tts || {};

    const embeddings = state.install.embeddings || {};
    state.install.embeddings = {
      huggingface: Array.isArray(embeddings.huggingface) ? [...new Set(embeddings.huggingface)] : [],
      custom: Array.isArray(embeddings.custom)
        ? [...new Set(embeddings.custom.map((item) => item.trim()).filter(Boolean))]
        : [],
      customInput: typeof embeddings.customInput === 'string'
        ? embeddings.customInput
        : (Array.isArray(embeddings.custom) ? embeddings.custom.join('') : ''),
      onnx: Array.isArray(embeddings.onnx) ? [...new Set(embeddings.onnx)] : [],
    };

    ['stt', 'tts'].forEach((category) => {
      const group = state.install[category];
      Object.keys(group).forEach((engineId) => {
        const entry = group[engineId] || {};
        entry.selected = entry.selected !== false;
        entry.variants = Array.isArray(entry.variants) ? [...new Set(entry.variants)] : [];
        group[engineId] = entry;
      });
    });
  }

  function pruneInstallSelectionsForBackends(selectedBackends) {
    ensureInstallState();
    const selected = new Set(selectedBackends || []);

    ['stt', 'tts'].forEach((category) => {
      if (!selected.has(category)) {
        state.install[category] = {};
      }
    });

    if (!selected.has('embeddings')) {
      state.install.embeddings = {
        huggingface: [],
        custom: [],
        customInput: '',
        onnx: [],
      };
    }
  }

  function getInstallOption(category, optionId) {
    return INSTALL_TARGETS[category]?.options?.find((item) => item.id === optionId) || null;
  }

  function getInstallOptionLabel(category, optionId) {
    const option = getInstallOption(category, optionId);
    return option?.label || optionId;
  }

  function isEngineSelected(category, engineId) {
    ensureInstallState();
    return Boolean(state.install?.[category]?.[engineId]?.selected);
  }

  function getEngineSelection(category, engineId) {
    ensureInstallState();
    return state.install?.[category]?.[engineId] || null;
  }

  function setEngineSelection(category, engineId, selected) {
    ensureInstallState();
    const group = state.install[category];
    if (!group) {
      return;
    }

    if (!selected) {
      delete group[engineId];
      return;
    }

    if (!group[engineId]) {
      const option = getInstallOption(category, engineId);
      const defaults = option?.variants?.filter((variant) => variant.default).map((variant) => variant.id) || [];
      group[engineId] = {
        selected: true,
        variants: defaults,
      };
      return;
    }

    group[engineId].selected = true;
    group[engineId].variants = Array.isArray(group[engineId].variants)
      ? [...new Set(group[engineId].variants)]
      : [];
  }

  function toggleVariantSelection(category, engineId, variantId, checked) {
    ensureInstallState();
    const group = state.install[category];
    if (!group) {
      return;
    }

    if (!group[engineId]) {
      setEngineSelection(category, engineId, true);
    }

    const selection = group[engineId];
    const variants = new Set(selection.variants || []);
    if (checked) {
      variants.add(variantId);
    } else {
      variants.delete(variantId);
    }
    selection.variants = Array.from(variants);
  }

  function getVariantLabel(category, engineId, variantId) {
    const variant = getInstallOption(category, engineId)?.variants?.find((item) => item.id === variantId);
    return variant?.label || variantId;
  }

  function toggleEmbeddingPreset(modelId, checked) {
    ensureInstallState();
    const models = new Set(state.install.embeddings.huggingface || []);
    if (checked) {
      models.add(modelId);
    } else {
      models.delete(modelId);
    }
    state.install.embeddings.huggingface = Array.from(models);
  }

  function setCustomEmbeddingModelsFromInput(value) {
    ensureInstallState();
    state.install.embeddings.customInput = value;
    state.install.embeddings.custom = parseCustomModelList(value);
  }

  function parseCustomModelList(value) {
    if (!value) {
      return [];
    }
    return Array.from(new Set(
      value
        .split(/ |,/)
        .map((entry) => entry.trim())
        .filter(Boolean),
    ));
  }

  function getCustomEmbeddingInputValue() {
    ensureInstallState();
    return state.install.embeddings.customInput || state.install.embeddings.custom.join('');
  }

  function getEmbeddingPresetOptions() {
    const fromConfig = extractTrustedEmbeddingModelsFromConfig();
    const merged = new Set([...DEFAULT_TRUSTED_EMBEDDING_MODELS, ...fromConfig]);
    return Array.from(merged).sort((a, b) => a.localeCompare(b));
  }

  function extractTrustedEmbeddingModelsFromConfig() {
    if (!Array.isArray(state.sections)) {
      return [];
    }

    const embeddingSection = state.sections.find((entry) => entry.name === 'Embeddings');
    if (!embeddingSection || !Array.isArray(embeddingSection.fields)) {
      return [];
    }

    const field = embeddingSection.fields.find((item) => item.key === 'trusted_hf_remote_code_models');
    if (!field || typeof field.value !== 'string') {
      return [];
    }

    return field.value
      .split(',')
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function buildInstallPlan() {
    ensureInstallState();
    const plan = {
      stt: [],
      tts: [],
      embeddings: {
        huggingface: [],
        custom: [],
        onnx: [],
      },
    };

    Object.entries(state.install.stt || {}).forEach(([engineId, entry]) => {
      if (!entry || entry.selected === false) {
        return;
      }
      const record = { engine: engineId };
      if (Array.isArray(entry.variants) && entry.variants.length) {
        record.models = [...new Set(entry.variants)];
      }
      plan.stt.push(record);
    });

    Object.entries(state.install.tts || {}).forEach(([engineId, entry]) => {
      if (!entry || entry.selected === false) {
        return;
      }
      const record = { engine: engineId };
      if (Array.isArray(entry.variants) && entry.variants.length) {
        record.variants = [...new Set(entry.variants)];
      }
      plan.tts.push(record);
    });

    const embeddings = state.install.embeddings || {};
    plan.embeddings.huggingface = Array.from(new Set(embeddings.huggingface || []));
    plan.embeddings.custom = Array.from(
      new Set((embeddings.custom || []).map((item) => item.trim()).filter(Boolean)),
    );
    plan.embeddings.onnx = Array.from(new Set(embeddings.onnx || []));

    if (
      !plan.stt.length &&
      !plan.tts.length &&
      !plan.embeddings.huggingface.length &&
      !plan.embeddings.custom.length &&
      !plan.embeddings.onnx.length
    ) {
      return null;
    }

    return plan;
  }

  function isAudioBundleStepActive() {
    return WIZARD_STEPS[state.wizard.currentStep]?.id === 'backend_config';
  }

  function audioBundleRequested() {
    const selectedBackends = new Set(state.wizard.answers.backends || []);
    const selectedFeatures = new Set(state.wizard.answers.features || []);
    return selectedBackends.has('stt') || selectedBackends.has('tts') || selectedFeatures.has('audio');
  }

  function summarizeAudioPlanEntries(category, entries, variantKey) {
    return (entries || []).map((entry) => {
      const label = getInstallOptionLabel(category, entry.engine);
      const variants = Array.isArray(entry[variantKey]) ? entry[variantKey] : [];
      if (!variants.length) {
        return label;
      }
      const variantLabels = variants.map((variantId) => getVariantLabel(category, entry.engine, variantId));
      return `${label} [${variantLabels.join(', ')}]`;
    });
  }

  function buildAudioCatalogMap(entries) {
    return (entries || []).reduce((catalog, entry) => {
      if (entry && entry.bundle_id) {
        catalog[entry.bundle_id] = entry;
      }
      return catalog;
    }, {});
  }

  function getAudioCatalogEntry(bundleId) {
    ensureAudioSetupState();
    return state.audio.catalog?.[bundleId] || null;
  }

  function getAudioBundleResourceProfiles(bundle) {
    if (!bundle?.resource_profiles) {
      return [];
    }

    return Object.values(bundle.resource_profiles).sort((left, right) => {
      const leftOrder = AUDIO_RESOURCE_PROFILE_ORDER.indexOf(left.profile_id);
      const rightOrder = AUDIO_RESOURCE_PROFILE_ORDER.indexOf(right.profile_id);
      const leftRank = leftOrder === -1 ? Number.MAX_SAFE_INTEGER : leftOrder;
      const rightRank = rightOrder === -1 ? Number.MAX_SAFE_INTEGER : rightOrder;
      return leftRank - rightRank;
    });
  }

  function getAudioProfileLabel(profileId, fallbackLabel = '') {
    return AUDIO_RESOURCE_PROFILE_LABELS[profileId] || fallbackLabel || humaniseKey(profileId);
  }

  function getAudioRecommendation(bundleId, resourceProfile) {
    ensureAudioSetupState();
    if (!bundleId) {
      return null;
    }

    if (resourceProfile) {
      const exactMatch = state.audio.recommendations.find(
        (entry) => entry.bundle_id === bundleId && entry.resource_profile === resourceProfile,
      );
      if (exactMatch) {
        return exactMatch;
      }
    }

    return state.audio.recommendations.find((entry) => entry.bundle_id === bundleId) || null;
  }

  function getRecommendedAudioRecommendation() {
    ensureAudioSetupState();
    return state.audio.recommendations[0] || null;
  }

  function getSelectedAudioRecommendation() {
    ensureAudioSetupState();
    return (
      getAudioRecommendation(state.audio.selectedBundleId, state.audio.selectedResourceProfile)
      || getRecommendedAudioRecommendation()
      || null
    );
  }

  function getSelectedAudioBundle() {
    ensureAudioSetupState();
    const recommendation = getSelectedAudioRecommendation();
    const bundleId = state.audio.selectedBundleId || recommendation?.bundle_id;
    if (!bundleId) {
      return recommendation?.bundle || null;
    }
    return getAudioCatalogEntry(bundleId) || recommendation?.bundle || null;
  }

  function getSelectedAudioProfile() {
    const recommendation = getSelectedAudioRecommendation();
    const bundle = getSelectedAudioBundle();
    const profileId = state.audio.selectedResourceProfile
      || recommendation?.resource_profile
      || bundle?.default_resource_profile
      || DEFAULT_AUDIO_RESOURCE_PROFILE;
    const bundleProfiles = bundle?.resource_profiles || {};
    return (
      bundleProfiles[profileId]
      || recommendation?.profile
      || bundleProfiles[bundle?.default_resource_profile]
      || getAudioBundleResourceProfiles(bundle)[0]
      || null
    );
  }

  function syncSelectedAudioSelection() {
    ensureAudioSetupState();

    const readinessBundleId = state.audio.readiness?.selected_bundle_id || null;
    const readinessProfile = state.audio.readiness?.selected_resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE;
    const exact = getAudioRecommendation(state.audio.selectedBundleId, state.audio.selectedResourceProfile);
    if (exact) {
      state.audio.selectedBundleId = exact.bundle_id;
      state.audio.selectedResourceProfile = exact.resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE;
      return;
    }

    const readinessExact = getAudioRecommendation(readinessBundleId, readinessProfile);
    if (readinessExact) {
      state.audio.selectedBundleId = readinessExact.bundle_id;
      state.audio.selectedResourceProfile = readinessExact.resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE;
      return;
    }

    const bundleFallback = getAudioRecommendation(state.audio.selectedBundleId);
    if (bundleFallback) {
      state.audio.selectedBundleId = bundleFallback.bundle_id;
      state.audio.selectedResourceProfile = bundleFallback.resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE;
      return;
    }

    const recommended = getRecommendedAudioRecommendation();
    if (recommended) {
      state.audio.selectedBundleId = recommended.bundle_id;
      state.audio.selectedResourceProfile = recommended.resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE;
      return;
    }

    if (!state.audio.selectedBundleId) {
      state.audio.selectedResourceProfile = DEFAULT_AUDIO_RESOURCE_PROFILE;
    }
  }

  function getSelectedAudioReadiness() {
    ensureAudioSetupState();
    const readiness = state.audio.readiness;
    if (!readiness) {
      return null;
    }
    if (!state.audio.selectedBundleId || !readiness.selected_bundle_id) {
      return readiness;
    }
    if (readiness.selected_bundle_id !== state.audio.selectedBundleId) {
      return null;
    }
    if (
      state.audio.selectedResourceProfile
      && readiness.selected_resource_profile
      && readiness.selected_resource_profile !== state.audio.selectedResourceProfile
    ) {
      return null;
    }
    return readiness;
  }

  function getAudioPrerequisiteHint(step) {
    if (!step) {
      return '';
    }

    const platform = state.audio?.machineProfile?.platform;
    if (platform === 'darwin' && step.macos_hint) {
      return step.macos_hint;
    }
    if (platform === 'windows' && step.windows_hint) {
      return step.windows_hint;
    }
    if (platform === 'linux' && step.linux_hint) {
      return step.linux_hint;
    }
    return step.detail || step.macos_hint || step.linux_hint || step.windows_hint || '';
  }

  async function loadAudioRecommendations(options = {}) {
    const { force = false } = options;
    ensureAudioSetupState();

    if (state.audio.loading) {
      return state.audio.recommendations;
    }
    if (!force && state.audio.loaded) {
      return state.audio.recommendations;
    }

    state.audio.loading = true;
    state.audio.error = '';

    try {
      const response = await fetchJson(`${API_BASE}/audio/recommendations`);
      state.audio.machineProfile = response.machine_profile || null;
      state.audio.recommendations = Array.isArray(response.recommendations) ? response.recommendations : [];
      state.audio.excluded = Array.isArray(response.excluded) ? response.excluded : [];
      state.audio.catalog = buildAudioCatalogMap(response.catalog);
      syncSelectedAudioSelection();
      state.audio.loaded = true;
      return state.audio.recommendations;
    } catch (error) {
      console.warn('Failed to load audio setup bundle recommendations', error);
      state.audio.error = error.message || String(error);
      state.audio.loaded = false;
      return null;
    } finally {
      state.audio.loading = false;
      if (isAudioBundleStepActive()) {
        renderWizardStep();
      }
    }
  }

  async function loadAudioReadiness(options = {}) {
    const { force = false, silent = false } = options;
    ensureAudioSetupState();

    if (state.audio.readinessLoading) {
      return state.audio.readiness;
    }
    if (!force && state.audio.readinessLoaded) {
      return state.audio.readiness;
    }

    state.audio.readinessLoading = true;

    try {
      const readiness = await fetchJson(`${API_BASE}/audio/readiness`);
      state.audio.readiness = readiness;
      state.audio.readinessLoaded = true;
      if (readiness?.selected_bundle_id) {
        state.audio.selectedBundleId = readiness.selected_bundle_id;
        state.audio.selectedResourceProfile = readiness.selected_resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE;
      }
      syncSelectedAudioSelection();
      return readiness;
    } catch (error) {
      if (!silent) {
        console.warn('Failed to load setup audio readiness', error);
      }
      return state.audio.readiness;
    } finally {
      state.audio.readinessLoading = false;
      if (isAudioBundleStepActive()) {
        renderWizardStep();
      }
    }
  }

  function setSelectedAudioBundle(bundleId, resourceProfile = null) {
    ensureAudioSetupState();
    state.audio.selectedBundleId = bundleId;
    state.audio.selectedResourceProfile = resourceProfile
      || getAudioRecommendation(bundleId)?.resource_profile
      || getAudioCatalogEntry(bundleId)?.default_resource_profile
      || DEFAULT_AUDIO_RESOURCE_PROFILE;
    state.audio.showAlternatives = false;
    if (isAudioBundleStepActive()) {
      renderWizardStep();
    }
  }

  function setSelectedAudioResourceProfile(resourceProfile) {
    ensureAudioSetupState();
    if (!state.audio.selectedBundleId) {
      return;
    }
    state.audio.selectedResourceProfile = resourceProfile || DEFAULT_AUDIO_RESOURCE_PROFILE;
    if (isAudioBundleStepActive()) {
      renderWizardStep();
    }
  }

  function toggleAudioAlternativeBundles() {
    ensureAudioSetupState();
    state.audio.showAlternatives = !state.audio.showAlternatives;
    renderWizardStep();
  }

  function toggleAdvancedAudioInstaller() {
    ensureAudioSetupState();
    state.audio.showAdvancedInstaller = !state.audio.showAdvancedInstaller;
    renderWizardStep();
  }

  function toggleAudioReadinessReport() {
    ensureAudioSetupState();
    state.audio.showReadiness = !state.audio.showReadiness;
    renderWizardStep();
  }

  async function handleAudioBundleProvision(options = {}) {
    const { safeRerun = false } = options;
    ensureAudioSetupState();

    if (!state.audio.selectedBundleId) {
      setMessage('error', 'Select an audio bundle before provisioning.');
      return;
    }

    state.audio.provisioning = true;
    state.audio.showReadiness = true;
    updateSaveState();
    renderWizardStep();
    setMessage(
      'info',
      safeRerun
        ? 'Rechecking the selected audio bundle and skipping already satisfied steps where possible…'
        : 'Provisioning the selected audio bundle. This may take a while if model downloads are needed.',
    );

    try {
      const response = await fetchJson(`${API_BASE}/audio/provision`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bundle_id: state.audio.selectedBundleId,
          resource_profile: state.audio.selectedResourceProfile || DEFAULT_AUDIO_RESOURCE_PROFILE,
          safe_rerun: safeRerun,
        }),
        timeoutMs: 120000,
      });
      state.audio.lastProvisionResult = response;
      applyInstallStatusSnapshot({
        status: response.status || 'completed',
        steps: Array.isArray(response.steps) ? response.steps : [],
        errors: Array.isArray(response.errors) ? response.errors : [],
      });
      await loadAudioReadiness({ force: true, silent: true });

      if (response.status === 'failed') {
        setMessage('error', 'Audio provisioning failed. Review the bundle steps and remediation report below.');
      } else if (response.status === 'partial') {
        setMessage('info', 'Audio provisioning finished with follow-up actions. Run verification after guided prerequisites are complete.');
      } else {
        setMessage('success', 'Audio bundle provisioning completed. Run verification to confirm readiness.');
      }
    } catch (error) {
      console.error('Failed to provision audio bundle', error);
      setMessage('error', `Unable to provision audio bundle: ${error.message || error}`);
    } finally {
      state.audio.provisioning = false;
      updateSaveState();
      renderWizardStep();
    }
  }

  async function handleAudioBundleVerification() {
    ensureAudioSetupState();

    if (!state.audio.selectedBundleId) {
      setMessage('error', 'Select an audio bundle before running verification.');
      return;
    }

    state.audio.verifying = true;
    state.audio.showReadiness = true;
    updateSaveState();
    renderWizardStep();
    setMessage('info', 'Running audio verification against the selected bundle…');

    try {
      const response = await fetchJson(`${API_BASE}/audio/verify`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          bundle_id: state.audio.selectedBundleId,
          resource_profile: state.audio.selectedResourceProfile || DEFAULT_AUDIO_RESOURCE_PROFILE,
        }),
        timeoutMs: 120000,
      });
      state.audio.lastVerificationResult = response;
      await loadAudioReadiness({ force: true, silent: true });

      if (response.status === 'ready') {
        setMessage('success', 'Audio verification passed. Primary STT and TTS paths are ready.');
      } else if (response.status === 'ready_with_warnings') {
        setMessage('info', 'Audio verification passed with warnings. Review the readiness report for advisory items.');
      } else if (response.status === 'partial') {
        setMessage('info', 'Audio verification found a partial setup. Review the remediation items before relying on speech features.');
      } else {
        setMessage('error', 'Audio verification failed. Review the remediation items before continuing.');
      }
    } catch (error) {
      console.error('Failed to verify audio bundle', error);
      setMessage('error', `Unable to verify audio bundle: ${error.message || error}`);
    } finally {
      state.audio.verifying = false;
      updateSaveState();
      renderWizardStep();
    }
  }

  function describeInstallPlan(plan) {
    if (!plan) {
      return [];
    }

    const summaries = [];

    if (Array.isArray(plan.stt) && plan.stt.length) {
      summaries.push(`STT: ${formatInstallSummary('stt', plan.stt, 'models')}`);
    }

    if (Array.isArray(plan.tts) && plan.tts.length) {
      summaries.push(`TTS: ${formatInstallSummary('tts', plan.tts, 'variants')}`);
    }

    const embeddingSummaries = [];
    if (Array.isArray(plan.embeddings?.huggingface) && plan.embeddings.huggingface.length) {
      embeddingSummaries.push(`huggingface (${plan.embeddings.huggingface.join(', ')})`);
    }
    if (Array.isArray(plan.embeddings?.onnx) && plan.embeddings.onnx.length) {
      embeddingSummaries.push(`onnx (${plan.embeddings.onnx.join(', ')})`);
    }
    if (Array.isArray(plan.embeddings?.custom) && plan.embeddings.custom.length) {
      embeddingSummaries.push(`custom (${plan.embeddings.custom.join(', ')})`);
    }
    if (embeddingSummaries.length) {
      summaries.push(`Embeddings: ${embeddingSummaries.join('; ')}`);
    }

    return summaries;
  }

  function formatInstallSummary(category, entries, variantKey) {
    return entries
      .map((entry) => {
        const label = getInstallOptionLabel(category, entry.engine);
        const variants = Array.isArray(entry[variantKey]) ? entry[variantKey] : [];
        if (!variants.length) {
          return label;
        }
        const variantLabels = variants.map((variantId) => getVariantLabel(category, entry.engine, variantId));
        return `${label} [${variantLabels.join(', ')}]`;
      })
      .join('; ');
  }

  async function bootstrapInstallStatus() {
    const snapshot = await fetchInstallStatusSnapshot();
    if (snapshot) {
      applyInstallStatusSnapshot(snapshot);
      if (shouldPollInstallStatus(snapshot.status)) {
        await startInstallStatusPolling();
      }
      return;
    }

    applyInstallStatusSnapshot(null);
  }

  async function beginInstallStatusMonitoring() {
    state.installStatus.redirectOnComplete = true;
    state.installStatus.active = true;
    updateInstallStatusPanel();
    await startInstallStatusPolling();
  }

  async function fetchInstallStatusSnapshot() {
    try {
      return await fetchJson(`${API_BASE}/install-status`);
    } catch (error) {
      console.warn('Unable to fetch installer status', error);
      return null;
    }
  }

  async function startInstallStatusPolling() {
    await pollInstallStatus();
    const currentStatus = state.installStatus.data?.status;
    if (!shouldPollInstallStatus(currentStatus)) {
      return;
    }

    stopInstallStatusPolling();
    state.installStatus.polling = true;
    installStatusTimer = setInterval(() => {
      pollInstallStatus();
    }, INSTALL_STATUS_POLL_INTERVAL);
  }

  function stopInstallStatusPolling() {
    if (installStatusTimer) {
      clearInterval(installStatusTimer);
      installStatusTimer = null;
    }
    state.installStatus.polling = false;
  }

  async function pollInstallStatus() {
    const snapshot = await fetchInstallStatusSnapshot();
    if (!snapshot) {
      return;
    }
    applyInstallStatusSnapshot(snapshot);
  }

  function applyInstallStatusSnapshot(snapshot) {
    if (snapshot) {
      state.installStatus.data = snapshot;
    } else if (!state.installStatus.redirectOnComplete) {
      state.installStatus.data = null;
    }

    const statusValue = state.installStatus.data?.status || (state.installStatus.redirectOnComplete ? 'in_progress' : 'idle');
    state.installStatus.active = statusValue !== 'idle' || state.installStatus.redirectOnComplete;

    if (!shouldPollInstallStatus(statusValue)) {
      stopInstallStatusPolling();
    }

    updateInstallStatusPanel();

    if (state.installStatus.redirectOnComplete) {
      if (statusValue === 'completed' && !(state.installStatus.data?.errors?.length)) {
        state.installStatus.redirectOnComplete = false;
        setMessage('success', 'Installations finished. Redirecting to quickstart…');
        setTimeout(() => {
          window.location.href = QUICKSTART_URL;
        }, 2000);
      } else if (statusValue === 'failed' || (state.installStatus.data?.errors?.length)) {
        state.installStatus.redirectOnComplete = false;
        setMessage('error', 'Some installation steps failed. Review the details below.');
      }
    }
  }

  function shouldPollInstallStatus(status) {
    return status === 'in_progress';
  }

  function updateInstallStatusPanel() {
    if (!elements.installStatusPanel) {
      return;
    }

    const data = state.installStatus.data;
    const awaiting = state.installStatus.redirectOnComplete;
    const statusValue = data?.status || (awaiting ? 'in_progress' : 'idle');

    if (statusValue === 'idle' && !awaiting) {
      elements.installStatusPanel.hidden = true;
      if (elements.installStatusSteps) {
        elements.installStatusSteps.innerHTML = '';
      }
      if (elements.installStatusErrors) {
        elements.installStatusErrors.hidden = true;
        elements.installStatusErrors.innerHTML = '';
      }
      return;
    }

    elements.installStatusPanel.hidden = false;

    if (elements.installStatusState) {
      const badge = formatInstallStatusBadge(statusValue);
      elements.installStatusState.textContent = badge.label;
      elements.installStatusState.className = `status-badge ${badge.className}`.trim();
    }

    if (elements.installStatusMessage) {
      elements.installStatusMessage.textContent = buildInstallStatusMessage(statusValue, data, awaiting);
    }

    renderInstallStatusSteps(Array.isArray(data?.steps) ? data.steps : [], statusValue);
    renderInstallStatusErrors(Array.isArray(data?.errors) ? data.errors : []);
  }

  function formatInstallStatusBadge(status) {
    switch (status) {
      case 'ready':
      case 'completed':
        return { label: 'Completed', className: 'badge-success' };
      case 'ready_with_warnings':
      case 'partial':
        return { label: 'Needs follow-up', className: 'badge-warning' };
      case 'failed':
        return { label: 'Failed', className: 'badge-failure' };
      case 'in_progress':
        return { label: 'In progress', className: 'badge-info' };
      default:
        return { label: 'Idle', className: 'badge-info' };
    }
  }

  function buildInstallStatusMessage(status, data, awaiting) {
    if (status === 'ready' || status === 'completed') {
      return 'All requested modules were installed successfully.';
    }
    if (status === 'ready_with_warnings' || status === 'partial') {
      return 'Provisioning finished with guided prerequisites or verification follow-up still needed.';
    }
    if (status === 'failed') {
      const count = data?.errors?.length || 0;
      return count
        ? `${count} step${count === 1 ? '' : 's'} failed. Review the details below.`
        : 'Installer reported failures. Review the details below.';
    }
    if (status === 'in_progress') {
      return awaiting && !data?.steps?.length
        ? 'Preparing installation tasks…'
        : 'Installer is downloading and preparing selected modules. Leave this page open until it finishes.';
    }
    return 'Installer idle.';
  }

  function renderInstallStatusSteps(steps, overallStatus) {
    if (!elements.installStatusSteps) {
      return;
    }

    elements.installStatusSteps.innerHTML = '';

    if (!steps.length) {
      const placeholder = document.createElement('li');
      placeholder.className = `install-step ${overallStatus}`;
      placeholder.textContent = overallStatus === 'in_progress'
        ? 'Waiting for installer progress…'
        : 'No installer activity recorded yet.';
      elements.installStatusSteps.appendChild(placeholder);
      return;
    }

    steps.forEach((step) => {
      const item = document.createElement('li');
      const statusClass = step.status || 'pending';
      item.className = `install-step ${statusClass}`;

      const header = document.createElement('div');
      header.className = 'install-step-header';

      const title = document.createElement('span');
      title.className = 'install-step-title';
      title.textContent = describeInstallStepName(step.name);
      header.appendChild(title);

      const statusLabel = document.createElement('span');
      statusLabel.className = `install-step-status ${statusClass}`;
      statusLabel.textContent = formatStepStatusLabel(step.status);
      header.appendChild(statusLabel);

      item.appendChild(header);

      if (step.detail) {
        const detail = document.createElement('p');
        detail.className = 'install-step-detail';
        detail.textContent = step.detail;
        item.appendChild(detail);
      }

      elements.installStatusSteps.appendChild(item);
    });
  }

  function renderInstallStatusErrors(errors) {
    if (!elements.installStatusErrors) {
      return;
    }

    if (!errors.length) {
      elements.installStatusErrors.hidden = true;
      elements.installStatusErrors.innerHTML = '';
      return;
    }

    elements.installStatusErrors.hidden = false;
    elements.installStatusErrors.innerHTML = '';

    const heading = document.createElement('strong');
    heading.textContent = 'Issues detected:';
    elements.installStatusErrors.appendChild(heading);

    const list = document.createElement('ul');
    errors.forEach((error) => {
      const item = document.createElement('li');
      item.textContent = error;
      list.appendChild(item);
    });
    elements.installStatusErrors.appendChild(list);
  }

  function describeInstallStepName(stepName) {
    if (!stepName) {
      return 'Installer';
    }

    const parts = stepName.split(':');
    const [category, identifier, variant] = parts;
    if (category === 'system') {
      return `System prerequisite - ${humaniseKey(identifier)}`;
    }
    if (category === 'deps' && (identifier === 'stt' || identifier === 'tts')) {
      const label = getInstallOptionLabel(identifier, variant) || variant;
      return `${identifier.toUpperCase()} dependencies - ${label}`;
    }
    if (category === 'deps' && identifier === 'embeddings') {
      return `Embeddings dependencies - ${humaniseKey(variant)}`;
    }
    if (category === 'stt' || category === 'tts') {
      const label = getInstallOptionLabel(category, identifier) || identifier;
      return `${category.toUpperCase()} - ${label}`;
    }
    if (category === 'embeddings') {
      if (identifier === 'huggingface') {
        return 'Embeddings - Hugging Face presets';
      }
      if (identifier === 'custom') {
        return 'Embeddings - Custom models';
      }
      if (identifier === 'onnx') {
        return 'Embeddings - ONNX models';
      }
      return `Embeddings - ${identifier}`;
    }
    return stepName.replace(/_/g, ' ');
  }

  function formatStepStatusLabel(status) {
    switch (status) {
      case 'completed':
        return 'Completed';
      case 'failed':
        return 'Failed';
      case 'guided_action_required':
        return 'Needs action';
      case 'skipped':
        return 'Skipped';
      case 'in_progress':
        return 'In progress';
      default:
        return 'Pending';
    }
  }

  function makeInstallId(...parts) {
    return ['install', ...parts.map((part) => String(part))]
      .join('-')
      .replace(/[^a-zA-Z0-9_-]+/g, '-');
  }


  const elements = {};
  let actionsBound = false;
  let wizardActionsBound = false;
  let visibilityActionsBound = false;
  let moduleOverlayActionsBound = false;
  let installStatusTimer = null;
  let walkthroughHighlights = [];

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheElements();
    bindModuleOverlayActions();
    initAssistant();
    hideConfigSection();
    setLoading(true);

    // Watchdog to avoid indefinite "Loading…" if the browser aborts the request
    let initWatchdogFired = false;
    const initWatchdog = setTimeout(() => {
      initWatchdogFired = true;
      setMessage('error', 'Timed out loading setup status. If this repeats, try a different browser or disable extensions, then reload.');
      if (elements.configPath) {
        elements.configPath.textContent = 'Error';
      }
      setLoading(false);
    }, 12000);

    try {
      const status = await fetchJson(`${API_BASE}/status`);
      state.status = status;

      if (!status.enabled) {
        renderDisabledState();
        return;
      }

      if (!status.needs_setup) {
        window.location.href = QUICKSTART_URL;
        return;
      }

      renderStatus(status);
      await loadAudioReadiness({ silent: true });
      initialiseWizard();
      await bootstrapInstallStatus();
    } catch (error) {
      console.error('Setup initialisation failed', error);
      setMessage('error', `Failed to load setup data: ${error.message || error}`);
    } finally {
      clearTimeout(initWatchdog);
      if (!initWatchdogFired) {
        setLoading(false);
      }
    }
  }

  function cacheElements() {
    elements.configSection = document.getElementById('configSection');
    elements.configSections = document.getElementById('configSections');
    elements.configLoading = document.getElementById('configLoading');
    elements.setupRequired = document.getElementById('setupRequired');
    elements.configPath = document.getElementById('configPath');
    elements.placeholderNotice = document.getElementById('placeholderNotice');
    elements.saveButton = document.getElementById('saveChanges');
    elements.completeButton = document.getElementById('completeSetup');
    elements.disableToggle = document.getElementById('disableWizardToggle');
    elements.actionMessage = document.getElementById('actionMessage');
    elements.wizardSection = document.getElementById('guidedWizard');
    elements.wizardContent = document.getElementById('wizardContent');
    elements.wizardProgress = document.getElementById('wizardProgress');
    elements.wizardMessage = document.getElementById('wizardMessage');
    elements.wizardBack = document.getElementById('wizardBack');
    elements.wizardNext = document.getElementById('wizardNext');
    elements.wizardSkip = document.getElementById('wizardSkip');
    elements.wizardSummary = document.getElementById('wizardSummary');
    elements.showAllSections = document.getElementById('showAllSections');
    elements.moduleWalkthroughs = document.getElementById('moduleWalkthroughs');
    elements.moduleWalkthroughList = document.getElementById('moduleWalkthroughList');
    elements.moduleOverlay = document.getElementById('moduleOverlay');
    elements.moduleOverlayTitle = document.getElementById('moduleOverlayTitle');
    elements.moduleOverlayIntro = document.getElementById('moduleOverlayIntro');
    elements.moduleOverlayStep = document.getElementById('moduleOverlayStep');
    elements.moduleOverlayBody = document.getElementById('moduleOverlayBody');
    elements.moduleOverlayBack = document.getElementById('moduleOverlayBack');
    elements.moduleOverlaySkip = document.getElementById('moduleOverlaySkip');
    elements.moduleOverlayNext = document.getElementById('moduleOverlayNext');
    elements.moduleOverlayClose = document.getElementById('moduleOverlayClose');
    elements.assistantRoot = document.getElementById('assistantRoot');
    elements.assistantToggle = document.getElementById('assistantToggle');
    elements.assistantPanel = document.getElementById('assistantPanel');
    elements.assistantMessages = document.getElementById('assistantMessages');
    elements.assistantForm = document.getElementById('assistantForm');
    elements.assistantInput = document.getElementById('assistantInput');
    elements.assistantSend = document.getElementById('assistantSend');
    elements.assistantClose = document.getElementById('assistantClose');
    elements.assistantTyping = document.getElementById('assistantTyping');
    elements.installStatusPanel = document.getElementById('installStatusPanel');
    elements.installStatusState = document.getElementById('installStatusState');
    elements.installStatusMessage = document.getElementById('installStatusMessage');
    elements.installStatusSteps = document.getElementById('installStatusSteps');
    elements.installStatusErrors = document.getElementById('installStatusErrors');
  }

  function hasPendingChanges() {
    return Object.keys(state.dirty).length > 0;
  }

  async function loadConfig() {
    try {
      const data = await fetchJson(`${API_BASE}/config`);
      state.sections = data.sections || [];
      state.configLoaded = true;
      refreshConfigView();
      ensureActionsBound();
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
    hideWizard();
    showConfigSection();
    if (elements.configSections) {
      elements.configSections.innerHTML = `
        <div class="empty-state">
          Guided setup is disabled. Set <code>enable_first_time_setup = true</code> in config.txt to use this page.
        </div>
      `;
    }
    if (elements.saveButton) {
      elements.saveButton.disabled = true;
    }
    if (elements.completeButton) {
      elements.completeButton.disabled = true;
    }
    setMessage('info', 'Setup wizard disabled via config.txt.');
  }

  function renderSections(sections) {
    const container = elements.configSections;
    if (!container) return;
    container.innerHTML = '';

    const hiddenNames = [];

    sections.forEach((section) => {
      const hasGuidedView = !!state.visibleSections;
      const isRecommended = !state.visibleSections || state.visibleSections.has(section.name);
      const isAdditional = !!state.visibleSections && !state.visibleSections.has(section.name);

      if (isAdditional) {
        hiddenNames.push(section.name);
      }

      if (isAdditional && !state.showHiddenSections) {
        return;
      }

      const details = document.createElement('details');
      details.className = 'section-card';
      if (isAdditional) {
        details.classList.add('wizard-additional');
      }
      details.open = shouldExpandSection(section, isRecommended);
      const sectionSlug = section.name.replace(/[^A-Za-z0-9_-]/g, '-');
      details.dataset.sectionName = section.name;
      details.id = `setup-section-${sectionSlug}`;

      const summary = document.createElement('summary');
      summary.className = 'section-summary';
      const summaryTitle = document.createElement('span');
      summaryTitle.className = 'section-title';
      summaryTitle.textContent = section.label || section.name;
      summary.appendChild(summaryTitle);

      if (hasGuidedView && isRecommended) {
        const badge = document.createElement('span');
        badge.className = 'section-pill recommended';
        badge.textContent = 'Recommended';
        summary.appendChild(badge);
      } else if (hasGuidedView && isAdditional) {
        const badge = document.createElement('span');
        badge.className = 'section-pill optional';
        badge.textContent = 'Additional';
        summary.appendChild(badge);
      }
      details.appendChild(summary);

      const content = document.createElement('div');
      content.className = 'section-content';

      const infoPanel = document.createElement('div');
      infoPanel.className = 'section-info';

      const infoTitle = document.createElement('h4');
      infoTitle.className = 'section-info-title';
      infoTitle.textContent = `About ${section.label || section.name}`;
      infoPanel.appendChild(infoTitle);

      const infoBody = document.createElement('p');
      infoBody.className = 'section-info-body';
      infoBody.textContent = getSectionDescription(section);
      infoPanel.appendChild(infoBody);

      const highlights = getSectionHighlights(section.name, section.fields);
      if (highlights.length) {
        const highlightList = document.createElement('ul');
        highlightList.className = 'section-info-list';
        highlights.forEach((item) => {
          const li = document.createElement('li');
          li.textContent = item;
          highlightList.appendChild(li);
        });
        infoPanel.appendChild(highlightList);
      }

      const placeholdersCount = (section.fields || []).filter((field) => field.placeholder).length;
      if (placeholdersCount > 0) {
        const placeholderNote = document.createElement('p');
        placeholderNote.className = 'section-info-note';
        placeholderNote.textContent = `${placeholdersCount} value${placeholdersCount === 1 ? '' : 's'} still use placeholder defaults.`;
        infoPanel.appendChild(placeholderNote);
      }

      content.appendChild(infoPanel);

      const fieldsWrapper = document.createElement('div');
      fieldsWrapper.className = 'fields-wrapper';

      section.fields.forEach((field) => {
        fieldsWrapper.appendChild(renderField(section.name, field));
      });

      content.appendChild(fieldsWrapper);
      details.appendChild(content);
      container.appendChild(details);
    });

    state.hiddenSections = hiddenNames;
    updateVisibilityControls();
  }

  function getSectionDescription(section) {
    const fallback = SECTION_INFO_DESCRIPTIONS[section.name];
    const computed = section.description || fallback || `Configuration options for ${section.label || section.name}.`;
    return computed;
  }

  function getSectionLabelByName(sectionName) {
    const match = state.sections.find((entry) => entry.name === sectionName);
    return match?.label || sectionName;
  }

  function getSectionHighlights(sectionName, fields) {
    const highlights = [];
    const authChoice = state.wizard.answers?.auth;
    if (sectionName === 'AuthNZ' && authChoice === 'single_user') {
      highlights.push('Using single-user API key mode (great for local installs).');
    }
    if (sectionName === 'AuthNZ' && authChoice === 'multi_user') {
      highlights.push('Multi-user authentication enabled for team access.');
    }
    if (sectionName === 'Database' && authChoice === 'multi_user') {
      highlights.push('Needed for multi-user deployments to manage shared data.');
    }

    const features = state.wizard.answers?.features || [];
    features.forEach((feature) => {
      const mappedSections = FEATURE_SECTION_MAP[feature] || [];
      if (mappedSections.includes(sectionName)) {
        highlights.push(`Supports: ${getWizardOptionLabel('features', feature)}`);
      }
    });
    const selectedAudioBundle = getSelectedAudioBundle();
    if (selectedAudioBundle && sectionName === 'STT-Settings' && Array.isArray(selectedAudioBundle.stt_plan)) {
      const sttEngines = summarizeAudioPlanEntries('stt', selectedAudioBundle.stt_plan, 'models');
      if (sttEngines.length) {
        highlights.push(`Audio bundle default STT: ${sttEngines.join(', ')}`);
      }
    }
    if (selectedAudioBundle && sectionName === 'TTS-Settings' && Array.isArray(selectedAudioBundle.tts_plan)) {
      const ttsEngines = summarizeAudioPlanEntries('tts', selectedAudioBundle.tts_plan, 'variants');
      if (ttsEngines.length) {
        highlights.push(`Audio bundle default TTS: ${ttsEngines.join(', ')}`);
      }
    }
    if (selectedAudioBundle && sectionName === 'Processing') {
      const readiness = getSelectedAudioReadiness();
      highlights.push(`Selected audio bundle: ${selectedAudioBundle.label}`);
      if (readiness?.status) {
        highlights.push(`Audio readiness: ${humaniseKey(readiness.status)}`);
      }
    }
    const installPlan = buildInstallPlan();
    if (installPlan?.stt?.length && sectionName === 'STT-Settings') {
      const engines = installPlan.stt.map((entry) => getInstallOptionLabel('stt', entry.engine));
      highlights.push(`Installing STT engines: ${engines.join(', ')}`);
    }
    if (installPlan?.tts?.length && sectionName === 'TTS-Settings') {
      const engines = installPlan.tts.map((entry) => getInstallOptionLabel('tts', entry.engine));
      highlights.push(`Installing TTS engines: ${engines.join(', ')}`);
    }
    if (installPlan?.stt?.length && sectionName === 'Processing') {
      highlights.push('Audio processing tuned for newly installed transcription pipelines.');
    }
    if (installPlan?.tts?.length && sectionName === 'Processing') {
      highlights.push('Consider adjusting streaming buffers for new TTS providers.');
    }
    if (installPlan?.embeddings?.huggingface?.length && sectionName === 'Embeddings') {
      highlights.push(`Pre-downloading embeddings: ${installPlan.embeddings.huggingface.join(', ')}`);
    }
    if (installPlan?.embeddings?.custom?.length && sectionName === 'Embeddings') {
      highlights.push(`Custom trusted models added: ${installPlan.embeddings.custom.join(', ')}`);
    }
    if (installPlan?.embeddings && (installPlan.embeddings.huggingface?.length || installPlan.embeddings.custom?.length) && sectionName === 'RAG') {
      highlights.push('RAG retrieval ready once install tasks finish.');
    }
    if (installPlan?.embeddings && (installPlan.embeddings.huggingface?.length || installPlan.embeddings.custom?.length) && sectionName === 'API') {
      highlights.push('Remember to add API keys for any remote embedding providers.');
    }
    const datastore = state.wizard.answers?.datastore;
    if (sectionName === 'Database' && datastore === 'postgres') {
      highlights.push('Configure PostgreSQL connection details before running migrations.');
    }
    if (sectionName === 'Database' && datastore === 'sqlite') {
      highlights.push('Using SQLite for the primary content store (default local setup).');
    }

    return highlights;
  }

  function initialiseWizard() {
    if (!elements.wizardSection) {
      skipWizard(true);
      return;
    }

    state.wizard.active = true;
    state.wizard.currentStep = 0;
    state.wizard.answers = {};
    state.wizard.completed = false;
    state.wizard.skipped = false;
    state.visibleSections = null;
    state.showHiddenSections = false;
    state.recommendedSections = new Set();

    resetInstallSelections();
    resetAudioSetupState({ preserveReadiness: true });

    elements.wizardSection.hidden = false;
    elements.wizardSkip.hidden = false;
    if (elements.wizardSummary) {
      elements.wizardSummary.hidden = true;
    }
    bindWizardActions();
    bindVisibilityActions();
    renderWizardStep();
  }

  function renderWizardStep() {
    // Clean up any per-step intervals before re-rendering
    try { stopKokoroEspeakAutoRefresh(); } catch (_) {}
    const step = WIZARD_STEPS[state.wizard.currentStep];
    if (!step || !elements.wizardContent) {
      return;
    }

    clearMessage();
    clearWizardMessage();
    elements.wizardContent.innerHTML = '';
    elements.wizardBack.disabled = state.wizard.currentStep === 0;
    elements.wizardNext.textContent = step.type === 'summary' ? 'Open configuration' : 'Next';
    elements.wizardSkip.hidden = step.type === 'summary';

    updateWizardProgress(step);
    ensureInstallState();

    if (step.type === 'summary') {
      const heading = renderWizardSummary();
      focusWizardHeading(heading);
      return;
    }

    if (step.type === 'module') {
      const heading = renderBackendConfigStep(step);
      focusWizardHeading(heading);
      return;
    }

    if (step.id === 'datastore' && !state.wizard.answers.datastore) {
      state.wizard.answers.datastore = 'sqlite';
    }

    const heading = renderWizardQuestionStep(step);
    focusWizardHeading(heading);
  }

  function renderWizardQuestionStep(step) {
    const fragment = document.createDocumentFragment();

    const title = document.createElement('h3');
    title.className = 'wizard-step-title';
    title.id = `wizard-step-${step.id}`;
    title.textContent = step.title;
    fragment.appendChild(title);

    let descriptionId;
    if (step.description) {
      const description = document.createElement('p');
      description.className = 'wizard-step-description';
      description.id = `wizard-step-${step.id}-description`;
      description.textContent = step.description;
      fragment.appendChild(description);
      descriptionId = description.id;
    }

    const fieldset = document.createElement('fieldset');
    fieldset.className = 'wizard-options';
    fieldset.setAttribute('aria-labelledby', title.id);
    if (descriptionId) {
      fieldset.setAttribute('aria-describedby', descriptionId);
    }

    const legend = document.createElement('legend');
    legend.className = 'sr-only';
    legend.textContent = step.title;
    fieldset.appendChild(legend);

    step.options.forEach((option) => {
      fieldset.appendChild(createWizardOption(step, option));
    });

    fragment.appendChild(fieldset);
    elements.wizardContent.appendChild(fragment);
    updateWizardOptionStyles(step.id);
  return title;
}

function renderBackendConfigStep(step) {
  ensureInstallState();
  ensureAudioSetupState();

  const fragment = document.createDocumentFragment();
  const title = document.createElement('h3');
  title.className = 'wizard-step-title';
  title.id = `wizard-step-${step.id}`;
  title.textContent = step.title;
  fragment.appendChild(title);

  let descriptionId;
  if (step.description) {
    const description = document.createElement('p');
    description.className = 'wizard-step-description';
    description.id = `wizard-step-${step.id}-description`;
    description.textContent = step.description;
    fragment.appendChild(description);
    descriptionId = description.id;
  }

  const container = document.createElement('div');
  container.className = 'install-sections';
  fragment.appendChild(container);

  const selectedBackends = new Set(state.wizard.answers.backends || []);
  const shouldShowAudioBundles = audioBundleRequested();
  pruneInstallSelectionsForBackends(selectedBackends);

  if (!selectedBackends.size && !shouldShowAudioBundles) {
    const empty = document.createElement('p');
    empty.className = 'install-empty';
    empty.textContent = 'Select a backend module on the previous step to see installation options.';
    container.appendChild(empty);
  } else {
    if (shouldShowAudioBundles) {
      container.appendChild(renderAudioBundleSection());
    }

    ['stt', 'tts', 'embeddings'].forEach((category) => {
      if (!selectedBackends.has(category)) {
        return;
      }
      if (
        shouldShowAudioBundles
        && (category === 'stt' || category === 'tts')
        && !state.audio.showAdvancedInstaller
      ) {
        return;
      }
      const catalog = INSTALL_TARGETS[category];
      if (!catalog) {
        return;
      }

      const section = document.createElement('section');
      section.className = 'install-section';
      section.dataset.category = category;

      const header = document.createElement('div');
      header.className = 'install-section-header';
      const heading = document.createElement('h4');
      heading.textContent = catalog.label;
      header.appendChild(heading);
      section.appendChild(header);

      if (catalog.description) {
        const blurb = document.createElement('p');
        blurb.className = 'install-section-description';
        blurb.textContent = (
          shouldShowAudioBundles
          && (category === 'stt' || category === 'tts')
          && state.audio.showAdvancedInstaller
        )
          ? `${catalog.description} Advanced fallback only; the curated bundle above is the default path.`
          : catalog.description;
        section.appendChild(blurb);
      }

      if (category === 'embeddings') {
        section.appendChild(renderEmbeddingInstallOptions());
      } else {
        const list = document.createElement('div');
        list.className = 'install-option-list';
        catalog.options.forEach((option) => {
          list.appendChild(renderInstallOptionCard(category, option));
        });
        section.appendChild(list);
      }

      container.appendChild(section);
    });
  }

  elements.wizardContent.appendChild(fragment);
  return title;
}

function renderInstallOptionCard(category, option) {
  const card = document.createElement('div');
  card.className = 'install-option-card';

  const header = document.createElement('div');
  header.className = 'install-option-header';

  const checkboxId = makeInstallId(category, option.id);
  const checkbox = document.createElement('input');
  checkbox.type = 'checkbox';
  checkbox.id = checkboxId;
  checkbox.checked = isEngineSelected(category, option.id);
  checkbox.addEventListener('change', (event) => {
    setEngineSelection(category, option.id, event.target.checked);
    renderWizardStep();
  });
  header.appendChild(checkbox);

  const label = document.createElement('label');
  label.className = 'install-option-label';
  label.setAttribute('for', checkboxId);
  label.textContent = option.label;
  header.appendChild(label);

  card.appendChild(header);

  if (option.hint) {
    const hint = document.createElement('p');
    hint.className = 'install-option-hint';
    hint.textContent = option.hint;
    card.appendChild(hint);
  }

  // Kokoro: show eSpeak detection badge using the audio health endpoint
  try {
    if (category === 'tts' && option && option.id === 'kokoro') {
      const badge = document.createElement('span');
      badge.id = 'kokoro-espeak-badge';
      badge.className = 'status-badge badge-info';
      badge.textContent = 'eSpeak: …';
      badge.style.marginLeft = '8px';
      header.appendChild(badge);
      // Async update
      updateKokoroEspeakBadge(badge).catch(() => {});
      // Start auto-refresh every ~10s while this step is visible
      startKokoroEspeakAutoRefresh(badge, 10000);
      // Manual refresh button
      const rbtn = document.createElement('button');
      rbtn.type = 'button';
      rbtn.className = 'btn btn-sm btn-secondary';
      rbtn.title = 'Refresh eSpeak status';
      rbtn.style.marginLeft = '6px';
      rbtn.innerHTML = '<i class="icon-refresh"></i>';
      rbtn.addEventListener('click', (ev) => { ev.preventDefault(); updateKokoroEspeakBadge(badge).catch(() => {}); });
      header.appendChild(rbtn);
    }
  } catch (_) { /* ignore */ }

  if (checkbox.checked && Array.isArray(option.variants) && option.variants.length) {
    card.appendChild(renderVariantGroup(category, option));
  }

  return card;
}

async function updateKokoroEspeakBadge(badgeEl) {
  if (!badgeEl) return;
  try {
    // Cache to avoid hammering the endpoint if re-rendered rapidly
    const now = Date.now();
    const cacheMs = 8000;
    if (!state._audioHealthCache) state._audioHealthCache = { t: 0, data: null };
    let health = state._audioHealthCache.data;
    if (!health || (now - state._audioHealthCache.t) > cacheMs) {
      health = await fetchJson('/api/v1/audio/health', { cache: 'no-store', timeoutMs: 6000 });
      state._audioHealthCache = { t: now, data: health };
    }
    const kok = (health && health.providers && (health.providers.details || {}).kokoro) || {};
    const ok = !!kok.espeak_lib_exists;
    const path = kok.espeak_lib_env || '';
    badgeEl.classList.remove('badge-info', 'badge-success', 'badge-alert');
    badgeEl.classList.add(ok ? 'badge-success' : 'badge-alert');
    badgeEl.textContent = ok ? 'eSpeak detected' : 'eSpeak not found';
    badgeEl.title = ok ? (path ? `PHONEMIZER_ESPEAK_LIBRARY=${path}` : 'Detected via system library search') : 'Install espeak-ng. Env var only needed for non-standard paths.';
  } catch (e) {
    try { badgeEl.classList.remove('badge-success', 'badge-alert'); badgeEl.classList.add('badge-warning'); } catch (_) {}
    try { badgeEl.textContent = 'eSpeak status: unknown'; } catch (_) {}
  }
}

function startKokoroEspeakAutoRefresh(badgeEl, intervalMs = 10000) {
  try { stopKokoroEspeakAutoRefresh(); } catch (_) {}
  try {
    state._kokoroEspeakTimer = setInterval(() => {
      updateKokoroEspeakBadge(badgeEl).catch(() => {});
    }, Math.max(4000, intervalMs|0));
  } catch (_) {}
}

function stopKokoroEspeakAutoRefresh() {
  try {
    if (state._kokoroEspeakTimer) {
      clearInterval(state._kokoroEspeakTimer);
      state._kokoroEspeakTimer = null;
    }
  } catch (_) {}
}

function renderVariantGroup(category, option) {
  const wrapper = document.createElement('div');
  wrapper.className = 'install-variant-group';

  if (option.variantsLabel) {
    const legend = document.createElement('p');
    legend.className = 'install-variant-label';
    legend.textContent = option.variantsLabel;
    wrapper.appendChild(legend);
  }

  const selection = getEngineSelection(category, option.id);
  const selectedVariants = new Set(selection?.variants || []);

  option.variants.forEach((variant) => {
    const variantId = makeInstallId(category, option.id, variant.id);
    const row = document.createElement('label');
    row.className = 'install-variant';

    const checkbox = document.createElement('input');
    checkbox.type = 'checkbox';
    checkbox.id = variantId;
    checkbox.checked = selectedVariants.has(variant.id);
    checkbox.addEventListener('change', (event) => {
      toggleVariantSelection(category, option.id, variant.id, event.target.checked);
      renderWizardStep();
    });
    row.appendChild(checkbox);

    const text = document.createElement('span');
    text.textContent = variant.label;
    row.appendChild(text);

    wrapper.appendChild(row);
  });

  return wrapper;
}

function renderEmbeddingInstallOptions() {
  ensureInstallState();

  const wrapper = document.createElement('div');
  wrapper.className = 'install-embeddings';

  const presets = getEmbeddingPresetOptions();
  if (presets.length) {
    const presetList = document.createElement('div');
    presetList.className = 'install-option-list install-embedding-presets';

    presets.forEach((modelId) => {
      const checkboxId = makeInstallId('embeddings', 'huggingface', modelId);
      const row = document.createElement('label');
      row.className = 'install-option';

      const checkbox = document.createElement('input');
      checkbox.type = 'checkbox';
      checkbox.id = checkboxId;
      checkbox.checked = state.install.embeddings.huggingface.includes(modelId);
      checkbox.addEventListener('change', (event) => {
        toggleEmbeddingPreset(modelId, event.target.checked);
      });
      row.appendChild(checkbox);

      const text = document.createElement('span');
      text.textContent = modelId;
      row.appendChild(text);

      presetList.appendChild(row);
    });

    wrapper.appendChild(presetList);
  } else {
    const note = document.createElement('p');
    note.className = 'install-empty';
    note.textContent = 'No trusted HuggingFace models detected yet.';
    wrapper.appendChild(note);
  }

  const customLabel = document.createElement('label');
  customLabel.className = 'install-custom-label';
  customLabel.setAttribute('for', 'install-embeddings-custom');
  customLabel.textContent = 'Custom trusted models (one per line)';
  wrapper.appendChild(customLabel);

  const textarea = document.createElement('textarea');
  textarea.id = 'install-embeddings-custom';
  textarea.className = 'install-custom-textarea';
  textarea.rows = 4;
  textarea.placeholder = 'e.g. sentence-transformers/gte-large';
  textarea.value = getCustomEmbeddingInputValue();
  textarea.addEventListener('input', (event) => {
    setCustomEmbeddingModelsFromInput(event.target.value);
  });
  wrapper.appendChild(textarea);

  const helper = document.createElement('p');
  helper.className = 'install-custom-hint';
  helper.textContent = 'These repositories will be added to the trusted list and downloaded after setup completes.';
  wrapper.appendChild(helper);

  return wrapper;
}

function renderAudioBundleSection() {
  ensureAudioSetupState();

  if (!state.audio.loaded && !state.audio.loading) {
    loadAudioRecommendations().catch(() => {});
  }
  if (!state.audio.readinessLoaded && !state.audio.readinessLoading) {
    loadAudioReadiness({ silent: true }).catch(() => {});
  }

  const section = document.createElement('section');
  section.className = 'install-section audio-bundle-stage';

  const header = document.createElement('div');
  header.className = 'install-section-header';

  const heading = document.createElement('h4');
  heading.textContent = 'Recommended audio bundle';
  header.appendChild(heading);

  const selectedReadiness = getSelectedAudioReadiness();
  if (selectedReadiness?.status) {
    const badge = document.createElement('span');
    const statusMeta = formatAudioReadinessBadge(selectedReadiness.status);
    badge.className = `status-badge ${statusMeta.className}`;
    badge.textContent = statusMeta.label;
    header.appendChild(badge);
  }

  section.appendChild(header);

  const intro = document.createElement('p');
  intro.className = 'install-section-description';
  intro.textContent = 'Use the curated bundle path for first-run speech setup. Advanced engine picking remains available below as a fallback.';
  section.appendChild(intro);

  if (state.audio.machineProfile) {
    section.appendChild(renderAudioMachineProfile(state.audio.machineProfile));
  }

  const selectedRecommendation = getSelectedAudioRecommendation();
  const recommendedRecommendation = getRecommendedAudioRecommendation();
  const selectedBundle = getSelectedAudioBundle();
  const selectedProfile = getSelectedAudioProfile();

  if (state.audio.loading && !selectedRecommendation) {
    const note = document.createElement('p');
    note.className = 'audio-stage-note';
    note.textContent = 'Checking local hardware and ranking curated audio bundles…';
    section.appendChild(note);
  } else if (state.audio.error && !selectedRecommendation) {
    const note = document.createElement('div');
    note.className = 'status-notice';
    note.textContent = `Unable to load audio bundle recommendations: ${state.audio.error}`;

    const retryButton = document.createElement('button');
    retryButton.type = 'button';
    retryButton.className = 'btn subtle';
    retryButton.textContent = 'Retry recommendations';
    retryButton.addEventListener('click', () => {
      loadAudioRecommendations({ force: true }).catch(() => {});
    });
    note.appendChild(document.createTextNode(' '));
    note.appendChild(retryButton);
    section.appendChild(note);
  } else if (selectedRecommendation) {
    const card = renderAudioBundleCard(selectedRecommendation, {
      selected: true,
      recommended: selectedRecommendation.selection_key === recommendedRecommendation?.selection_key,
    });
    section.appendChild(card);

    if (selectedBundle) {
      section.appendChild(renderAudioProfileSelector(selectedBundle, {
        selectedProfileId: selectedProfile?.profile_id || state.audio.selectedResourceProfile,
        recommendedProfileId: recommendedRecommendation?.bundle_id === selectedBundle.bundle_id
          ? recommendedRecommendation?.resource_profile
          : selectedBundle.default_resource_profile,
      }));
    }
  } else {
    const note = document.createElement('p');
    note.className = 'audio-stage-note';
    note.textContent = 'No compatible audio bundles were ranked for this machine yet. You can still use the advanced engine picker.';
    section.appendChild(note);
  }

  if (state.audio.showAlternatives) {
    const seenBundles = new Set();
    const alternatives = state.audio.recommendations.filter((entry) => {
      if (entry.bundle_id === selectedRecommendation?.bundle_id) {
        return false;
      }
      if (seenBundles.has(entry.bundle_id)) {
        return false;
      }
      seenBundles.add(entry.bundle_id);
      return true;
    });
    if (alternatives.length) {
      const altHeading = document.createElement('p');
      altHeading.className = 'audio-stage-note';
      altHeading.textContent = 'Alternative bundles';
      section.appendChild(altHeading);

      const grid = document.createElement('div');
      grid.className = 'audio-bundle-alt-grid';
      alternatives.forEach((entry) => {
        grid.appendChild(renderAudioBundleCard(entry, {
          compact: true,
          recommended: entry.selection_key === recommendedRecommendation?.selection_key,
        }));
      });
      section.appendChild(grid);
    }
  }

  if (state.audio.excluded.length) {
    const excluded = document.createElement('p');
    excluded.className = 'audio-stage-note';
    excluded.textContent = `Unavailable bundles: ${state.audio.excluded.map((entry) => entry.bundle?.label || entry.bundle_id).join(', ')}`;
    section.appendChild(excluded);
  }

  const actions = document.createElement('div');
  actions.className = 'audio-bundle-actions';

  const provisionButton = document.createElement('button');
  provisionButton.type = 'button';
  provisionButton.className = 'btn primary';
  provisionButton.disabled = !selectedRecommendation || state.audio.provisioning || state.audio.verifying;
  provisionButton.textContent = state.audio.provisioning
    ? 'Provisioning bundle…'
    : (selectedRecommendation?.bundle_id === recommendedRecommendation?.bundle_id
      ? 'Provision recommended bundle'
      : 'Provision selected bundle');
  provisionButton.addEventListener('click', () => {
    handleAudioBundleProvision().catch(() => {});
  });
  actions.appendChild(provisionButton);

  const chooseButton = document.createElement('button');
  chooseButton.type = 'button';
  chooseButton.className = 'btn subtle';
  chooseButton.disabled = state.audio.loading || state.audio.provisioning;
  chooseButton.textContent = state.audio.showAlternatives ? 'Hide alternatives' : 'Choose different bundle';
  chooseButton.addEventListener('click', toggleAudioAlternativeBundles);
  actions.appendChild(chooseButton);

  const verifyButton = document.createElement('button');
  verifyButton.type = 'button';
  verifyButton.className = 'btn subtle';
  verifyButton.disabled = !selectedRecommendation || state.audio.verifying || state.audio.provisioning;
  verifyButton.textContent = state.audio.verifying ? 'Running verification…' : 'Run verification';
  verifyButton.addEventListener('click', () => {
    handleAudioBundleVerification().catch(() => {});
  });
  actions.appendChild(verifyButton);

  const rerunButton = document.createElement('button');
  rerunButton.type = 'button';
  rerunButton.className = 'btn subtle';
  rerunButton.disabled = !selectedRecommendation || state.audio.provisioning || state.audio.verifying;
  rerunButton.textContent = 'Safe rerun';
  rerunButton.addEventListener('click', () => {
    handleAudioBundleProvision({ safeRerun: true }).catch(() => {});
  });
  actions.appendChild(rerunButton);

  const readinessButton = document.createElement('button');
  readinessButton.type = 'button';
  readinessButton.className = 'btn subtle';
  readinessButton.textContent = state.audio.showReadiness ? 'Hide readiness report' : 'View readiness report';
  readinessButton.addEventListener('click', toggleAudioReadinessReport);
  actions.appendChild(readinessButton);

  const advancedButton = document.createElement('button');
  advancedButton.type = 'button';
  advancedButton.className = 'btn subtle';
  advancedButton.textContent = state.audio.showAdvancedInstaller
    ? 'Hide advanced engine picker'
    : 'Show advanced engine picker';
  advancedButton.addEventListener('click', toggleAdvancedAudioInstaller);
  actions.appendChild(advancedButton);

  section.appendChild(actions);

  if (state.audio.showAdvancedInstaller) {
    const advancedNote = document.createElement('p');
    advancedNote.className = 'audio-stage-note';
    advancedNote.textContent = 'Advanced mode is open below. Use it only if the curated bundle does not fit this machine.';
    section.appendChild(advancedNote);
  }

  if (state.audio.showReadiness) {
    section.appendChild(renderAudioReadinessReport());
  }

  return section;
}

function renderAudioMachineProfile(profile) {
  const wrapper = document.createElement('div');
  wrapper.className = 'audio-profile-summary';

  const title = document.createElement('p');
  title.className = 'audio-profile-title';
  title.textContent = 'Detected machine profile';
  wrapper.appendChild(title);

  const chips = document.createElement('div');
  chips.className = 'audio-profile-chips';
  chips.appendChild(createAudioProfileChip(`${humaniseKey(profile.platform)} / ${profile.arch}`));
  chips.appendChild(createAudioProfileChip(profile.cuda_available ? 'CUDA detected' : 'CPU only'));
  chips.appendChild(createAudioProfileChip(profile.apple_silicon ? 'Apple Silicon' : 'Non-Apple Silicon'));
  chips.appendChild(createAudioProfileChip(profile.ffmpeg_available ? 'FFmpeg present' : 'FFmpeg needed'));
  chips.appendChild(createAudioProfileChip(profile.espeak_available ? 'eSpeak present' : 'eSpeak needed'));
  chips.appendChild(createAudioProfileChip(`Free disk ${profile.free_disk_gb} GB`));
  chips.appendChild(createAudioProfileChip(
    profile.network_available_for_downloads ? 'Downloads available' : 'Offline downloads disabled',
  ));
  wrapper.appendChild(chips);
  return wrapper;
}

function createAudioProfileChip(label) {
  const chip = document.createElement('span');
  chip.className = 'audio-profile-chip';
  chip.textContent = label;
  return chip;
}

function renderAudioProfileSelector(bundle, options = {}) {
  const {
    selectedProfileId = bundle?.default_resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE,
    recommendedProfileId = bundle?.default_resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE,
  } = options;

  const profiles = getAudioBundleResourceProfiles(bundle);
  const wrapper = document.createElement('div');
  wrapper.className = 'audio-resource-profile-panel';

  const header = document.createElement('div');
  header.className = 'audio-resource-profile-header';

  const heading = document.createElement('p');
  heading.className = 'audio-resource-profile-title';
  heading.textContent = 'Recommended profile';
  header.appendChild(heading);

  const note = document.createElement('span');
  note.className = 'audio-resource-profile-note';
  note.textContent = 'Choose the speech footprint that fits this machine.';
  header.appendChild(note);
  wrapper.appendChild(header);

  const grid = document.createElement('div');
  grid.className = 'audio-resource-profile-grid';

  profiles.forEach((profile) => {
    const card = document.createElement('button');
    card.type = 'button';
    card.className = 'audio-resource-profile-card';
    if (profile.profile_id === selectedProfileId) {
      card.classList.add('selected');
    }
    if (profile.profile_id === recommendedProfileId) {
      card.classList.add('recommended');
    }

    const titleRow = document.createElement('div');
    titleRow.className = 'audio-resource-profile-card-header';

    const title = document.createElement('span');
    title.className = 'audio-resource-profile-card-title';
    title.textContent = getAudioProfileLabel(profile.profile_id, profile.label);
    titleRow.appendChild(title);

    if (profile.profile_id === recommendedProfileId) {
      const badge = document.createElement('span');
      badge.className = 'status-badge badge-success';
      badge.textContent = 'Recommended';
      titleRow.appendChild(badge);
    }

    card.appendChild(titleRow);

    const description = document.createElement('p');
    description.className = 'audio-resource-profile-card-description';
    description.textContent = profile.description || 'Curated speech profile.';
    card.appendChild(description);

    const meta = document.createElement('div');
    meta.className = 'audio-resource-profile-meta';
    if (profile.resource_class) {
      meta.appendChild(createAudioProfileChip(`Class ${humaniseKey(profile.resource_class)}`));
    }
    if (profile.estimated_disk_gb) {
      meta.appendChild(createAudioProfileChip(`~${profile.estimated_disk_gb} GB`));
    }
    card.appendChild(meta);

    card.addEventListener('click', () => {
      setSelectedAudioResourceProfile(profile.profile_id);
    });
    grid.appendChild(card);
  });

  wrapper.appendChild(grid);
  return wrapper;
}

function renderAudioBundleCard(recommendation, options = {}) {
  const {
    selected = false,
    recommended = false,
    compact = false,
  } = options;
  const bundle = getAudioCatalogEntry(recommendation.bundle_id) || recommendation.bundle || {};
  const profile = (
    recommendation.profile
    || bundle.resource_profiles?.[recommendation.resource_profile]
    || bundle.resource_profiles?.[bundle.default_resource_profile]
    || null
  );
  const card = document.createElement('article');
  card.className = 'audio-bundle-card';
  if (selected) {
    card.classList.add('selected');
  }
  if (recommended) {
    card.classList.add('recommended');
  }
  if (compact) {
    card.classList.add('compact');
  }

  const header = document.createElement('div');
  header.className = 'audio-bundle-card-header';

  const titleBlock = document.createElement('div');
  const title = document.createElement('h5');
  title.className = 'audio-bundle-card-title';
  title.textContent = bundle.label || recommendation.label || recommendation.bundle_id;
  titleBlock.appendChild(title);

  const description = document.createElement('p');
  description.className = 'audio-bundle-card-description';
  description.textContent = bundle.description || 'Curated audio setup bundle.';
  titleBlock.appendChild(description);

  if (profile) {
    const profileLine = document.createElement('p');
    profileLine.className = 'audio-bundle-card-profile';
    profileLine.textContent = `${getAudioProfileLabel(profile.profile_id, profile.label)} profile`;
    titleBlock.appendChild(profileLine);
  }
  header.appendChild(titleBlock);

  const badges = document.createElement('div');
  badges.className = 'audio-bundle-card-badges';
  if (recommended) {
    const recommendedBadge = document.createElement('span');
    recommendedBadge.className = 'status-badge badge-success';
    recommendedBadge.textContent = 'Recommended';
    badges.appendChild(recommendedBadge);
  }
  if (selected) {
    const selectedBadge = document.createElement('span');
    selectedBadge.className = 'status-badge badge-info';
    selectedBadge.textContent = 'Selected';
    badges.appendChild(selectedBadge);
  }
  const offlineBadge = document.createElement('span');
  offlineBadge.className = `status-badge ${bundle.offline_runtime_supported ? 'badge-success' : 'badge-warning'}`;
  offlineBadge.textContent = bundle.offline_runtime_supported ? 'Offline runtime ready' : 'Hosted fallback capable';
  badges.appendChild(offlineBadge);
  header.appendChild(badges);
  card.appendChild(header);

  if (Array.isArray(recommendation.reasons) && recommendation.reasons.length) {
    const reasons = document.createElement('ul');
    reasons.className = 'audio-bundle-reasons';
    recommendation.reasons.forEach((reason) => {
      const item = document.createElement('li');
      item.textContent = reason;
      reasons.appendChild(item);
    });
    card.appendChild(reasons);
  }

  const planSummary = buildAudioBundlePlanSummary(bundle, profile);
  if (planSummary.length) {
    const summary = document.createElement('div');
    summary.className = 'audio-bundle-meta';
    planSummary.forEach((entry) => {
      const item = document.createElement('span');
      item.className = 'audio-bundle-meta-item';
      item.textContent = entry;
      summary.appendChild(item);
    });
    card.appendChild(summary);
  }

  if (!compact) {
    const automaticSteps = [
      ...(bundle.system_prerequisites || []).filter((step) => step.automation_tier === 'automatic'),
      ...(bundle.python_dependencies || []),
      ...(bundle.model_assets || []),
    ];
    const guidedSteps = [
      ...(bundle.system_prerequisites || []).filter((step) => step.automation_tier !== 'automatic'),
    ];

    appendAudioAutomationGroup(card, 'Automatic steps', automaticSteps);
    appendAudioAutomationGroup(card, 'Guided prerequisites', guidedSteps);
  }

  if (compact) {
    const action = document.createElement('button');
    action.type = 'button';
    action.className = 'btn subtle';
    action.textContent = 'Use this bundle';
    action.addEventListener('click', () => {
      setSelectedAudioBundle(recommendation.bundle_id, recommendation.resource_profile);
    });
    card.appendChild(action);
  }

  return card;
}

function buildAudioBundlePlanSummary(bundle, profile = null) {
  if (!bundle) {
    return [];
  }

  const selectedProfile = profile
    || bundle.resource_profiles?.[bundle.default_resource_profile]
    || null;
  const summary = [];
  const stt = summarizeAudioPlanEntries('stt', selectedProfile?.stt_plan || bundle.stt_plan, 'models');
  const tts = summarizeAudioPlanEntries('tts', selectedProfile?.tts_plan || bundle.tts_plan, 'variants');
  if (stt.length) {
    summary.push(`STT: ${stt.join('; ')}`);
  }
  if (tts.length) {
    summary.push(`TTS: ${tts.join('; ')}`);
  }

  const embeddingSummary = [];
  const embeddingsPlan = selectedProfile?.embeddings_plan || bundle.embeddings_plan;
  if (embeddingsPlan?.huggingface?.length) {
    embeddingSummary.push(`HF ${embeddingsPlan.huggingface.join(', ')}`);
  }
  if (embeddingsPlan?.custom?.length) {
    embeddingSummary.push(`Custom ${embeddingsPlan.custom.join(', ')}`);
  }
  if (embeddingSummary.length) {
    summary.push(`Embeddings: ${embeddingSummary.join(' | ')}`);
  }

  if (selectedProfile?.estimated_disk_gb) {
    summary.push(`Disk: ~${selectedProfile.estimated_disk_gb} GB`);
  }
  if (selectedProfile?.resource_class) {
    summary.push(`Tier: ${humaniseKey(selectedProfile.resource_class)}`);
  }

  return summary;
}

function appendAudioAutomationGroup(container, label, steps) {
  if (!Array.isArray(steps) || !steps.length) {
    return;
  }

  const group = document.createElement('div');
  group.className = 'audio-bundle-tier-group';

  const heading = document.createElement('p');
  heading.className = 'audio-bundle-tier-title';
  heading.textContent = label;
  group.appendChild(heading);

  const list = document.createElement('ul');
  list.className = 'audio-bundle-tier-list';

  steps.forEach((step) => {
    const item = document.createElement('li');
    item.className = 'audio-bundle-tier-item';

    const copy = document.createElement('div');
    copy.className = 'audio-bundle-tier-copy';

    const row = document.createElement('div');
    row.className = 'audio-bundle-tier-row';

    const title = document.createElement('span');
    title.className = 'audio-bundle-tier-label';
    title.textContent = step.label;
    row.appendChild(title);

    const badge = document.createElement('span');
    const tierText = String(step.automation_tier || 'guided').replace(/_/g, ' ');
    const tierClass = step.automation_tier === 'automatic'
      ? 'badge-success'
      : (step.automation_tier === 'manual_blocked' ? 'badge-alert' : 'badge-warning');
    badge.className = `status-badge ${tierClass}`;
    badge.textContent = humaniseKey(tierText);
    row.appendChild(badge);

    copy.appendChild(row);

    const hintText = getAudioPrerequisiteHint(step);
    if (hintText) {
      const hint = document.createElement('p');
      hint.className = 'audio-bundle-tier-hint';
      hint.textContent = hintText;
      copy.appendChild(hint);
    }

    item.appendChild(copy);
    list.appendChild(item);
  });

  group.appendChild(list);
  container.appendChild(group);
}

function renderAudioReadinessReport() {
  const panel = document.createElement('div');
  panel.className = 'audio-readiness-panel';

  const header = document.createElement('div');
  header.className = 'audio-readiness-header';

  const heading = document.createElement('h5');
  heading.textContent = 'Audio readiness report';
  header.appendChild(heading);

  const readiness = getSelectedAudioReadiness() || state.audio.readiness;
  const statusMeta = formatAudioReadinessBadge(readiness?.status || 'not_started');
  const badge = document.createElement('span');
  badge.className = `status-badge ${statusMeta.className}`;
  badge.textContent = statusMeta.label;
  header.appendChild(badge);
  panel.appendChild(header);

  if (state.audio.readinessLoading && !readiness) {
    const loading = document.createElement('p');
    loading.className = 'audio-stage-note';
    loading.textContent = 'Loading readiness report…';
    panel.appendChild(loading);
    return panel;
  }

  if (!readiness) {
    const empty = document.createElement('p');
    empty.className = 'audio-readiness-empty';
    empty.textContent = 'No readiness snapshot recorded yet. Provision and verify a bundle to populate this report.';
    panel.appendChild(empty);
    return panel;
  }

  const list = document.createElement('div');
  list.className = 'audio-readiness-list';
  appendAudioReadinessItem(list, 'Selected bundle', getAudioCatalogEntry(readiness.selected_bundle_id)?.label || readiness.selected_bundle_id || 'Not selected');
  appendAudioReadinessItem(
    list,
    'Selected profile',
    getAudioProfileLabel(readiness.selected_resource_profile || DEFAULT_AUDIO_RESOURCE_PROFILE),
  );
  appendAudioReadinessItem(list, 'Updated', formatFriendlyTimestamp(readiness.updated_at));
  appendAudioReadinessItem(list, 'Last verification', formatFriendlyTimestamp(readiness.last_verification?.verified_at));
  appendAudioReadinessItem(
    list,
    'FFmpeg',
    readiness.machine_profile?.ffmpeg_available === undefined
      ? 'Unknown'
      : (readiness.machine_profile.ffmpeg_available ? 'Detected' : 'Missing'),
  );
  appendAudioReadinessItem(
    list,
    'eSpeak',
    readiness.machine_profile?.espeak_available === undefined
      ? 'Unknown'
      : (readiness.machine_profile.espeak_available ? 'Detected' : 'Missing'),
  );
  appendAudioReadinessItem(
    list,
    'STT usable',
    readiness.last_verification?.stt_health?.usable === undefined
      ? 'Unknown'
      : (readiness.last_verification.stt_health.usable ? 'Yes' : 'No'),
  );
  appendAudioReadinessItem(list, 'TTS status', readiness.last_verification?.tts_health?.status || 'Unknown');
  panel.appendChild(list);

  if (Array.isArray(readiness.remediation_items) && readiness.remediation_items.length) {
    const issues = document.createElement('div');
    issues.className = 'install-status-errors';

    const headingLabel = document.createElement('strong');
    headingLabel.textContent = 'Remediation items';
    issues.appendChild(headingLabel);

    const issueList = document.createElement('ul');
    readiness.remediation_items.forEach((item) => {
      const entry = document.createElement('li');
      if (typeof item === 'string') {
        entry.textContent = item;
      } else {
        const action = item.action ? ` (${humaniseKey(item.action)})` : '';
        entry.textContent = `${item.message || item.code || 'Issue detected'}${action}`;
      }
      issueList.appendChild(entry);
    });
    issues.appendChild(issueList);
    panel.appendChild(issues);
  }

  return panel;
}

function appendAudioReadinessItem(container, label, value) {
  const row = document.createElement('div');
  row.className = 'audio-readiness-item';

  const title = document.createElement('span');
  title.className = 'audio-readiness-label';
  title.textContent = label;
  row.appendChild(title);

  const copy = document.createElement('span');
  copy.className = 'audio-readiness-value';
  copy.textContent = value || 'Not available';
  row.appendChild(copy);

  container.appendChild(row);
}

function formatAudioReadinessBadge(status) {
  switch (status) {
    case 'ready':
      return { label: 'Ready', className: 'badge-success' };
    case 'ready_with_warnings':
      return { label: 'Ready with warnings', className: 'badge-warning' };
    case 'partial':
      return { label: 'Partial', className: 'badge-warning' };
    case 'failed':
      return { label: 'Failed', className: 'badge-failure' };
    case 'provisioning':
      return { label: 'Provisioning', className: 'badge-info' };
    default:
      return { label: 'Not started', className: 'badge-info' };
  }
}

function formatFriendlyTimestamp(value) {
  if (!value) {
    return 'Not available';
  }
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) {
    return value;
  }
  return parsed.toLocaleString();
}

function renderWizardSummary() {
    const summaryContainer = document.createElement('div');
    summaryContainer.className = 'wizard-content-summary';

    const heading = document.createElement('h3');
    heading.className = 'wizard-step-title';
    heading.id = 'wizard-step-summary';
    heading.textContent = 'All set! Here’s what we’ll focus on.';
    summaryContainer.appendChild(heading);

    const summaryList = document.createElement('ul');
    let recommendedNames = Array.from(computeRecommendedSections());
    if (state.sections.length) {
      const availableNames = new Set(state.sections.map((section) => section.name));
      recommendedNames = recommendedNames.filter((name) => availableNames.has(name));
    }
    const recommended = recommendedNames.map((name) => escapeHtml(getSectionLabelByName(name)));
    const featureSelections = Array.from(state.wizard.answers.features || []).map((value) => escapeHtml(getWizardOptionLabel('features', value)));
    const selectedAudioBundle = getSelectedAudioBundle();
    const selectedAudioProfile = getSelectedAudioProfile();
    const audioReadiness = getSelectedAudioReadiness();
    const installPlan = buildInstallPlan();
    const installSummaries = describeInstallPlan(installPlan);
    const datastoreChoice = state.wizard.answers.datastore ? escapeHtml(getWizardOptionLabel('datastore', state.wizard.answers.datastore)) : null;

    const lines = [];
    if (recommended.length) {
      lines.push(`We will highlight: <strong>${recommended.join(', ')}</strong>`);
    }
    if (featureSelections.length) {
      lines.push(`Selected capabilities: ${featureSelections.join(', ')}`);
    }
    if (selectedAudioBundle) {
      const readinessLabel = audioReadiness?.status ? ` (${escapeHtml(humaniseKey(audioReadiness.status))})` : '';
      const profileLabel = selectedAudioProfile
        ? ` / ${escapeHtml(getAudioProfileLabel(selectedAudioProfile.profile_id, selectedAudioProfile.label))}`
        : '';
      lines.push(`Audio bundle: <strong>${escapeHtml(selectedAudioBundle.label)}</strong>${profileLabel}${readinessLabel}`);
    }
    if (installSummaries.length) {
      const installSummaryText = installSummaries.map((entry) => escapeHtml(entry)).join(' · ');
      lines.push(`Install actions: ${installSummaryText}`);
    }
    if (datastoreChoice) {
      lines.push(`Datastore preference: ${datastoreChoice}`);
    }
    if (!lines.length) {
      lines.push('We will show the full configuration so you can adjust anything.');
    }

    lines.forEach((line) => {
      const item = document.createElement('li');
      item.innerHTML = line;
      summaryList.appendChild(item);
    });

    const body = document.createElement('p');
    body.className = 'wizard-step-description';
    body.textContent = 'Click “Open configuration” to review and save your settings. You can still reveal every section later.';

    summaryContainer.appendChild(body);
    summaryContainer.appendChild(summaryList);
    elements.wizardContent.appendChild(summaryContainer);
    return heading;
  }

  function updateWizardProgress(step) {
    if (!elements.wizardProgress) {
      return;
    }

    if (!step) {
      elements.wizardProgress.textContent = '';
      return;
    }

    if (step.type === 'summary') {
      elements.wizardProgress.innerHTML = '<strong>Review</strong> · Confirm your selections';
      return;
    }

    const stepIndex = QUESTION_STEPS.findIndex((item) => item.id === step.id);
    const position = stepIndex >= 0 ? stepIndex + 1 : state.wizard.currentStep + 1;
    const safeTitle = escapeHtml(step.title);
    const total = TOTAL_GUIDED_STEPS || QUESTION_STEPS.length || 1;
    elements.wizardProgress.innerHTML = `<strong>Step ${position} of ${total}</strong> · ${safeTitle}`;
  }

  function setWizardMessage(level, message) {
    if (!elements.wizardMessage) {
      return;
    }

    const classes = ['wizard-message', 'visible'];
    if (level) {
      classes.push(level);
    }

    elements.wizardMessage.className = classes.join(' ');
    elements.wizardMessage.textContent = message;
    elements.wizardMessage.hidden = false;
  }

  function clearWizardMessage() {
    if (!elements.wizardMessage) {
      return;
    }

    elements.wizardMessage.className = 'wizard-message';
    elements.wizardMessage.textContent = '';
    elements.wizardMessage.hidden = true;
  }

  function focusWizardHeading(element) {
    if (!element) {
      return;
    }

    element.setAttribute('tabindex', '-1');
    element.focus();
    element.addEventListener('blur', () => {
      element.removeAttribute('tabindex');
    }, { once: true });
  }

  function focusWizardMessage() {
    if (!elements.wizardMessage || elements.wizardMessage.hidden) {
      return;
    }

    elements.wizardMessage.setAttribute('tabindex', '-1');
    elements.wizardMessage.focus();
    elements.wizardMessage.addEventListener('blur', () => {
      elements.wizardMessage.removeAttribute('tabindex');
    }, { once: true });
  }

  function createWizardOption(step, option) {
    const wrapper = document.createElement('label');
    wrapper.className = 'wizard-option';

    const input = document.createElement('input');
    input.type = step.type === 'multi' ? 'checkbox' : 'radio';
    input.name = `wizard-${step.id}`;
    input.value = option.value;
    input.checked = isOptionSelected(step.id, option.value);

    input.addEventListener('change', (event) => {
      toggleWizardSelection(step, option.value, event.target.checked, step.type === 'multi');
      if (step.id === 'backends') {
        pruneInstallSelectionsForBackends(new Set(state.wizard.answers.backends || []));
        renderWizardStep();
        return;
      }
      updateWizardOptionStyles(step.id);
    });

    const content = document.createElement('div');
    content.className = 'wizard-option-content';

    const title = document.createElement('div');
    title.className = 'wizard-option-title';
    title.textContent = option.label;
    content.appendChild(title);

    if (option.hint) {
      const hint = document.createElement('p');
      hint.className = 'wizard-option-hint';
      hint.textContent = option.hint;
      content.appendChild(hint);
    }

    if (Array.isArray(option.details) && option.details.length) {
      const detailList = document.createElement('ul');
      detailList.className = 'wizard-option-details';
      option.details.forEach((detail) => {
        const item = document.createElement('li');
        item.textContent = detail;
        detailList.appendChild(item);
      });
      content.appendChild(detailList);
    }

    wrapper.appendChild(input);
    wrapper.appendChild(content);

    if (input.checked) {
      wrapper.classList.add('selected');
    }

    return wrapper;
  }

  function isOptionSelected(stepId, value) {
    const answer = state.wizard.answers[stepId];
    if (Array.isArray(answer)) {
      return answer.includes(value);
    }
    return answer === value;
  }

  function getWizardStep(stepId) {
    return WIZARD_STEPS.find((step) => step.id === stepId);
  }

  function getWizardOptionLabel(stepId, value) {
    const step = getWizardStep(stepId);
    const option = step?.options?.find((item) => item.value === value);
    return option?.label || value;
  }

  function toggleWizardSelection(step, value, checked, isMulti) {
    if (isMulti) {
      const current = new Set(state.wizard.answers[step.id] || []);
      if (checked) {
        current.add(value);
      } else {
        current.delete(value);
      }
      state.wizard.answers[step.id] = Array.from(current);
      return;
    }

    if (checked) {
      state.wizard.answers[step.id] = value;
    }
  }

  function updateWizardOptionStyles(stepId) {
    const inputs = elements.wizardContent?.querySelectorAll(`[name="wizard-${stepId}"]`) || [];
    inputs.forEach((input) => {
      const parent = input.closest('.wizard-option');
      if (!parent) return;
      if (input.checked) {
        parent.classList.add('selected');
      } else {
        parent.classList.remove('selected');
      }
    });
  }

  function handleWizardNext() {
    const step = WIZARD_STEPS[state.wizard.currentStep];
    if (!step) {
      return;
    }

    if (step.type === 'single') {
      const choice = state.wizard.answers[step.id];
      if (!choice) {
        setWizardMessage('info', 'Please choose an option to continue.');
        focusWizardMessage();
        return;
      }
    }

    if (step.type === 'multi' && !step.optional) {
      const selections = state.wizard.answers[step.id] || [];
      if (!selections.length) {
        setWizardMessage('info', 'Select at least one capability or skip the wizard to continue.');
        focusWizardMessage();
        return;
      }
    }

    if (step.type === 'summary') {
      completeWizard();
      return;
    }

    state.wizard.currentStep = Math.min(state.wizard.currentStep + 1, WIZARD_STEPS.length - 1);
    renderWizardStep();
  }

  function handleWizardBack() {
    if (state.wizard.currentStep === 0) {
      return;
    }
    state.wizard.currentStep -= 1;
    renderWizardStep();
  }

  function skipWizard(silent = false) {
    state.wizard.active = false;
    state.wizard.skipped = true;
    state.visibleSections = null;
    state.showHiddenSections = true;
    state.recommendedSections = new Set();
    resetInstallSelections();
    clearWizardMessage();
    hideWizard();
    ensureConfigLoaded();
    if (!silent) {
      setMessage('info', 'Showing full configuration.');
    }
  }

  function completeWizard() {
    state.wizard.active = false;
    state.wizard.completed = true;
    clearMessage();
    clearWizardMessage();

    const depthPreference = state.wizard.answers.depth;
    const recommended = computeRecommendedSections();
    state.recommendedSections = recommended;

    if (depthPreference === 'guided' && recommended.size > 0) {
      state.visibleSections = recommended;
      state.showHiddenSections = false;
    } else {
      state.visibleSections = null;
      state.showHiddenSections = true;
    }

    hideWizard();
    ensureConfigLoaded().then(() => {
      updateSectionSummaryBanner();
    });
  }

  function hideWizard() {
    try { stopKokoroEspeakAutoRefresh(); } catch (_) {}
    if (elements.wizardSection) {
      elements.wizardSection.hidden = true;
    }
    clearWizardMessage();
    if (elements.wizardProgress) {
      elements.wizardProgress.textContent = '';
    }
  }

  function hideConfigSection() {
    if (elements.configSection) {
      elements.configSection.hidden = true;
    }
  }

  function showConfigSection() {
    if (elements.configSection) {
      elements.configSection.hidden = false;
    }
  }

  async function ensureConfigLoaded() {
    showConfigSection();
    if (state.configLoaded) {
      refreshConfigView();
      return;
    }

    setLoading(true);
    // Watchdog for configuration snapshot
    let cfgWatchdogFired = false;
    const cfgWatchdog = setTimeout(() => {
      cfgWatchdogFired = true;
      setMessage('error', 'Timed out loading configuration snapshot. Ensure localhost access is allowed and reload.');
      setLoading(false);
    }, 12000);
    try {
      await loadConfig();
    } finally {
      clearTimeout(cfgWatchdog);
      if (!cfgWatchdogFired) {
        setLoading(false);
      }
    }
  }

  function refreshConfigView() {
    if (!state.configLoaded) {
      return;
    }
    renderSections(state.sections);
    updateSectionSummaryBanner();
    updateSaveState();
    renderModuleWalkthroughs();
  }

  function computeRecommendedSections() {
    const sections = new Set(['Setup']);
    const authChoice = state.wizard.answers.auth;

    if (authChoice === 'single_user') {
      sections.add('AuthNZ');
    }

    if (authChoice === 'multi_user') {
      sections.add('AuthNZ');
      sections.add('Database');
    }

    const features = state.wizard.answers.features || [];
    features.forEach((feature) => {
      (FEATURE_SECTION_MAP[feature] || []).forEach((section) => sections.add(section));
    });
    const backends = state.wizard.answers.backends || [];
    backends.forEach((backend) => {
      (BACKEND_SECTION_MAP[backend] || []).forEach((section) => sections.add(section));
    });

    const datastore = state.wizard.answers.datastore;
    (DATASTORE_SECTION_MAP[datastore] || []).forEach((section) => sections.add(section));

    return sections;
  }

  function updateSectionSummaryBanner() {
    if (!elements.wizardSummary) {
      return;
    }

    const hiddenCount = state.hiddenSections.length;
    if (!state.visibleSections || state.showHiddenSections || hiddenCount === 0) {
      elements.wizardSummary.hidden = true;
      return;
    }

    const availableNames = new Set(state.sections.map((entry) => entry.name));
    const recommendedList = Array.from(state.recommendedSections || [])
      .filter((section) => state.visibleSections.has(section) && availableNames.has(section));
    const sectionItems = recommendedList
      .map((section) => `<span>${escapeHtml(getSectionLabelByName(section))}</span>`)
      .join(', ');
    const headline = sectionItems ? `showing key sections ${sectionItems}.` : 'showing the most relevant sections first.';

    elements.wizardSummary.hidden = false;
    elements.wizardSummary.innerHTML = `
      <strong>Guided view:</strong> ${headline}
      <br />${hiddenCount} additional section${hiddenCount === 1 ? '' : 's'} hidden. Use the button below to reveal them.`;
  }

  function updateVisibilityControls() {
    if (!elements.showAllSections) {
      return;
    }

    const hiddenCount = state.hiddenSections.length;

    if (!state.visibleSections || hiddenCount === 0) {
      elements.showAllSections.hidden = true;
      return;
    }

    elements.showAllSections.hidden = false;
    if (state.showHiddenSections) {
      elements.showAllSections.textContent = 'Hide additional sections';
    } else {
      elements.showAllSections.textContent = `Show ${hiddenCount} additional section${hiddenCount === 1 ? '' : 's'}`;
    }
  }

  function bindWizardActions() {
    if (wizardActionsBound) {
      return;
    }

    elements.wizardNext?.addEventListener('click', handleWizardNext);
    elements.wizardBack?.addEventListener('click', handleWizardBack);
    elements.wizardSkip?.addEventListener('click', () => skipWizard(false));
    wizardActionsBound = true;
  }

  function bindVisibilityActions() {
    if (visibilityActionsBound) {
      return;
    }

    elements.showAllSections?.addEventListener('click', handleToggleSections);
    visibilityActionsBound = true;
  }

  function handleToggleSections() {
    state.showHiddenSections = !state.showHiddenSections;
    refreshConfigView();
    if (state.showHiddenSections) {
      setMessage('info', 'Showing all configuration sections.');
    } else {
      clearMessage();
    }
  }

  function bindModuleOverlayActions() {
    if (moduleOverlayActionsBound) {
      return;
    }

    elements.moduleOverlayBack?.addEventListener('click', handleModuleOverlayBack);
    elements.moduleOverlayNext?.addEventListener('click', handleModuleOverlayNext);
    elements.moduleOverlaySkip?.addEventListener('click', () => closeModuleWalkthrough({ completed: false }));
    elements.moduleOverlayClose?.addEventListener('click', () => closeModuleWalkthrough({ completed: false }));
    elements.moduleOverlay?.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        closeModuleWalkthrough({ completed: false });
      }
    });
    moduleOverlayActionsBound = true;
  }

  function renderModuleWalkthroughs() {
    if (!elements.moduleWalkthroughs || !elements.moduleWalkthroughList) {
      return;
    }

    const modules = Object.entries(MODULE_WALKTHROUGHS);
    if (!modules.length) {
      elements.moduleWalkthroughs.hidden = true;
      elements.moduleWalkthroughList.innerHTML = '';
      return;
    }

    const selected = new Set(state.wizard.answers?.features || []);
    const backendPreferences = new Set(state.wizard.answers?.backends || []);
    if (backendPreferences.has('stt') || backendPreferences.has('tts')) {
      selected.add('audio');
    }
    if (backendPreferences.has('embeddings')) {
      selected.add('embeddings');
    }
    const completed = state.walkthroughCompleted || new Set();
    elements.moduleWalkthroughList.innerHTML = '';

    modules.forEach(([moduleId, config]) => {
      const card = document.createElement('article');
      card.className = 'module-walkthrough-card';

      if (selected.has(moduleId)) {
        const pill = document.createElement('div');
        pill.className = 'module-walkthrough-pill';
        pill.textContent = 'Recommended';
        card.appendChild(pill);
        card.classList.add('recommended');
      }

      if (completed instanceof Set && completed.has(moduleId)) {
        card.classList.add('completed');
      }

      const title = document.createElement('h4');
      title.textContent = config.title;
      card.appendChild(title);

      if (config.intro) {
        const summary = document.createElement('p');
        summary.textContent = config.intro;
        card.appendChild(summary);
      }

      const button = document.createElement('button');
      button.type = 'button';
      button.className = 'btn subtle';
      button.textContent = completed instanceof Set && completed.has(moduleId) ? 'Review steps' : 'Start walkthrough';
      button.addEventListener('click', () => startModuleWalkthrough(moduleId));
      card.appendChild(button);

      elements.moduleWalkthroughList.appendChild(card);
    });

    elements.moduleWalkthroughs.hidden = false;
  }

  function startModuleWalkthrough(moduleId) {
    const moduleConfig = MODULE_WALKTHROUGHS[moduleId];
    if (!moduleConfig) {
      return;
    }

    const moduleSections = new Set();
    (moduleConfig.steps || []).forEach((step) => {
      (step.focus || []).forEach((target) => {
        if (target?.section) {
          moduleSections.add(target.section);
        }
      });
    });

    if (state.visibleSections && !state.showHiddenSections) {
      const requiresAdditional = Array.from(moduleSections).some((sectionName) => !state.visibleSections.has(sectionName));
      if (requiresAdditional) {
        state.showHiddenSections = true;
        refreshConfigView();
      }
    }

    state.walkthrough.active = true;
    state.walkthrough.module = moduleId;
    state.walkthrough.stepIndex = 0;
    state.walkthrough.returnFocus = document.activeElement;
    if (elements.moduleOverlay) {
      elements.moduleOverlay.hidden = false;
      elements.moduleOverlay.setAttribute('aria-hidden', 'false');
      elements.moduleOverlay.focus({ preventScroll: true });
    }
    renderModuleWalkthroughStep();
  }

  function handleModuleOverlayBack() {
    if (!state.walkthrough.active) {
      return;
    }
    state.walkthrough.stepIndex = Math.max(0, state.walkthrough.stepIndex - 1);
    renderModuleWalkthroughStep();
  }

  function handleModuleOverlayNext() {
    if (!state.walkthrough.active) {
      return;
    }

    const moduleConfig = MODULE_WALKTHROUGHS[state.walkthrough.module];
    const steps = moduleConfig?.steps || [];
    const isLastStep = state.walkthrough.stepIndex >= steps.length - 1;

    if (isLastStep) {
      closeModuleWalkthrough({ completed: true });
      return;
    }

    state.walkthrough.stepIndex = Math.min(steps.length - 1, state.walkthrough.stepIndex + 1);
    renderModuleWalkthroughStep();
  }

  function renderModuleWalkthroughStep() {
    const moduleConfig = MODULE_WALKTHROUGHS[state.walkthrough.module];
    const steps = moduleConfig?.steps || [];
    const step = steps[state.walkthrough.stepIndex] || null;

    if (!elements.moduleOverlayTitle || !moduleConfig) {
      return;
    }

    elements.moduleOverlayTitle.textContent = moduleConfig.title;
    if (elements.moduleOverlayIntro) {
      elements.moduleOverlayIntro.textContent = moduleConfig.intro || '';
    }

    if (elements.moduleOverlayStep) {
      if (steps.length) {
        elements.moduleOverlayStep.textContent = `Step ${state.walkthrough.stepIndex + 1} of ${steps.length}`;
      } else {
        elements.moduleOverlayStep.textContent = '';
      }
    }

    if (elements.moduleOverlayBack) {
      elements.moduleOverlayBack.disabled = state.walkthrough.stepIndex === 0;
    }

    if (elements.moduleOverlayNext) {
      elements.moduleOverlayNext.textContent = state.walkthrough.stepIndex >= steps.length - 1 ? 'Finish' : 'Next';
    }

    if (elements.moduleOverlayBody) {
      elements.moduleOverlayBody.innerHTML = '';
      if (step) {
        const heading = document.createElement('h4');
        heading.textContent = step.title;
        elements.moduleOverlayBody.appendChild(heading);

        if (step.description) {
          const desc = document.createElement('p');
          desc.textContent = step.description;
          elements.moduleOverlayBody.appendChild(desc);
        }

        if (Array.isArray(step.points) && step.points.length) {
          const list = document.createElement('ul');
          step.points.forEach((point) => {
            const item = document.createElement('li');
            item.textContent = point;
            list.appendChild(item);
          });
          elements.moduleOverlayBody.appendChild(list);
        }

        if (step.note) {
          const note = document.createElement('p');
          note.textContent = step.note;
          elements.moduleOverlayBody.appendChild(note);
        }
      } else {
        const message = document.createElement('p');
        message.textContent = 'Nothing else to configure for this module.';
        elements.moduleOverlayBody.appendChild(message);
      }
    }

    applyWalkthroughFocus(step);
  }

  function closeModuleWalkthrough(options = {}) {
    const { completed = false } = options;
    const moduleId = state.walkthrough.module;

    state.walkthrough.active = false;
    state.walkthrough.module = null;
    state.walkthrough.stepIndex = 0;

    if (completed && moduleId) {
      state.walkthroughCompleted.add(moduleId);
    }

    if (elements.moduleOverlay) {
      elements.moduleOverlay.hidden = true;
      elements.moduleOverlay.setAttribute('aria-hidden', 'true');
    }

    clearWalkthroughHighlights();
    renderModuleWalkthroughs();

    if (state.walkthrough.returnFocus && typeof state.walkthrough.returnFocus.focus === 'function') {
      try {
        state.walkthrough.returnFocus.focus();
      } catch {
        // Ignore focus errors
      }
    }
    state.walkthrough.returnFocus = null;
  }

  function applyWalkthroughFocus(step) {
    clearWalkthroughHighlights();
    if (!step || !Array.isArray(step.focus)) {
      return;
    }

    step.focus.forEach((target, index) => {
      setTimeout(() => {
        highlightWalkthroughTarget(target);
      }, index * 120);
    });
  }

  function highlightWalkthroughTarget(target) {
    if (!target || !target.section) {
      return;
    }

    focusSectionFromAssistant(target.section, target.key);

    const sectionSelector = `.section-card[data-section-name="${cssEscape(target.section)}"]`;
    const sectionCard = elements.configSections?.querySelector(sectionSelector);
    if (sectionCard && !walkthroughHighlights.includes(sectionCard)) {
      sectionCard.classList.add('focus-highlight');
      walkthroughHighlights.push(sectionCard);
    }

    if (target.key) {
      const fieldSelector = `.field-card[data-section-name="${cssEscape(target.section)}"][data-field-key="${cssEscape(target.key)}"]`;
      const fieldCard = elements.configSections?.querySelector(fieldSelector);
      if (fieldCard && !walkthroughHighlights.includes(fieldCard)) {
        fieldCard.classList.add('focus-highlight');
        walkthroughHighlights.push(fieldCard);
      }
    }
  }

  function clearWalkthroughHighlights() {
    walkthroughHighlights.forEach((element) => {
      element.classList.remove('focus-highlight');
    });
    walkthroughHighlights = [];
  }

  function initAssistant() {
    if (!elements.assistantRoot || state.assistant.initialised) {
      return;
    }

    elements.assistantToggle?.addEventListener('click', () => toggleAssistant(!state.assistant.open));
    elements.assistantClose?.addEventListener('click', () => toggleAssistant(false));
    elements.assistantForm?.addEventListener('submit', handleAssistantSubmit);
    elements.assistantInput?.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleAssistantSubmit(event);
      }
    });
    elements.assistantPanel?.addEventListener('keydown', (event) => {
      if (event.key === 'Escape') {
        toggleAssistant(false);
      }
    });

    state.assistant.initialised = true;
  }

  function toggleAssistant(forceOpen) {
    if (!elements.assistantPanel) {
      return;
    }

    const targetOpen = typeof forceOpen === 'boolean' ? forceOpen : !state.assistant.open;
    if (targetOpen === state.assistant.open) {
      return;
    }

    state.assistant.open = targetOpen;
    elements.assistantPanel.hidden = !targetOpen;
    elements.assistantRoot?.classList.toggle('assistant-open', targetOpen);
    elements.assistantToggle?.setAttribute('aria-expanded', targetOpen ? 'true' : 'false');

    if (targetOpen) {
      if (!state.assistant.greeted) {
        addAssistantMessage('assistant', 'Hi! I’m here to help with configuration. Try asking “Where do I set the API keys?”');
        state.assistant.greeted = true;
      }
      setTimeout(() => {
        elements.assistantInput?.focus();
      }, 120);
    } else if (elements.assistantToggle) {
      elements.assistantToggle.focus();
    }
  }

  function handleAssistantSubmit(event) {
    event?.preventDefault();
    if (!elements.assistantInput || state.assistant.sending) {
      return;
    }

    const question = elements.assistantInput.value.trim();
    if (!question) {
      return;
    }

    addAssistantMessage('user', question);
    elements.assistantInput.value = '';
    sendAssistantQuestion(question);
  }

  function addAssistantMessage(role, content, matches = []) {
    if (!elements.assistantMessages) {
      return;
    }

    const message = {
      role,
      content,
      matches,
      timestamp: Date.now(),
    };
    state.assistant.history.push(message);

    const wrapper = document.createElement('div');
    wrapper.className = `assistant-message ${role}`;

    const bubble = document.createElement('div');
    bubble.className = 'assistant-bubble';
    bubble.innerHTML = String(content || '')
      .split('\n')
      .map((line) => escapeHtml(line))
      .join('<br />');
    wrapper.appendChild(bubble);

    if (role === 'assistant' && Array.isArray(matches) && matches.length) {
      const suggestions = document.createElement('ul');
      suggestions.className = 'assistant-suggestions';

      matches.forEach((entry) => {
        const item = document.createElement('li');
        const button = document.createElement('button');
        button.type = 'button';
        button.className = 'assistant-link';
        const label = entry.label || humaniseKey(entry.key || '') || entry.section_label || 'View section';
        const sectionLabel = entry.section_label ? ` (${entry.section_label})` : '';
        button.textContent = `${label}${sectionLabel}`;
        button.addEventListener('click', () => focusSectionFromAssistant(entry.section, entry.key));
        item.appendChild(button);
        suggestions.appendChild(item);
      });

      wrapper.appendChild(suggestions);
    }

    elements.assistantMessages.appendChild(wrapper);
    scrollAssistantMessages();
  }

  function scrollAssistantMessages() {
    if (!elements.assistantMessages) {
      return;
    }
    elements.assistantMessages.scrollTop = elements.assistantMessages.scrollHeight;
  }

  function sendAssistantQuestion(question) {
    setAssistantLoading(true);
    setAssistantTyping(true);

    fetchJson(`${API_BASE}/assistant`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ question }),
    })
      .then((response) => {
        addAssistantMessage('assistant', response.answer || 'Here is what I found.', response.matches || []);
      })
      .catch((error) => {
        const message = `Sorry, I ran into a problem: ${error.message || error}`;
        addAssistantMessage('assistant', message);
      })
      .finally(() => {
        setAssistantTyping(false);
        setAssistantLoading(false);
      });
  }

  function setAssistantLoading(isLoading) {
    state.assistant.sending = isLoading;
    if (elements.assistantInput) {
      elements.assistantInput.disabled = isLoading;
    }
    if (elements.assistantSend) {
      elements.assistantSend.disabled = isLoading;
      elements.assistantSend.setAttribute('aria-busy', isLoading ? 'true' : 'false');
    }
  }

  function setAssistantTyping(isTyping) {
    if (!elements.assistantTyping) {
      return;
    }
    elements.assistantTyping.hidden = !isTyping;
  }

  function focusSectionFromAssistant(sectionName, key) {
    if (!sectionName || !elements.configSections) {
      return;
    }

    const selector = `.section-card[data-section-name="${cssEscape(sectionName)}"]`;
    const sectionCard = elements.configSections.querySelector(selector);
    if (!sectionCard) {
      return;
    }

    sectionCard.open = true;
    sectionCard.scrollIntoView({ behavior: 'smooth', block: 'start' });

    if (key) {
      const fieldSelector = `[data-section="${cssEscape(sectionName)}"][data-key="${cssEscape(key)}"]`;
      const targetInput = sectionCard.querySelector(fieldSelector);
      if (targetInput) {
        targetInput.focus({ preventScroll: true });
      }
    }
  }

  function cssEscape(value) {
    if (window.CSS && typeof window.CSS.escape === 'function') {
      return window.CSS.escape(String(value));
    }
    return String(value).replace(/[^a-zA-Z0-9_-]/g, '\\$&');
  }

  function renderField(sectionName, field) {
    const wrapper = document.createElement('div');
    wrapper.className = 'field-card';
    if (field.placeholder) {
      wrapper.classList.add('placeholder');
    }
    wrapper.dataset.sectionName = sectionName;
    wrapper.dataset.fieldKey = field.key;

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
    const hintText = (field.hint || '').trim();
    const friendlyKey = humaniseKey(field.key) || field.key;
    const fallbackHint = `Adjust ${friendlyKey} in ${getSectionLabelByName(sectionName)}.`;
    const hint = document.createElement('p');
    hint.className = 'field-hint';
    hint.textContent = hintText || fallbackHint;
    wrapper.appendChild(hint);

    // Provide quick "Copy .env snippet" for likely credential fields
    try {
      if (shouldShowEnvSnippet(sectionName, field)) {
        const actions = document.createElement('div');
        actions.className = 'field-actions';
        const copyBtn = document.createElement('button');
        copyBtn.type = 'button';
        copyBtn.className = 'btn subtle';
        copyBtn.textContent = 'Copy .env snippet';
        copyBtn.addEventListener('click', async () => {
          const snippet = buildEnvSnippet(field);
          try {
            await navigator.clipboard.writeText(snippet);
            setMessage('info', `Copied snippet for ${field.key} to clipboard`);
          } catch (e) {
            setMessage('error', 'Failed to copy to clipboard');
          }
        });
        actions.appendChild(copyBtn);
        wrapper.appendChild(actions);
      }
    } catch (e) { /* no-op */ }
    return wrapper;
  }

  function likelyCredentialKey(key) {
    const k = String(key || '').toUpperCase();
    return /API_KEY|TOKEN|SECRET|CLIENT_SECRET|ACCESS_TOKEN|BEARER/i.test(k);
  }

  function shouldShowEnvSnippet(sectionName, field) {
    if (!sectionName || !field) return false;
    const inApiSection = String(sectionName).toLowerCase() === 'api';
    const looksSecret = !!field.is_secret || likelyCredentialKey(field.key);
    const isPlaceholder = !!field.placeholder || !String(field.value || '').trim();
    return inApiSection && looksSecret && isPlaceholder;
  }

  function buildEnvSnippet(field) {
    const key = String(field.key || 'KEY').toUpperCase();
    // Do not include actual values to avoid leaking secrets
    return `# Add to your .env file\n${key}=<your_value_here>`;
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
    const audioBusy = state.audio?.provisioning || state.audio?.verifying;
    const actionBusy = state.saving || audioBusy;

    if (elements.saveButton) {
      elements.saveButton.disabled = !hasChanges || actionBusy;
    }

    if (elements.completeButton) {
      elements.completeButton.disabled = hasChanges || actionBusy;
    }
  }

  function shouldExpandSection(section, isRecommended = true) {
    const placeholders = (section.fields || []).some((field) => field.placeholder);
    if (placeholders) {
      return true;
    }

    if (!state.visibleSections) {
      return true;
    }

    if (isRecommended) {
      return true;
    }

    return false;
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

      const installPlan = buildInstallPlan();
      const payload = { disable_first_time_setup: elements.disableToggle.checked };
      if (installPlan) {
        payload.install_plan = installPlan;
      }
      const response = await fetchJson(`${API_BASE}/complete`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
      if (elements.completeButton) {
        elements.completeButton.disabled = true;
      }
      if (response.install_plan_submitted) {
        setMessage('info', 'Setup completed. Installing required Python packages and model files-keep this tab open until the installer finishes.');
        await beginInstallStatusMonitoring();
      } else {
        setMessage('success', `${response.message || 'Setup completed.'} Redirecting to quickstart…`);
        setTimeout(() => window.location.href = QUICKSTART_URL, 2500);
      }
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
    if (actionsBound) {
      return;
    }
    elements.saveButton?.addEventListener('click', handleSave);
    elements.completeButton?.addEventListener('click', handleComplete);
    actionsBound = true;
  }

  function ensureActionsBound() {
    bindActions();
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

  function clearMessage() {
    if (!elements.actionMessage) return;
    elements.actionMessage.textContent = '';
    elements.actionMessage.className = 'action-message';
  }

  function appendMessage(additional) {
    if (!elements.actionMessage) return;
    elements.actionMessage.textContent += `\n${additional}`;
  }

  async function handleResetSetup() {
    const confirmed = window.confirm('This will reset setup flags and require a server restart. Continue?');
    if (!confirmed) return;

    setSaving(true);
    try {
      const response = await fetchJson(`${API_BASE}/reset`, { method: 'POST' });
      const message = response && response.message ? response.message : 'Setup flags reset. Restart the server and revisit /setup.';
      setMessage('success', message);
    } catch (error) {
      const text = String(error && error.message ? error.message : error || 'Unknown error');
      if (/401|403/.test(text)) {
        setMessage('error', 'Reset denied: admin access required.');
      } else {
        setMessage('error', `Reset failed: ${text}`);
      }
    } finally {
      setSaving(false);
    }
  }

  async function fetchJson(url, options = {}, retries = 2) {
    // More resilient fetch with timeout, no-store cache, and retry on AbortError/network glitches
    const controller = new AbortController();
    const timeoutMs = options.timeoutMs || 10000; // default 10s
    const timer = setTimeout(() => controller.abort(), timeoutMs);

    const init = {
      method: options.method || 'GET',
      cache: options.cache || 'no-store',
      credentials: options.credentials || 'same-origin',
      headers: {
        'Accept': 'application/json',
        ...(options.headers || {}),
      },
      body: options.body,
      signal: controller.signal,
    };

    try {
      const response = await fetch(url, init);
      if (!response.ok) {
        const text = await response.text().catch(() => '');
        const err = new Error(text || response.statusText);
        err.status = response.status;
        throw err;
      }
      // Try JSON first
      return await response.json();
    } catch (err) {
      const message = String(err && err.message ? err.message : err || '');
      const isAbort = err && (err.name === 'AbortError' || /AbortError/i.test(message));
      const isTransient = isAbort || /NetworkError|TypeError: Failed to fetch/i.test(message);
      if ((isTransient) && retries > 0) {
        // small backoff before retry
        await new Promise((r) => setTimeout(r, 250 * (3 - retries)));
        return fetchJson(url, options, retries - 1);
      }
      throw err;
    } finally {
      clearTimeout(timer);
    }
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
