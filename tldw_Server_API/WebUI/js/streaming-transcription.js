/**
 * Streaming Transcription Module
 * Handles WebSocket-based real-time audio transcription using Nemo STT models
 */

class StreamingTranscriptionClient {
    constructor() {
        this.ws = null;
        this.mediaRecorder = null;
        this.audioContext = null;
        this.analyser = null;
        this.visualizer = null;
        this.isRecording = false;
        this.isConnected = false;
        this.isConfigured = false; // server config-ack received
        this.isReady = false;      // server model initialized
        this.startTime = null;
        this.chunksSent = 0;
        this.responsesReceived = 0;
        this.durationInterval = null;
        this.visualizerAnimationId = null;

        this.initializeUI();
    }

    initializeUI() {
        // Cache UI elements
        this.elements = {
            connectBtn: document.getElementById('connectStreamingBtn'),
            startBtn: document.getElementById('startStreamingBtn'),
            stopBtn: document.getElementById('stopStreamingBtn'),
            statusIndicator: document.getElementById('streamingStatusIndicator'),
            statusText: document.getElementById('streamingStatusText'),
            transcript: document.getElementById('streamingTranscript'),
            partialBox: document.getElementById('streamingPartial'),
            partialText: document.getElementById('streamingPartialText'),
            visualizer: document.getElementById('streamingVisualizer'),
            volume: document.getElementById('streamingVolume'),
            duration: document.getElementById('streamingDuration'),
            chunks: document.getElementById('streamingChunks'),
            responses: document.getElementById('streamingResponses'),
            debug: document.getElementById('streamingDebug'),
            connectionInfo: document.getElementById('streamingConnectionInfo'),
            configHint: document.getElementById('streamingConfigHint'),
            configHintText: document.querySelector('#streamingConfigHint .config-text')
        };

        // Initialize visualizer if canvas exists
        if (this.elements.visualizer) {
            this.initVisualizer();
        }

        // Language "Other" toggle
        const langSelect = document.getElementById('streamingLanguage');
        const langOther = document.getElementById('streamingLanguageOther');
        if (langSelect && langOther) {
            const toggleOther = () => {
                if (langSelect.value === 'other') {
                    langOther.style.display = 'block';
                    langOther.focus();
                } else {
                    langOther.style.display = 'none';
                }
            };
            langSelect.addEventListener('change', toggleOther);
            toggleOther();
        }

        // Helper: set language options per model
        this.setLanguageOptions = (model) => {
            const select = document.getElementById('streamingLanguage');
            if (!select) return;
            const prevValue = select.value;
            let html = '<option value="">Auto-detect</option>';

            if (model === 'parakeet' || model === 'canary') {
                const optionsEU = [
                    ['Bulgarian', 'bg'], ['Croatian', 'hr'], ['Czech', 'cs'], ['Danish', 'da'],
                    ['Dutch', 'nl'], ['English', 'en'], ['Estonian', 'et'], ['Finnish', 'fi'],
                    ['French', 'fr'], ['German', 'de'], ['Greek', 'el'], ['Hungarian', 'hu'],
                    ['Italian', 'it'], ['Latvian', 'lv'], ['Lithuanian', 'lt'], ['Maltese', 'mt'],
                    ['Polish', 'pl'], ['Portuguese', 'pt'], ['Romanian', 'ro'], ['Slovak', 'sk'],
                    ['Slovenian', 'sl'], ['Spanish', 'es'], ['Swedish', 'sv'], ['Russian', 'ru'],
                    ['Ukrainian', 'uk']
                ];
                for (const [name, code] of optionsEU) {
                    const selected = code === 'en' ? ' selected' : '';
                    html += `<option value="${code}"${selected}>${name} (${code})</option>`;
                }
            } else if (model === 'whisper') {
                const optionsCommon = [
                    ['English', 'en'], ['Spanish', 'es'], ['German', 'de'], ['French', 'fr'],
                    ['Chinese', 'zh'], ['Japanese', 'ja'], ['Korean', 'ko'], ['Russian', 'ru'],
                    ['Portuguese', 'pt'], ['Italian', 'it'], ['Arabic', 'ar'], ['Hindi', 'hi'],
                    ['Dutch', 'nl'], ['Turkish', 'tr'], ['Polish', 'pl'], ['Vietnamese', 'vi'],
                    ['Thai', 'th']
                ];
                for (const [name, code] of optionsCommon) {
                    html += `<option value="${code}">${name} (${code})</option>`;
                }
            }

            html += '<option value="other">Other…</option>';
            select.innerHTML = html;
            // Restore previous selection if still present, else keep default (Auto for Whisper, en for Parakeet/Canary)
            if (prevValue && [...select.options].some(o => o.value === prevValue)) {
                select.value = prevValue;
            }
        };
    }

    initVisualizer() {
        const canvas = this.elements.visualizer;
        const ctx = canvas.getContext('2d');

        // Set canvas size
        canvas.width = canvas.offsetWidth;
        canvas.height = 100;

        const draw = () => {
            this.visualizerAnimationId = requestAnimationFrame(draw);

            if (!this.analyser) {
                ctx.fillStyle = '#000';
                ctx.fillRect(0, 0, canvas.width, canvas.height);
                return;
            }

            const bufferLength = this.analyser.frequencyBinCount;
            const dataArray = new Uint8Array(bufferLength);
            this.analyser.getByteFrequencyData(dataArray);

            // Calculate volume
            const volume = Math.round(dataArray.reduce((a, b) => a + b) / bufferLength / 255 * 100);
            if (this.elements.volume) {
                this.elements.volume.textContent = volume;
            }

            // Draw frequency bars
            ctx.fillStyle = '#000';
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            const barWidth = (canvas.width / bufferLength) * 2.5;
            let x = 0;

            for (let i = 0; i < bufferLength; i++) {
                const barHeight = (dataArray[i] / 255) * canvas.height;

                // Create gradient colors
                const r = barHeight + 25 * (i / bufferLength);
                const g = 250 * (i / bufferLength);
                const b = 50;

                ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
                ctx.fillRect(x, canvas.height - barHeight, barWidth, barHeight);

                x += barWidth + 1;
            }
        };

        draw();
    }

    async toggleConnection() {
        if (this.isConnected) {
            this.disconnect();
        } else {
            await this.connect();
        }
    }

    async connect() {
        this.updateStatus('Connecting...', 'connecting');

        try {
            // Get server URL and authentication
            const baseUrl = window.location.origin.replace('http', 'ws');
            const wsUrl = `${baseUrl}/api/v1/audio/stream/transcribe`;

            // Get API token - first try from global API client, then localStorage
            let apiToken = '';
            if (window.apiClient && window.apiClient.token) {
                apiToken = window.apiClient.token;
                this.logDebug('Using API key from server config');
            } else {
                apiToken = localStorage.getItem('apiToken') || '';
                if (apiToken) {
                    this.logDebug('Using API key from localStorage');
                }
            }

            if (!apiToken) {
                this.logDebug('Warning: No API key found, connection may fail');
            }

            const finalUrl = apiToken ? `${wsUrl}?token=${encodeURIComponent(apiToken)}` : wsUrl;

            this.ws = new WebSocket(finalUrl);

            this.ws.onopen = () => {
                this.isConnected = true;
                this.isConfigured = false;
                this.isReady = false;
                this.updateStatus('Connected', 'connected');
                this.elements.connectBtn.textContent = 'Disconnect';
                // Keep Start disabled until config-ack arrives
                if (this.elements.startBtn) this.elements.startBtn.disabled = true;
                if (this.elements.configHint) {
                    this.elements.configHint.style.display = 'inline-flex';
                    if (this.elements.configHintText) {
                        this.elements.configHintText.textContent = 'Waiting for server configuration…';
                    }
                }

                // Send configuration immediately after connection
                setTimeout(() => {
                    this.sendConfiguration();
                }, 100); // Small delay to ensure connection is fully established

                this.logDebug('WebSocket connected');
                this.updateConnectionInfo();
            };

            this.ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                this.handleMessage(data);
            };

            this.ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                this.logDebug(`WebSocket error: ${error}`);
                this.addTranscript('Connection error occurred', 'error');
            };

            this.ws.onclose = () => {
                this.isConnected = false;
                this.isConfigured = false;
                this.isReady = false;
                this.updateStatus('Disconnected', 'disconnected');
                this.elements.connectBtn.textContent = 'Connect to Server';
                if (this.elements.startBtn) this.elements.startBtn.disabled = true;
                this.elements.stopBtn.disabled = true;
                if (this.elements.configHint) {
                    this.elements.configHint.style.display = 'none';
                }

                if (this.isRecording) {
                    this.stopRecording();
                }

                this.logDebug('WebSocket disconnected');
                this.updateConnectionInfo();
            };

        } catch (error) {
            console.error('Connection failed:', error);
            this.updateStatus('Connection failed', 'disconnected');
            this.addTranscript(`Connection failed: ${error.message}`, 'error');
        }
    }

    disconnect() {
        if (this.ws) {
            this.ws.close();
            this.ws = null;
        }
    }

    sendConfiguration() {
        if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
            this.logDebug('WebSocket not ready, cannot send configuration');
            return;
        }

        const model = document.getElementById('streamingModel').value;
        const config = {
            type: 'config',
            model: model,
            sample_rate: parseInt(document.getElementById('streamingSampleRate').value),
            chunk_duration: parseFloat(document.getElementById('streamingChunkDuration').value),
            enable_partial: document.getElementById('streamingEnablePartial').checked,
            enable_vad: document.getElementById('streamingEnableVAD').checked,
            vad_threshold: parseFloat(document.getElementById('streamingVADThreshold').value || 0.5)
        };

        if (model === 'parakeet') {
            config.variant = document.getElementById('streamingVariant').value;
            console.log('Parakeet variant selected:', config.variant);
            const langSelect = document.getElementById('streamingLanguage');
            const langOther = document.getElementById('streamingLanguageOther');
            let language = langSelect ? langSelect.value : '';
            if (language === 'other' && langOther) {
                language = (langOther.value || '').trim();
            }
            if (language) config.language = language;
        } else if (model === 'canary') {
            const langSelect = document.getElementById('streamingLanguage');
            const langOther = document.getElementById('streamingLanguageOther');
            let language = langSelect ? langSelect.value : '';
            if (language === 'other' && langOther) {
                language = (langOther.value || '').trim();
            }
            if (language) config.language = language;
        } else if (model === 'whisper') {
            config.whisper_model_size = document.getElementById('whisperModelSize').value;
            config.task = document.getElementById('whisperTask').value;
            const langSelect = document.getElementById('streamingLanguage');
            const langOther = document.getElementById('streamingLanguageOther');
            let language = langSelect ? langSelect.value : '';
            if (language === 'other' && langOther) {
                language = (langOther.value || '').trim();
            }
            if (language) config.language = language;
            // Whisper works better with longer chunks
            config.chunk_duration = 5.0;  // Override to optimal duration for Whisper
        }

        console.log('Sending configuration:', config);
        this.ws.send(JSON.stringify(config));
        this.logDebug(`Sent config: ${JSON.stringify(config)}`);
    }

    async startRecording() {
        try {
            // Request microphone access
            const stream = await navigator.mediaDevices.getUserMedia({
                audio: {
                    channelCount: 1,
                    sampleRate: parseInt(document.getElementById('streamingSampleRate').value),
                    echoCancellation: true,
                    noiseSuppression: true
                }
            });

            // Create audio context for visualization
            this.audioContext = new (window.AudioContext || window.webkitAudioContext)();
            const source = this.audioContext.createMediaStreamSource(stream);
            this.analyser = this.audioContext.createAnalyser();
            this.analyser.fftSize = 256;
            source.connect(this.analyser);

            // Log audio context info
            this.logDebug(`Audio context sample rate: ${this.audioContext.sampleRate}Hz`);
            this.logDebug(`Configured sample rate: ${parseInt(document.getElementById('streamingSampleRate').value)}Hz`);

            // Create script processor for audio chunks
            // Increased buffer size for better performance and larger chunks
            const bufferSize = 16384; // Increased from 4096 (~1 second at 16kHz)
            const scriptProcessor = this.audioContext.createScriptProcessor(bufferSize, 1, 1);
            source.connect(scriptProcessor);
            scriptProcessor.connect(this.audioContext.destination);

            // Initialize audio buffer for accumulation
            this.audioBuffer = [];
            this.bufferDuration = 0;
            const model = document.getElementById('streamingModel').value;

            // Set target buffer duration based on model
            const targetDuration = model === 'whisper' ? 5.0 : 2.0; // seconds
            const configuredSampleRate = parseInt(document.getElementById('streamingSampleRate').value);
            const targetSamples = targetDuration * configuredSampleRate;

            scriptProcessor.onaudioprocess = (event) => {
                if (!this.isRecording) return;

                const inputData = event.inputBuffer.getChannelData(0);
                let audioData = inputData;

                // Handle sample rate conversion if needed
                if (this.audioContext.sampleRate !== configuredSampleRate) {
                    // Simple downsampling/upsampling
                    const ratio = configuredSampleRate / this.audioContext.sampleRate;
                    const newLength = Math.floor(inputData.length * ratio);
                    audioData = new Float32Array(newLength);

                    for (let i = 0; i < newLength; i++) {
                        const srcIndex = i / ratio;
                        const srcIndexFloor = Math.floor(srcIndex);
                        const srcIndexCeil = Math.min(Math.ceil(srcIndex), inputData.length - 1);
                        const fraction = srcIndex - srcIndexFloor;

                        // Linear interpolation for resampling
                        audioData[i] = inputData[srcIndexFloor] * (1 - fraction) +
                                      inputData[srcIndexCeil] * fraction;
                    }
                }

                // Accumulate audio data
                this.audioBuffer.push(...audioData);

                // Check if we have enough samples
                if (this.audioBuffer.length >= targetSamples) {
                    // Create chunk from accumulated buffer
                    const chunkToSend = new Float32Array(this.audioBuffer.slice(0, targetSamples));

                    // Keep overlap for context (10% of buffer)
                    const overlapSamples = Math.floor(targetSamples * 0.1);
                    this.audioBuffer = this.audioBuffer.slice(targetSamples - overlapSamples);

                    // Convert to base64
                    const base64 = this.arrayBufferToBase64(chunkToSend.buffer);

                    // Send to WebSocket
                    if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                        this.ws.send(JSON.stringify({
                            type: 'audio',
                            data: base64
                        }));
                        this.chunksSent++;
                        this.elements.chunks.textContent = this.chunksSent;

                        this.logDebug(`Sent audio chunk ${this.chunksSent}: ${chunkToSend.length} samples`);
                    }
                }
            };

            this.isRecording = true;
            this.startTime = Date.now();
            this.chunksSent = 0;
            this.responsesReceived = 0;

            // Update UI
            this.elements.startBtn.disabled = true;
            this.elements.stopBtn.disabled = false;
            this.addTranscript('Recording started...', 'status');

            // Start duration timer
            this.durationInterval = setInterval(() => {
                const elapsed = Math.floor((Date.now() - this.startTime) / 1000);
                const minutes = Math.floor(elapsed / 60);
                const seconds = elapsed % 60;
                this.elements.duration.textContent = `${minutes}:${seconds.toString().padStart(2, '0')}`;
            }, 1000);

            this.logDebug('Recording started');

        } catch (error) {
            console.error('Failed to start recording:', error);
            this.addTranscript(`Failed to start recording: ${error.message}`, 'error');
        }
    }

    stopRecording() {
        if (this.isRecording) {
            this.isRecording = false;

            // Send any remaining buffered audio before stopping
            if (this.audioBuffer && this.audioBuffer.length > 0) {
                const remainingAudio = new Float32Array(this.audioBuffer);
                const base64 = this.arrayBufferToBase64(remainingAudio.buffer);

                if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                    this.ws.send(JSON.stringify({
                        type: 'audio',
                        data: base64
                    }));
                    this.chunksSent++;
                    this.elements.chunks.textContent = this.chunksSent;
                }

                this.audioBuffer = [];
            }

            // Stop audio context
            if (this.audioContext) {
                this.audioContext.close();
                this.audioContext = null;
                this.analyser = null;
            }

            // Send commit message to get final transcript
            if (this.ws && this.ws.readyState === WebSocket.OPEN) {
                this.ws.send(JSON.stringify({ type: 'commit' }));
            }

            // Update UI
            this.elements.startBtn.disabled = false;
            this.elements.stopBtn.disabled = true;
            this.addTranscript('Recording stopped', 'status');

            // Stop duration timer
            if (this.durationInterval) {
                clearInterval(this.durationInterval);
                this.durationInterval = null;
            }

            this.logDebug('Recording stopped');
        }
    }

    handleMessage(data) {
        this.responsesReceived++;
        this.elements.responses.textContent = this.responsesReceived;

        this.logDebug(`Received: ${JSON.stringify(data)}`);

        switch (data.type) {
            case 'partial':
                this.showPartial(data.text);
                break;

            case 'transcription':
            case 'final':
                this.addTranscript(data.text, 'final');
                this.hidePartial();
                break;

            case 'full_transcript':
                this.addTranscript(`[Full Transcript] ${data.text}`, 'final');
                break;

            case 'error':
                this.addTranscript(`Error: ${data.message}`, 'error');
                break;

            case 'status':
                this.addTranscript(`Status: ${data.state} - ${data.model || ''}`, 'status');
                // Enable Start only after config-ack (state === 'configured' or 'ready')
                if (data.state === 'configured') {
                    this.isConfigured = true;
                    if (this.elements.startBtn) this.elements.startBtn.disabled = false;
                    this.updateStatus('Configured', 'connected');
                    if (this.elements.configHint) this.elements.configHint.style.display = 'none';
                } else if (data.state === 'ready') {
                    this.isReady = true;
                    // If configured state was missed for some reason, allow start after ready
                    if (this.elements.startBtn) this.elements.startBtn.disabled = false;
                    this.updateStatus('Ready', 'connected');
                    if (this.elements.configHint) this.elements.configHint.style.display = 'none';
                }
                break;

            case 'warning':
                this.addTranscript(`Warning: ${data.message}`, 'warning');
                if (data.fallback) {
                    this.addTranscript(`Using ${data.active_model} instead of ${data.original_model}`, 'warning');
                }
                break;

            default:
                console.log('Unknown message type:', data);
        }
    }

    showPartial(text) {
        if (this.elements.partialBox && this.elements.partialText) {
            this.elements.partialBox.style.display = 'block';
            this.elements.partialText.textContent = text;
        }
    }

    hidePartial() {
        if (this.elements.partialBox) {
            this.elements.partialBox.style.display = 'none';
        }
    }

    addTranscript(text, type = 'final') {
        const entry = document.createElement('div');
        entry.className = `transcript-entry ${type}`;

        const timestamp = new Date().toLocaleTimeString();
        entry.textContent = `[${timestamp}] ${text}`;

        // Remove placeholder if exists
        const placeholder = this.elements.transcript.querySelector('.transcript-placeholder');
        if (placeholder) {
            placeholder.remove();
        }

        this.elements.transcript.appendChild(entry);
        this.elements.transcript.scrollTop = this.elements.transcript.scrollHeight;
    }

    clearTranscript() {
        this.elements.transcript.innerHTML = '<div class="transcript-placeholder">Connect and start recording to see transcript...</div>';
        this.elements.chunks.textContent = '0';
        this.elements.responses.textContent = '0';
        this.elements.duration.textContent = '0:00';
        this.hidePartial();
        this.chunksSent = 0;
        this.responsesReceived = 0;
    }

    updateStatus(text, state) {
        this.elements.statusText.textContent = text;
        this.elements.statusIndicator.className = `status-indicator ${state}`;
    }

    updateConnectionInfo() {
        const info = {
            connected: this.isConnected,
            url: this.ws ? this.ws.url : 'Not connected',
            readyState: this.ws ? this.ws.readyState : 'N/A',
            protocol: this.ws ? this.ws.protocol : 'N/A'
        };

        this.elements.connectionInfo.textContent = JSON.stringify(info, null, 2);
    }

    logDebug(message) {
        const timestamp = new Date().toISOString();
        const currentLog = this.elements.debug.textContent;
        const newLog = `[${timestamp}] ${message}\n${currentLog}`;

        // Keep only last 20 messages
        const lines = newLog.split('\n').slice(0, 20);
        this.elements.debug.textContent = lines.join('\n');
    }

    arrayBufferToBase64(buffer) {
        const bytes = new Uint8Array(buffer);
        let binary = '';
        for (let i = 0; i < bytes.byteLength; i++) {
            binary += String.fromCharCode(bytes[i]);
        }
        return window.btoa(binary);
    }
}

// Global instance
let streamingClient = null;

// API Key Management
function saveStreamingApiKey() {
    const apiKeyInput = document.getElementById('streamingApiKey');
    if (apiKeyInput) {
        const apiKey = apiKeyInput.value.trim();
        if (apiKey) {
            localStorage.setItem('apiToken', apiKey);
            alert('API key saved successfully!');
        } else {
            alert('Please enter a valid API key');
        }
    }
}

function toggleApiKeyVisibility() {
    const apiKeyInput = document.getElementById('streamingApiKey');
    if (apiKeyInput) {
        apiKeyInput.type = apiKeyInput.type === 'password' ? 'text' : 'password';
    }
}

// Load saved API key on page load
document.addEventListener('DOMContentLoaded', () => {
    const apiKeyInput = document.getElementById('streamingApiKey');
    if (apiKeyInput) {
        // First try to get from global API client (server config)
        if (window.apiClient && window.apiClient.token) {
            apiKeyInput.value = window.apiClient.token;
        } else {
            // Fall back to localStorage
            const savedApiKey = localStorage.getItem('apiToken');
            if (savedApiKey) {
                apiKeyInput.value = savedApiKey;
            }
        }
    }
});

// Global functions for HTML onclick handlers
function toggleStreamingConnection() {
    if (!streamingClient) {
        streamingClient = new StreamingTranscriptionClient();
    }
    streamingClient.toggleConnection();
}

function startStreamingRecording() {
    // Check if button is actually disabled
    const startBtn = document.getElementById('startStreamingBtn');
    if (startBtn && startBtn.disabled) {
        console.log('Start button is disabled, ignoring click');
        return;
    }

    if (streamingClient && streamingClient.isConnected) {
        // Ensure server has acknowledged configuration
        if (!streamingClient.isConfigured && !streamingClient.isReady) {
            console.log('Waiting for server config-ack before starting recording');
            streamingClient.addTranscript('Waiting for server configuration acknowledgment...', 'status');
            return;
        }
        streamingClient.startRecording();
    } else {
        console.error('Cannot start recording: Not connected to server');
    }
}

function stopStreamingRecording() {
    if (streamingClient) {
        streamingClient.stopRecording();
    }
}

function clearStreamingTranscript() {
    if (!streamingClient) {
        streamingClient = new StreamingTranscriptionClient();
    }
    streamingClient.clearTranscript();
}

function updateModelOptions() {
    const model = document.getElementById('streamingModel').value;
    const variantGroup = document.getElementById('variantGroup');
    const languageGroup = document.getElementById('languageGroup');
    const whisperModelGroup = document.getElementById('whisperModelGroup');
    const whisperTaskGroup = document.getElementById('whisperTaskGroup');

    if (model === 'parakeet') {
        variantGroup.style.display = 'block';
        languageGroup.style.display = 'block';
        whisperModelGroup.style.display = 'none';
        whisperTaskGroup.style.display = 'none';
        // Populate language list for Parakeet
        if (window.streamingClient && typeof window.streamingClient.setLanguageOptions === 'function') {
            window.streamingClient.setLanguageOptions('parakeet');
        }
    } else if (model === 'canary') {
        variantGroup.style.display = 'none';
        languageGroup.style.display = 'block';
        whisperModelGroup.style.display = 'none';
        whisperTaskGroup.style.display = 'none';
        // Populate language list for Canary
        if (window.streamingClient && typeof window.streamingClient.setLanguageOptions === 'function') {
            window.streamingClient.setLanguageOptions('canary');
        }
    } else if (model === 'whisper') {
        variantGroup.style.display = 'none';
        languageGroup.style.display = 'block';
        whisperModelGroup.style.display = 'block';
        whisperTaskGroup.style.display = 'block';
        // Populate language list for Whisper (auto-detect by default)
        if (window.streamingClient && typeof window.streamingClient.setLanguageOptions === 'function') {
            window.streamingClient.setLanguageOptions('whisper');
        }
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    // Only initialize if we're on the streaming tab
    if (document.getElementById('tabAudioStreaming')) {
        console.log('Streaming transcription module loaded');
        // Ensure language/options are initialized for current model selection
        try { updateModelOptions(); } catch (e) { /* noop */ }
    }
});
