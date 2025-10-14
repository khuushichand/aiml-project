/**
 * TTS Module for WebUI
 * Handles Text-to-Speech functionality with multiple providers
 */

const TTS = {
    // Current state
    currentProvider: 'vibevoice',
    currentAudioUrl: null,
    isGenerating: false,
    abortController: null,
    history: [],
    customVoices: [],
    catalogVoices: [],
    // When custom voice management is not available (501),
    // fallback to showing provider catalog voices
    _catalogFallback: false,
    
    // Get API token from api-client or localStorage
    getApiToken() {
        // First try to get from api-client if available
        if (window.apiClient && window.apiClient.token) {
            return window.apiClient.token;
        }
        // Fallback to localStorage
        return localStorage.getItem('apiToken') || '';
    },
    
    // Provider configurations
    providers: {
        vibevoice: {
            name: 'VibeVoice',
            supportsCloning: true,
            maxLength: 64000,
            models: ['1.5B', '7B']
        },
        kokoro: {
            name: 'Kokoro',
            supportsCloning: false,
            maxLength: 10000,
            supportsMixing: true
        },
        higgs: {
            name: 'Higgs Audio',
            supportsCloning: true,
            maxLength: 10000,
            languages: 50
        },
        chatterbox: {
            name: 'Chatterbox',
            supportsCloning: true,
            maxLength: 5000,
            supportsEmotion: true
        },
        openai: {
            name: 'OpenAI',
            supportsCloning: false,
            maxLength: 4096,
            requiresKey: true
        },
        elevenlabs: {
            name: 'ElevenLabs',
            supportsCloning: true,
            maxLength: 5000,
            requiresKey: true
        }
    },
    
    // Initialize the TTS module
    init() {
        console.log('Initializing TTS module...');
        this.loadHistory();
        this.checkProviderStatus();
        this.refreshVoiceList();
        this.setupEventListeners();
        
        // Set initial provider
        this.switchProvider('vibevoice');
    },
    
    // Set up event listeners
    setupEventListeners() {
        // Speed sliders
        ['kokoro', 'openai'].forEach(provider => {
            const slider = document.getElementById(`${provider}-speed`);
            if (slider) {
                slider.addEventListener('input', (e) => {
                    document.getElementById(`${provider}-speed-value`).textContent = `${e.target.value}x`;
                });
            }
        });
        
        // Intensity/stability sliders
        const intensitySlider = document.getElementById('chatterbox-intensity');
        if (intensitySlider) {
            intensitySlider.addEventListener('input', (e) => {
                document.getElementById('chatterbox-intensity-value').textContent = `${e.target.value}%`;
            });
        }
        
        const stabilitySlider = document.getElementById('elevenlabs-stability');
        if (stabilitySlider) {
            stabilitySlider.addEventListener('input', (e) => {
                document.getElementById('elevenlabs-stability-value').textContent = `${e.target.value}%`;
            });
        }
        
        const claritySlider = document.getElementById('elevenlabs-clarity');
        if (claritySlider) {
            claritySlider.addEventListener('input', (e) => {
                document.getElementById('elevenlabs-clarity-value').textContent = `${e.target.value}%`;
            });
        }
    },
    
    // Switch to a different provider
    switchProvider(provider) {
        console.log(`Switching to provider: ${provider}`);
        
        // Update current provider
        this.currentProvider = provider;
        
        // Update UI tabs
        document.querySelectorAll('.sub-tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.provider === provider);
        });
        
        document.querySelectorAll('.provider-content').forEach(content => {
            content.classList.toggle('active', content.id === `provider-${provider}`);
        });
        
        // Update max length based on provider
        const maxLength = this.providers[provider].maxLength || 5000;
        const textInput = document.getElementById('tts-text-input');
        if (textInput) {
            textInput.maxLength = maxLength;
            this.updateCharCounter();
        }
        
        // Load custom voices for this provider
        this.loadCustomVoicesForProvider(provider);
    },
    
    // Check provider status
    async checkProviderStatus() {
        try {
            const apiToken = this.getApiToken();
            const headers = {};
            
            // Add authorization header if token exists
            if (apiToken) {
                headers['Authorization'] = `Bearer ${apiToken}`;
            }
            
            const response = await fetch('/api/v1/audio/health', {
                headers: headers
            });
            const data = await response.json();
            
            if (data.status === 'healthy' && data.providers) {
                // Update status indicators
                Object.keys(this.providers).forEach(provider => {
                    const indicator = document.getElementById(`status-${provider}`);
                    if (indicator) {
                        const providerData = data.providers.details?.[provider];
                        if (providerData && providerData.status === 'available') {
                            indicator.classList.add('active');
                            indicator.classList.remove('error');
                        } else {
                            indicator.classList.remove('active');
                            indicator.classList.add('error');
                        }
                    }
                });
            }
        } catch (error) {
            console.error('Error checking provider status:', error);
        }
    },
    
    // Update character counter
    updateCharCounter() {
        const textInput = document.getElementById('tts-text-input');
        const counter = document.getElementById('tts-char-counter');
        if (textInput && counter) {
            const maxLength = this.providers[this.currentProvider].maxLength || 5000;
            counter.textContent = `${textInput.value.length} / ${maxLength}`;
        }
    },
    
    // Load sample text
    loadSampleText() {
        const samples = {
            vibevoice: "Welcome to VibeVoice! I can generate expressive long-form speech with multiple speakers and even add background music. Let me demonstrate my capabilities with this sample text.",
            kokoro: "Hello! This is Kokoro speaking. I'm a lightweight TTS model that can blend multiple voices together. Try mixing af_bella and af_sky for unique voice combinations!",
            higgs: "Greetings! Higgs Audio here, supporting over 50 languages with high-quality synthesis. I can even generate music and clone voices from short audio samples.",
            chatterbox: "Hi there! I'm Chatterbox, and I can express emotions in my speech. Whether happy, sad, or excited, I can adjust my emotional tone to match your needs.",
            openai: "This is OpenAI's text-to-speech system. We provide consistent, high-quality voices suitable for a wide range of applications.",
            elevenlabs: "Welcome to ElevenLabs! We specialize in ultra-realistic voice synthesis with fine control over voice characteristics."
        };
        
        const textInput = document.getElementById('tts-text-input');
        if (textInput) {
            textInput.value = samples[this.currentProvider] || samples.vibevoice;
            this.updateCharCounter();
        }
    },
    
    // Clear text
    clearText() {
        const textInput = document.getElementById('tts-text-input');
        if (textInput) {
            textInput.value = '';
            this.updateCharCounter();
        }
    },
    
    // Generate speech
    async generate() {
        if (this.isGenerating) {
            this.showStatus('Generation already in progress', 'info');
            return;
        }
        
        const textInput = document.getElementById('tts-text-input');
        if (!textInput || !textInput.value.trim()) {
            this.showStatus('Please enter some text', 'error');
            return;
        }
        
        this.isGenerating = true;
        this.abortController = new AbortController();
        
        // Update UI
        document.getElementById('tts-generate-btn').style.display = 'none';
        document.getElementById('tts-stop-btn').style.display = 'inline-block';
        this.showStatus('Generating speech...', 'info');
        
        try {
            // Build request based on provider
            const request = this.buildRequest();
            
            // Make API call
            const apiToken = this.getApiToken();
            const headers = {
                'Content-Type': 'application/json'
            };
            
            // Add authorization header if token exists
            if (apiToken) {
                headers['Authorization'] = `Bearer ${apiToken}`;
            }
            
            const response = await fetch('/api/v1/audio/speech', {
                method: 'POST',
                headers: headers,
                body: JSON.stringify(request),
                signal: this.abortController.signal
            });
            
            if (!response.ok) {
                const error = await response.text();
                throw new Error(error || `HTTP ${response.status}`);
            }
            
            // Handle streaming or non-streaming response
            if (request.stream) {
                await this.handleStreamingResponse(response);
            } else {
                await this.handleNonStreamingResponse(response);
            }
            
            this.showStatus('Speech generated successfully!', 'success');
            
            // Add to history
            this.addToHistory({
                text: textInput.value.substring(0, 100) + (textInput.value.length > 100 ? '...' : ''),
                provider: this.currentProvider,
                voice: this.getSelectedVoice(),
                timestamp: new Date().toISOString()
            });
            
        } catch (error) {
            if (error.name === 'AbortError') {
                this.showStatus('Generation cancelled', 'info');
            } else {
                console.error('TTS generation error:', error);
                this.showStatus(`Error: ${error.message}`, 'error');
            }
        } finally {
            this.isGenerating = false;
            document.getElementById('tts-generate-btn').style.display = 'inline-block';
            document.getElementById('tts-stop-btn').style.display = 'none';
        }
    },
    
    // Build request based on current provider
    buildRequest() {
        const text = document.getElementById('tts-text-input').value;
        const format = document.getElementById('tts-format').value;
        const streaming = document.getElementById('tts-streaming').checked;
        
        let request = {
            input: text,
            response_format: format,
            stream: streaming,
            extra_params: {}
        };
        
        // Provider-specific settings
        switch (this.currentProvider) {
            case 'vibevoice':
                const customVoice = document.getElementById('vibevoice-custom-voice').value;
                request.model = document.getElementById('vibevoice-model').value;
                request.voice = customVoice || document.getElementById('vibevoice-voice').value;
                request.provider = 'vibevoice';
                
                // Add advanced generation parameters under extra_params
                request.extra_params = {
                    cfg_scale: parseFloat(document.getElementById('vibevoice-cfg').value),
                    diffusion_steps: parseInt(document.getElementById('vibevoice-steps').value),
                    temperature: parseFloat(document.getElementById('vibevoice-temperature').value),
                    top_p: parseFloat(document.getElementById('vibevoice-topp').value),
                    attention_type: document.getElementById('vibevoice-attention').value,
                };
                
                // Add seed if provided
                const seed = document.getElementById('vibevoice-seed').value;
                if (seed) {
                    request.extra_params.seed = parseInt(seed);
                }
                
                // Add features
                request.extra_params.background_music = document.getElementById('vibevoice-music').checked;
                request.extra_params.enable_singing = document.getElementById('vibevoice-singing').checked;
                request.extra_params.speaker_count = parseInt(document.getElementById('vibevoice-speakers').value);
                break;
                
            case 'kokoro':
                const voiceMix = document.getElementById('kokoro-voice-mix').value;
                request.model = 'kokoro';
                request.voice = voiceMix || document.getElementById('kokoro-voice').value;
                request.speed = parseFloat(document.getElementById('kokoro-speed').value);
                break;
                
            case 'higgs':
                request.model = 'higgs';
                request.voice = document.getElementById('higgs-voice').value;
                request.lang_code = document.getElementById('higgs-language').value;
                break;
                
            case 'chatterbox':
                request.model = 'chatterbox';
                request.voice = document.getElementById('chatterbox-voice').value;
                request.extra_params = {
                    emotion: document.getElementById('chatterbox-emotion').value,
                    emotion_intensity: parseInt(document.getElementById('chatterbox-intensity').value)
                };
                break;
                
            case 'openai':
                request.model = document.getElementById('openai-model').value;
                request.voice = document.getElementById('openai-voice').value;
                request.speed = parseFloat(document.getElementById('openai-speed').value);
                break;
                
            case 'elevenlabs':
                request.model = 'elevenlabs';
                request.voice = document.getElementById('elevenlabs-voice').value;
                request.extra_params = {
                    stability: parseInt(document.getElementById('elevenlabs-stability').value) / 100,
                    clarity: parseInt(document.getElementById('elevenlabs-clarity').value) / 100
                };
                break;
        }
        
        return request;
    },
    
    // Get selected voice name
    getSelectedVoice() {
        switch (this.currentProvider) {
            case 'vibevoice':
                return document.getElementById('vibevoice-custom-voice').value || 
                       document.getElementById('vibevoice-voice').value;
            case 'kokoro':
                return document.getElementById('kokoro-voice-mix').value || 
                       document.getElementById('kokoro-voice').value;
            case 'higgs':
                return document.getElementById('higgs-voice').value;
            case 'chatterbox':
                return document.getElementById('chatterbox-voice').value;
            case 'openai':
                return document.getElementById('openai-voice').value;
            case 'elevenlabs':
                return document.getElementById('elevenlabs-voice').value;
            default:
                return 'default';
        }
    },
    
    // Handle streaming response with real-time playback (MSE where supported)
    async handleStreamingResponse(response) {
        const format = document.getElementById('tts-format').value;
        const audioPlayer = document.getElementById('tts-audio-player');

        // Use MSE for MP3 when supported, fallback to buffering
        const useMSE = 'MediaSource' in window && MediaSource.isTypeSupported('audio/mpeg');
        if (useMSE && format === 'mp3') {
            const mediaSource = new MediaSource();
            const url = URL.createObjectURL(mediaSource);
            if (this.currentAudioUrl) {
                URL.revokeObjectURL(this.currentAudioUrl);
            }
            this.currentAudioUrl = url;
            audioPlayer.src = url;
            audioPlayer.play();

            mediaSource.addEventListener('sourceopen', async () => {
                const sourceBuffer = mediaSource.addSourceBuffer('audio/mpeg');
                const reader = response.body.getReader();
                const queue = [];
                let appending = false;

                const appendNext = () => {
                    if (appending || queue.length === 0) return;
                    appending = true;
                    const chunk = queue.shift();
                    try {
                        sourceBuffer.appendBuffer(chunk);
                    } catch (e) {
                        appending = false;
                        console.error('SourceBuffer append error:', e);
                        // Fallback: end stream
                        try { mediaSource.endOfStream(); } catch (_) {}
                    }
                };

                sourceBuffer.addEventListener('updateend', () => {
                    appending = false;
                    appendNext();
                });

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    queue.push(value.buffer);
                    appendNext();
                }
                // End the stream when done (after buffer flush)
                const endWhenFlushed = () => {
                    if (!sourceBuffer.updating && queue.length === 0) {
                        try { mediaSource.endOfStream(); } catch (_) {}
                    } else {
                        setTimeout(endWhenFlushed, 50);
                    }
                };
                endWhenFlushed();
            });
        } else {
            // Fallback: buffer then play
            const reader = response.body.getReader();
            const chunks = [];
            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                chunks.push(value);
            }
            const mime = format === 'wav' ? 'audio/wav' : (format === 'opus' ? 'audio/opus' : (format === 'aac' ? 'audio/aac' : 'audio/mpeg'));
            const blob = new Blob(chunks, { type: mime });
            const url = URL.createObjectURL(blob);
            if (this.currentAudioUrl) {
                URL.revokeObjectURL(this.currentAudioUrl);
            }
            this.currentAudioUrl = url;
            audioPlayer.src = url;
            audioPlayer.play();
        }

        document.getElementById('tts-download-btn').disabled = false;
    },
    
    // Handle non-streaming response
    async handleNonStreamingResponse(response) {
        const blob = await response.blob();
        const url = URL.createObjectURL(blob);
        
        // Update audio player
        const audioPlayer = document.getElementById('tts-audio-player');
        if (audioPlayer) {
            if (this.currentAudioUrl) {
                URL.revokeObjectURL(this.currentAudioUrl);
            }
            this.currentAudioUrl = url;
            audioPlayer.src = url;
            audioPlayer.play();
        }
        
        // Enable download button
        document.getElementById('tts-download-btn').disabled = false;
    },
    
    // Stop generation
    stop() {
        if (this.abortController) {
            this.abortController.abort();
            this.abortController = null;
        }
    },
    
    // Download audio
    downloadAudio() {
        if (!this.currentAudioUrl) return;
        
        const a = document.createElement('a');
        a.href = this.currentAudioUrl;
        a.download = `tts_${this.currentProvider}_${Date.now()}.${document.getElementById('tts-format').value}`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    },
    
    // Open voice upload modal
    openVoiceUpload(provider) {
        const modal = document.getElementById('voice-upload-modal');
        if (modal) {
            modal.style.display = 'block';
            modal.dataset.provider = provider;
        }
    },
    
    // Close voice upload modal
    closeVoiceUpload() {
        const modal = document.getElementById('voice-upload-modal');
        if (modal) {
            modal.style.display = 'none';
        }
    },
    
    // Upload voice
    async uploadVoice() {
        const modal = document.getElementById('voice-upload-modal');
        const provider = modal.dataset.provider || this.currentProvider;
        
        const name = document.getElementById('voice-upload-name').value;
        const description = document.getElementById('voice-upload-description').value;
        const fileInput = document.getElementById('voice-upload-file');
        
        if (!name || !fileInput.files[0]) {
            this.showStatus('Please provide a name and select a file', 'error');
            return;
        }
        
        const formData = new FormData();
        formData.append('name', name);
        formData.append('description', description);
        formData.append('provider', provider);
        formData.append('file', fileInput.files[0]);
        
        try {
            const apiToken = this.getApiToken();
            const headers = {};
            
            // Add authorization header if token exists
            if (apiToken) {
                headers['Authorization'] = `Bearer ${apiToken}`;
            }
            
            const response = await fetch('/api/v1/audio/voices/upload', {
                method: 'POST',
                headers: headers,
                body: formData
            });
            
            if (response.status === 501) {
                this.showStatus('Custom voice upload is not available for this provider or build.', 'warning');
                return;
            }
            if (!response.ok) {
                throw new Error(`Upload failed: ${response.statusText}`);
            }
            
            const result = await response.json();
            this.showStatus('Voice uploaded successfully!', 'success');
            this.closeVoiceUpload();
            this.refreshVoiceList();
            this.loadCustomVoicesForProvider(provider);
            
        } catch (error) {
            console.error('Voice upload error:', error);
            this.showStatus(`Upload failed: ${error.message}`, 'error');
        }
    },
    
    // Upload voice clone for specific providers
    async uploadVoiceClone(provider) {
        const fileInput = document.getElementById(`${provider}-voice-upload`);
        if (!fileInput || !fileInput.files[0]) {
            this.showStatus('Please select an audio file', 'error');
            return;
        }
        
        // This would trigger the voice upload with provider-specific settings
        this.openVoiceUpload(provider);
    },
    
    // Refresh voice list (both custom and catalog)
    async refreshVoiceList() {
        try {
            const apiToken = this.getApiToken();
            const headers = {};
            
            // Add authorization header if token exists
            if (apiToken) {
                headers['Authorization'] = `Bearer ${apiToken}`;
            }
            // Fetch custom voices (if available)
            let customUnavailable = false;
            try {
                const response = await fetch('/api/v1/audio/voices', { headers });
                if (response.status === 501) {
                    customUnavailable = true;
                    this.customVoices = [];
                } else if (!response.ok) {
                    throw new Error('Failed to fetch voices');
                } else {
                    const data = await response.json();
                    this.customVoices = data.voices || [];
                }
            } catch (e) {
                console.warn('Custom voice fetch failed:', e);
                this.customVoices = [];
            }

            // Always fetch catalog voices for current provider
            try {
                this.catalogVoices = await this._fetchProviderCatalogVoices(this.currentProvider);
            } catch (e) {
                console.warn('Catalog voice fetch failed:', e);
                this.catalogVoices = [];
            }

            // Catalog fallback flag only if custom unavailable and catalog present
            this._catalogFallback = customUnavailable && this.catalogVoices.length > 0;

            // Render
            this.displayVoiceList();
            if (customUnavailable) {
                this.showStatus('Custom voice management is not available in this build; showing provider catalog voices.', 'warning');
            }
            
        } catch (error) {
            console.error('Error fetching voices:', error);
        }
    },

    // Helper: fetch provider catalog voices (returns an array)
    async _fetchProviderCatalogVoices(provider) {
        const apiToken = this.getApiToken();
        const headers = {};
        if (apiToken) headers['Authorization'] = `Bearer ${apiToken}`;
        const url = provider ? `/api/v1/audio/voices/catalog?provider=${encodeURIComponent(provider)}`
                             : '/api/v1/audio/voices/catalog';
        const res = await fetch(url, { headers });
        if (!res.ok) throw new Error(`Failed to fetch voice catalog (${res.status})`);
        const body = await res.json();
        // If provider specified, server returns { provider: [voices] }
        if (provider && body && typeof body === 'object') {
            const key = provider.toLowerCase();
            return Array.isArray(body[key]) ? body[key] : [];
        }
        // If no provider specified, flatten all providers into a single list with provider tag
        const out = [];
        for (const [prov, list] of Object.entries(body || {})) {
            if (Array.isArray(list)) {
                list.forEach(v => out.push({ ...v, provider: prov }));
            }
        }
        return out;
    },
    
    // Display voice list
    displayVoiceList() {
        const voiceList = document.getElementById('voice-list');
        if (!voiceList) return;

        const renderCustom = () => {
            if (!this.customVoices.length) {
                return '<p class="text-muted">No custom voices uploaded yet</p>';
            }
            return this.customVoices.map(v => {
                const id = v.voice_id;
                const name = v.name || id || 'Voice';
                const provider = v.provider || '';
                const description = v.description || '';
                return `
                <div class="voice-item" data-voice-id="${id}" data-provider="${provider}" data-voice-name="${name}">
                    <h5>${name} <span class="badge">Custom</span></h5>
                    <p class="text-muted">${provider}</p>
                    <small>${description || 'No description'}</small>
                    <div class="voice-actions">
                        <button class="btn btn-sm btn-primary" onclick="TTS.useCustomVoiceFromEl(this)">
                            <i class="fas fa-check"></i> Use Voice
                        </button>
                        <button class="btn btn-sm btn-secondary" onclick="TTS.previewVoice('${id}')">
                            <i class="fas fa-play"></i> Preview
                        </button>
                        <button class="btn btn-sm btn-danger" onclick="TTS.deleteVoice('${id}')">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>`;
            }).join('');
        };

        const renderCatalog = () => {
            if (!this.catalogVoices.length) {
                return '<p class="text-muted">No catalog voices available</p>';
            }
            return this.catalogVoices.map(v => {
                const id = v.id || v.name || 'voice';
                const name = v.name || v.id || 'Voice';
                const provider = v.provider || this.currentProvider || '';
                const description = v.description || 'Catalog voice';
                const meta = [v.language, v.gender].filter(Boolean).join(' · ');
                return `
                <div class="voice-item" data-voice-id="${id}" data-provider="${provider}" data-voice-name="${name}">
                    <h5>${name} <span class="badge">Catalog</span></h5>
                    <p class="text-muted">${provider}${meta ? ` • ${meta}` : ''}</p>
                    <small>${description}</small>
                    <div class="voice-actions">
                        <button class="btn btn-sm btn-primary" onclick="TTS.useCatalogVoiceFromEl(this)">
                            <i class="fas fa-check"></i> Use Voice
                        </button>
                    </div>
                </div>`;
            }).join('');
        };

        // Two sections side-by-side (if space allows)
        voiceList.innerHTML = `
            <div class="voice-sections" style="display:grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap:16px;">
                <div class="voice-section">
                    <h5>Your Custom Voices</h5>
                    ${renderCustom()}
                </div>
                <div class="voice-section">
                    <h5>Provider Catalog Voices</h5>
                    ${renderCatalog()}
                </div>
            </div>
        `;
    },

    // Internal helper: switch UI to provider and select a voice in the correct control
    _selectProviderVoice(provider, voiceId, name = '', isCustom = false) {
        // Switch provider sub-tab in TTS UI
        this.switchProvider(provider);

        const selectIdMap = {
            vibevoice: isCustom ? 'vibevoice-custom-voice' : 'vibevoice-voice',
            kokoro: 'kokoro-voice',
            higgs: 'higgs-voice',
            chatterbox: 'chatterbox-voice',
            openai: 'openai-voice',
            elevenlabs: 'elevenlabs-voice'
        };
        const sid = selectIdMap[provider] || null;
        if (!sid) return false;
        const sel = document.getElementById(sid);
        if (!sel) return false;

        // Determine value to set
        let value = voiceId;
        if (provider === 'vibevoice' && isCustom) {
            value = `custom:${voiceId}`;
        }
        // Ensure option exists
        let opt = Array.from(sel.options).find(o => o.value === value || o.text === name || o.text === voiceId);
        if (!opt) {
            const o = document.createElement('option');
            o.value = value;
            o.textContent = name || voiceId;
            sel.appendChild(o);
        }
        sel.value = value;
        try { sel.dispatchEvent(new Event('change')); } catch (_) { /* ignore */ }
        return true;
    },

    // Use a catalog voice in the TTS tab
    async useCatalogVoice(provider, voiceId, name = '') {
        try {
            const ok = this._selectProviderVoice(provider, voiceId, name, false);
            if (!ok) throw new Error('Voice control not found');
            this.showStatus(`Selected voice ${name || voiceId} (${provider})`, 'success');
            // Also sync Audio → Text to Speech panel
            const providerSelect = document.getElementById('audioTTS_provider');
            if (providerSelect) {
                providerSelect.value = provider;
                if (typeof updateTTSProviderOptions === 'function') {
                    try { updateTTSProviderOptions(); } catch (_) { /* ignore */ }
                }
                if (typeof loadProviderVoices === 'function') {
                    try { await loadProviderVoices(); } catch (_) { /* ignore */ }
                }
                const voiceSelect = document.getElementById('audioTTS_voice');
                if (voiceSelect) {
                    let opt = Array.from(voiceSelect.options).find(o => o.value === voiceId || o.text === name || o.text === voiceId);
                    if (!opt) {
                        const o = document.createElement('option');
                        o.value = voiceId;
                        o.textContent = name || voiceId;
                        voiceSelect.appendChild(o);
                    }
                    voiceSelect.value = voiceId;
                    try { voiceSelect.dispatchEvent(new Event('change')); } catch (_) { /* ignore */ }
                }
            }
        } catch (e) {
            console.error('Failed to use catalog voice:', e);
            this.showStatus('Failed to select catalog voice', 'error');
        }
    },

    // Use a custom voice in the TTS tab
    async useCustomVoice(provider, voiceId, name = '') {
        try {
            const ok = this._selectProviderVoice(provider, voiceId, name, true);
            if (!ok) throw new Error('Custom voice control not found');
            this.showStatus(`Selected custom voice ${name || voiceId} (${provider})`, 'success');
            // Sync into Audio → Text to Speech panel as a generic voice selection
            const providerSelect = document.getElementById('audioTTS_provider');
            if (providerSelect) {
                providerSelect.value = provider;
                if (typeof updateTTSProviderOptions === 'function') {
                    try { updateTTSProviderOptions(); } catch (_) { /* ignore */ }
                }
                if (typeof loadProviderVoices === 'function') {
                    try { await loadProviderVoices(); } catch (_) { /* ignore */ }
                }
                const voiceSelect = document.getElementById('audioTTS_voice');
                if (voiceSelect) {
                    // We set the base voice if detectable, otherwise append a synthetic option
                    let opt = Array.from(voiceSelect.options).find(o => o.text === name || o.value === voiceId);
                    if (!opt) {
                        const o = document.createElement('option');
                        o.value = voiceId;
                        o.textContent = name || voiceId;
                        voiceSelect.appendChild(o);
                    }
                    voiceSelect.value = voiceId;
                    try { voiceSelect.dispatchEvent(new Event('change')); } catch (_) { /* ignore */ }
                }
            }
        } catch (e) {
            console.error('Failed to use custom voice:', e);
            this.showStatus('Failed to select custom voice', 'error');
        }
    },

    // Event hooks from voice list buttons
    useCatalogVoiceFromEl(btn) {
        try {
            const item = btn.closest('.voice-item');
            if (!item) return;
            const provider = item.getAttribute('data-provider') || this.currentProvider;
            const voiceId = item.getAttribute('data-voice-id');
            const name = item.getAttribute('data-voice-name') || '';
            return this.useCatalogVoice(provider, voiceId, name);
        } catch (e) {
            console.error('useCatalogVoiceFromEl error:', e);
        }
    },

    useCustomVoiceFromEl(btn) {
        try {
            const item = btn.closest('.voice-item');
            if (!item) return;
            const provider = item.getAttribute('data-provider') || this.currentProvider;
            const voiceId = item.getAttribute('data-voice-id');
            const name = item.getAttribute('data-voice-name') || '';
            return this.useCustomVoice(provider, voiceId, name);
        } catch (e) {
            console.error('useCustomVoiceFromEl error:', e);
        }
    },
    
    // Load custom voices for current provider
    loadCustomVoicesForProvider(provider) {
        const providerVoices = this.customVoices.filter(v => v.provider === provider);
        
        // Update custom voice dropdown for VibeVoice
        if (provider === 'vibevoice') {
            const select = document.getElementById('vibevoice-custom-voice');
            if (select) {
                select.innerHTML = '<option value="">None</option>' + 
                    providerVoices.map(v => `<option value="custom:${v.voice_id}">${v.name}</option>`).join('');
            }
        }
    },
    
    // Preview voice
    async previewVoice(voiceId) {
        try {
            const apiToken = this.getApiToken();
            const headers = {
                'Content-Type': 'application/json'
            };
            
            // Add authorization header if token exists
            if (apiToken) {
                headers['Authorization'] = `Bearer ${apiToken}`;
            }
            
            const response = await fetch(`/api/v1/audio/voices/${voiceId}/preview`, {
                method: 'POST',
                headers: headers,
                body: JSON.stringify({
                    text: 'This is a preview of your custom voice.'
                })
            });
            
            if (response.status === 501) {
                this.showStatus('Voice preview is not available for this provider or build.', 'warning');
                return;
            }
            if (!response.ok) {
                throw new Error('Preview failed');
            }
            
            const blob = await response.blob();
            const url = URL.createObjectURL(blob);
            
            const audio = new Audio(url);
            audio.play();
            
        } catch (error) {
            console.error('Preview error:', error);
            this.showStatus('Failed to preview voice', 'error');
        }
    },
    
    // Delete voice
    async deleteVoice(voiceId) {
        if (!confirm('Are you sure you want to delete this voice?')) return;
        
        try {
            const apiToken = this.getApiToken();
            const headers = {};
            
            // Add authorization header if token exists
            if (apiToken) {
                headers['Authorization'] = `Bearer ${apiToken}`;
            }
            
            const response = await fetch(`/api/v1/audio/voices/${voiceId}`, {
                method: 'DELETE',
                headers: headers
            });
            
            if (response.status === 501) {
                this.showStatus('Deleting custom voices is not available for this provider or build.', 'warning');
                return;
            }
            if (!response.ok) {
                throw new Error('Delete failed');
            }
            
            this.showStatus('Voice deleted successfully', 'success');
            this.refreshVoiceList();
            
        } catch (error) {
            console.error('Delete error:', error);
            this.showStatus('Failed to delete voice', 'error');
        }
    },
    
    // Add to history
    addToHistory(item) {
        this.history.unshift(item);
        if (this.history.length > 20) {
            this.history = this.history.slice(0, 20);
        }
        this.saveHistory();
        this.displayHistory();
    },
    
    // Display history
    displayHistory() {
        const historyList = document.getElementById('tts-history');
        if (!historyList) return;
        
        if (this.history.length === 0) {
            historyList.innerHTML = '<p class="text-muted">No generation history yet</p>';
            return;
        }
        
        historyList.innerHTML = this.history.map((item, index) => `
            <div class="history-item">
                <div>
                    <strong>${item.provider}</strong> - ${item.voice}<br>
                    <small>${item.text}</small><br>
                    <small class="text-muted">${new Date(item.timestamp).toLocaleString()}</small>
                </div>
                <button class="btn btn-sm btn-secondary" onclick="TTS.replayHistory(${index})">
                    <i class="fas fa-redo"></i> Replay
                </button>
            </div>
        `).join('');
    },
    
    // Replay from history
    replayHistory(index) {
        const item = this.history[index];
        if (!item) return;
        
        // Set provider
        this.switchProvider(item.provider);
        
        // Set text
        document.getElementById('tts-text-input').value = item.text;
        this.updateCharCounter();
        
        // Could also restore voice settings if stored
    },
    
    // Save to history
    saveToHistory() {
        // Already saved in addToHistory
        this.showStatus('Saved to history', 'success');
    },
    
    // Clear history
    clearHistory() {
        if (confirm('Are you sure you want to clear the history?')) {
            this.history = [];
            this.saveHistory();
            this.displayHistory();
            this.showStatus('History cleared', 'success');
        }
    },
    
    // Save history to localStorage
    saveHistory() {
        try {
            localStorage.setItem('tts_history', JSON.stringify(this.history));
        } catch (error) {
            console.error('Error saving history:', error);
        }
    },
    
    // Load history from localStorage
    loadHistory() {
        try {
            const saved = localStorage.getItem('tts_history');
            if (saved) {
                this.history = JSON.parse(saved);
                this.displayHistory();
            }
        } catch (error) {
            console.error('Error loading history:', error);
            this.history = [];
        }
    },
    
    // Show status message
    showStatus(message, type = 'info') {
        const statusEl = document.getElementById('tts-status');
        if (statusEl) {
            statusEl.textContent = message;
            statusEl.className = `status-message ${type}`;
            
            // Auto-hide after 5 seconds for non-error messages
            if (type !== 'error') {
                setTimeout(() => {
                    statusEl.className = 'status-message';
                }, 5000);
            }
        }
    }
};

// Initialization is triggered lazily by tts-loader.js when the Audio > TTS tab is activated.
