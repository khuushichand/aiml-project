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
  };

  const elements = {};
  let actionsBound = false;
  let wizardActionsBound = false;
  let visibilityActionsBound = false;

  document.addEventListener('DOMContentLoaded', init);

  async function init() {
    cacheElements();
    initAssistant();
    hideConfigSection();
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
      initialiseWizard();
    } catch (error) {
      console.error('Setup initialisation failed', error);
      setMessage('error', `Failed to load setup data: ${error.message || error}`);
    } finally {
      setLoading(false);
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
    elements.assistantRoot = document.getElementById('assistantRoot');
    elements.assistantToggle = document.getElementById('assistantToggle');
    elements.assistantPanel = document.getElementById('assistantPanel');
    elements.assistantMessages = document.getElementById('assistantMessages');
    elements.assistantForm = document.getElementById('assistantForm');
    elements.assistantInput = document.getElementById('assistantInput');
    elements.assistantSend = document.getElementById('assistantSend');
    elements.assistantClose = document.getElementById('assistantClose');
    elements.assistantTyping = document.getElementById('assistantTyping');
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

    if (step.type === 'summary') {
      const heading = renderWizardSummary();
      focusWizardHeading(heading);
      return;
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

    const lines = [];
    if (recommended.length) {
      lines.push(`We will highlight: <strong>${recommended.join(', ')}</strong>`);
    }
    if (featureSelections.length) {
      lines.push(`Selected capabilities: ${featureSelections.join(', ')}`);
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

    if (step.type === 'multi') {
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
    try {
      await loadConfig();
    } finally {
      setLoading(false);
    }
  }

  function refreshConfigView() {
    if (!state.configLoaded) {
      return;
    }
    renderSections(state.sections);
    updateSectionSummaryBanner();
    updateSaveState();
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
