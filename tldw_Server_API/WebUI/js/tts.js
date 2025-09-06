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
    customVoices: {},
    
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
                document.getElementById('chatterbox-intensity-value`).textContent = `${e.target.value}%`;
            });
        }
        
        const stabilitySlider = document.getElementById('elevenlabs-stability');
        if (stabilitySlider) {
            stabilitySlider.addEventListener('input', (e) => {
                document.getElementById('elevenlabs-stability-value`).textContent = `${e.target.value}%`;
            });
        }
        
        const claritySlider = document.getElementById('elevenlabs-clarity');
        if (claritySlider) {
            claritySlider.addEventListener('input', (e) => {
                document.getElementById('elevenlabs-clarity-value`).textContent = `${e.target.value}%`;
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
            const response = await fetch('/api/v1/audio/health');
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
            const response = await fetch('/api/v1/audio/speech', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${API_KEY}` // If needed
                },
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
            stream: streaming
        };
        
        // Provider-specific settings
        switch (this.currentProvider) {
            case 'vibevoice':
                const customVoice = document.getElementById('vibevoice-custom-voice').value;
                request.model = `vibevoice:${document.getElementById('vibevoice-model').value}`;
                request.voice = customVoice || document.getElementById('vibevoice-voice').value;
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
                request.language = document.getElementById('higgs-language').value;
                break;
                
            case 'chatterbox':
                request.model = 'chatterbox';
                request.voice = document.getElementById('chatterbox-voice').value;
                request.emotion = document.getElementById('chatterbox-emotion').value;
                request.emotion_intensity = parseInt(document.getElementById('chatterbox-intensity').value);
                break;
                
            case 'openai':
                request.model = document.getElementById('openai-model').value;
                request.voice = document.getElementById('openai-voice').value;
                request.speed = parseFloat(document.getElementById('openai-speed').value);
                break;
                
            case 'elevenlabs':
                request.model = 'elevenlabs';
                request.voice = document.getElementById('elevenlabs-voice').value;
                request.stability = parseInt(document.getElementById('elevenlabs-stability').value) / 100;
                request.clarity = parseInt(document.getElementById('elevenlabs-clarity').value) / 100;
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
    
    // Handle streaming response
    async handleStreamingResponse(response) {
        const reader = response.body.getReader();
        const chunks = [];
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            chunks.push(value);
        }
        
        // Combine chunks and create blob
        const blob = new Blob(chunks, { type: 'audio/mpeg' });
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
            const response = await fetch('/api/v1/audio/voices/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${API_KEY}` // If needed
                },
                body: formData
            });
            
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
    
    // Refresh voice list
    async refreshVoiceList() {
        try {
            const response = await fetch('/api/v1/audio/voices', {
                headers: {
                    'Authorization': `Bearer ${API_KEY}` // If needed
                }
            });
            
            if (!response.ok) {
                throw new Error('Failed to fetch voices');
            }
            
            const data = await response.json();
            this.customVoices = data.voices || [];
            this.displayVoiceList();
            
        } catch (error) {
            console.error('Error fetching voices:', error);
        }
    },
    
    // Display voice list
    displayVoiceList() {
        const voiceList = document.getElementById('voice-list');
        if (!voiceList) return;
        
        if (this.customVoices.length === 0) {
            voiceList.innerHTML = '<p class="text-muted">No custom voices uploaded yet</p>';
            return;
        }
        
        voiceList.innerHTML = this.customVoices.map(voice => `
            <div class="voice-item" data-voice-id="${voice.voice_id}">
                <h5>${voice.name}</h5>
                <p class="text-muted">${voice.provider}</p>
                <small>${voice.description || 'No description'}</small>
                <div class="voice-actions">
                    <button class="btn btn-sm btn-secondary" onclick="TTS.previewVoice('${voice.voice_id}')">
                        <i class="fas fa-play"></i> Preview
                    </button>
                    <button class="btn btn-sm btn-danger" onclick="TTS.deleteVoice('${voice.voice_id}')">
                        <i class="fas fa-trash"></i>
                    </button>
                </div>
            </div>
        `).join('');
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
            const response = await fetch(`/api/v1/audio/voices/${voiceId}/preview`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${API_KEY}` // If needed
                },
                body: JSON.stringify({
                    text: 'This is a preview of your custom voice.'
                })
            });
            
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
            const response = await fetch(`/api/v1/audio/voices/${voiceId}`, {
                method: 'DELETE',
                headers: {
                    'Authorization': `Bearer ${API_KEY}` // If needed
                }
            });
            
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

// Initialize when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => TTS.init());
} else {
    TTS.init();
}