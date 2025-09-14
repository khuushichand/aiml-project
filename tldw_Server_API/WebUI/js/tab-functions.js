/**
 * Tab-specific functions for the WebUI
 * This file contains all functions that are called from onclick handlers in dynamically loaded tabs
 */

// ============================================================================
// Audio Tab Functions (TTS and STT)
// ============================================================================

function updateTTSProviderOptions() {
    const provider = document.getElementById('audioTTS_provider').value;
    const modelSelect = document.getElementById('audioTTS_model');
    const voiceSelect = document.getElementById('audioTTS_voice');
    
    // Clear existing options
    modelSelect.innerHTML = '';
    voiceSelect.innerHTML = '';
    
    // Define provider-specific options
    const providerConfigs = {
        openai: {
            models: [
                { value: 'tts-1', text: 'tts-1 (Standard)' },
                { value: 'tts-1-hd', text: 'tts-1-hd (High Definition)' }
            ],
            voices: [
                { value: 'alloy', text: 'Alloy' },
                { value: 'echo', text: 'Echo' },
                { value: 'fable', text: 'Fable' },
                { value: 'onyx', text: 'Onyx' },
                { value: 'nova', text: 'Nova' },
                { value: 'shimmer', text: 'Shimmer' }
            ]
        },
        elevenlabs: {
            models: [
                { value: 'eleven_monolingual_v1', text: 'Eleven Monolingual v1' },
                { value: 'eleven_multilingual_v2', text: 'Eleven Multilingual v2' },
                { value: 'eleven_turbo_v2', text: 'Eleven Turbo v2' }
            ],
            voices: [
                { value: 'rachel', text: 'Rachel' },
                { value: 'clyde', text: 'Clyde' },
                { value: 'domi', text: 'Domi' },
                { value: 'dave', text: 'Dave' },
                { value: 'fin', text: 'Fin' },
                { value: 'bella', text: 'Bella' },
                { value: 'antoni', text: 'Antoni' },
                { value: 'thomas', text: 'Thomas' },
                { value: 'charlie', text: 'Charlie' },
                { value: 'emily', text: 'Emily' },
                { value: 'elli', text: 'Elli' },
                { value: 'callum', text: 'Callum' },
                { value: 'patrick', text: 'Patrick' },
                { value: 'harry', text: 'Harry' },
                { value: 'liam', text: 'Liam' },
                { value: 'dorothy', text: 'Dorothy' },
                { value: 'josh', text: 'Josh' },
                { value: 'arnold', text: 'Arnold' },
                { value: 'charlotte', text: 'Charlotte' },
                { value: 'matilda', text: 'Matilda' },
                { value: 'matthew', text: 'Matthew' },
                { value: 'james', text: 'James' },
                { value: 'joseph', text: 'Joseph' },
                { value: 'jeremy', text: 'Jeremy' },
                { value: 'michael', text: 'Michael' },
                { value: 'ethan', text: 'Ethan' },
                { value: 'gigi', text: 'Gigi' },
                { value: 'freya', text: 'Freya' },
                { value: 'grace', text: 'Grace' },
                { value: 'daniel', text: 'Daniel' },
                { value: 'serena', text: 'Serena' },
                { value: 'adam', text: 'Adam' },
                { value: 'nicole', text: 'Nicole' },
                { value: 'jessie', text: 'Jessie' },
                { value: 'ryan', text: 'Ryan' },
                { value: 'sam', text: 'Sam' },
                { value: 'glinda', text: 'Glinda' },
                { value: 'giovanni', text: 'Giovanni' },
                { value: 'mimi', text: 'Mimi' }
            ]
        },
        higgs: {
            models: [
                { value: 'higgs-3b', text: 'Higgs 3B Model' }
            ],
            voices: [
                { value: 'default', text: 'Default Voice' },
                { value: 'male_1', text: 'Male Voice 1' },
                { value: 'male_2', text: 'Male Voice 2' },
                { value: 'female_1', text: 'Female Voice 1' },
                { value: 'female_2', text: 'Female Voice 2' }
            ]
        },
        kokoro: {
            models: [
                { value: 'kokoro', text: 'Kokoro ONNX' }
            ],
            voices: [
                { value: 'af_bella', text: 'Bella (US female)' },
                { value: 'af_sky', text: 'Sky (US female)' },
                { value: 'am_adam', text: 'Adam (US male)' },
                { value: 'am_michael', text: 'Michael (US male)' },
                { value: 'bf_emma', text: 'Emma (UK female)' },
                { value: 'bm_george', text: 'George (UK male)' }
            ]
        },
        vibevoice: {
            models: [
                { value: '1.5B', text: 'VibeVoice 1.5B (90 min generation)' },
                { value: '7B', text: 'VibeVoice 7B (45 min generation)' }
            ],
            voices: [
                { value: 'speaker_1', text: 'Speaker 1' },
                { value: 'speaker_2', text: 'Speaker 2' },
                { value: 'speaker_3', text: 'Speaker 3' },
                { value: 'speaker_4', text: 'Speaker 4' }
            ]
        },
        chatterbox: {
            models: [
                { value: 'chatterbox-v1', text: 'Chatterbox v1' }
            ],
            voices: [
                { value: 'neutral', text: 'Neutral' },
                { value: 'happy', text: 'Happy' },
                { value: 'sad', text: 'Sad' },
                { value: 'angry', text: 'Angry' },
                { value: 'excited', text: 'Excited' },
                { value: 'calm', text: 'Calm' }
            ]
        },
        kokoro: {
            models: [
                { value: 'kokoro-v1', text: 'Kokoro v1' }
            ],
            voices: [
                { value: 'default', text: 'Default Voice' },
                { value: 'warm', text: 'Warm' },
                { value: 'professional', text: 'Professional' },
                { value: 'friendly', text: 'Friendly' }
            ]
        }
    };
    
    // Get the configuration for the selected provider
    const config = providerConfigs[provider] || providerConfigs.openai;
    
    // Populate model dropdown
    config.models.forEach(model => {
        const option = document.createElement('option');
        option.value = model.value;
        option.textContent = model.text;
        modelSelect.appendChild(option);
    });
    
    // Populate voice dropdown
    config.voices.forEach(voice => {
        const option = document.createElement('option');
        option.value = voice.value;
        option.textContent = voice.text;
        voiceSelect.appendChild(option);
    });
    
    // Show/hide provider-specific options
    const allProviderOptions = document.querySelectorAll('.provider-options');
    allProviderOptions.forEach(el => el.style.display = 'none');
    
    const providerOptionsEl = document.getElementById(`${provider}_options`);
    if (providerOptionsEl) {
        providerOptionsEl.style.display = 'block';
    }
    
    // Show/hide voice cloning section based on provider support
    const voiceCloningSection = document.getElementById('voiceCloning');
    if (voiceCloningSection) {
        const supportsCloningProviders = ['higgs', 'vibevoice', 'chatterbox'];
        voiceCloningSection.style.display = supportsCloningProviders.includes(provider) ? 'block' : 'none';
    }
    
    // Show/hide pitch control based on provider support
    const pitchGroup = document.getElementById('audioTTS_pitch_group');
    if (pitchGroup) {
        const supportsPitchProviders = ['elevenlabs', 'vibevoice', 'chatterbox'];
        pitchGroup.style.display = supportsPitchProviders.includes(provider) ? 'block' : 'none';
    }
}

function checkTTSProviderStatus() {
    // This function would check the status of TTS providers
    // For now, just update the UI to show checking
    const statusIndicators = document.querySelectorAll('.provider-status .status-dot');
    statusIndicators.forEach(dot => {
        dot.classList.add('loading');
    });
    
    // Simulate checking (in real implementation, this would call the API)
    setTimeout(() => {
        statusIndicators.forEach(dot => {
            dot.classList.remove('loading');
            // Randomly set as available or unavailable for demo
            if (Math.random() > 0.3) {
                dot.classList.add('available');
            } else {
                dot.classList.add('unavailable');
            }
        });
    }, 1000);
}

async function loadProviderVoices() {
    try {
        const provider = document.getElementById('audioTTS_provider')?.value || '';
        const voiceSelect = document.getElementById('audioTTS_voice');
        const voiceList = document.getElementById('audioTTS_voiceList');
        if (!provider || !voiceSelect) return;

        // Show loading state
        if (voiceList) {
            voiceList.style.display = 'block';
            voiceList.innerHTML = '<span class="loading-spinner"></span> Loading voices...';
        }

        const res = await apiClient.get('/api/v1/audio/voices', { provider });
        const voices = res?.[provider] || [];

        // Update dropdown
        if (Array.isArray(voices) && voices.length) {
            voiceSelect.innerHTML = '';
            voices.forEach(v => {
                const opt = document.createElement('option');
                opt.value = v.id || v.name || '';
                opt.textContent = v.name ? `${v.name}` : (v.id || 'voice');
                voiceSelect.appendChild(opt);
            });
        }

        // Render list
        if (voiceList) {
            if (!Array.isArray(voices) || !voices.length) {
                voiceList.innerHTML = '<span class="text-muted">No voices reported by provider.</span>';
            } else {
                const items = voices.map(v => {
                    const meta = [v.language, v.gender].filter(Boolean).join(' · ');
                    return `<div class="voice-item" style="padding:4px 0; border-bottom: 1px dashed var(--color-border);">
                        <strong>${v.name || v.id}</strong>
                        <div class="text-muted" style="font-size: 0.85em;">${meta || ''}</div>
                        <div style="font-size: 0.85em;">${v.description || ''}</div>
                    </div>`;
                }).join('');
                voiceList.innerHTML = items;
            }
        }
    } catch (err) {
        console.error('Failed to load voices', err);
        const voiceList = document.getElementById('audioTTS_voiceList');
        if (voiceList) {
            voiceList.style.display = 'block';
            voiceList.innerHTML = `<span class="error">Error loading voices: ${err?.message || err}</span>`;
        }
    }
}

function clearVoiceReference() {
    const voiceRefInfo = document.getElementById('voiceRefInfo');
    const voiceRefInput = document.getElementById('audioTTS_voiceReference');
    const voiceRefPlayer = document.getElementById('voiceRefPlayer');
    
    if (voiceRefInfo) voiceRefInfo.style.display = 'none';
    if (voiceRefInput) voiceRefInput.value = '';
    if (voiceRefPlayer) voiceRefPlayer.src = '';
}

// Streaming STT Functions
function updateModelOptions() {
    const model = document.getElementById('streamingModel').value;
    const variantGroup = document.getElementById('variantGroup');
    const languageGroup = document.getElementById('languageGroup');
    const whisperModelGroup = document.getElementById('whisperModelGroup');
    const whisperTaskGroup = document.getElementById('whisperTaskGroup');
    
    if (model === 'parakeet') {
        variantGroup.style.display = 'block';
        languageGroup.style.display = 'none';
        whisperModelGroup.style.display = 'none';
        whisperTaskGroup.style.display = 'none';
    } else if (model === 'canary') {
        variantGroup.style.display = 'none';
        languageGroup.style.display = 'block';
        whisperModelGroup.style.display = 'none';
        whisperTaskGroup.style.display = 'none';
    } else if (model === 'whisper') {
        variantGroup.style.display = 'none';
        languageGroup.style.display = 'block';
        whisperModelGroup.style.display = 'block';
        whisperTaskGroup.style.display = 'block';
    }
}

// Initialize TTS options when tab is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Check if we're on the audio tab
    setTimeout(() => {
        const ttsProvider = document.getElementById('audioTTS_provider');
        if (ttsProvider) {
            updateTTSProviderOptions();
        }
        
        const sttModel = document.getElementById('streamingModel');
        if (sttModel) {
            updateModelOptions();
        }
    }, 500);
});

// ============================================================================
// Web Scraping Friendly Ingest
// ============================================================================

function initializeWebScrapingIngestTab() {
    try {
        // Populate model dropdowns (if not already)
        if (typeof window.populateModelDropdowns === 'function') {
            window.populateModelDropdowns();
        }

        // Method-driven UI toggles
        const methodSelect = document.getElementById('friendlyIngest_scrape_method');
        if (methodSelect) {
            methodSelect.addEventListener('change', updateFriendlyScrapeMethodUI);
            updateFriendlyScrapeMethodUI();
        }

        // Cookies validation when toggled/edited
        const useCookies = document.getElementById('friendlyIngest_use_cookies');
        const cookiesInput = document.getElementById('friendlyIngest_cookies');
        if (useCookies) {
            useCookies.addEventListener('change', validateFriendlyCookies);
            useCookies.addEventListener('change', updateFriendlyIngestValidationState);
        }
        if (cookiesInput) {
            cookiesInput.addEventListener('blur', validateFriendlyCookies);
            cookiesInput.addEventListener('input', () => {
                // Clear status while typing
                const status = document.getElementById('friendlyIngest_cookies_status');
                if (status) {
                    status.textContent = '';
                }
            });
            cookiesInput.addEventListener('input', updateFriendlyIngestValidationState);
        }
        validateFriendlyCookies();

        // Basic inputs listeners for validation
        const urlsEl = document.getElementById('friendlyIngest_urls');
        const methodEl = document.getElementById('friendlyIngest_scrape_method');
        const urlLevelEl = document.getElementById('friendlyIngest_url_level');
        const maxPagesEl = document.getElementById('friendlyIngest_max_pages');
        const maxDepthEl = document.getElementById('friendlyIngest_max_depth');

        [urlsEl, methodEl, urlLevelEl, maxPagesEl, maxDepthEl].forEach(el => {
            if (el) {
                el.addEventListener('input', updateFriendlyIngestValidationState);
                el.addEventListener('change', updateFriendlyIngestValidationState);
            }
        });

        // Initial validation state
        updateFriendlyIngestValidationState();
    } catch (e) {
        console.warn('Failed to initialize Web Scraping Ingest tab:', e.message);
    }
}

function updateFriendlyScrapeMethodUI() {
    const method = document.getElementById('friendlyIngest_scrape_method')?.value || 'individual';
    const show = (id, visible) => {
        const el = document.getElementById(id);
        if (el) el.style.display = visible ? 'block' : 'none';
    };

    // url_level: needs url_level only
    show('group_friendlyIngest_url_level', method === 'url_level');
    // sitemap: needs max_pages
    show('group_friendlyIngest_max_pages', method === 'recursive_scraping' || method === 'sitemap');
    // recursive_scraping: needs both max_pages and max_depth
    show('group_friendlyIngest_max_depth', method === 'recursive_scraping');
}

function validateFriendlyCookies() {
    const use = document.getElementById('friendlyIngest_use_cookies')?.checked;
    const input = document.getElementById('friendlyIngest_cookies');
    const status = document.getElementById('friendlyIngest_cookies_status');
    const group = document.getElementById('group_friendlyIngest_cookies');

    if (!input || !status || !group) return;

    // Enable/disable textarea based on checkbox
    input.disabled = !use;
    if (!use) {
        status.textContent = '';
        return;
    }

    const text = input.value.trim();
    if (text === '') {
        status.textContent = 'Provide valid JSON when using cookies.';
        status.style.color = 'var(--color-text-muted)';
        return;
    }

    try {
        const parsed = JSON.parse(text);
        const ok = Array.isArray(parsed) || typeof parsed === 'object';
        if (!ok) throw new Error('Cookies must be an object or an array of objects');

        // Pretty print normalized JSON back into the field
        input.value = JSON.stringify(parsed, null, 2);
        status.textContent = 'Cookies JSON valid';
        status.style.color = 'var(--color-success, #2e7d32)';
    } catch (e) {
        status.textContent = 'Invalid JSON: ' + e.message;
        status.style.color = 'var(--color-error, #c62828)';
    }
}

function updateFriendlyIngestValidationState() {
    const submitBtn = document.getElementById('friendlyIngest_submit');
    const hintEl = document.getElementById('friendlyIngest_validation_hint');
    const summaryEl = document.getElementById('friendlyIngest_validation_summary');
    if (!submitBtn) return;

    let isValid = true;
    const errors = [];
    // Reset field highlights
    const resetInvalid = (id) => { const el = document.getElementById(id); if (el) el.classList.remove('input-invalid'); };
    const markInvalid = (id) => { const el = document.getElementById(id); if (el) el.classList.add('input-invalid'); };
    ['friendlyIngest_urls','friendlyIngest_url_level','friendlyIngest_max_pages','friendlyIngest_max_depth','friendlyIngest_cookies']
        .forEach(resetInvalid);

    const urls = (document.getElementById('friendlyIngest_urls')?.value || '')
        .split('\n').map(s => s.trim()).filter(Boolean);
    if (urls.length === 0) {
        isValid = false;
        errors.push('Enter at least one URL.');
        markInvalid('friendlyIngest_urls');
    }

    const method = document.getElementById('friendlyIngest_scrape_method')?.value || 'individual';
    const urlLevel = parseInt(document.getElementById('friendlyIngest_url_level')?.value || '0', 10);
    const maxPages = parseInt(document.getElementById('friendlyIngest_max_pages')?.value || '0', 10);
    const maxDepth = parseInt(document.getElementById('friendlyIngest_max_depth')?.value || '0', 10);

    if (method === 'url_level' && (!urlLevel || urlLevel < 1)) {
        isValid = false;
        errors.push('Set URL Level to 1 or higher for url_level method.');
        markInvalid('friendlyIngest_url_level');
    }
    if (method === 'recursive_scraping' && (!maxPages || maxPages < 1 || !maxDepth || maxDepth < 1)) {
        isValid = false;
        errors.push('Set Max Pages and Max Depth (>= 1) for recursive_scraping.');
        if (!maxPages || maxPages < 1) markInvalid('friendlyIngest_max_pages');
        if (!maxDepth || maxDepth < 1) markInvalid('friendlyIngest_max_depth');
    }
    if (method === 'sitemap' && (!maxPages || maxPages < 1)) {
        isValid = false;
        errors.push('Set Max Pages (>= 1) for sitemap method.');
        markInvalid('friendlyIngest_max_pages');
    }

    const useCookies = document.getElementById('friendlyIngest_use_cookies')?.checked;
    const cookiesText = document.getElementById('friendlyIngest_cookies')?.value || '';
    if (useCookies) {
        try {
            if (cookiesText.trim() === '') {
                isValid = false;
                errors.push('Provide Cookies JSON when "Use Cookies" is enabled.');
                markInvalid('friendlyIngest_cookies');
            } else {
                const parsed = JSON.parse(cookiesText);
                if (!(Array.isArray(parsed) || typeof parsed === 'object')) {
                    isValid = false;
                    errors.push('Cookies JSON must be an object or an array of objects.');
                    markInvalid('friendlyIngest_cookies');
                }
            }
        } catch (e) {
            isValid = false;
            errors.push('Cookies JSON is invalid: ' + e.message);
            markInvalid('friendlyIngest_cookies');
        }
    }

    submitBtn.disabled = !isValid;

    if (hintEl) {
        if (isValid) {
            hintEl.textContent = '';
        } else {
            // Render as list for clarity
            const list = errors.map(e => `<li>${e}</li>`).join('');
            hintEl.innerHTML = `<ul style="margin: 6px 0 0 18px;">${list}</ul>`;
        }
    }

    if (summaryEl) {
        if (isValid) {
            summaryEl.classList.remove('visible');
            summaryEl.innerHTML = '';
        } else {
            const prefix = '<strong>Please fix the following:</strong>';
            const list = errors.map(e => `<li>${e}</li>`).join('');
            summaryEl.innerHTML = `${prefix}<ul style="margin: 6px 0 0 18px;">${list}</ul>`;
            summaryEl.classList.add('visible');
        }
    }
}

function submitWebScrapingIngestFriendly(previewOnly = false) {
    try {
        // Collect values
        const urlsText = document.getElementById('friendlyIngest_urls').value || '';
        const titlesText = document.getElementById('friendlyIngest_titles').value || '';
        const authorsText = document.getElementById('friendlyIngest_authors').value || '';
        const keywordsText = document.getElementById('friendlyIngest_keywords').value || '';

        const scrapeMethod = document.getElementById('friendlyIngest_scrape_method').value;
        const urlLevel = parseInt(document.getElementById('friendlyIngest_url_level').value || '2', 10);
        const maxPages = parseInt(document.getElementById('friendlyIngest_max_pages').value || '10', 10);
        const maxDepth = parseInt(document.getElementById('friendlyIngest_max_depth').value || '3', 10);

        const performAnalysis = document.getElementById('friendlyIngest_perform_analysis').checked;
        const customPrompt = document.getElementById('friendlyIngest_custom_prompt').value || null;
        const systemPrompt = document.getElementById('friendlyIngest_system_prompt').value || null;
        const apiName = document.getElementById('friendlyIngest_api_name').value || null;

        const performTranslation = document.getElementById('friendlyIngest_perform_translation').checked;
        const translationLanguage = document.getElementById('friendlyIngest_translation_language').value || 'en';

        const performChunking = document.getElementById('friendlyIngest_perform_chunking').checked;
        const chunkMethod = document.getElementById('friendlyIngest_chunk_method').value || null;
        const chunkSize = parseInt(document.getElementById('friendlyIngest_chunk_size').value || '500', 10);
        const chunkOverlap = parseInt(document.getElementById('friendlyIngest_chunk_overlap').value || '200', 10);
        const useAdaptiveChunking = document.getElementById('friendlyIngest_use_adaptive_chunking').checked;
        const useMultiLevelChunking = document.getElementById('friendlyIngest_use_multi_level_chunking').checked;
        const chunkLanguage = document.getElementById('friendlyIngest_chunk_language').value || null;

        const useCookies = document.getElementById('friendlyIngest_use_cookies').checked;
        const cookiesText = document.getElementById('friendlyIngest_cookies').value || '';
        const timestampOption = document.getElementById('friendlyIngest_timestamp_option').checked;
        const overwriteExisting = document.getElementById('friendlyIngest_overwrite_existing').checked;
        const performRolling = document.getElementById('friendlyIngest_perform_rolling_summarization').checked;
        const performConfabCheck = document.getElementById('friendlyIngest_perform_confabulation_check_of_analysis').checked;
        const customChapterPattern = document.getElementById('friendlyIngest_custom_chapter_pattern').value || null;

        // Transform inputs
        // Ensure validation state is up to date; if invalid, show inline hints and stop
        updateFriendlyIngestValidationState();

        const urls = urlsText.split('\n').map(s => s.trim()).filter(Boolean);
        const method = scrapeMethod;
        const buttonDisabled = document.getElementById('friendlyIngest_submit')?.disabled;
        if (buttonDisabled) {
            // Inline hints are already shown by validation state
            return;
        }

        const titles = titlesText ? titlesText.split('\n').map(s => s.trim()).filter(Boolean) : [];
        const authors = authorsText ? authorsText.split('\n').map(s => s.trim()).filter(Boolean) : [];
        const keywords = keywordsText ? keywordsText.split(',').map(s => s.trim()).filter(Boolean) : [];

        // Additional method-specific validation
        // Method-specific checks are covered by validation state

        // Validate cookies JSON if provided
        if (useCookies && cookiesText) {
            try {
                const parsed = JSON.parse(cookiesText);
                document.getElementById('friendlyIngest_cookies').value = JSON.stringify(parsed, null, 2);
            } catch (e) {
                validateFriendlyCookies();
                updateFriendlyIngestValidationState();
                return;
            }
        }

        // Build payload according to IngestWebContentRequest
        const payload = {
            urls,
            titles: titles.length ? titles : undefined,
            authors: authors.length ? authors : undefined,
            keywords: keywords.length ? keywords : undefined,

            scrape_method: scrapeMethod,
            url_level: isNaN(urlLevel) ? undefined : urlLevel,
            max_pages: isNaN(maxPages) ? undefined : maxPages,
            max_depth: isNaN(maxDepth) ? undefined : maxDepth,

            perform_analysis: performAnalysis,
            custom_prompt: customPrompt || undefined,
            system_prompt: systemPrompt || undefined,
            api_name: apiName || undefined,

            perform_translation: performTranslation,
            translation_language: translationLanguage || 'en',

            perform_rolling_summarization: performRolling,
            perform_confabulation_check_of_analysis: performConfabCheck,

            perform_chunking: performChunking,
            chunk_method: chunkMethod || undefined,
            use_adaptive_chunking: useAdaptiveChunking,
            use_multi_level_chunking: useMultiLevelChunking,
            chunk_language: chunkLanguage || undefined,
            chunk_size: isNaN(chunkSize) ? undefined : chunkSize,
            chunk_overlap: isNaN(chunkOverlap) ? undefined : chunkOverlap,

            use_cookies: useCookies,
            cookies: useCookies && cookiesText ? cookiesText : undefined,

            timestamp_option: timestampOption,
            overwrite_existing: overwriteExisting,
            custom_chapter_pattern: customChapterPattern || undefined
        };

        // Set hidden payload and send request
        const hidden = document.getElementById('friendlyIngest_payload');
        hidden.value = JSON.stringify(payload, null, 2);

        if (previewOnly) {
            // Just show cURL
            endpointHelper.showCurl('friendlyIngest', 'POST', '/api/v1/media/ingest-web-content', 'json');
            const curl = document.getElementById('friendlyIngest_curl');
            if (curl) curl.style.display = 'block';
            return;
        }

        // Use generic makeRequest to show curl and handle long-running UI
        makeRequest('friendlyIngest', 'POST', '/api/v1/media/ingest-web-content', 'json');
    } catch (e) {
        console.error('Failed to build ingest payload:', e);
        Toast.error('Failed to build ingest payload: ' + e.message);
    }
}

// ============================================================================
// Chat Tab Functions
// ============================================================================

function toggleLogprobs() {
    const logprobsChecked = document.getElementById('chatCompletions_logprobs').checked;
    document.getElementById('top_logprobs_group').style.display = logprobsChecked ? 'block' : 'none';
}

function toggleToolChoiceJSON() {
    const toolChoice = document.getElementById('chatCompletions_tool_choice').value;
    document.getElementById('tool_choice_json_group').style.display = toolChoice === 'specific' ? 'block' : 'none';
}

async function makeChatCompletionsRequest() {
    const responseEl = document.getElementById('chatCompletions_response');
    
    try {
        // Build the payload with all parameters
        const payload = {};
        
        // Basic Parameters
        const provider = document.getElementById('chatCompletions_provider').value;
        if (provider) payload.api_provider = provider;
        
        const model = document.getElementById('chatCompletions_model').value;
        if (model) payload.model = model;
        
        const messagesText = document.getElementById('chatCompletions_messages').value;
        try {
            const parsedMessages = JSON.parse(messagesText);
            if (!Array.isArray(parsedMessages)) {
                throw new Error('Messages must be an array');
            }
            payload.messages = parsedMessages;
        } catch (e) {
            throw new Error('Invalid messages JSON format: ' + e.message);
        }
        
        const temperature = parseFloat(document.getElementById('chatCompletions_temperature').value);
        if (!isNaN(temperature)) payload.temperature = temperature;
        
        const maxTokens = parseInt(document.getElementById('chatCompletions_max_tokens').value);
        if (!isNaN(maxTokens)) payload.max_tokens = maxTokens;
        
        payload.stream = document.getElementById('chatCompletions_stream').checked;
        
        // Sampling Parameters
        const frequencyPenalty = parseFloat(document.getElementById('chatCompletions_frequency_penalty').value);
        if (!isNaN(frequencyPenalty)) payload.frequency_penalty = frequencyPenalty;
        
        const presencePenalty = parseFloat(document.getElementById('chatCompletions_presence_penalty').value);
        if (!isNaN(presencePenalty)) payload.presence_penalty = presencePenalty;
        
        const topP = parseFloat(document.getElementById('chatCompletions_top_p').value);
        if (!isNaN(topP)) payload.top_p = topP;
        
        const topK = parseInt(document.getElementById('chatCompletions_top_k').value);
        if (!isNaN(topK)) payload.topk = topK;
        
        const minP = parseFloat(document.getElementById('chatCompletions_min_p').value);
        if (!isNaN(minP)) payload.minp = minP;
        
        const seed = parseInt(document.getElementById('chatCompletions_seed').value);
        if (!isNaN(seed)) payload.seed = seed;
        
        const n = parseInt(document.getElementById('chatCompletions_n').value);
        if (!isNaN(n)) payload.n = n;
        
        // Response Control
        const responseFormat = document.querySelector('input[name="chatCompletions_response_format"]:checked').value;
        if (responseFormat === 'json_object') {
            payload.response_format = { type: 'json_object' };
        }
        
        const stopSequences = document.getElementById('chatCompletions_stop').value;
        if (stopSequences) {
            payload.stop = stopSequences.split(',').map(s => s.trim()).filter(s => s);
        }
        
        const user = document.getElementById('chatCompletions_user').value;
        if (user) payload.user = user;
        
        const logprobs = document.getElementById('chatCompletions_logprobs').checked;
        if (logprobs) {
            payload.logprobs = true;
            const topLogprobs = parseInt(document.getElementById('chatCompletions_top_logprobs').value);
            if (!isNaN(topLogprobs)) payload.top_logprobs = topLogprobs;
        }
        
        const logitBiasText = document.getElementById('chatCompletions_logit_bias').value;
        if (logitBiasText && logitBiasText !== '{}') {
            try {
                const parsed = JSON.parse(logitBiasText);
                if (parsed && typeof parsed === 'object') {
                    payload.logit_bias = parsed;
                }
            } catch (e) {
                console.warn('Invalid logit bias JSON:', e);
            }
        }
        
        // Context & Templates
        const promptTemplate = document.getElementById('chatCompletions_prompt_template').value;
        if (promptTemplate) payload.prompt_template_name = promptTemplate;
        
        const characterIdStr = document.getElementById('chatCompletions_character_id').value;
        if (characterIdStr) {
            const characterId = parseInt(characterIdStr);
            if (!isNaN(characterId) && characterId > 0) {
                payload.character_id = characterId;
            } else {
                console.warn('Invalid character ID:', characterIdStr);
            }
        }
        
        const conversationId = document.getElementById('chatCompletions_conversation_id').value;
        if (conversationId) {
            // Basic validation for conversation ID
            if (/^[a-zA-Z0-9_-]+$/.test(conversationId)) {
                payload.conversation_id = conversationId;
            } else {
                console.warn('Invalid conversation ID format:', conversationId);
            }
        }
        
        // Function Calling
        const toolsText = document.getElementById('chatCompletions_tools').value;
        if (toolsText && toolsText !== '[]') {
            try {
                const parsedTools = JSON.parse(toolsText);
                if (parsedTools && Array.isArray(parsedTools)) {
                    payload.tools = parsedTools;
                }
            } catch (e) {
                console.warn('Invalid tools JSON:', e);
            }
        }
        
        const toolChoice = document.getElementById('chatCompletions_tool_choice').value;
        if (toolChoice === 'specific') {
            const toolChoiceJSON = document.getElementById('chatCompletions_tool_choice_json').value;
            if (toolChoiceJSON && toolChoiceJSON !== '{}') {
                try {
                    const parsed = JSON.parse(toolChoiceJSON);
                    if (parsed) {
                        payload.tool_choice = parsed;
                    }
                } catch (e) {
                    console.warn('Invalid tool choice JSON:', e);
                }
            }
        } else if (toolChoice !== 'auto') {
            payload.tool_choice = toolChoice;
        }
        
        // Display the request payload for debugging
        console.log('Request payload:', payload);
        responseEl.textContent = 'Sending request with parameters:\n' + JSON.stringify(payload, null, 2) + '\n\n';
        
        if (payload.stream) {
            // Handle streaming response
            responseEl.textContent += 'Streaming response:\n';
            const response = await apiClient.post('/api/v1/chat/completions', payload, {
                streaming: true,
                onProgress: (chunk) => {
                    if (chunk.choices && chunk.choices[0] && chunk.choices[0].delta && chunk.choices[0].delta.content) {
                        responseEl.textContent += chunk.choices[0].delta.content;
                    }
                }
            });
            responseEl.textContent += '\n\n[Stream Complete]';
        } else {
            // Handle regular response
            const response = await apiClient.post('/api/v1/chat/completions', payload);
            responseEl.textContent += '\nResponse:\n' + JSON.stringify(response, null, 2);
        }
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        console.error('Chat completions error:', error);
    }
}

// Interactive chat interface
const MAX_CHAT_MESSAGES = 100;
let chatMessages = [
    {role: 'system', content: 'You are a helpful assistant.'}
];

// Function to update the system prompt
function updateSystemPrompt() {
    const systemPromptTextarea = document.getElementById('chat-system-prompt');
    if (systemPromptTextarea) {
        const newSystemPrompt = systemPromptTextarea.value.trim();
        if (newSystemPrompt) {
            // Update the first message in chatMessages (system message)
            chatMessages[0] = {role: 'system', content: newSystemPrompt};
            
            // Update the display in the chat messages
            const messagesDiv = document.getElementById('chat-messages');
            const systemMessageDiv = messagesDiv.querySelector('.chat-message.system');
            if (systemMessageDiv) {
                systemMessageDiv.textContent = 'System: ' + newSystemPrompt;
            }
            
            console.log('System prompt updated:', newSystemPrompt);
        }
    }
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const messagesDiv = document.getElementById('chat-messages');
    const model = document.getElementById('chat-model').value;
    
    if (!input.value.trim()) return;
    
    const userMessage = input.value;
    input.value = '';
    
    // Add user message to display
    const userDiv = document.createElement('div');
    userDiv.className = 'chat-message user';
    // Create user message elements safely
    const userLabel = document.createElement('strong');
    userLabel.textContent = 'User:';
    const userContent = document.createElement('span');
    userContent.textContent = userMessage;
    userDiv.appendChild(userLabel);
    userDiv.appendChild(document.createTextNode(' '));
    userDiv.appendChild(userContent);
    messagesDiv.appendChild(userDiv);
    
    // Add to messages array with history limit
    chatMessages.push({role: 'user', content: userMessage});
    if (chatMessages.length > MAX_CHAT_MESSAGES) {
        const systemMsg = chatMessages[0];
        chatMessages = [systemMsg, ...chatMessages.slice(-(MAX_CHAT_MESSAGES - 1))];
    }
    
    // Create assistant message placeholder
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'chat-message assistant';
    const assistantLabel = document.createElement('strong');
    assistantLabel.textContent = 'Assistant:';
    const assistantContent = document.createElement('span');
    assistantContent.className = 'typing';
    assistantContent.textContent = 'Thinking...';
    assistantDiv.appendChild(assistantLabel);
    assistantDiv.appendChild(document.createTextNode(' '));
    assistantDiv.appendChild(assistantContent);
    messagesDiv.appendChild(assistantDiv);
    
    // Smooth scrolling
    requestAnimationFrame(() => {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    });
    
    try {
        // Get the provider if selected
        const providerSelect = document.getElementById('chat-provider');
        const provider = providerSelect ? providerSelect.value : '';
        
        // Build request payload
        const requestPayload = {
            model: model,
            messages: chatMessages,
            temperature: 0.7,
            max_tokens: 1000
        };
        
        // Add provider if selected
        if (provider) {
            requestPayload.api_provider = provider;
        }
        
        const response = await apiClient.post('/api/v1/chat/completions', requestPayload);
        
        if (response.choices && response.choices[0] && response.choices[0].message) {
            const assistantMessage = response.choices[0].message.content;
            chatMessages.push({role: 'assistant', content: assistantMessage});
            
            // Limit chat history
            if (chatMessages.length > MAX_CHAT_MESSAGES) {
                const systemMsg = chatMessages[0];
                chatMessages = [systemMsg, ...chatMessages.slice(-(MAX_CHAT_MESSAGES - 1))];
            }
            
            assistantDiv.innerHTML = '';
            const label = document.createElement('strong');
            label.textContent = 'Assistant:';
            const content = document.createElement('span');
            content.textContent = assistantMessage;
            assistantDiv.appendChild(label);
            assistantDiv.appendChild(document.createTextNode(' '));
            assistantDiv.appendChild(content);
        } else {
            assistantDiv.innerHTML = '';
            const label2 = document.createElement('strong');
            label2.textContent = 'Assistant:';
            const error = document.createElement('em');
            error.textContent = 'No response received';
            assistantDiv.appendChild(label2);
            assistantDiv.appendChild(document.createTextNode(' '));
            assistantDiv.appendChild(error);
        }
    } catch (error) {
        assistantDiv.innerHTML = '';
        const errorLabel = document.createElement('strong');
        errorLabel.textContent = 'Assistant:';
        const errorMsg = document.createElement('em');
        errorMsg.textContent = `Error: ${error.message}`;
        assistantDiv.appendChild(errorLabel);
        assistantDiv.appendChild(document.createTextNode(' '));
        assistantDiv.appendChild(errorMsg);
        console.error('Chat error:', error);
    }
    
    requestAnimationFrame(() => {
        messagesDiv.scrollTop = messagesDiv.scrollHeight;
    });
}

function clearChat() {
    // Get the current system prompt from the textarea
    const systemPromptTextarea = document.getElementById('chat-system-prompt');
    const currentSystemPrompt = systemPromptTextarea ? systemPromptTextarea.value.trim() : 'You are a helpful assistant.';
    
    chatMessages = [
        {role: 'system', content: currentSystemPrompt}
    ];
    const messagesDiv = document.getElementById('chat-messages');
    // Use DocumentFragment for better performance
    const fragment = document.createDocumentFragment();
    const systemDiv = document.createElement('div');
    systemDiv.className = 'chat-message system';
    systemDiv.textContent = 'System: ' + currentSystemPrompt;
    fragment.appendChild(systemDiv);
    messagesDiv.innerHTML = '';
    messagesDiv.appendChild(fragment);
}

async function exportCharacter() {
    const characterId = document.getElementById('exportCharacter_character_id').value;
    const format = document.getElementById('exportCharacter_format').value;
    const responseEl = document.getElementById('exportCharacter_response');
    
    try {
        responseEl.textContent = 'Exporting...';
        
        const response = await apiClient.get(`/api/v1/characters/${characterId}/export`, {
            format: format
        });
        
        if (format === 'json' || format === 'markdown') {
            responseEl.textContent = typeof response === 'string' ? response : JSON.stringify(response, null, 2);
        } else {
            // For PNG export, we'd need to handle binary data differently
            responseEl.textContent = 'PNG export successful. Binary data received.';
        }
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
    }
}

// ============================================================================
// Character/Conversation Tab Functions
// ============================================================================

async function createCharacter() {
    const responseEl = document.getElementById('charactersCreate_response');
    try {
        responseEl.textContent = 'Creating character...';
        
        // Collect all form values
        const body = {};
        
        // Required field
        const name = document.getElementById('charactersCreate_name').value;
        if (!name) {
            throw new Error('Character name is required');
        }
        body.name = name;
        
        // Basic Information
        const description = document.getElementById('charactersCreate_description').value;
        if (description) body.description = description;
        
        const personality = document.getElementById('charactersCreate_personality').value;
        if (personality) body.personality = personality;
        
        const scenario = document.getElementById('charactersCreate_scenario').value;
        if (scenario) body.scenario = scenario;
        
        // Conversation Settings
        const systemPrompt = document.getElementById('charactersCreate_system_prompt').value;
        if (systemPrompt) body.system_prompt = systemPrompt;
        
        const postHistoryInstructions = document.getElementById('charactersCreate_post_history_instructions').value;
        if (postHistoryInstructions) body.post_history_instructions = postHistoryInstructions;
        
        const firstMessage = document.getElementById('charactersCreate_first_message').value;
        if (firstMessage) body.first_message = firstMessage;
        
        const messageExample = document.getElementById('charactersCreate_message_example').value;
        if (messageExample) body.message_example = messageExample;
        
        // Handle alternate_greetings
        const alternateGreetingsValue = document.getElementById('charactersCreate_alternate_greetings').value;
        if (alternateGreetingsValue) {
            try {
                body.alternate_greetings = JSON.parse(alternateGreetingsValue);
            } catch (e) {
                body.alternate_greetings = alternateGreetingsValue.split(',').map(g => g.trim()).filter(g => g);
            }
        }
        
        // Metadata
        const creator = document.getElementById('charactersCreate_creator').value;
        if (creator) body.creator = creator;
        
        const creatorNotes = document.getElementById('charactersCreate_creator_notes').value;
        if (creatorNotes) body.creator_notes = creatorNotes;
        
        const characterVersion = document.getElementById('charactersCreate_character_version').value;
        if (characterVersion) body.character_version = characterVersion;
        
        const tags = document.getElementById('charactersCreate_tags').value;
        if (tags) {
            body.tags = tags.split(',').map(t => t.trim()).filter(t => t);
        }
        
        const extensionsValue = document.getElementById('charactersCreate_extensions').value;
        if (extensionsValue && extensionsValue !== '{}') {
            try {
                body.extensions = JSON.parse(extensionsValue);
            } catch (e) {
                throw new Error('Extensions must be valid JSON');
            }
        }
        
        const imageBase64 = document.getElementById('charactersCreate_image_base64').value;
        if (imageBase64) body.image_base64 = imageBase64;
        
        const response = await apiClient.makeRequest('POST', '/api/v1/characters', { body });
        responseEl.textContent = JSON.stringify(response, null, 2);
        Toast.success('Character created successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to create character: ${error.message}`);
    }
}

async function listCharacters() {
    const responseEl = document.getElementById('charactersList_response');
    try {
        responseEl.textContent = 'Loading characters...';
        const response = await apiClient.makeRequest('GET', '/api/v1/characters');
        responseEl.textContent = JSON.stringify(response, null, 2);
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to list characters: ${error.message}`);
    }
}

async function getCharacter() {
    const responseEl = document.getElementById('charactersGet_response');
    try {
        const characterId = document.getElementById('charactersGet_id').value;
        if (!characterId) {
            throw new Error('Character ID is required');
        }
        
        responseEl.textContent = 'Loading character...';
        const response = await apiClient.makeRequest('GET', `/api/v1/characters/${characterId}`);
        responseEl.textContent = JSON.stringify(response, null, 2);
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to get character: ${error.message}`);
    }
}

async function updateCharacter() {
    const responseEl = document.getElementById('charactersUpdate_response');
    try {
        const characterId = document.getElementById('charactersUpdate_id').value;
        if (!characterId) {
            throw new Error('Character ID is required');
        }
        
        const payload = document.getElementById('charactersUpdate_payload').value;
        const body = JSON.parse(payload);
        
        responseEl.textContent = 'Updating character...';
        const response = await apiClient.makeRequest('PUT', `/api/v1/characters/${characterId}`, { body });
        responseEl.textContent = JSON.stringify(response, null, 2);
        Toast.success('Character updated successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to update character: ${error.message}`);
    }
}

async function deleteCharacter() {
    const responseEl = document.getElementById('charactersDelete_response');
    try {
        const characterId = document.getElementById('charactersDelete_id').value;
        if (!characterId) {
            throw new Error('Character ID is required');
        }
        
        responseEl.textContent = 'Deleting character...';
        const response = await apiClient.makeRequest('DELETE', `/api/v1/characters/${characterId}`);
        responseEl.textContent = response ? JSON.stringify(response, null, 2) : 'Character deleted successfully';
        Toast.success('Character deleted successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to delete character: ${error.message}`);
    }
}

// Conversation functions
async function createConversation() {
    const responseEl = document.getElementById('conversationsCreate_response');
    try {
        responseEl.textContent = 'Creating conversation...';
        
        const metadata = document.getElementById('conversationsCreate_metadata').value;
        
        const body = {
            title: document.getElementById('conversationsCreate_title').value,
            initial_message: document.getElementById('conversationsCreate_initial_message').value
        };
        
        const characterId = document.getElementById('conversationsCreate_character_id').value;
        if (characterId) body.character_id = characterId;
        
        const systemPrompt = document.getElementById('conversationsCreate_system_prompt').value;
        if (systemPrompt) body.system_prompt = systemPrompt;
        
        if (metadata && metadata.trim() !== '{}') {
            body.metadata = JSON.parse(metadata);
        }
        
        const response = await apiClient.makeRequest('POST', '/api/v1/conversations', { body });
        responseEl.textContent = JSON.stringify(response, null, 2);
        Toast.success('Conversation created successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to create conversation: ${error.message}`);
    }
}

async function listConversations() {
    const responseEl = document.getElementById('conversationsList_response');
    try {
        responseEl.textContent = 'Loading conversations...';
        
        const params = new URLSearchParams();
        const characterId = document.getElementById('conversationsList_character_id').value;
        if (characterId) params.append('character_id', characterId);
        
        const limit = document.getElementById('conversationsList_limit').value;
        if (limit) params.append('limit', limit);
        
        const queryString = params.toString();
        const url = queryString ? `/api/v1/conversations?${queryString}` : '/api/v1/conversations';
        
        const response = await apiClient.makeRequest('GET', url);
        responseEl.textContent = JSON.stringify(response, null, 2);
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to list conversations: ${error.message}`);
    }
}

async function getConversationDetails() {
    const responseEl = document.getElementById('conversationsGet_response');
    try {
        const conversationId = document.getElementById('conversationsGet_id').value;
        if (!conversationId) {
            throw new Error('Conversation ID is required');
        }
        
        responseEl.textContent = 'Loading conversation...';
        
        const includeMessages = document.getElementById('conversationsGet_include_messages').checked;
        const params = includeMessages ? '?include_messages=true' : '';
        
        const response = await apiClient.makeRequest('GET', `/api/v1/conversations/${conversationId}${params}`);
        responseEl.textContent = JSON.stringify(response, null, 2);
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to get conversation: ${error.message}`);
    }
}

async function sendConversationMessage() {
    const responseEl = document.getElementById('conversationsChat_response');
    try {
        const conversationId = document.getElementById('conversationsChat_id').value;
        if (!conversationId) {
            throw new Error('Conversation ID is required');
        }
        
        const message = document.getElementById('conversationsChat_message').value;
        if (!message) {
            throw new Error('Message is required');
        }
        
        responseEl.textContent = 'Sending message...';
        
        const body = { message };
        
        const model = document.getElementById('conversationsChat_model').value;
        if (model) body.model = model;
        
        const temperature = document.getElementById('conversationsChat_temperature').value;
        if (temperature) body.temperature = parseFloat(temperature);
        
        const stream = document.getElementById('conversationsChat_stream').checked;
        body.stream = stream;
        
        if (stream) {
            // Handle streaming response
            responseEl.textContent = 'Streaming response...\n';
            const response = await fetch(`${apiClient.baseUrl}/api/v1/conversations/${conversationId}/chat`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'X-API-KEY': apiClient.token
                },
                body: JSON.stringify(body)
            });
            
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                const lines = chunk.split('\n');
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const data = line.slice(6);
                        if (data === '[DONE]') continue;
                        
                        try {
                            const parsed = JSON.parse(data);
                            if (parsed.choices?.[0]?.delta?.content) {
                                responseEl.textContent += parsed.choices[0].delta.content;
                            }
                        } catch (e) {
                            console.error('Error parsing SSE data:', e);
                        }
                    }
                }
            }
        } else {
            const response = await apiClient.makeRequest('POST', `/api/v1/conversations/${conversationId}/chat`, { body });
            responseEl.textContent = JSON.stringify(response, null, 2);
        }
        
        Toast.success('Message sent successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to send message: ${error.message}`);
    }
}

async function updateConversation() {
    const responseEl = document.getElementById('conversationsUpdate_response');
    try {
        const conversationId = document.getElementById('conversationsUpdate_id').value;
        if (!conversationId) {
            throw new Error('Conversation ID is required');
        }
        
        const payload = document.getElementById('conversationsUpdate_payload').value;
        const body = JSON.parse(payload);
        
        responseEl.textContent = 'Updating conversation...';
        const response = await apiClient.makeRequest('PUT', `/api/v1/conversations/${conversationId}`, { body });
        responseEl.textContent = JSON.stringify(response, null, 2);
        Toast.success('Conversation updated successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to update conversation: ${error.message}`);
    }
}

async function deleteConversation() {
    const responseEl = document.getElementById('conversationsDelete_response');
    try {
        const conversationId = document.getElementById('conversationsDelete_id').value;
        if (!conversationId) {
            throw new Error('Conversation ID is required');
        }
        
        responseEl.textContent = 'Deleting conversation...';
        const response = await apiClient.makeRequest('DELETE', `/api/v1/conversations/${conversationId}`);
        responseEl.textContent = response ? JSON.stringify(response, null, 2) : 'Conversation deleted successfully';
        Toast.success('Conversation deleted successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to delete conversation: ${error.message}`);
    }
}

async function exportConversation() {
    const responseEl = document.getElementById('conversationsExport_response');
    try {
        const conversationId = document.getElementById('conversationsExport_id').value;
        if (!conversationId) {
            throw new Error('Conversation ID is required');
        }
        
        const format = document.getElementById('conversationsExport_format').value;
        
        responseEl.textContent = 'Exporting conversation...';
        const response = await apiClient.makeRequest('GET', `/api/v1/conversations/${conversationId}/export?format=${format}`);
        
        if (format === 'json') {
            responseEl.textContent = JSON.stringify(response, null, 2);
        } else {
            responseEl.textContent = response;
        }
        
        Toast.success('Conversation exported successfully');
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        Toast.error(`Failed to export conversation: ${error.message}`);
    }
}

// ============================================================================
// Initialization Functions
// ============================================================================

function initializeChatCompletionsTab() {
    console.log('Chat Completions tab initialized');
    // Populate model dropdowns when tab is initialized
    if (typeof populateModelDropdowns === 'function') {
        populateModelDropdowns();
    }
}

// Store provider data globally for filtering
let globalProvidersInfo = null;

async function populateModelDropdowns() {
    try {
        // Get available providers from API
        const providersInfo = await apiClient.getAvailableProviders();
        
        // Store globally for filtering
        globalProvidersInfo = providersInfo;
        
        if (!providersInfo || !providersInfo.providers || providersInfo.providers.length === 0) {
            console.warn('No LLM providers configured');
            document.querySelectorAll('.llm-model-select').forEach(select => {
                select.innerHTML = '<option value="">No models available - check configuration</option>';
            });
            return;
        }
        
        // Build options HTML
        let optionsHtml = '';
        const defaultProvider = providersInfo.default_provider;
        let defaultModel = null;
        
        const sortedProviders = providersInfo.providers.sort((a, b) => {
            if (a.type === 'commercial' && b.type === 'local') return -1;
            if (a.type === 'local' && b.type === 'commercial') return 1;
            return a.display_name.localeCompare(b.display_name);
        });
        
        sortedProviders.forEach(provider => {
            if (provider.models && provider.models.length > 0) {
                optionsHtml += `<optgroup label="${provider.display_name}">`;
                
                provider.models.forEach(model => {
                    const value = `${provider.name}/${model}`;
                    const displayName = model;
                    const isDefault = provider.name === defaultProvider && provider.default_model === model;
                    
                    if (isDefault) {
                        defaultModel = value;
                    }
                    
                    optionsHtml += `<option value="${value}"${isDefault ? ' data-default="true"' : ''}>${displayName}${isDefault ? ' (default)' : ''}</option>`;
                });
                
                optionsHtml += '</optgroup>';
            }
        });
        
        // Update all model select dropdowns
        document.querySelectorAll('.llm-model-select').forEach(select => {
            const currentValue = select.value;
            const hasUseDefault = select.querySelector('option[value=""]');
            
            let html = '';
            if (hasUseDefault && hasUseDefault.textContent.includes('Use default')) {
                html = '<option value="">Use default</option>';
            }
            html += optionsHtml;
            
            select.innerHTML = html;
            
            if (currentValue) {
                select.value = currentValue;
            } else if (defaultModel && !hasUseDefault) {
                select.value = defaultModel;
            }
        });
        
        console.log(`Populated model dropdowns with ${providersInfo.total_configured} providers`);
        
        // Set up provider change event listeners
        setupProviderChangeListeners();
        
    } catch (error) {
        console.error('Failed to populate model dropdowns:', error);
        document.querySelectorAll('.llm-model-select').forEach(select => {
            select.innerHTML = '<option value="">Error loading models</option>';
        });
    }
}

// Function to filter models based on selected provider
function filterModelsByProvider(providerSelectId, modelSelectId) {
    const providerSelect = document.getElementById(providerSelectId);
    const modelSelect = document.getElementById(modelSelectId);
    
    if (!providerSelect || !modelSelect || !globalProvidersInfo) {
        return;
    }
    
    const selectedProvider = providerSelect.value;
    
    // Clear current options
    modelSelect.innerHTML = '';
    
    if (!selectedProvider || selectedProvider === '') {
        // If "Default" or no provider selected, show all models grouped by provider
        const sortedProviders = globalProvidersInfo.providers.sort((a, b) => {
            if (a.type === 'commercial' && b.type === 'local') return -1;
            if (a.type === 'local' && b.type === 'commercial') return 1;
            return a.display_name.localeCompare(b.display_name);
        });
        
        sortedProviders.forEach(provider => {
            if (provider.models && provider.models.length > 0) {
                const optgroup = document.createElement('optgroup');
                optgroup.label = provider.display_name;
                
                provider.models.forEach(model => {
                    const option = document.createElement('option');
                    option.value = `${provider.name}/${model}`;
                    option.textContent = model;
                    if (provider.name === globalProvidersInfo.default_provider && model === provider.default_model) {
                        option.textContent += ' (default)';
                        option.dataset.default = 'true';
                    }
                    optgroup.appendChild(option);
                });
                
                modelSelect.appendChild(optgroup);
            }
        });
        
        // Select default model if available
        const defaultOption = modelSelect.querySelector('[data-default="true"]');
        if (defaultOption) {
            modelSelect.value = defaultOption.value;
        }
    } else {
        // Show only models for selected provider
        const provider = globalProvidersInfo.providers.find(p => p.name === selectedProvider);
        if (provider && provider.models && provider.models.length > 0) {
            // Add models without optgroup since we're showing only one provider
            provider.models.forEach(model => {
                const option = document.createElement('option');
                option.value = `${provider.name}/${model}`;
                option.textContent = model;
                modelSelect.appendChild(option);
            });
            
            // Select first model by default
            if (provider.models.length > 0) {
                modelSelect.value = `${provider.name}/${provider.models[0]}`;
            }
        } else {
            // No models for this provider
            const option = document.createElement('option');
            option.value = '';
            option.textContent = 'No models available for this provider';
            modelSelect.appendChild(option);
        }
    }
}

// Setup event listeners for provider dropdowns
function setupProviderChangeListeners() {
    // Add event listener for chat completions provider dropdown
    const chatCompletionsProvider = document.getElementById('chatCompletions_provider');
    if (chatCompletionsProvider) {
        // Remove any existing listeners first
        const newProvider = chatCompletionsProvider.cloneNode(true);
        chatCompletionsProvider.parentNode.replaceChild(newProvider, chatCompletionsProvider);
        
        newProvider.addEventListener('change', () => {
            filterModelsByProvider('chatCompletions_provider', 'chatCompletions_model');
        });
    }
    
    // Add event listener for interactive chat provider dropdown
    const chatProvider = document.getElementById('chat-provider');
    if (chatProvider) {
        // Remove any existing listeners first
        const newProvider = chatProvider.cloneNode(true);
        chatProvider.parentNode.replaceChild(newProvider, chatProvider);
        
        newProvider.addEventListener('change', () => {
            filterModelsByProvider('chat-provider', 'chat-model');
        });
    }
}

// ============================================================================
// Prompts Tab Functions
// ============================================================================

async function createPrompt() {
    const responseEl = document.getElementById('promptsCreate_response');
    const curlEl = document.getElementById('promptsCreate_curl');
    
    try {
        // Collect form data
        const name = document.getElementById('promptsCreate_name').value.trim();
        if (!name) {
            throw new Error('Name is required');
        }
        
        const payload = {
            name: name
        };
        
        // Add optional fields if they have values
        const systemPrompt = document.getElementById('promptsCreate_system_prompt').value.trim();
        if (systemPrompt) {
            payload.system_prompt = systemPrompt;
        }
        
        const userPrompt = document.getElementById('promptsCreate_user_prompt').value.trim();
        if (userPrompt) {
            payload.user_prompt = userPrompt;
        }
        
        const details = document.getElementById('promptsCreate_details').value.trim();
        if (details) {
            payload.details = details;
        }
        
        const author = document.getElementById('promptsCreate_author').value.trim();
        if (author) {
            payload.author = author;
        }
        
        const keywordsStr = document.getElementById('promptsCreate_keywords').value.trim();
        if (keywordsStr) {
            // Convert comma-separated string to array
            payload.keywords = keywordsStr.split(',').map(k => k.trim()).filter(k => k);
        }
        
        // Make the API request
        responseEl.textContent = 'Creating prompt...';
        
        // Generate cURL command
        const curlCommand = apiClient.generateCurl('POST', '/api/v1/prompts', { body: payload });
        if (curlEl) {
            curlEl.textContent = curlCommand;
        }
        
        const response = await apiClient.makeRequest('POST', '/api/v1/prompts', { body: payload });
        responseEl.textContent = JSON.stringify(response, null, 2);
        
        // Show success message
        if (typeof Toast !== 'undefined' && Toast.success) {
            Toast.success('Prompt created successfully');
        }
        
        // Optionally clear the form
        document.getElementById('promptsCreate_name').value = '';
        document.getElementById('promptsCreate_system_prompt').value = '';
        document.getElementById('promptsCreate_user_prompt').value = '';
        document.getElementById('promptsCreate_details').value = '';
        document.getElementById('promptsCreate_author').value = '';
        document.getElementById('promptsCreate_keywords').value = '';
        
    } catch (error) {
        responseEl.textContent = `Error: ${error.message}`;
        if (typeof Toast !== 'undefined' && Toast.error) {
            Toast.error(`Failed to create prompt: ${error.message}`);
        }
    }
}

// Make sure functions are globally available
console.log('Tab functions loaded successfully');
