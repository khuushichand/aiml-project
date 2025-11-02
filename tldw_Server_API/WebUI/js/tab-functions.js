/**
 * Tab-specific functions for the WebUI
 * This file contains all functions that are called from onclick handlers in dynamically loaded tabs
 */

// ============================================================================
// Audio Tab Functions (TTS and STT)
// ============================================================================

let _audioTTSAbort = null;

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

// Build and send request for Audio → TTS panel
async function audioTTSGenerate() {
    const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
    const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';
    const provider = document.getElementById('audioTTS_provider')?.value || '';
    const model = document.getElementById('audioTTS_model')?.value || '';
    const voice = document.getElementById('audioTTS_voice')?.value || '';
    const input = document.getElementById('audioTTS_input')?.value || '';
    const response_format = document.getElementById('audioTTS_response_format')?.value || 'mp3';
    const speed = parseFloat(document.getElementById('audioTTS_speed')?.value || '1.0');
    const stream = !!(document.getElementById('audioTTS_stream')?.checked);

    const req = { model, input, voice, response_format, speed, stream };

    // Prefer recorded mic sample for voice cloning; else use file input if present
    try {
        if (window._audioTTSRec && _audioTTSRec.blob) {
            req.voice_reference = await _audioBlobToBase64Wav(_audioTTSRec.blob);
        } else {
            const fileInput = document.getElementById('audioTTS_voiceReference');
            if (fileInput && fileInput.files && fileInput.files[0]) {
                const arr = await fileInput.files[0].arrayBuffer();
                const bytes = new Uint8Array(arr);
                let bin=''; const step=0x8000;
                for(let i=0;i<bytes.length;i+=step){ bin+=String.fromCharCode.apply(null, bytes.subarray(i,i+step)); }
                req.voice_reference = btoa(bin);
            }
        }
    } catch (e) {
        console.warn('Failed to attach voice reference', e);
    }

    const status = document.getElementById('audioTTS_status');
    if (status) status.textContent = 'Generating...';
    const stopBtn = document.getElementById('stopButton');
    if (stopBtn) stopBtn.style.display = 'inline-block';
    _audioTTSAbort = new AbortController();

    try {
        const res = await fetch(`${baseUrl}/api/v1/audio/speech`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            body: JSON.stringify(req),
            signal: _audioTTSAbort.signal
        });
        if (!res.ok) {
            const errText = await res.text();
            throw new Error(errText || `HTTP ${res.status}`);
        }
        const blob = await res.blob();
        const url = URL.createObjectURL(blob);
        const player = document.getElementById('audioTTS_player');
        if (player) { player.src = url; player.style.display = 'block'; }
        const dlBtn = document.getElementById('downloadButton');
        if (dlBtn) dlBtn.style.display = 'inline-block';
        if (status) status.textContent = `Done (${(blob.size/1024).toFixed(1)} KB)`;
    } catch (e) {
        console.error('Audio TTS failed', e);
        if (status) status.textContent = (e.name === 'AbortError') ? 'Cancelled' : `Error: ${e.message}`;
    }
    finally {
        const stopBtn = document.getElementById('stopButton');
        if (stopBtn) stopBtn.style.display = 'none';
        _audioTTSAbort = null;
    }
}

// Button handlers wired in audio_content.html
async function generateTTS() {
    return audioTTSGenerate();
}

function stopTTS() {
    try { if (_audioTTSAbort) _audioTTSAbort.abort(); } catch (_) {}
}

function downloadAudio() {
    const player = document.getElementById('audioTTS_player');
    if (!player || !player.src) return;
    const a = document.createElement('a');
    a.href = player.src;
    a.download = 'speech.' + ((document.getElementById('audioTTS_response_format')?.value) || 'mp3');
    document.body.appendChild(a);
    a.click();
    setTimeout(()=>{ try { a.remove(); } catch(_){} }, 0);
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

// ----------------------------------------------------------------------------
// Transcript Segmentation (TreeSeg) UI Functions
// ----------------------------------------------------------------------------

function segParseEntries() {
    const raw = (document.getElementById('segInput')?.value || '').trim();
    if (!raw) return [];
    if (raw.startsWith('[') || raw.startsWith('{')) {
        try {
            const data = JSON.parse(raw);
            return Array.isArray(data) ? data : [data];
        } catch (e) {
            alert('Invalid JSON in transcript input');
            return [];
        }
    }
    return raw.split('\n').map(line => ({ composite: line.trim() })).filter(e => e.composite);
}

// ----------------------------------------------------------------------------
// Embeddings DLQ Admin Functions
// ----------------------------------------------------------------------------

let embeddingsDLQTimer = null;

async function embeddingsListDLQ() {
    const stageEl = document.getElementById('embeddingsDLQ_stage');
    const countEl = document.getElementById('embeddingsDLQ_count');
    const out = document.getElementById('embeddingsDLQ_results');
    if (!out) return;
    out.textContent = 'Loading...';
    try {
        const stage = stageEl.value;
        const count = parseInt(countEl.value || '50', 10);
        const res = await apiClient.get(`/api/v1/embeddings/dlq?stage=${encodeURIComponent(stage)}&count=${count}`);
        // Render a minimal table with requeue buttons
        const items = (res && res.items) ? res.items : [];
        const rows = items.map(item => {
            const eid = item.entry_id;
            const job = item.job_id || '';
            const err = (item.error || '').toString().slice(0, 120);
            const code = (item.fields && item.fields.error_code) ? item.fields.error_code : '-';
            const ftype = (item.fields && item.fields.failure_type) ? item.fields.failure_type : '-';
            const state = (item.dlq_state || '-');
            const note = (item.operator_note || '');
            return `<tr>
                <td><code>${eid}</code></td>
                <td>${job}</td>
                <td class="text-muted">${Utils.escapeHtml(err)}</td>
                <td>${Utils.escapeHtml(code)}</td>
                <td>${Utils.escapeHtml(ftype)}</td>
                <td>${Utils.escapeHtml(state)}</td>
                <td>${Utils.escapeHtml(note)}</td>
                <td>
                    <button class="api-button" onclick="embeddingsRequeueDLQ('${eid}')">Requeue</button>
                    ${job ? `<button class="api-button btn-warning" onclick="embeddingsSkipJob('${job}')">Skip</button>` : ''}
                    <div class="btn-group" style="margin-top:4px">
                      <button class="api-button" onclick="embeddingsSetDLQState('${eid}','quarantined')">Quarantine</button>
                      <button class="api-button" onclick="embeddingsApproveDLQ('${eid}')">Approve</button>
                      <button class="api-button" onclick="embeddingsSetDLQState('${eid}','ignored')">Ignore</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        out.innerHTML = `
            <table class="table">
                <thead>
                    <tr><th>Entry ID</th><th>Job ID</th><th>Error</th><th>Code</th><th>Type</th><th>State</th><th>Note</th><th>Action</th></tr>
                </thead>
                <tbody>${rows || '<tr><td colspan="8">No DLQ items</td></tr>'}</tbody>
            </table>
            <details style="margin-top:8px"><summary>Raw</summary><pre>${Utils.syntaxHighlight(res)}</pre></details>
        `;
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error('Failed to list DLQ');
    }
}

async function embeddingsRequeueDLQ(entryId) {
    const stage = document.getElementById('embeddingsDLQ_stage').value;
    const out = document.getElementById('embeddingsDLQ_results');
    try {
        const res = await apiClient.post('/api/v1/embeddings/dlq/requeue', {
            stage,
            entry_id: entryId,
            delete_from_dlq: true
        });
        if (res && res.warning) {
            Toast.warn(`Requeued with warning: ${res.warning}`);
        } else {
            Toast.success('Requeued DLQ item');
        }
        // Refresh list
        embeddingsListDLQ();
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error('Failed to requeue DLQ item');
    }
}

// Enhanced DLQ list with job_id filter, selection, and stage badges
async function embeddingsListDLQ2() {
    const stageEl = document.getElementById('embeddingsDLQ_stage');
    const countEl = document.getElementById('embeddingsDLQ_count');
    const jobIdEl = document.getElementById('embeddingsDLQ_job_id');
    const out = document.getElementById('embeddingsDLQ_results');
    if (!out) return;
    out.textContent = 'Loading...';
    try {
        const stage = stageEl.value;
        const count = parseInt(countEl.value || '50', 10);
        const jobId = (jobIdEl && jobIdEl.value || '').trim();
        const q = new URLSearchParams({ stage, count: String(count) });
        if (jobId) q.set('job_id', jobId);
        const res = await apiClient.get(`/api/v1/embeddings/dlq?${q.toString()}`);
        try { await embeddingsRefreshDLQBadges(); } catch (e) { /* ignore */ }
        const items = (res && res.items) ? res.items : [];
        const rows = items.map(item => {
            const eid = item.entry_id;
            const job = item.job_id || '';
            const err = (item.error || '').toString().slice(0, 120);
            const code = (item.fields && item.fields.error_code) ? item.fields.error_code : '-';
            const ftype = (item.fields && item.fields.failure_type) ? item.fields.failure_type : '-';
            const state = (item.dlq_state || '-');
            const note = (item.operator_note || '');
            return `<tr>
                <td><input type="checkbox" class="dlq-select" data-entry-id="${eid}" /></td>
                <td><code>${eid}</code></td>
                <td>${job}</td>
                <td class="text-muted">${Utils.escapeHtml(err)}</td>
                <td>${Utils.escapeHtml(code)}</td>
                <td>${Utils.escapeHtml(ftype)}</td>
                <td>${Utils.escapeHtml(state)}</td>
                <td>${Utils.escapeHtml(note)}</td>
                <td>
                    <button class="api-button" onclick="embeddingsRequeueDLQ('${eid}')">Requeue</button>
                    ${job ? `<button class="api-button btn-warning" onclick="embeddingsSkipJob('${job}')">Skip</button>` : ''}
                    <div class="btn-group" style="margin-top:4px">
                      <button class="api-button" onclick="embeddingsSetDLQState('${eid}','quarantined')">Quarantine</button>
                      <button class="api-button" onclick="embeddingsApproveDLQ('${eid}')">Approve</button>
                      <button class="api-button" onclick="embeddingsSetDLQState('${eid}','ignored')">Ignore</button>
                    </div>
                </td>
            </tr>`;
        }).join('');
        out.innerHTML = `
            <table class="table">
                <thead>
                    <tr><th></th><th>Entry ID</th><th>Job ID</th><th>Error</th><th>Code</th><th>Type</th><th>State</th><th>Note</th><th>Action</th></tr>
                </thead>
                <tbody>${rows || '<tr><td colspan="9">No DLQ items</td></tr>'}</tbody>
            </table>
            <details style="margin-top:8px"><summary>Raw</summary><pre>${Utils.syntaxHighlight(res)}</pre></details>
        `;
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error('Failed to list DLQ');
    }
}

async function embeddingsSkipJob(jobId) {
    if (!jobId) return;
    if (!confirm(`Mark job ${jobId} as skipped?`)) return;
    try {
        await apiClient.post('/api/v1/embeddings/job/skip', { job_id: jobId, ttl_seconds: 7*24*3600 });
        Toast.success(`Job ${jobId} marked as skipped`);
    } catch (e) {
        Toast.error('Failed to mark job as skipped');
    }
}

function embeddingsDLQToggleSelectAll(cb) {
    try {
        const out = document.getElementById('embeddingsDLQ_results');
        if (!out) return;
        const boxes = out.querySelectorAll('input.dlq-select');
        boxes.forEach(b => b.checked = !!cb.checked);
    } catch (e) { /* ignore */ }
}

async function embeddingsRequeueDLQSelected() {
    const out = document.getElementById('embeddingsDLQ_results');
    const stage = document.getElementById('embeddingsDLQ_stage').value;
    if (!out) return;
    try {
        const selected = Array.from(out.querySelectorAll('input.dlq-select:checked')).map(b => b.getAttribute('data-entry-id')).filter(Boolean);
        if (selected.length === 0) {
            Toast.error('No DLQ entries selected');
            return;
        }
        const res = await apiClient.post('/api/v1/embeddings/dlq/requeue/bulk', {
            stage,
            entry_ids: selected,
            delete_from_dlq: true
        });
        if (res && Array.isArray(res.results) && res.results.some(r => r.warning)) {
            Toast.warn('Some entries requeued with validation warnings');
        } else {
            Toast.success(`Requeued ${selected.length} DLQ item(s)`);
        }
        embeddingsListDLQ2();
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error('Failed to bulk requeue');
    }
}

async function embeddingsRequeueDLQAllFiltered() {
    const out = document.getElementById('embeddingsDLQ_results');
    const stage = document.getElementById('embeddingsDLQ_stage').value;
    if (!out) return;
    try {
        const all = Array.from(out.querySelectorAll('input.dlq-select')).map(b => b.getAttribute('data-entry-id')).filter(Boolean);
        if (all.length === 0) {
            Toast.error('No DLQ entries listed');
            return;
        }
        const res = await apiClient.post('/api/v1/embeddings/dlq/requeue/bulk', {
            stage,
            entry_ids: all,
            delete_from_dlq: true
        });
        if (res && Array.isArray(res.results) && res.results.some(r => r.warning)) {
            Toast.warn('Some entries requeued with validation warnings');
        } else {
            Toast.success(`Requeued ${all.length} DLQ item(s)`);
        }
        embeddingsListDLQ2();
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error('Failed to bulk requeue (all filtered)');
    }
}

async function embeddingsRefreshDLQBadges() {
    try {
        const client = window.apiClient;
        if (!client || !client.token) {
            return;
        }
        const res = await client.get('/api/v1/embeddings/dlq/stats');
        const dlq = (res && res.dlq) || {};
        const map = {
            embedding: dlq['embeddings:embedding:dlq'] || 0,
            chunking: dlq['embeddings:chunking:dlq'] || 0,
            storage: dlq['embeddings:storage:dlq'] || 0,
        };
        const badgeE = document.getElementById('dlq-badge-embedding');
        const badgeC = document.getElementById('dlq-badge-chunking');
        const badgeS = document.getElementById('dlq-badge-storage');
        const badgeE2 = document.getElementById('dlq-badge-embedding2');
        const badgeC2 = document.getElementById('dlq-badge-chunking2');
        const badgeS2 = document.getElementById('dlq-badge-storage2');
        const apply = (el, label, v) => {
            if (!el) return;
            el.textContent = `${label}: ${v}`;
            el.classList.remove('badge-warn', 'badge-crit');
            if (v >= 100) el.classList.add('badge-crit'); else if (v >= 10) el.classList.add('badge-warn');
        };
        apply(badgeE, 'embedding', map.embedding);
        apply(badgeC, 'chunking', map.chunking);
        apply(badgeS, 'storage', map.storage);
        apply(badgeE2, 'embedding', map.embedding);
        apply(badgeC2, 'chunking', map.chunking);
        apply(badgeS2, 'storage', map.storage);
        if (typeof embeddingsRefreshHydeStatus === 'function') {
            await embeddingsRefreshHydeStatus();
        }
    } catch (e) { /* ignore */ }
}

async function embeddingsRefreshHydeStatus() {
    const badge = document.getElementById('hyde-status-badge');
    if (!badge) return;
    const client = window.apiClient;
    if (!client || !client.token) {
        return;
    }
    try {
        const res = await client.get('/api/v1/embeddings/health');
        const hyde = (res && res.hyde) || {};
        const enabled = !!hyde.enabled;
        const infoParts = [];
        const questionsPerChunk = hyde.questions_per_chunk;
        if (enabled) {
            if (typeof questionsPerChunk === 'number' && questionsPerChunk > 0) {
                infoParts.push(`N=${questionsPerChunk}`);
            }
            if (hyde.provider && hyde.model) {
                infoParts.push(`${hyde.provider}/${hyde.model}`);
            } else if (hyde.provider) {
                infoParts.push(`${hyde.provider}`);
            }
            if (hyde.weight !== undefined && hyde.weight !== null) {
                const weight = Number.parseFloat(hyde.weight);
                if (!Number.isNaN(weight)) {
                    infoParts.push(`w=${weight.toFixed(2)}`);
                }
            }
            badge.textContent = infoParts.length ? `HYDE: Enabled (${infoParts.join(', ')})` : 'HYDE: Enabled';
            badge.classList.remove('badge-alert', 'badge-warning', 'badge-info');
            badge.classList.add('badge-success');
        } else {
            const pending = (typeof questionsPerChunk === 'number' && questionsPerChunk > 0);
            badge.textContent = pending ? `HYDE: Disabled (N=${questionsPerChunk})` : 'HYDE: Disabled';
            badge.classList.remove('badge-success', 'badge-warning', 'badge-info');
            badge.classList.add('badge-alert');
        }
    } catch (e) {
        badge.textContent = 'HYDE: Unknown';
        badge.classList.remove('badge-success');
        badge.classList.add('badge-warning');
    }
}

async function embeddingsSetDLQState(entryId, state) {
    const stage = document.getElementById('embeddingsDLQ_stage').value;
    let operator_note = undefined;
    if (state === 'approved_for_requeue') {
        operator_note = prompt('Approval note (required):', 'Reviewed and safe to requeue');
        if (!operator_note || !operator_note.trim()) {
            Toast.error('Approval note is required');
            return;
        }
    }
    try {
        await apiClient.post('/api/v1/embeddings/dlq/state', { stage, entry_id: entryId, state, operator_note });
        Toast.success('DLQ state updated');
        embeddingsListDLQ2();
    } catch (e) {
        Toast.error('Failed to update DLQ state');
    }
}

async function embeddingsApproveDLQ(entryId) {
    return embeddingsSetDLQState(entryId, 'approved_for_requeue');
}

// ----------------------------------------------------------------------------
// Embeddings Stage Controls (pause/resume/drain)
// ----------------------------------------------------------------------------

async function embeddingsStageStatus() {
    const out = document.getElementById('embeddingsStage_status');
    try {
        const res = await apiClient.get('/api/v1/embeddings/stage/status');
        out.textContent = Utils.syntaxHighlight(res);
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error('Failed to fetch stage status');
    }
}

async function embeddingsStageControl(action) {
    const stage = document.getElementById('embeddingsStage_stage').value;
    const out = document.getElementById('embeddingsStage_status');
    try {
        await apiClient.post('/api/v1/embeddings/stage/control', { stage, action });
        Toast.success(`${action} sent to ${stage}`);
        await embeddingsStageStatus();
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        Toast.error(`Failed to ${action} stage`);
    }
}

async function embeddingsStagePause() { return embeddingsStageControl('pause'); }
async function embeddingsStageResume() { return embeddingsStageControl('resume'); }
async function embeddingsStageDrain() { return embeddingsStageControl('drain'); }

function embeddingsStartDLQAutoRefresh() {
    try { embeddingsStopDLQAutoRefresh(); } catch (e) { /* ignore */ }
    embeddingsRefreshDLQBadges();
    embeddingsDLQTimer = setInterval(embeddingsRefreshDLQBadges, 10000);
    try { Utils.saveToStorage('embeddings-dlq-auto-refresh', true); } catch (e) { /* ignore */ }
}

function embeddingsStopDLQAutoRefresh() {
    if (embeddingsDLQTimer) {
        clearInterval(embeddingsDLQTimer);
        embeddingsDLQTimer = null;
    }
    try { Utils.saveToStorage('embeddings-dlq-auto-refresh', false); } catch (e) { /* ignore */ }
}

async function segmentTranscriptRun() {
    const entries = segParseEntries();
    if (!entries.length) {
        alert('Please provide transcript entries');
        return;
    }

    const K = parseInt(document.getElementById('segK')?.value || '6', 10);
    const min_segment_size = parseInt(document.getElementById('segMinSize')?.value || '5', 10);
    const lambda_balance = parseFloat(document.getElementById('segLambda')?.value || '0.01');
    const utterance_expansion_width = parseInt(document.getElementById('segWidth')?.value || '2', 10);
    const embeddings_provider = (document.getElementById('segProvider')?.value || '').trim() || undefined;
    const embeddings_model = (document.getElementById('segModel')?.value || '').trim() || undefined;

    const payload = {
        entries,
        K,
        min_segment_size,
        lambda_balance,
        utterance_expansion_width,
        embeddings_provider,
        embeddings_model,
    };

    const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
    const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';

    try {
        const res = await fetch(`${baseUrl}/api/v1/audio/segment/transcript`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            },
            body: JSON.stringify(payload),
        });
        if (!res.ok) {
            const text = await res.text();
            throw new Error(`HTTP ${res.status}: ${text}`);
        }
        const data = await res.json();
        segRenderResults(data, entries.length);
    } catch (e) {
        console.error('Segmentation failed', e);
        alert(`Segmentation failed: ${e.message}`);
    }
}

function segRenderResults(result, totalCount) {
    const transEl = document.getElementById('segTransitions');
    if (transEl) transEl.textContent = JSON.stringify(result.transitions || [], null, 2);

    const timeline = document.getElementById('segTimeline');
    if (timeline) timeline.innerHTML = '';
    const segments = result.segments || [];
    const totalLen = totalCount || segments.reduce((a, s) => a + (s.indices?.length || 0), 0);
    if (timeline) {
        segments.forEach((seg, idx) => {
            const len = (seg.indices && seg.indices.length) ? seg.indices.length : 1;
            const widthPct = Math.max(2, Math.round((len / Math.max(1, totalLen)) * 100));
            const div = document.createElement('div');
            div.title = `Segment ${idx + 1}: ${len} items`;
            div.style.cssText = `height: 18px; background:${segColor(idx)}; width:${widthPct}%; min-width:6px;`;
            timeline.appendChild(div);
        });
    }

    const list = document.getElementById('segList');
    if (list) list.innerHTML = '';
    segments.forEach((seg, idx) => {
        const box = document.createElement('div');
        box.className = 'result-item';
        const speakers = (seg.speakers || []).join(', ');
        const header = document.createElement('div');
        header.innerHTML = `<strong>Segment ${idx + 1}</strong> | Indices: ${seg.start_index}-${seg.end_index} | Speakers: ${speakers || '-'}`;

        const pre = document.createElement('pre');
        pre.textContent = (seg.text || '').slice(0, 800);
        pre.style.whiteSpace = 'pre-wrap';
        pre.style.maxHeight = '200px';
        pre.style.overflow = 'auto';

        box.appendChild(header);
        box.appendChild(pre);
        if (list) list.appendChild(box);
    });
}

function segColor(i) {
    const colors = ['#4caf50', '#2196f3', '#ff9800', '#9c27b0', '#e91e63', '#00bcd4', '#8bc34a'];
    return colors[i % colors.length];
}

function segClearOutput() {
    const transEl = document.getElementById('segTransitions');
    if (transEl) transEl.textContent = '---';
    const timeline = document.getElementById('segTimeline');
    if (timeline) timeline.innerHTML = '';
    const list = document.getElementById('segList');
    if (list) list.innerHTML = '';
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

        const res = await apiClient.get('/api/v1/audio/voices/catalog', { provider });
        const voices = (res && (res[provider] || res[provider?.toLowerCase?.()] || res[provider?.toUpperCase?.()])) || res || [];

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
                    const id = v.id || v.name || 'voice';
                    const name = v.name || v.id || 'Voice';
                    const meta = [v.language, v.gender].filter(Boolean).join(' · ');
                    return `<div class="voice-item" style="padding:6px 0; border-bottom: 1px dashed var(--color-border); display:flex; align-items:center; justify-content:space-between; gap:8px;">
                        <div class="voice-meta">
                            <strong>${name}</strong>
                            <div class="text-muted" style="font-size: 0.85em;">${meta || ''}</div>
                            <div style="font-size: 0.85em;">${v.description || ''}</div>
                        </div>
                        <div class="voice-actions">
                            <button class="btn-small" onclick="apiTTSUseVoice('${provider}','${id}','${name.replace(/"/g, '&quot;')}')">
                                <i class="icon-check"></i> Use Voice
                            </button>
                        </div>
                    </div>`;
                }).join('');
                // Replace HTML injection with safe DOM build
                voiceList.innerHTML = '';
                voices.forEach(v => {
                    const id = v.id || v.name || 'voice';
                    const name = v.name || v.id || 'Voice';
                    const metaText = [v.language, v.gender].filter(Boolean).join(' · ');
                    const row = document.createElement('div');
                    row.className = 'voice-item';
                    row.style.cssText = 'padding:6px 0; border-bottom: 1px dashed var(--color-border); display:flex; align-items:center; justify-content:space-between; gap:8px;';
                    const meta = document.createElement('div');
                    meta.className = 'voice-meta';
                    const strong = document.createElement('strong');
                    strong.textContent = name;
                    const muted = document.createElement('div');
                    muted.className = 'text-muted';
                    muted.style.fontSize = '0.85em';
                    muted.textContent = metaText || '';
                    const desc = document.createElement('div');
                    desc.style.fontSize = '0.85em';
                    desc.textContent = v.description || '';
                    meta.appendChild(strong);
                    meta.appendChild(muted);
                    meta.appendChild(desc);
                    const actions = document.createElement('div');
                    actions.className = 'voice-actions';
                    const btn = document.createElement('button');
                    btn.className = 'btn-small';
                    btn.innerHTML = '<i class="icon-check"></i> Use Voice';
                    btn.addEventListener('click', () => apiTTSUseVoice(provider, id, name));
                    actions.appendChild(btn);
                    row.appendChild(meta);
                    row.appendChild(actions);
                    voiceList.appendChild(row);
                });
            }
        }
    } catch (err) {
        console.error('Failed to load voices', err);
        const voiceList = document.getElementById('audioTTS_voiceList');
        if (voiceList) {
            voiceList.style.display = 'block';
            const span = document.createElement('span');
            span.className = 'error';
            span.textContent = `Error loading voices: ${err?.message || err}`;
            voiceList.innerHTML = '';
            voiceList.appendChild(span);
        }
    }
}

// Use voice helper for Audio → Text to Speech panel
async function apiTTSUseVoice(provider, voiceId, name) {
    try {
        const providerSelect = document.getElementById('audioTTS_provider');
        if (providerSelect) {
            providerSelect.value = provider;
            if (typeof updateTTSProviderOptions === 'function') {
                try { updateTTSProviderOptions(); } catch (_) { /* ignore */ }
            }
        }
        // Reload the provider voices to keep dropdown consistent
        try { await loadProviderVoices(); } catch (_) { /* ignore */ }
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
        // Brief inline confirmation
        const voiceList = document.getElementById('audioTTS_voiceList');
        if (voiceList) {
            const msg = document.createElement('div');
            msg.className = 'text-success';
            msg.style.marginBottom = '6px';
            msg.textContent = `Selected voice ${name || voiceId} (${provider})`;
            voiceList.prepend(msg);
            setTimeout(() => { try { msg.remove(); } catch (_) {} }, 2000);
        }
        // Sync selection into TTS tab as well
        if (window.TTS && typeof TTS._selectProviderVoice === 'function') {
            try { TTS._selectProviderVoice(provider, voiceId, name, false); } catch (_) { /* ignore */ }
        }
    } catch (e) {
        console.error('apiTTSUseVoice failed:', e);
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

// ----------------------------------------------------------------------------
// Audio TTS: Quick mic recording for voice reference
// ----------------------------------------------------------------------------
let _audioTTSRec = { mr: null, chunks: [], blob: null, url: null };

async function startAudioTTSRecording() {
    try {
        if (_audioTTSRec.mr) return;
        if (!window.MediaRecorder) {
            const s = document.getElementById('audioTTS_rec_status');
            if (s) s.textContent = 'Recording not supported by this browser';
            return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Choose a supported mimeType
        let mr;
        try {
            let opts;
            if (MediaRecorder.isTypeSupported) {
                const cands = ['audio/webm;codecs=opus','audio/webm','audio/mp4'];
                for (const mt of cands) {
                    if (MediaRecorder.isTypeSupported(mt)) { opts = { mimeType: mt }; break; }
                }
            }
            mr = new MediaRecorder(stream, opts);
        } catch (_) {
            mr = new MediaRecorder(stream);
        }
        _audioTTSRec = { mr, chunks: [], blob: null, url: null };
        const s = document.getElementById('audioTTS_rec_status');
        const b1 = document.getElementById('audioTTS_rec_start');
        const b2 = document.getElementById('audioTTS_rec_stop');
        if (s) s.textContent = 'Recording...';
        if (b1) b1.disabled = true;
        if (b2) b2.disabled = false;
        mr.ondataavailable = (e)=>{ if(e.data && e.data.size) _audioTTSRec.chunks.push(e.data); };
        mr.onstop = () => {
            try { if (_audioTTSRec._timer) { clearInterval(_audioTTSRec._timer); _audioTTSRec._timer = null; } } catch(_){}
            const blob = new Blob(_audioTTSRec.chunks, { type: 'audio/webm' });
            _audioTTSRec.blob = blob;
            const url = URL.createObjectURL(blob);
            _audioTTSRec.url = url;
            const p = document.getElementById('audioTTS_rec_playback');
            if (p) { p.src = url; p.style.display = 'block'; }
            if (s) s.textContent = 'Recorded';
            if (b1) b1.disabled = false;
            if (b2) b2.disabled = true;
            const badge = document.getElementById('audioTTS_recording_badge');
            if (badge) badge.style.display = 'inline-block';
            const clr = document.getElementById('audioTTS_rec_clear');
            if (clr) clr.disabled = false;
            const fileInput = document.getElementById('audioTTS_voiceReference');
            if (fileInput) fileInput.disabled = true;
            try { stream.getTracks().forEach(t => t.stop()); } catch(_){}
        };
        // Soft cap with countdown
        try {
            const MAX_SEC = Math.max(3, Math.min(60, parseInt((window._audioRecMaxSec||15), 10)));
            const startTs = Date.now();
            _audioTTSRec._timer = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTs) / 1000);
                const left = Math.max(0, MAX_SEC - elapsed);
                if (s) s.textContent = `Recording... ${left}s left`;
                if (elapsed >= MAX_SEC) {
                    try { mr.stop(); } catch(_){}
                }
            }, 250);
        } catch(_){}
        mr.start();
    } catch (e) {
        console.error('AudioTTS recording failed', e);
        const s = document.getElementById('audioTTS_rec_status');
        if (s) s.textContent = 'Recording failed';
    }
}

function stopAudioTTSRecording() {
    try { if (_audioTTSRec.mr) _audioTTSRec.mr.stop(); } catch(e){ console.error(e); }
}

function clearAudioTTSRecording() {
    try { if (_audioTTSRec && _audioTTSRec.url) URL.revokeObjectURL(_audioTTSRec.url); } catch(_) {}
    _audioTTSRec = { mr: null, chunks: [], blob: null, url: null };
    const p = document.getElementById('audioTTS_rec_playback');
    if (p) { try { p.pause(); } catch(_){} p.removeAttribute('src'); p.style.display='none'; }
    const badge = document.getElementById('audioTTS_recording_badge');
    if (badge) badge.style.display = 'none';
    const s = document.getElementById('audioTTS_rec_status');
    if (s) s.textContent = 'Idle (recording overrides file)';
    const clr = document.getElementById('audioTTS_rec_clear');
    if (clr) clr.disabled = true;
    const b1 = document.getElementById('audioTTS_rec_start');
    if (b1) b1.disabled = false;
    const b2 = document.getElementById('audioTTS_rec_stop');
    if (b2) b2.disabled = true;
    const fileInput = document.getElementById('audioTTS_voiceReference');
    if (fileInput) fileInput.disabled = false;
}

async function _audioBlobToBase64Wav(blob) {
    // Convert to WAV for server compatibility
    const buf = await blob.arrayBuffer();
    const ac = new (window.AudioContext||window.webkitAudioContext)();
    const audioBuffer = await ac.decodeAudioData(buf);
    const wavView = _encodeWavFromBuffer(audioBuffer);
    const wavBlob = new Blob([wavView], { type: 'audio/wav' });
    const wavBuf = await wavBlob.arrayBuffer();
    const bytes = new Uint8Array(wavBuf);
    let binary=''; const step=0x8000;
    for(let i=0;i<bytes.length;i+=step) binary+=String.fromCharCode.apply(null, bytes.subarray(i,i+step));
    return btoa(binary);
}

function _encodeWavFromBuffer(audioBuffer){
    const data = audioBuffer.numberOfChannels>1? _mixToMono(audioBuffer): audioBuffer.getChannelData(0);
    const sr = audioBuffer.sampleRate;
    const pcm = _floatTo16(data);
    const ab = new ArrayBuffer(44 + pcm.length*2); const view = new DataView(ab);
    _writeStr(view,0,'RIFF'); view.setUint32(4,36+pcm.length*2,true); _writeStr(view,8,'WAVE');
    _writeStr(view,12,'fmt '); view.setUint32(16,16,true); view.setUint16(20,1,true);
    view.setUint16(22,1,true); view.setUint32(24,sr,true); view.setUint32(28,sr*2,true);
    view.setUint16(32,2,true); view.setUint16(34,16,true); _writeStr(view,36,'data'); view.setUint32(40,pcm.length*2,true);
    let off=44; for(let i=0;i<pcm.length;i++,off+=2) view.setInt16(off, pcm[i], true);
    return view;
}
function _floatTo16(input){ const out=new Int16Array(input.length); for(let i=0;i<input.length;i++){ let s=Math.max(-1,Math.min(1,input[i])); out[i]=s<0?s*0x8000:s*0x7FFF;} return out; }
function _mixToMono(buf){ const l=buf.length; const a=buf.getChannelData(0), b=buf.getChannelData(1), o=new Float32Array(l); for(let i=0;i<l;i++) o[i]=0.5*(a[i]+b[i]); return o; }
function _writeStr(view, offset, str){ for (let i=0;i<str.length;i++) view.setUint8(offset+i, str.charCodeAt(i)); }

// File Transcription: Quick mic recording
let _fileTransRec = { mr: null, chunks: [], blob: null, url: null };
async function startFileTransRecording() {
    try {
        if (_fileTransRec.mr) return;
        if (!window.MediaRecorder) {
            const s = document.getElementById('fileTrans_rec_status');
            if (s) s.textContent = 'Recording not supported by this browser';
            return;
        }
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        // Choose a supported mimeType
        let mr;
        try {
            let opts;
            if (MediaRecorder.isTypeSupported) {
                const cands = ['audio/webm;codecs=opus','audio/webm','audio/mp4'];
                for (const mt of cands) {
                    if (MediaRecorder.isTypeSupported(mt)) { opts = { mimeType: mt }; break; }
                }
            }
            mr = new MediaRecorder(stream, opts);
        } catch (_) {
            mr = new MediaRecorder(stream);
        }
        _fileTransRec = { mr, chunks: [], blob: null, url: null };
        const s = document.getElementById('fileTrans_rec_status');
        const b1 = document.getElementById('fileTrans_rec_start');
        const b2 = document.getElementById('fileTrans_rec_stop');
        if (s) s.textContent = 'Recording...';
        if (b1) b1.disabled = true;
        if (b2) b2.disabled = false;
        mr.ondataavailable = (e)=>{ if(e.data && e.data.size) _fileTransRec.chunks.push(e.data); };
        mr.onstop = () => {
            try { if (_fileTransRec._timer) { clearInterval(_fileTransRec._timer); _fileTransRec._timer = null; } } catch(_){}
            const blob = new Blob(_fileTransRec.chunks, { type: 'audio/webm' });
            _fileTransRec.blob = blob;
            const url = URL.createObjectURL(blob);
            _fileTransRec.url = url;
            const p = document.getElementById('fileTrans_rec_playback');
            if (p) { p.src = url; p.style.display = 'block'; }
            if (s) s.textContent = 'Recorded';
            if (b1) b1.disabled = false;
            if (b2) b2.disabled = true;
            const badge = document.getElementById('fileTrans_recording_badge');
            if (badge) badge.style.display = 'inline-block';
            const clr = document.getElementById('fileTrans_rec_clear');
            if (clr) clr.disabled = false;
            const file = document.getElementById('fileTrans_audio');
            if (file) file.disabled = true;
            try { stream.getTracks().forEach(t => t.stop()); } catch(_){}
        };
        // Soft cap with countdown
        try {
            const MAX_SEC = Math.max(3, Math.min(60, parseInt((window._fileTransRecMaxSec||15), 10)));
            const startTs = Date.now();
            _fileTransRec._timer = setInterval(() => {
                const elapsed = Math.floor((Date.now() - startTs) / 1000);
                const left = Math.max(0, MAX_SEC - elapsed);
                if (s) s.textContent = `Recording... ${left}s left`;
                if (elapsed >= MAX_SEC) {
                    try { mr.stop(); } catch(_){}
                }
            }, 250);
        } catch(_){}
        mr.start();
    } catch (e) {
        console.error('FileTrans recording failed', e);
        const s = document.getElementById('fileTrans_rec_status');
        if (s) s.textContent = 'Recording failed';
    }
}

function stopFileTransRecording() {
    try { if (_fileTransRec.mr) _fileTransRec.mr.stop(); } catch(e){ console.error(e); }
}

function clearFileTransRecording() {
    try { if (_fileTransRec && _fileTransRec.url) URL.revokeObjectURL(_fileTransRec.url); } catch(_) {}
    _fileTransRec = { mr: null, chunks: [], blob: null, url: null };
    const p = document.getElementById('fileTrans_rec_playback');
    if (p) { try { p.pause(); } catch(_){} p.removeAttribute('src'); p.style.display='none'; }
    const badge = document.getElementById('fileTrans_recording_badge');
    if (badge) badge.style.display = 'none';
    const s = document.getElementById('fileTrans_rec_status');
    if (s) s.textContent = 'Idle (recording overrides file)';
    const clr = document.getElementById('fileTrans_rec_clear');
    if (clr) clr.disabled = true;
    const b1 = document.getElementById('fileTrans_rec_start');
    if (b1) b1.disabled = false;
    const b2 = document.getElementById('fileTrans_rec_stop');
    if (b2) b2.disabled = true;
    const file = document.getElementById('fileTrans_audio');
    if (file) file.disabled = false;
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
        // Load embedding providers/models from server then init dropdowns
        loadEmbeddingProviderConfig().then(() => {
            initEmbeddingDropdowns();
        }).catch(() => {
            initEmbeddingDropdowns();
        });
    }, 500);
});

// Bind Enter-to-send for chat input when DOM ready
document.addEventListener('DOMContentLoaded', function() {
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                sendChatMessage();
            }
        });
    }
});

// ----------------------------------------------------------------------------
// File-based Transcription UI
// ----------------------------------------------------------------------------

async function audioFileTranscribeRun() {
    const fileInput = document.getElementById('fileTrans_audio');
    if (!fileInput || !fileInput.files || !fileInput.files[0]) {
        alert('Please select an audio file');
        return;
    }
    const fd = new FormData();
    fd.append('file', fileInput.files[0]);
    fd.append('model', document.getElementById('fileTrans_model')?.value || 'whisper-1');
    const lang = (document.getElementById('fileTrans_language')?.value || '').trim();
    if (lang) fd.append('language', lang);
    fd.append('response_format', document.getElementById('fileTrans_response')?.value || 'json');
    fd.append('temperature', document.getElementById('fileTrans_temp')?.value || '0.0');
    fd.append('timestamp_granularities', document.getElementById('fileTrans_ts')?.value || 'segment');

    const doSeg = document.getElementById('fileTrans_segment')?.checked;
    if (doSeg) {
        fd.append('segment', 'true');
        fd.append('seg_K', document.getElementById('fileSegK')?.value || '6');
        fd.append('seg_min_segment_size', document.getElementById('fileSegMin')?.value || '5');
        fd.append('seg_lambda_balance', document.getElementById('fileSegLambda')?.value || '0.01');
        fd.append('seg_utterance_expansion_width', document.getElementById('fileSegWidth')?.value || '2');
        const p = (document.getElementById('fileSegProvider')?.value || '').trim();
        const m = (document.getElementById('fileSegModel')?.value || '').trim();
        if (p) fd.append('seg_embeddings_provider', p);
        if (m) fd.append('seg_embeddings_model', m);
    }

    try {
        const data = await apiClient.makeRequest('POST', '/api/v1/audio/transcriptions', { body: fd });
        renderFileTranscriptionResult(data);
    } catch (e) {
        console.error('Transcription failed', e);
        alert(`Transcription failed: ${e.message}`);
    }
}

function renderFileTranscriptionResult(result) {
    const out = document.getElementById('fileTrans_output');
    if (out) out.textContent = result?.text || '(no text)';

    const segBlock = document.getElementById('fileSeg_results');
    if (!result?.segmentation || !result.segmentation.segments) {
        if (segBlock) segBlock.style.display = 'none';
        return;
    }
    if (segBlock) segBlock.style.display = 'block';
    const seg = result.segmentation;
    const transEl = document.getElementById('fileSegTransitions');
    if (transEl) transEl.textContent = JSON.stringify(seg.transitions || [], null, 2);
    const timeline = document.getElementById('fileSegTimeline');
    const list = document.getElementById('fileSegList');
    if (timeline) timeline.innerHTML = '';
    if (list) list.innerHTML = '';
    const segments = seg.segments || [];
    const totalLen = segments.reduce((a, s) => a + (s.indices?.length || 0), 0);
    if (timeline) {
        segments.forEach((s, i) => {
            const len = (s.indices && s.indices.length) ? s.indices.length : 1;
            const widthPct = Math.max(2, Math.round((len / Math.max(1, totalLen)) * 100));
            const div = document.createElement('div');
            div.title = `Segment ${i + 1}: ${len} items`;
            div.style.cssText = `height: 18px; background:${segColor(i)}; width:${widthPct}%; min-width:6px;`;
            timeline.appendChild(div);
        });
    }
    if (list) {
        segments.forEach((s, i) => {
            const box = document.createElement('div');
            box.className = 'result-item';
            const speakers = (s.speakers || []).join(', ');
            const header = document.createElement('div');
            header.innerHTML = `<strong>Segment ${i + 1}</strong> | Indices: ${s.start_index}-${s.end_index} | Speakers: ${speakers || '-'}`;
            const pre = document.createElement('pre');
            pre.textContent = (s.text || '').slice(0, 800);
            pre.style.whiteSpace = 'pre-wrap';
            pre.style.maxHeight = '200px';
            pre.style.overflow = 'auto';
            box.appendChild(header);
            box.appendChild(pre);
            list.appendChild(box);
        });
    }
}

function audioFileTranscribeClear() {
    const out = document.getElementById('fileTrans_output');
    if (out) out.textContent = '---';
    const segBlock = document.getElementById('fileSeg_results');
    if (segBlock) segBlock.style.display = 'none';
    const t1 = document.getElementById('fileSegTransitions');
    const t2 = document.getElementById('fileSegTimeline');
    const t3 = document.getElementById('fileSegList');
    if (t1) t1.textContent = '---';
    if (t2) t2.innerHTML = '';
    if (t3) t3.innerHTML = '';
}

// ----------------------------------------------------------------------------
// Embedding provider/model dropdown helpers
// ----------------------------------------------------------------------------

const EMBED_PROVIDER_CONFIG = {
    openai: {
        models: ['text-embedding-3-small', 'text-embedding-3-large']
    },
    huggingface: {
        models: ['sentence-transformers/all-MiniLM-L6-v2', 'BAAI/bge-small-en-v1.5']
    },
    local: {
        models: ['all-MiniLM-L6-v2', 'all-MiniLM-L12-v2']
    }
};

async function loadEmbeddingProviderConfig() {
    try {
        const baseUrl = (window.apiClient && window.apiClient.baseUrl) ? window.apiClient.baseUrl : window.location.origin;
        const token = (window.apiClient && window.apiClient.token) ? window.apiClient.token : '';
        const res = await fetch(`${baseUrl}/api/v1/embeddings/providers-config`, {
            headers: {
                ...(token ? { 'Authorization': `Bearer ${token}` } : {}),
            }
        });
        if (!res.ok) return;
        const data = await res.json();
        if (data && Array.isArray(data.providers)) {
            // Reset config
            const newCfg = {};
            const providerNames = [];
            data.providers.forEach(p => {
                newCfg[p.name] = { models: Array.isArray(p.models) ? p.models : [] };
                providerNames.push(p.name);
            });
            // Merge in known defaults if none present
            const fallbacks = {
                openai: ['text-embedding-3-small', 'text-embedding-3-large'],
                huggingface: ['sentence-transformers/all-MiniLM-L6-v2'],
                local: ['all-MiniLM-L6-v2']
            };
            Object.keys(fallbacks).forEach(k => {
                if (!newCfg[k]) newCfg[k] = { models: fallbacks[k] };
                if (!Array.isArray(newCfg[k].models) || !newCfg[k].models.length) newCfg[k].models = fallbacks[k];
            });
            // Mutate constant object properties (safe under const binding)
            Object.keys(EMBED_PROVIDER_CONFIG).forEach(k => delete EMBED_PROVIDER_CONFIG[k]);
            Object.keys(newCfg).forEach(k => EMBED_PROVIDER_CONFIG[k] = newCfg[k]);

            // Set defaults in UI if present
            const defProv = data.default_provider || '';
            const defModel = data.default_model || '';
            // Populate provider selects dynamically
            populateProviderSelect('segProvider', providerNames, defProv);
            populateProviderSelect('fileSegProvider', providerNames, defProv);
            // Ensure model lists are updated to match providers
            updateEmbeddingModels('segProvider', 'segModel');
            updateEmbeddingModels('fileSegProvider', 'fileSegModel');
            // Try to select default model when provider matches server default
            if (defProv && defModel) {
                const segProv = document.getElementById('segProvider');
                const segModel = document.getElementById('segModel');
                if (segProv && segModel && segProv.value === defProv && [...segModel.options].some(o => o.value === defModel)) {
                    segModel.value = defModel;
                }
                const fileProv = document.getElementById('fileSegProvider');
                const fileModel = document.getElementById('fileSegModel');
                if (fileProv && fileModel && fileProv.value === defProv && [...fileModel.options].some(o => o.value === defModel)) {
                    fileModel.value = defModel;
                }
            }
        }
    } catch (e) {
        console.warn('Could not load embeddings providers config from server', e);
    }
}

function populateProviderSelect(selectId, providers, defaultProvider) {
    try {
        const sel = document.getElementById(selectId);
        if (!sel) return;
        const current = sel.value;
        const opts = [
            { value: '', text: '(use server default)' },
            ...providers.map(p => ({ value: p, text: p.charAt(0).toUpperCase() + p.slice(1) }))
        ];
        sel.innerHTML = '';
        opts.forEach(o => {
            const opt = document.createElement('option');
            opt.value = o.value;
            opt.textContent = o.text;
            sel.appendChild(opt);
        });
        if (defaultProvider && providers.includes(defaultProvider)) {
            sel.value = defaultProvider;
        } else if ([...sel.options].some(o => o.value === current)) {
            sel.value = current;
        }
    } catch (e) {
        console.warn('populateProviderSelect failed', e);
    }
}

async function refreshEmbeddingProviders() {
    try {
        await loadEmbeddingProviderConfig();
        // Refresh model lists to reflect any changes
        updateEmbeddingModels('segProvider', 'segModel');
        updateEmbeddingModels('fileSegProvider', 'fileSegModel');
    } catch (e) {
        console.warn('Refresh providers failed', e);
    }
}

function initEmbeddingDropdowns() {
    setupEmbeddingDropdown('segProvider', 'segModel');
    setupEmbeddingDropdown('fileSegProvider', 'fileSegModel');
}

function setupEmbeddingDropdown(providerId, modelId) {
    const prov = document.getElementById(providerId);
    const model = document.getElementById(modelId);
    if (!prov || !model) return;
    prov.addEventListener('change', () => updateEmbeddingModels(providerId, modelId));
    updateEmbeddingModels(providerId, modelId);
}

function updateEmbeddingModels(providerId, modelId) {
    const prov = document.getElementById(providerId);
    const model = document.getElementById(modelId);
    if (!prov || !model) return;
    const provider = prov.value;
    const defaultOpt = document.createElement('option');
    defaultOpt.value = '';
    defaultOpt.textContent = '(use provider default)';
    model.innerHTML = '';
    model.appendChild(defaultOpt);
    if (!provider) return;
    const cfg = EMBED_PROVIDER_CONFIG[provider] || { models: [] };
    cfg.models.forEach(m => {
        const opt = document.createElement('option');
        opt.value = m;
        opt.textContent = m;
        model.appendChild(opt);
    });
}

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
    // Crawl controls for recursive/url_level
    const needsCrawlControls = (method === 'recursive_scraping' || method === 'url_level');
    show('group_friendlyIngest_crawl_strategy', needsCrawlControls);
    show('group_friendlyIngest_include_external', needsCrawlControls);
    show('group_friendlyIngest_score_threshold', needsCrawlControls);
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
        status.classList.remove('error');
        return;
    }

    const text = input.value.trim();
    if (text === '') {
        status.textContent = 'Provide valid JSON when using cookies.';
        status.classList.add('error');
        return;
    }

    try {
        const parsed = JSON.parse(text);
        const ok = Array.isArray(parsed) || typeof parsed === 'object';
        if (!ok) throw new Error('Cookies must be an object or an array of objects');

        // Pretty print normalized JSON back into the field
        input.value = JSON.stringify(parsed, null, 2);
        status.textContent = 'Cookies JSON valid';
        status.classList.remove('error');
    } catch (e) {
        status.textContent = 'Invalid JSON: ' + e.message;
        status.classList.add('error');
    }
}

function updateFriendlyIngestValidationState() {
    const submitBtn = document.getElementById('friendlyIngest_submit');
    const hintEl = document.getElementById('friendlyIngest_validation_hint');
    const summaryEl = document.getElementById('friendlyIngest_validation_summary');
    if (!submitBtn) return;

    let isValid = true;
    const errors = [];
    // Reset field highlights and hints
    const resetInvalid = (id) => { const el = document.getElementById(id); if (el) el.classList.remove('input-invalid'); };
    const markInvalid = (id) => { const el = document.getElementById(id); if (el) el.classList.add('input-invalid'); };
    ['friendlyIngest_urls','friendlyIngest_url_level','friendlyIngest_max_pages','friendlyIngest_max_depth','friendlyIngest_cookies']
        .forEach(resetInvalid);
    const clearHint = (id) => { const el = document.getElementById(id); if (el) { el.textContent = ''; el.classList.remove('error'); } };
    const setHint = (id, msg) => { const el = document.getElementById(id); if (el) { el.textContent = msg; el.classList.add('error'); } };
    ['friendlyIngest_urls_hint','friendlyIngest_url_level_hint','friendlyIngest_max_pages_hint','friendlyIngest_max_depth_hint']
        .forEach(clearHint);

    const urls = (document.getElementById('friendlyIngest_urls')?.value || '')
        .split('\n').map(s => s.trim()).filter(Boolean);
    if (urls.length === 0) {
        isValid = false;
        errors.push('Enter at least one URL.');
        markInvalid('friendlyIngest_urls');
        setHint('friendlyIngest_urls_hint', 'Enter at least one valid URL, one per line.');
    }

    const method = document.getElementById('friendlyIngest_scrape_method')?.value || 'individual';
    const urlLevel = parseInt(document.getElementById('friendlyIngest_url_level')?.value || '0', 10);
    const maxPages = parseInt(document.getElementById('friendlyIngest_max_pages')?.value || '0', 10);
    const maxDepth = parseInt(document.getElementById('friendlyIngest_max_depth')?.value || '0', 10);

    if (method === 'url_level' && (!urlLevel || urlLevel < 1)) {
        isValid = false;
        errors.push('Set URL Level to 1 or higher for url_level method.');
        markInvalid('friendlyIngest_url_level');
        setHint('friendlyIngest_url_level_hint', 'URL Level must be 1 or greater.');
    }
    if (method === 'recursive_scraping' && (!maxPages || maxPages < 1 || !maxDepth || maxDepth < 1)) {
        isValid = false;
        errors.push('Set Max Pages and Max Depth (>= 1) for recursive_scraping.');
        if (!maxPages || maxPages < 1) { markInvalid('friendlyIngest_max_pages'); setHint('friendlyIngest_max_pages_hint', 'Max Pages must be 1 or greater.'); }
        if (!maxDepth || maxDepth < 1) { markInvalid('friendlyIngest_max_depth'); setHint('friendlyIngest_max_depth_hint', 'Max Depth must be 1 or greater.'); }
    }
    if (method === 'sitemap' && (!maxPages || maxPages < 1)) {
        isValid = false;
        errors.push('Set Max Pages (>= 1) for sitemap method.');
        markInvalid('friendlyIngest_max_pages');
        setHint('friendlyIngest_max_pages_hint', 'Max Pages must be 1 or greater.');
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
        const propEngine = document.getElementById('friendlyIngest_prop_engine')?.value || null;
        const propProfile = document.getElementById('friendlyIngest_prop_profile')?.value || null;
        const propAggr = parseInt(document.getElementById('friendlyIngest_prop_aggr')?.value || '1', 10);
        const propMinLen = parseInt(document.getElementById('friendlyIngest_prop_minlen')?.value || '15', 10);
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
            // Proposition-specific (only when method='propositions')
            ...(chunkMethod === 'propositions' ? {
                proposition_engine: propEngine || undefined,
                proposition_prompt_profile: propProfile || undefined,
                proposition_aggressiveness: isNaN(propAggr) ? undefined : propAggr,
                proposition_min_proposition_length: isNaN(propMinLen) ? undefined : propMinLen
            } : {}),

            use_cookies: useCookies,
            cookies: useCookies && cookiesText ? cookiesText : undefined,

            timestamp_option: timestampOption,
            overwrite_existing: overwriteExisting,
            custom_chapter_pattern: customChapterPattern || undefined
        };

        // Optional crawl controls (only applicable for recursive/url_level)
        try {
            const crawlStrategy = document.getElementById('friendlyIngest_crawl_strategy')?.value || null;
            const includeExternal = !!(document.getElementById('friendlyIngest_include_external')?.checked);
            const scoreThreshold = parseFloat(document.getElementById('friendlyIngest_score_threshold')?.value || '0');
            if (scrapeMethod === 'recursive_scraping' || scrapeMethod === 'url_level') {
                payload.crawl_strategy = crawlStrategy || undefined;
                payload.include_external = includeExternal;
                payload.score_threshold = isNaN(scoreThreshold) ? undefined : scoreThreshold;
            }
        } catch (_) {}

        // Toggle proposition controls based on method
        const methodSelect = document.getElementById('friendlyIngest_chunk_method');
        const togglePropControls = () => {
            const isProps = (methodSelect.value === 'propositions');
            document.getElementById('friendlyIngest_prop_engine_group').style.display = isProps ? '' : 'none';
            document.getElementById('friendlyIngest_prop_profile_group').style.display = isProps ? '' : 'none';
            document.getElementById('friendlyIngest_prop_aggr_group').style.display = isProps ? '' : 'none';
            document.getElementById('friendlyIngest_prop_minlen_group').style.display = isProps ? '' : 'none';
        };
        // Ensure controls are in correct state
        try { togglePropControls(); } catch(e) {}
        // Register change listener once
        if (!methodSelect._propToggleBound) {
            methodSelect.addEventListener('change', togglePropControls);
            methodSelect._propToggleBound = true;
        }

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
// Multi-Item Analysis Tab
// ============================================================================

function initializeMultiItemAnalysisTab() {
    try {
        // Ensure model dropdowns are populated
        if (typeof window.populateModelDropdowns === 'function') {
            window.populateModelDropdowns();
        }

        // Basic initial render
        const queue = Utils.getFromStorage('multi-analysis-queue') || [];
        renderMultiQueue(queue);

        // Scrape method field toggles
        const methodSelect = document.getElementById('multi_scrape_method');
        if (methodSelect) {
            methodSelect.addEventListener('change', updateMultiScrapeMethodUI);
            updateMultiScrapeMethodUI();
        }
        // Processing type toggles and file accept
        const procType = document.getElementById('multi_processing_type');
        if (procType) {
            procType.addEventListener('change', updateProcessingTypeUI);
            updateProcessingTypeUI();
        }

        // Start with Advanced collapsed
        const advBody = document.getElementById('multi_advanced_options');
        const advBtn = document.getElementById('multi_adv_toggle_btn');
        if (advBody && advBtn) {
            advBody.style.display = 'none';
            advBtn.textContent = 'Show';
        }
    } catch (e) {
        console.warn('Failed to initialize Multi-Item Analysis tab:', e.message);
    }
}

function multiGetSettings() {
    return {
        model: document.getElementById('multi_model')?.value || '',
        temperature: parseFloat(document.getElementById('multi_temperature')?.value || '0.7'),
        systemPrompt: document.getElementById('multi_system_prompt')?.value || '',
        analysisPrompt: document.getElementById('multi_custom_prompt')?.value || 'Summarize key points, takeaways, and action items.',
        storeOption: document.getElementById('multi_store_option')?.value || 'none',
        showMetadata: document.getElementById('multi_show_metadata')?.checked ?? true,
    };
}

function updateMultiScrapeMethodUI() {
    const method = document.getElementById('multi_scrape_method')?.value || 'Individual URLs';
    const show = (id, visible) => { const el = document.getElementById(id); if (el) el.style.display = visible ? 'block' : 'none'; };
    show('group_multi_url_level', method === 'URL Level');
    show('group_multi_max_pages', method === 'Recursive Scraping' || method === 'Sitemap');
    show('group_multi_max_depth', method === 'Recursive Scraping');
}

function updateProcessingTypeUI() {
    const type = document.getElementById('multi_processing_type')?.value || 'web';
    const show = (id, visible) => { const el = document.getElementById(id); if (el) el.style.display = visible ? 'block' : 'none'; };
    const webMode = (type === 'web');
    show('group_multi_scrape_method', webMode);
    show('group_multi_url_level', webMode);
    show('group_multi_max_pages', webMode);
    show('group_multi_max_depth', webMode);
    show('group_multi_crawl_strategy', webMode);
    show('group_multi_include_external', webMode);
    show('group_multi_score_threshold', webMode);
    // Advanced groups
    show('adv_videos', type === 'videos');
    show('adv_audios', type === 'audios');
    show('adv_documents', type === 'documents');
    show('adv_pdfs', type === 'pdfs');
    show('adv_ebooks', type === 'ebooks');
    // Files group and accept
    show('group_multi_files', type !== 'web');
    const f = document.getElementById('multi_files');
    const hint = document.getElementById('multi_files_hint');
    if (f) {
        let accept = '';
        let hintText = '';
        if (type === 'videos') { accept = 'video/*'; hintText = 'Accepts common video formats.'; }
        else if (type === 'audios') { accept = 'audio/*'; hintText = 'Accepts common audio formats.'; }
        else if (type === 'documents') { accept = '.txt,.md,.docx,.rtf,.html,.htm,.xml'; hintText = 'txt, md, docx, rtf, html, xml'; }
        else if (type === 'pdfs') { accept = '.pdf'; hintText = 'PDF files only'; }
        else if (type === 'ebooks') { accept = '.epub,.mobi,.azw3'; hintText = 'epub, mobi, azw3'; }
        f.setAttribute('accept', accept);
        if (hint) hint.textContent = `Accepted: ${hintText}`;
    }
}

// Jump to Vector Stores tab (Embeddings → Vector Stores)
function jumpToVectorStores() {
    try {
        const top = document.querySelector('.top-tab-button[data-toptab="embeddings"]');
        if (top) top.click();
        setTimeout(() => {
            const sub = document.querySelector('#embeddings-subtabs .sub-tab-button[data-content-id="tabVectorStores"]');
            if (sub) sub.click();
        }, 100);
    } catch (e) {
        console.warn('Failed to switch to Vector Stores tab:', e);
    }
}

function toggleMultiAdvancedOptions() {
    const body = document.getElementById('multi_advanced_options');
    const btn = document.getElementById('multi_adv_toggle_btn');
    if (!body || !btn) return;
    const isHidden = body.style.display === 'none' || body.style.display === '';
    body.style.display = isHidden ? 'block' : 'none';
    btn.textContent = isHidden ? 'Hide' : 'Show';
}

function renderMultiQueue(queue) {
    const container = document.getElementById('multi_queue_container');
    if (!container) return;
    container.innerHTML = '';

    if (!Array.isArray(queue) || queue.length === 0) {
        container.innerHTML = '<div style="color: var(--color-text-muted);">Queue is empty.</div>';
        return;
    }

    queue.forEach(item => {
        const card = document.createElement('div');
        card.className = 'endpoint-section';
        const key = item.ephemeral ? item.id : item.media_id;
        card.id = `multi_item_${key}`;

        let metaHtml = '';
        if (item.metadata && multiGetSettings().showMetadata) {
            metaHtml = `<div class="json-viewer-content" style="margin-top:8px;">${escapeHtml(JSON.stringify(item.metadata, null, 2))}</div>`;
        }

        card.innerHTML = `
            <h3 style="margin-bottom:4px;">${escapeHtml(item.title || 'Untitled')} <small style="color: var(--color-text-muted);">(${item.ephemeral ? 'Ephemeral' : 'ID: ' + item.media_id})</small></h3>
            <div style="margin-bottom:8px; color: var(--color-text-secondary);">${escapeHtml(item.source || '')}</div>
            ${metaHtml}
            <div class="form-group" style="margin-top:10px; display:flex; gap:8px; flex-wrap:wrap;">
                <button class="btn btn-primary" onclick="${item.ephemeral ? `multiAnalyzeEphemeral('${key}')` : `multiAnalyzeItem(${key})`}">Analyze</button>
                <button class="btn" onclick="${item.ephemeral ? `multiSaveEphemeralAnalysis('${key}')` : `multiSaveItemAnalysis(${key})`}">Save Analysis</button>
                <button class="btn btn-danger" onclick="${item.ephemeral ? `multiRemoveEphemeral('${key}')` : `multiRemoveFromQueue(${key})`}">Remove</button>
            </div>
            <h4>Analysis</h4>
            <pre id="multi_analysis_${key}">(Not analyzed)</pre>
        `;
        container.appendChild(card);
    });
}

function multiPersistQueue(queue) {
    Utils.saveToStorage('multi-analysis-queue', queue || []);
}

function multiClearQueue() {
    multiPersistQueue([]);
    renderMultiQueue([]);
}

function multiRemoveFromQueue(mediaId) {
    const queue = Utils.getFromStorage('multi-analysis-queue') || [];
    const filtered = queue.filter(q => q.media_id !== mediaId);
    multiPersistQueue(filtered);
    renderMultiQueue(filtered);
}

async function multiSearchItems() {
    const q = document.getElementById('multi_search_query')?.value || '';
    const target = document.getElementById('multi_search_results');
    try {
        target.textContent = 'Searching...';
        const payload = { query: q, fields: ["title", "content"], sort_by: 'relevance' };
        const res = await apiClient.post('/api/v1/media/search', payload);
        // Render results with checkboxes
        let html = '';
        if (res && res.results && res.results.length > 0) {
            html += '<div>';
            res.results.forEach(r => {
                html += `
                  <div style="display:flex; align-items:center; gap:8px; margin:4px 0;">
                    <input type="checkbox" class="multi-search-select" data-media-id="${r.media_id}" data-title="${escapeAttr(r.title || '')}" data-source="${escapeAttr(r.source || '')}">
                    <div>
                      <div><strong>${escapeHtml(r.title || 'Untitled')}</strong> <small style="color:var(--color-text-muted)">(ID: ${r.media_id})</small></div>
                      <div style="color:var(--color-text-secondary)">${escapeHtml((r.snippet || r.source || '').toString())}</div>
                    </div>
                  </div>`;
            });
            html += '</div>';
        } else {
            html = '(No results)';
        }
        target.innerHTML = html;
    } catch (e) {
        target.textContent = 'Search failed: ' + e.message;
    }
}

function multiClearSearchResults() {
    const target = document.getElementById('multi_search_results');
    if (target) target.textContent = '(No results)';
}

function multiAddSelectedFromSearch() {
    const checkboxes = document.querySelectorAll('.multi-search-select:checked');
    if (checkboxes.length === 0) return;
    const queue = Utils.getFromStorage('multi-analysis-queue') || [];
    checkboxes.forEach(cb => {
        const mediaId = parseInt(cb.getAttribute('data-media-id'));
        const title = cb.getAttribute('data-title') || '';
        const source = cb.getAttribute('data-source') || '';
        if (!queue.find(q => q.media_id === mediaId)) {
            queue.push({ media_id: mediaId, title, source });
        }
    });
    multiPersistQueue(queue);
    renderMultiQueue(queue);
}

async function multiIngestUrlsToQueue() {
    const urlsText = document.getElementById('multi_urls')?.value || '';
    const method = document.getElementById('multi_scrape_method')?.value || 'Individual URLs';
    const procType = document.getElementById('multi_processing_type')?.value || 'web';
    const urlLevel = parseInt(document.getElementById('multi_url_level')?.value || '2', 10);
    const maxPages = parseInt(document.getElementById('multi_max_pages')?.value || '10', 10);
    const maxDepth = parseInt(document.getElementById('multi_max_depth')?.value || '3', 10);
    const modeSel = document.getElementById('multi_process_mode');
    const persist = modeSel ? (modeSel.value === 'persist') : false;
    const status = document.getElementById('multi_ingest_status');

    if (!urlsText.trim()) {
        status.textContent = 'Provide at least one URL.';
        return;
    }

    try {
        status.textContent = 'Submitting ingestion request...';
        let res;
        if (procType === 'web') {
            const payload = {
                scrape_method: method,
                url_input: urlsText,
                url_level: method === 'URL Level' ? urlLevel : null,
                max_pages: (method === 'Recursive Scraping' || method === 'Sitemap') ? maxPages : 10,
                max_depth: method === 'Recursive Scraping' ? maxDepth : 3,
                // Crawl controls (optional)
                crawl_strategy: (document.getElementById('multi_crawl_strategy')?.value || 'best_first'),
                include_external: !!(document.getElementById('multi_include_external')?.checked),
                score_threshold: parseFloat(document.getElementById('multi_score_threshold')?.value || '0'),
                summarize_checkbox: false,
                custom_prompt: null,
                api_name: null,
                keywords: '',
                custom_titles: null,
                system_prompt: null,
                temperature: 0.7,
                custom_cookies: null,
                mode: persist ? 'persist' : 'ephemeral'
            };
            res = await apiClient.post('/api/v1/media/process-web-scraping', payload);
        } else {
            // Build FormData for other process-only endpoints
            const fd = new FormData();
            urlsText.split('\n').map(s=>s.trim()).filter(Boolean).forEach(u => fd.append('urls', u));
            const doAnalysis = document.getElementById('multi_perform_analysis')?.checked ?? true;
            fd.append('perform_analysis', doAnalysis ? 'true' : 'false');
            const systemPrompt = document.getElementById('multi_system_prompt')?.value || '';
            const customPrompt = document.getElementById('multi_custom_prompt')?.value || '';
            if (systemPrompt) fd.append('system_prompt', systemPrompt);
            if (customPrompt) fd.append('custom_prompt', customPrompt);
            const modelValue = document.getElementById('multi_model')?.value || '';
            const provider = modelValue ? modelValue.split('/')[0] : '';
            if (provider) fd.append('api_name', provider);
            // Files
            const filesInput = document.getElementById('multi_files');
            if (filesInput && filesInput.files && filesInput.files.length > 0) {
                Array.from(filesInput.files).forEach(file => fd.append('files', file));
            }
            // Advanced per-type
            if (procType === 'videos') {
                const tm = document.getElementById('multi_vid_transcription_model')?.value || '';
                if (tm) fd.append('transcription_model', tm);
                fd.append('diarize', document.getElementById('multi_vid_diarize')?.checked ? 'true' : 'false');
                fd.append('vad_use', document.getElementById('multi_vid_vad_use')?.checked ? 'true' : 'false');
                fd.append('timestamp_option', document.getElementById('multi_vid_timestamp_option')?.checked ? 'true' : 'false');
                fd.append('perform_confabulation_check_of_analysis', document.getElementById('multi_vid_confab_check')?.checked ? 'true' : 'false');
                const st = document.getElementById('multi_vid_start_time')?.value || '';
                const et = document.getElementById('multi_vid_end_time')?.value || '';
                if (st) fd.append('start_time', st);
                if (et) fd.append('end_time', et);
                fd.append('perform_chunking', document.getElementById('multi_vid_perform_chunking')?.checked ? 'true' : 'false');
                const cm = document.getElementById('multi_vid_chunk_method')?.value || '';
                if (cm) fd.append('chunk_method', cm);
                const cs = document.getElementById('multi_vid_chunk_size')?.value || '';
                const co = document.getElementById('multi_vid_chunk_overlap')?.value || '';
                if (cs) fd.append('chunk_size', cs);
                if (co) fd.append('chunk_overlap', co);
                const cl = document.getElementById('multi_vid_chunk_language')?.value || '';
                if (cl) fd.append('chunk_language', cl);
                fd.append('use_adaptive_chunking', document.getElementById('multi_vid_use_adaptive_chunking')?.checked ? 'true' : 'false');
                fd.append('use_multi_level_chunking', document.getElementById('multi_vid_use_multi_level_chunking')?.checked ? 'true' : 'false');
                fd.append('summarize_recursively', document.getElementById('multi_vid_summarize_recursively')?.checked ? 'true' : 'false');
            } else if (procType === 'audios') {
                const tm = document.getElementById('multi_aud_transcription_model')?.value || '';
                if (tm) fd.append('transcription_model', tm);
                fd.append('diarize', document.getElementById('multi_aud_diarize')?.checked ? 'true' : 'false');
                fd.append('vad_use', document.getElementById('multi_aud_vad_use')?.checked ? 'true' : 'false');
                fd.append('timestamp_option', document.getElementById('multi_aud_timestamp_option')?.checked ? 'true' : 'false');
                fd.append('perform_chunking', document.getElementById('multi_aud_perform_chunking')?.checked ? 'true' : 'false');
                const cm = document.getElementById('multi_aud_chunk_method')?.value || '';
                if (cm) fd.append('chunk_method', cm);
                const cs = document.getElementById('multi_aud_chunk_size')?.value || '';
                const co = document.getElementById('multi_aud_chunk_overlap')?.value || '';
                if (cs) fd.append('chunk_size', cs);
                if (co) fd.append('chunk_overlap', co);
                const cl = document.getElementById('multi_aud_chunk_language')?.value || '';
                if (cl) fd.append('chunk_language', cl);
                fd.append('use_adaptive_chunking', document.getElementById('multi_aud_use_adaptive_chunking')?.checked ? 'true' : 'false');
                fd.append('use_multi_level_chunking', document.getElementById('multi_aud_use_multi_level_chunking')?.checked ? 'true' : 'false');
                fd.append('summarize_recursively', document.getElementById('multi_aud_summarize_recursively')?.checked ? 'true' : 'false');
            } else if (procType === 'documents') {
                fd.append('use_cookies', document.getElementById('multi_doc_use_cookies')?.checked ? 'true' : 'false');
                const ck = document.getElementById('multi_doc_cookies')?.value || '';
                if (ck) fd.append('cookies', ck);
                fd.append('perform_chunking', document.getElementById('multi_doc_perform_chunking')?.checked ? 'true' : 'false');
                const cm = document.getElementById('multi_doc_chunk_method')?.value || '';
                if (cm) fd.append('chunk_method', cm);
                const cs = document.getElementById('multi_doc_chunk_size')?.value || '';
                const co = document.getElementById('multi_doc_chunk_overlap')?.value || '';
                if (cs) fd.append('chunk_size', cs);
                if (co) fd.append('chunk_overlap', co);
                const cl = document.getElementById('multi_doc_chunk_language')?.value || '';
                if (cl) fd.append('chunk_language', cl);
                const ccp = document.getElementById('multi_doc_custom_chapter_pattern')?.value || '';
                if (ccp) fd.append('custom_chapter_pattern', ccp);
            } else if (procType === 'pdfs') {
                const engine = document.getElementById('multi_pdf_parsing_engine')?.value || '';
                if (engine) fd.append('pdf_parsing_engine', engine);
                const ccp = document.getElementById('multi_pdf_custom_chapter_pattern')?.value || '';
                if (ccp) fd.append('custom_chapter_pattern', ccp);
                fd.append('use_cookies', document.getElementById('multi_pdf_use_cookies')?.checked ? 'true' : 'false');
                const ck = document.getElementById('multi_pdf_cookies')?.value || '';
                if (ck) fd.append('cookies', ck);
                fd.append('perform_chunking', document.getElementById('multi_pdf_perform_chunking')?.checked ? 'true' : 'false');
                const cm = document.getElementById('multi_pdf_chunk_method')?.value || '';
                if (cm) fd.append('chunk_method', cm);
                const cs = document.getElementById('multi_pdf_chunk_size')?.value || '';
                const co = document.getElementById('multi_pdf_chunk_overlap')?.value || '';
                if (cs) fd.append('chunk_size', cs);
                if (co) fd.append('chunk_overlap', co);
                const cl = document.getElementById('multi_pdf_chunk_language')?.value || '';
                if (cl) fd.append('chunk_language', cl);
            } else if (procType === 'ebooks') {
                fd.append('perform_chunking', document.getElementById('multi_ebook_perform_chunking')?.checked ? 'true' : 'false');
                const cm = document.getElementById('multi_ebook_chunk_method')?.value || '';
                if (cm) fd.append('chunk_method', cm);
                const cs = document.getElementById('multi_ebook_chunk_size')?.value || '';
                const co = document.getElementById('multi_ebook_chunk_overlap')?.value || '';
                if (cs) fd.append('chunk_size', cs);
                if (co) fd.append('chunk_overlap', co);
                const ccp = document.getElementById('multi_ebook_custom_chapter_pattern')?.value || '';
                if (ccp) fd.append('custom_chapter_pattern', ccp);
            }

            let endpoint = '';
            if (procType === 'videos') endpoint = '/api/v1/media/process-videos';
            else if (procType === 'audios') endpoint = '/api/v1/media/process-audios';
            else if (procType === 'documents') endpoint = '/api/v1/media/process-documents';
            else if (procType === 'pdfs') endpoint = '/api/v1/media/process-pdfs';
            else if (procType === 'ebooks') endpoint = '/api/v1/media/process-ebooks';
            else endpoint = '/api/v1/media/process-documents';

            res = await apiClient.makeRequest('POST', endpoint, { body: fd });
        }

        if (procType === 'web' && persist && res && res.media_ids && res.media_ids.length > 0) {
            const queue = Utils.getFromStorage('multi-analysis-queue') || [];
            // Fetch basic details for each media id
            for (const id of res.media_ids) {
                try {
                    const detail = await apiClient.get(`/api/v1/media/${id}`);
                    queue.push({ media_id: id, title: detail.title || 'Untitled', source: detail.source || '', metadata: { type: detail.media_type || '', author: detail.author || '' } });
                } catch (e) {
                    queue.push({ media_id: id, title: `Media ${id}`, source: '' });
                }
            }
            multiPersistQueue(queue);
            renderMultiQueue(queue);
            status.textContent = `Ingested and added ${res.media_ids.length} item(s) to queue.`;
        } else if (procType !== 'web' || !persist) {
            // Add ephemeral results to queue
            const results = (res && res.results) ? res.results : [];
            if (!Array.isArray(results) || results.length === 0) {
                status.textContent = 'No results returned.';
                return;
            }
            const queue = Utils.getFromStorage('multi-analysis-queue') || [];
            results.forEach(r => {
                const id = `e_${Date.now()}_${Math.random().toString(36).slice(2,8)}`;
                const title = r.title || r.input_ref || 'Untitled';
                const source = r.processing_source || r.url || r.source || '';
                const content = r.content || '';
                const metadata = r.metadata || {};
                queue.push({ id, ephemeral: true, title, source, content, metadata });
            });
            multiPersistQueue(queue);
            renderMultiQueue(queue);
            status.textContent = `Processed ${results.length} item(s) and added to queue.`;
        } else {
            status.textContent = 'No media IDs returned.';
        }
    } catch (e) {
        status.textContent = 'Ingestion failed: ' + e.message;
    }
}

async function multiAnalyzeItem(mediaId) {
    const settings = multiGetSettings();
    const outEl = document.getElementById(`multi_analysis_${mediaId}`);
    const card = document.getElementById(`multi_item_${mediaId}`);
    if (outEl) outEl.textContent = 'Analyzing...';
    if (card && typeof Loading !== 'undefined') Loading.show(card, 'Analyzing...');
    try {
        // Get content of media
        const detail = await apiClient.get(`/api/v1/media/${mediaId}`);
        const title = detail.title || `Media ${mediaId}`;
        const content = detail.content || '';
        const modelValue = settings.model; // provider/model or empty

        // Build messages
        const messages = [];
        if (settings.systemPrompt) {
            messages.push({ role: 'system', content: settings.systemPrompt });
        }
        const promptText = `${settings.analysisPrompt}\n\nTitle: ${title}\n\nContent:\n${content}`;
        messages.push({ role: 'user', content: promptText });

        // Prepare payload for chat completions
        const payload = {
            model: modelValue ? modelValue.split('/').slice(1).join('/') : undefined,
            messages,
            temperature: isNaN(settings.temperature) ? 0.7 : settings.temperature
        };
        const provider = modelValue ? modelValue.split('/')[0] : '';
        if (provider) payload.api_provider = provider;

        const resp = await apiClient.post('/api/v1/chat/completions', payload);
        let analysis = '';
        if (resp && resp.choices && resp.choices[0] && resp.choices[0].message) {
            analysis = resp.choices[0].message.content || '';
        } else {
            analysis = '(No response)';
        }
        if (outEl) outEl.textContent = analysis;
    } catch (e) {
        if (outEl) outEl.textContent = 'Analysis failed: ' + e.message;
    }
    finally {
        if (card && typeof Loading !== 'undefined') Loading.hide(card);
    }
}

async function multiSaveItemAnalysis(mediaId) {
    const settings = multiGetSettings();
    const outEl = document.getElementById(`multi_analysis_${mediaId}`);
    if (!outEl) return;
    const text = outEl.textContent || '';
    if (!text || text === '(Not analyzed)' || text.startsWith('Analyzing')) {
        Toast && Toast.warning ? Toast.warning('Nothing to save for this item') : console.warn('Nothing to save');
        return;
    }

    try {
        if (settings.storeOption === 'media') {
            await apiClient.put(`/api/v1/media/${mediaId}`, { analysis: text });
            Toast && Toast.success ? Toast.success('Saved to media') : console.log('Saved to media');
        } else if (settings.storeOption === 'version') {
            await apiClient.post(`/api/v1/media/${mediaId}/versions`, { content: null, prompt: multiGetSettings().analysisPrompt || '', analysis_content: text });
            Toast && Toast.success ? Toast.success('Saved as new version') : console.log('Saved as new version');
        } else {
            Toast && Toast.info ? Toast.info('Store option is set to "Do not store"') : console.log('Not stored');
        }
    } catch (e) {
        Toast && Toast.error ? Toast.error('Save failed: ' + e.message) : console.error('Save failed:', e);
    }
}

async function multiAnalyzeAll() {
    const queue = Utils.getFromStorage('multi-analysis-queue') || [];
    const bar = document.getElementById('multi_progress_bar');
    const wrap = document.getElementById('multi_progress');
    const txt = document.getElementById('multi_progress_text');
    const cnt = document.getElementById('multi_progress_count');
    if (wrap) wrap.style.display = 'block';
    const total = queue.length;
    let i = 0;
    const update = () => {
        if (bar) bar.style.width = `${total ? Math.round((i / total) * 100) : 0}%`;
        if (cnt) cnt.textContent = `${i} / ${total}`;
    };
    if (txt) txt.textContent = 'Analyzing...';
    update();
    for (const item of queue) {
        if (item.ephemeral) {
            await multiAnalyzeEphemeral(item.id);
        } else {
            await multiAnalyzeItem(item.media_id);
        }
        i += 1;
        update();
    }
    if (txt) txt.textContent = 'Completed';
}

async function multiAnalyzeEphemeral(id) {
    const settings = multiGetSettings();
    const queue = Utils.getFromStorage('multi-analysis-queue') || [];
    const item = queue.find(q => q.ephemeral && q.id === id);
    const outEl = document.getElementById(`multi_analysis_${id}`);
    const card = document.getElementById(`multi_item_${id}`);
    if (!item || !outEl) return;
    outEl.textContent = 'Analyzing...';
    if (card && typeof Loading !== 'undefined') Loading.show(card, 'Analyzing...');
    try {
        const title = item.title || 'Untitled';
        const content = item.content || '';
        const modelValue = settings.model;
        const messages = [];
        if (settings.systemPrompt) messages.push({ role: 'system', content: settings.systemPrompt });
        const promptText = `${settings.analysisPrompt}\n\nTitle: ${title}\n\nContent:\n${content}`;
        messages.push({ role: 'user', content: promptText });
        const payload = {
            model: modelValue ? modelValue.split('/').slice(1).join('/') : undefined,
            messages,
            temperature: isNaN(settings.temperature) ? 0.7 : settings.temperature
        };
        const provider = modelValue ? modelValue.split('/')[0] : '';
        if (provider) payload.api_provider = provider;
        const resp = await apiClient.post('/api/v1/chat/completions', payload);
        let analysis = '';
        if (resp && resp.choices && resp.choices[0] && resp.choices[0].message) {
            analysis = resp.choices[0].message.content || '';
        } else {
            analysis = '(No response)';
        }
        outEl.textContent = analysis;
    } catch (e) {
        outEl.textContent = 'Analysis failed: ' + e.message;
    }
    finally {
        if (card && typeof Loading !== 'undefined') Loading.hide(card);
    }
}

function multiRemoveEphemeral(id) {
    const queue = Utils.getFromStorage('multi-analysis-queue') || [];
    const filtered = queue.filter(q => !(q.ephemeral && q.id === id));
    multiPersistQueue(filtered);
    renderMultiQueue(filtered);
}

async function multiSaveEphemeralAnalysis(id) {
    const settings = multiGetSettings();
    const outEl = document.getElementById(`multi_analysis_${id}`);
    if (!outEl) return;
    if (settings.storeOption !== 'none') {
        Toast && Toast.info ? Toast.info('Cannot save analysis for ephemeral items. Choose "Do not store" or persist content first.') : console.log('Ephemeral save disabled');
        return;
    }
    Toast && Toast.success ? Toast.success('Analysis kept locally (not stored).') : console.log('Local only');
}

// Helpers for HTML escaping
function escapeHtml(str) {
    return (str || '').replace(/[&<>"']/g, function(m) {
        return ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;','\'':'&#39;'}[m]);
    });
}
function escapeAttr(str) {
    return escapeHtml(str).replace(/\n/g, ' ');
}

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
let chatStreamHandle = null; // active SSE handle for streaming chat
let chatConversationId = null; // current conversation id if any
let chatAutoContinueInProgress = false; // guard for auto-continue

// ------------------------------------------------------------
// Minimal Markdown Renderer (safe)
// ------------------------------------------------------------
function mdEscape(s) {
    const str = String(s || '');
    // If project-provided HTML escaper exists, use it and short-circuit
    if (Utils && typeof Utils.escapeHtml === 'function') {
        return Utils.escapeHtml(str);
    }
    // Fallback: minimal escaping
    return str
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
}

function createCodeBlockElement(codeText, lang) {
    const wrapper = document.createElement('div');
    wrapper.className = 'code-block-wrapper';
    wrapper.style.position = 'relative';

    const pre = document.createElement('pre');
    pre.className = 'code-block';
    pre.style.padding = '8px';
    pre.style.background = 'var(--code-bg, #f5f5f5)';
    pre.style.border = '1px solid #ddd';
    pre.style.borderRadius = '4px';
    pre.style.overflow = 'auto';

    const code = document.createElement('code');
    if (lang) code.setAttribute('data-lang', lang);
    // Use lightweight highlighter for display (keeps original for copy)
    try {
        code.innerHTML = highlightCode(codeText, lang);
    } catch (_) {
        code.textContent = codeText;
    }
    pre.appendChild(code);

    const btn = document.createElement('button');
    btn.className = 'btn btn-sm';
    btn.textContent = 'Copy';
    btn.style.position = 'absolute';
    btn.style.top = '4px';
    btn.style.right = '4px';
    btn.addEventListener('click', async () => {
        const ok = await Utils.copyToClipboard(codeText);
        if (typeof Toast !== 'undefined') {
            ok ? Toast.success('Copied code') : Toast.error('Copy failed');
        }
    });

    wrapper.appendChild(pre);
    wrapper.appendChild(btn);
    return wrapper;
}

function renderMarkdownToElement(text, container) {
    // Clear container
    container.innerHTML = '';
    if (!text) return;

    // Split by fenced code blocks: ```lang\n...```; keep non-greedy across blocks
    const regex = /```([a-zA-Z0-9_-]+)?\n([\s\S]*?)```/g;
    let lastIndex = 0;
    let match;
    while ((match = regex.exec(text)) !== null) {
        const before = text.slice(lastIndex, match.index);
        if (before) {
            appendPlainMarkdown(before, container);
        }
        const lang = (match[1] || '').trim();
        const codeText = match[2] || '';
        container.appendChild(createCodeBlockElement(codeText, lang));
        lastIndex = regex.lastIndex;
    }
    const tail = text.slice(lastIndex);
    if (tail) appendPlainMarkdown(tail, container);
}

function appendPlainMarkdown(text, container) {
    // paragraphs by double newline
    const paras = String(text).split(/\n\n+/);
    paras.forEach((p) => {
        if (!p.trim()) return;
        const div = document.createElement('div');
        // Inline transforms (safe)
        let html = mdEscape(p);
        // inline code `code`
        html = html.replace(/`([^`]+)`/g, '<code>$1</code>');
        // bold **text**
        html = html.replace(/\*\*([^*]+)\*\*/g, '<strong>$1</strong>');
        // italic *text* (simple heuristic; avoids lookbehind)
        html = html.replace(/(^|\s)\*([^*]+)\*(?=\s|$)/g, '$1<em>$2</em>');
        // links [text](url)
        html = html.replace(/\[([^\]]+)\]\((https?:[^)\s]+)\)/g, '<a href="$2" target="_blank" rel="noopener noreferrer">$1<\/a>');
        // line breaks
        html = html.replace(/\n/g, '<br>');
        div.innerHTML = html;
        container.appendChild(div);
    });
}

// Very lightweight highlighter for common languages (json, js/ts, python)
function highlightCode(src, lang) {
    const s = String(src || '');
    const esc = (v) => v
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/\"/g, '&quot;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
    let out = esc(s);
    const langNorm = (lang || '').toLowerCase();

    if (langNorm === 'json') {
        // Try to pretty print JSON
        try { out = esc(JSON.stringify(JSON.parse(s), null, 2)); } catch(_) {}
        // Keys: &quot;key&quot;:
        out = out.replace(/(^|\n)\s*(&quot;[^&]*?&quot;)(\s*:\s*)/g, (m, a, key, sep) => `${a}<span class="tok-key">${key}</span>${sep}`);
        // Strings
        out = out.replace(/&quot;(?:[^&]|&(?!quot;))*&quot;/g, (m) => `<span class="tok-string">${m}</span>`);
        // Numbers (no lookbehind): capture and reinsert prefix
        out = out.replace(/(^|[^\w\-])(-?\d+(?:\.\d+)?(?:[eE][+\-]?\d+)?)(?![\w\-])/g, (m, pre, num) => `${pre}<span class="tok-number">${num}</span>`);
        // Booleans/null
        out = out.replace(/\b(true|false)\b/g, '<span class="tok-boolean">$1</span>');
        out = out.replace(/\bnull\b/g, '<span class="tok-null">null</span>');
        return out;
    }

    // Basic JS/TS highlighting
    if (/(js|javascript|ts|typescript)/.test(langNorm)) {
        const kw = /(\b)(break|case|catch|class|const|continue|debugger|default|delete|do|else|export|extends|finally|for|function|if|import|in|instanceof|let|new|return|super|switch|this|throw|try|typeof|var|void|while|with|yield)(\b)/g;
        out = out
            // comments
            .replace(/(\/\/.*?$)/gm, '<span class="tok-comment">$1</span>')
            .replace(/(\/\*[\s\S]*?\*\/)/g, '<span class="tok-comment">$1</span>')
            // strings
            .replace(/(['"`])([^\\\n]|\\.|\n)*?\1/g, '<span class="tok-string">$&</span>')
            // numbers (no lookbehind)
            .replace(/(^|[^\w\-])(-?\d+(?:\.\d+)?)(?![\w\-])/g, (m, pre, num) => `${pre}<span class="tok-number">${num}</span>`)
            // keywords
            .replace(kw, '$1<span class="tok-kw">$2</span>$3')
            // function names (simple heuristic)
            .replace(/\b([A-Za-z_][\w]*)\s*(?=\()/g, '<span class="tok-func">$1</span>');
        return out;
    }

    // Basic Python highlighting
    if (/(py|python)/.test(langNorm)) {
        const kw = /(\b)(and|as|assert|break|class|continue|def|del|elif|else|except|False|finally|for|from|global|if|import|in|is|lambda|None|nonlocal|not|or|pass|raise|return|True|try|while|with|yield)(\b)/g;
        out = out
            .replace(/(#.*?$)/gm, '<span class="tok-comment">$1</span>')
            .replace(/(['"]).*?\1/g, '<span class="tok-string">$&</span>')
            .replace(/(^|[^\w\-])(-?\d+(?:\.\d+)?)(?![\w\-])/g, (m, pre, num) => `${pre}<span class="tok-number">${num}</span>`)
            .replace(kw, '$1<span class="tok-kw">$2</span>$3');
        return out;
    }

    // Default: no specific highlighting beyond escaping
    return out;
}

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
    const streamToggle = document.getElementById('chat-stream');
    const saveToggle = document.getElementById('chat-save-to-db');
    const convIdInput = document.getElementById('chat-conversation-id');
    const sendBtn = document.getElementById('chat-send-btn');
    const stopBtn = document.getElementById('chat-stop-btn');
    const tempEl = document.getElementById('chat-temp');
    const topPEl = document.getElementById('chat-top-p');
    const maxTokEl = document.getElementById('chat-max-tokens');

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
    const answerContainer = document.createElement('div');
    answerContainer.className = 'assistant-answer';
    answerContainer.textContent = 'Thinking...';
    const toolsContainer = document.createElement('div');
    toolsContainer.className = 'assistant-tools';
    toolsContainer.style.marginTop = '6px';
    assistantDiv.appendChild(assistantLabel);
    assistantDiv.appendChild(document.createTextNode(' '));
    assistantDiv.appendChild(answerContainer);
    assistantDiv.appendChild(toolsContainer);
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
            temperature: tempEl && tempEl.value ? parseFloat(tempEl.value) : 0.7,
            top_p: topPEl && topPEl.value ? parseFloat(topPEl.value) : 1,
            max_tokens: maxTokEl && maxTokEl.value ? parseInt(maxTokEl.value) : 1000
        };

        // Add provider if selected
        if (provider) {
            requestPayload.api_provider = provider;
        }
        // Persist provider/model + sampling choices
        try {
            Utils.saveToStorage('chat-ui-selection', { provider, model });
            Utils.saveToStorage('chat-ui-sampling', {
                temperature: requestPayload.temperature,
                top_p: requestPayload.top_p,
                max_tokens: requestPayload.max_tokens
            });
        } catch (_) {}

        // Include conversation id and save preference
        if (typeof chatConversationId === 'string' && chatConversationId.length > 0) {
            requestPayload.conversation_id = chatConversationId;
        }
        if (saveToggle && saveToggle.checked) {
            requestPayload.save_to_db = true;
        }

        // Streaming path
        if (streamToggle && streamToggle.checked) {
            // Prepare assistant placeholder for deltas
            answerContainer.textContent = '';
            toolsContainer.innerHTML = '';

            if (sendBtn) sendBtn.disabled = true;
            if (stopBtn) stopBtn.style.display = '';

            let assembled = '';
            const toolCallsAcc = [];
            const toolResultsAcc = [];
            const debugChunks = [];
            let renderScheduled = false;
            const scheduleRender = () => {
                if (renderScheduled) return;
                renderScheduled = true;
                requestAnimationFrame(() => {
                    renderScheduled = false;
                    try {
                        renderMarkdownToElement(assembled, answerContainer);
                        renderToolCalls(toolCallsAcc, toolsContainer);
                        renderToolResults(toolResultsAcc, toolsContainer);
                    } catch (_) {}
                });
            };
            chatStreamHandle = apiClient.streamSSE('/api/v1/chat/completions', {
                method: 'POST',
                body: requestPayload,
                onEvent: (evt) => {
                    try {
                        debugChunks.push(evt);
                        const delta = evt?.choices?.[0]?.delta?.content;
                        if (typeof delta === 'string' && delta.length > 0) {
                            assembled += delta;
                            scheduleRender();
                            messagesDiv.scrollTop = messagesDiv.scrollHeight;
                        }
                        // Accumulate streamed tool calls
                        const dTools = evt?.choices?.[0]?.delta?.tool_calls;
                        if (Array.isArray(dTools) && dTools.length) {
                            dTools.forEach((tc) => {
                                const idx = typeof tc.index === 'number' ? tc.index : 0;
                                if (!toolCallsAcc[idx]) toolCallsAcc[idx] = { name: '', args: '' };
                                const fn = tc.function || {};
                                if (fn.name) toolCallsAcc[idx].name = fn.name;
                                if (typeof fn.arguments === 'string') toolCallsAcc[idx].args += fn.arguments;
                            });
                            scheduleRender();
                        }
                        // Accumulate streamed tool results if present
                        const dResults = evt?.tool_results || evt?.tldw_tool_results;
                        if (Array.isArray(dResults) && dResults.length) {
                            dResults.forEach((r) => {
                                const name = r?.name || r?.tool || '';
                                const content = typeof r?.content === 'string' ? r.content : JSON.stringify(r?.content ?? r);
                                toolResultsAcc.push({ name, content });
                            });
                            scheduleRender();
                        }
                        const meta = evt?.tldw_metadata || evt?.metadata;
                        const cid = meta?.conversation_id || evt?.tldw_conversation_id;
                        if (cid && cid !== chatConversationId) {
                            chatConversationId = cid;
                            if (convIdInput) convIdInput.value = cid;
                        }
                    } catch (_) { /* ignore */ }
                },
                timeout: 600000
            });

            try {
                await chatStreamHandle.done;
                chatMessages.push({ role: 'assistant', content: assembled });
            } catch (e) {
                // If aborted, leave partial text with marker
                const suffix = (e && e.name === 'AbortError') ? ' [stopped]' : ` [error: ${e?.message || 'failed'}]`;
                renderMarkdownToElement(assembled + suffix, answerContainer);
            } finally {
                if (stopBtn) stopBtn.style.display = 'none';
                if (sendBtn) sendBtn.disabled = false;
                chatStreamHandle = null;
                // Append debug JSON panel
                appendAssistantDebugPanel(assistantDiv, { chunks: debugChunks });
                // Auto-continue if configured and tools present
                maybeAutoContinueAfterTools(toolCallsAcc.length > 0, toolResultsAcc.length > 0, !!(streamToggle && streamToggle.checked));
            }
            return;
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

            // Rebuild assistantDiv contents with markdown + tools
            assistantDiv.innerHTML = '';
            const label = document.createElement('strong');
            label.textContent = 'Assistant:';
            const ans = document.createElement('div');
            const tools = document.createElement('div');
            tools.className = 'assistant-tools';
            tools.style.marginTop = '6px';
            renderMarkdownToElement(assistantMessage || '', ans);
            assistantDiv.appendChild(label);
            assistantDiv.appendChild(document.createTextNode(' '));
            assistantDiv.appendChild(ans);
            assistantDiv.appendChild(tools);
            // Render tool calls if present in message
            try {
                const tcs = response.choices[0].message.tool_calls;
                if (Array.isArray(tcs) && tcs.length) {
                    const acc = tcs.map(tc => ({ name: tc?.function?.name || '', args: String(tc?.function?.arguments || '') }));
                    renderToolCalls(acc, tools);
                }
            } catch (_) {}
            // Render tool results if present in payload (best-effort)
            try {
                const toolMsgs = response.tool_messages || response.tldw_tool_results || [];
                if (Array.isArray(toolMsgs) && toolMsgs.length) {
                    const acc = toolMsgs.map(tm => ({ name: tm?.name || tm?.tool || '', content: typeof tm?.content === 'string' ? tm.content : JSON.stringify(tm?.content ?? tm) }));
                    renderToolResults(acc, tools);
                } else if (Array.isArray(response.messages)) {
                    const toolOnly = response.messages.filter(m => m?.role === 'tool');
                    if (toolOnly.length) {
                        const acc2 = toolOnly.map(m => ({ name: m?.name || '', content: typeof m?.content === 'string' ? m.content : JSON.stringify(m?.content ?? m) }));
                        renderToolResults(acc2, tools);
                    }
                }
            } catch(_) {}
            // Append raw JSON debug panel
            appendAssistantDebugPanel(assistantDiv, response);

            // Capture conversation id from non-streaming response
            try {
                const cid = response?.tldw_conversation_id || response?.tldw_metadata?.conversation_id;
                if (cid) {
                    chatConversationId = cid;
                    if (convIdInput) convIdInput.value = cid;
                }
            } catch (_) {}
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
    // Clear conversation id (do not change stream/save toggles)
    chatConversationId = null;
    const convIdInput = document.getElementById('chat-conversation-id');
    if (convIdInput) convIdInput.value = '';
}

// Stop streaming if active
function stopChatStream() {
    try {
        if (chatStreamHandle && chatStreamHandle.abort) {
            chatStreamHandle.abort();
        }
    } catch (_) {}
}

// Reset only the conversation id (keep messages)
function resetChatConversation() {
    chatConversationId = null;
    const convIdInput = document.getElementById('chat-conversation-id');
    if (convIdInput) convIdInput.value = '';
    if (typeof Toast !== 'undefined' && Toast.info) {
        Toast.info('Conversation ID cleared');
    }
}

// Copy last assistant message
async function copyLastAssistantMessage() {
    try {
        for (let i = chatMessages.length - 1; i >= 0; i--) {
            if (chatMessages[i].role === 'assistant') {
                await navigator.clipboard.writeText(chatMessages[i].content || '');
                if (typeof Toast !== 'undefined' && Toast.success) Toast.success('Copied last answer');
                return;
            }
        }
        if (typeof Toast !== 'undefined' && Toast.info) Toast.info('No assistant message to copy');
    } catch (e) {
        if (typeof Toast !== 'undefined' && Toast.error) Toast.error('Copy failed');
        else console.error('Copy failed', e);
    }
}

// Retry last user message by re-sending it
function retryLastUserMessage() {
    for (let i = chatMessages.length - 1; i >= 0; i--) {
        if (chatMessages[i].role === 'user') {
            const input = document.getElementById('chat-input');
            if (input) input.value = chatMessages[i].content || '';
            sendChatMessage();
            return;
        }
    }
    if (typeof Toast !== 'undefined' && Toast.info) Toast.info('No user message to retry');
}

// Edit-and-resend: move last user message back to input and remove it from the history/DOM
function editLastUserMessage() {
    // Find last user message index
    let idx = -1;
    for (let i = chatMessages.length - 1; i >= 0; i--) {
        if (chatMessages[i].role === 'user') { idx = i; break; }
    }
    if (idx === -1) {
        if (typeof Toast !== 'undefined' && Toast.info) Toast.info('No user message to edit');
        return;
    }
    const msg = chatMessages[idx].content || '';
    // Remove from history (keep system and earlier messages)
    chatMessages.splice(idx, 1);
    // Remove from DOM: remove last .chat-message.user element
    try {
        const messagesDiv = document.getElementById('chat-messages');
        const userNodes = messagesDiv ? messagesDiv.querySelectorAll('.chat-message.user') : [];
        if (userNodes && userNodes.length) {
            const lastUserNode = userNodes[userNodes.length - 1];
            lastUserNode.parentElement.removeChild(lastUserNode);
        }
    } catch (_) {}
    // Put content into input
    const input = document.getElementById('chat-input');
    if (input) input.value = msg;
    if (typeof Toast !== 'undefined' && Toast.info) Toast.info('Editing last user message');
}

// Render tool calls (function name + JSON args) into a container
function renderToolCalls(toolCalls, container) {
    if (!container) return;
    container.innerHTML = '';
    const calls = (Array.isArray(toolCalls) ? toolCalls : []).filter(tc => (tc && (tc.name || tc.args)));
    if (!calls.length) return;
    const header = document.createElement('div');
    header.className = 'assistant-tools-header';
    header.textContent = 'Tool calls:';
    container.appendChild(header);
    calls.forEach((tc, i) => {
        const block = document.createElement('div');
        block.className = 'tool-call-block';
        block.style.borderLeft = '3px solid #ccc';
        block.style.paddingLeft = '8px';
        block.style.margin = '4px 0';
        const name = document.createElement('div');
        name.innerHTML = `<strong>${mdEscape(tc.name || 'function')}</strong>`;
        block.appendChild(name);
        const codeEl = createCodeBlockElement(String(tc.args || ''), 'json');
        block.appendChild(codeEl);
        container.appendChild(block);
    });
}

// Render tool results block(s)
function renderToolResults(toolResults, container) {
    if (!container) return;
    const results = (Array.isArray(toolResults) ? toolResults : []).filter(tr => (tr && (tr.name || tr.content)));
    if (!results.length) return;
    // Add header once if not present
    const presentHeader = container.querySelector('.assistant-tools-header[data-kind="results"]');
    if (!presentHeader) {
        const header = document.createElement('div');
        header.className = 'assistant-tools-header';
        header.setAttribute('data-kind', 'results');
        header.textContent = 'Tool results:';
        container.appendChild(header);
    }
    results.forEach((r) => {
        const block = document.createElement('div');
        block.className = 'tool-result-block';
        block.style.borderLeft = '3px solid #ccc';
        block.style.paddingLeft = '8px';
        block.style.margin = '4px 0';
        const name = document.createElement('div');
        name.innerHTML = `<strong>${mdEscape(r.name || 'result')}</strong>`;
        block.appendChild(name);
        const content = typeof r.content === 'string' ? r.content : JSON.stringify(r.content || r);
        const codeEl = createCodeBlockElement(content, 'json');
        block.appendChild(codeEl);
        container.appendChild(block);
    });
}

// Add a collapsible raw JSON debug panel under an assistant message
function appendAssistantDebugPanel(assistantDiv, data) {
    try {
        const details = document.createElement('details');
        details.className = 'assistant-debug';
        const summary = document.createElement('summary');
        summary.textContent = 'Debug: raw JSON';
        const pre = document.createElement('pre');
        pre.innerHTML = Utils.syntaxHighlightJSON(data);
        details.appendChild(summary);
        details.appendChild(pre);
        assistantDiv.appendChild(details);
    } catch (_) {}
}

// Auto-continue after tools if server persisted tool results into conversation
function maybeAutoContinueAfterTools(hadToolCalls, hadToolResults, streaming) {
    try {
        const autoEl = document.getElementById('chat-auto-continue');
        const saveEl = document.getElementById('chat-save-to-db');
        if (!autoEl || !autoEl.checked) return;
        if (!saveEl || !saveEl.checked) return; // require persistence
        if (!chatConversationId) return; // need conv id to continue
        if (chatAutoContinueInProgress) return;
        // Only continue if we saw tool results (server executed) or at least tool calls (best-effort)
        if (!hadToolCalls && !hadToolResults) return;
        chatAutoContinueInProgress = true;
        setTimeout(() => {
            continueConversation().finally(() => { chatAutoContinueInProgress = false; });
        }, 250); // small delay to let UI settle
    } catch (_) {}
}

// Continue conversation without adding a new user message
async function continueConversation() {
    const messagesDiv = document.getElementById('chat-messages');
    const model = document.getElementById('chat-model').value;
    const providerSelect = document.getElementById('chat-provider');
    const provider = providerSelect ? providerSelect.value : '';
    const streamToggle = document.getElementById('chat-stream');
    const saveToggle = document.getElementById('chat-save-to-db');
    const convIdInput = document.getElementById('chat-conversation-id');
    const sendBtn = document.getElementById('chat-send-btn');
    const stopBtn = document.getElementById('chat-stop-btn');
    const tempEl = document.getElementById('chat-temp');
    const topPEl = document.getElementById('chat-top-p');
    const maxTokEl = document.getElementById('chat-max-tokens');

    // Create assistant placeholder
    const assistantDiv = document.createElement('div');
    assistantDiv.className = 'chat-message assistant';
    const assistantLabel = document.createElement('strong');
    assistantLabel.textContent = 'Assistant:';
    const answerContainer = document.createElement('div');
    answerContainer.className = 'assistant-answer';
    answerContainer.textContent = 'Continuing...';
    const toolsContainer = document.createElement('div');
    toolsContainer.className = 'assistant-tools';
    toolsContainer.style.marginTop = '6px';
    assistantDiv.appendChild(assistantLabel);
    assistantDiv.appendChild(document.createTextNode(' '));
    assistantDiv.appendChild(answerContainer);
    assistantDiv.appendChild(toolsContainer);
    messagesDiv.appendChild(assistantDiv);
    requestAnimationFrame(() => { messagesDiv.scrollTop = messagesDiv.scrollHeight; });

    const requestPayload = {
        model: model,
        messages: chatMessages,
        conversation_id: chatConversationId,
        temperature: tempEl && tempEl.value ? parseFloat(tempEl.value) : 0.7,
        top_p: topPEl && topPEl.value ? parseFloat(topPEl.value) : 1,
        max_tokens: maxTokEl && maxTokEl.value ? parseInt(maxTokEl.value) : 1000
    };
    if (provider) requestPayload.api_provider = provider;
    if (saveToggle && saveToggle.checked) requestPayload.save_to_db = true;

    // Streaming path
    if (streamToggle && streamToggle.checked) {
        if (sendBtn) sendBtn.disabled = true;
        if (stopBtn) stopBtn.style.display = '';
        let assembled = '';
        const toolCallsAcc = [];
        const toolResultsAcc = [];
        const debugChunks = [];
        let renderScheduled = false;
        const scheduleRender = () => {
            if (renderScheduled) return;
            renderScheduled = true;
            requestAnimationFrame(() => {
                renderScheduled = false;
                try {
                    renderMarkdownToElement(assembled, answerContainer);
                    renderToolCalls(toolCallsAcc, toolsContainer);
                    renderToolResults(toolResultsAcc, toolsContainer);
                } catch (_) {}
            });
        };
        chatStreamHandle = apiClient.streamSSE('/api/v1/chat/completions', {
            method: 'POST',
            body: requestPayload,
            onEvent: (evt) => {
                try {
                    debugChunks.push(evt);
                    const delta = evt?.choices?.[0]?.delta?.content;
                    if (typeof delta === 'string' && delta.length > 0) {
                        assembled += delta;
                        scheduleRender();
                        messagesDiv.scrollTop = messagesDiv.scrollHeight;
                    }
                    const dTools = evt?.choices?.[0]?.delta?.tool_calls;
                    if (Array.isArray(dTools) && dTools.length) {
                        dTools.forEach((tc) => {
                            const idx = typeof tc.index === 'number' ? tc.index : 0;
                            if (!toolCallsAcc[idx]) toolCallsAcc[idx] = { name: '', args: '' };
                            const fn = tc.function || {};
                            if (fn.name) toolCallsAcc[idx].name = fn.name;
                            if (typeof fn.arguments === 'string') toolCallsAcc[idx].args += fn.arguments;
                        });
                        scheduleRender();
                    }
                    const dResults = evt?.tool_results || evt?.tldw_tool_results;
                    if (Array.isArray(dResults) && dResults.length) {
                        dResults.forEach((r) => {
                            const name = r?.name || r?.tool || '';
                            const content = typeof r?.content === 'string' ? r.content : JSON.stringify(r?.content ?? r);
                            toolResultsAcc.push({ name, content });
                        });
                        scheduleRender();
                    }
                } catch(_) {}
            },
            timeout: 600000
        });
        try {
            await chatStreamHandle.done;
            chatMessages.push({ role: 'assistant', content: assembled });
        } catch (e) {
            const suffix = (e && e.name === 'AbortError') ? ' [stopped]' : ` [error: ${e?.message || 'failed'}]`;
            renderMarkdownToElement(assembled + suffix, answerContainer);
        } finally {
            if (stopBtn) stopBtn.style.display = 'none';
            if (sendBtn) sendBtn.disabled = false;
            chatStreamHandle = null;
            appendAssistantDebugPanel(assistantDiv, { chunks: debugChunks });
        }
        return;
    }

    // Non-stream
    try {
        const response = await apiClient.post('/api/v1/chat/completions', requestPayload);
        const assistantMessage = response?.choices?.[0]?.message?.content || '';
        chatMessages.push({ role: 'assistant', content: assistantMessage });
        assistantDiv.innerHTML = '';
        const label = document.createElement('strong');
        label.textContent = 'Assistant:';
        const ans = document.createElement('div');
        const tools = document.createElement('div');
        tools.className = 'assistant-tools';
        tools.style.marginTop = '6px';
        renderMarkdownToElement(assistantMessage, ans);
        assistantDiv.appendChild(label);
        assistantDiv.appendChild(document.createTextNode(' '));
        assistantDiv.appendChild(ans);
        assistantDiv.appendChild(tools);
        // tool calls/results
        try {
            const tcs = response.choices?.[0]?.message?.tool_calls;
            if (Array.isArray(tcs) && tcs.length) {
                const acc = tcs.map(tc => ({ name: tc?.function?.name || '', args: String(tc?.function?.arguments || '') }));
                renderToolCalls(acc, tools);
            }
            const toolMsgs = response.tool_messages || response.tldw_tool_results || [];
            if (Array.isArray(toolMsgs) && toolMsgs.length) {
                const rs = toolMsgs.map(tm => ({ name: tm?.name || tm?.tool || '', content: typeof tm?.content === 'string' ? tm.content : JSON.stringify(tm?.content ?? tm) }));
                renderToolResults(rs, tools);
            }
        } catch(_) {}
        appendAssistantDebugPanel(assistantDiv, response);
    } catch (error) {
        assistantDiv.innerHTML = '';
        const errorLabel = document.createElement('strong');
        errorLabel.textContent = 'Assistant:';
        const errorMsg = document.createElement('em');
        errorMsg.textContent = `Error: ${error.message}`;
        assistantDiv.appendChild(errorLabel);
        assistantDiv.appendChild(document.createTextNode(' '));
        assistantDiv.appendChild(errorMsg);
    }
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
            title: document.getElementById('conversationsCreate_title').value
        };

        const characterId = document.getElementById('conversationsCreate_character_id').value;
        if (!characterId) throw new Error('Character ID is required');
        body.character_id = parseInt(characterId);

        if (metadata && metadata.trim() !== '{}') {
            body.metadata = JSON.parse(metadata);
        }

        const response = await apiClient.makeRequest('POST', '/api/v1/chats', { body });
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
        const url = queryString ? `/api/v1/chats?${queryString}` : '/api/v1/chats';

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

        const response = await apiClient.makeRequest('GET', `/api/v1/chats/${conversationId}`);
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

        // Always use messages endpoint (no streaming)
        const payload = { role: 'user', content: message };
        const response = await apiClient.makeRequest('POST', `/api/v1/chats/${conversationId}/messages`, { body: payload });
        responseEl.textContent = JSON.stringify(response, null, 2);

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
        const filtered = {};
        if (body.title) filtered.title = body.title;
        if (typeof body.rating !== 'undefined') filtered.rating = body.rating;
        const response = await apiClient.makeRequest('PUT', `/api/v1/chats/${conversationId}`, { body: filtered });
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
        const response = await apiClient.makeRequest('DELETE', `/api/v1/chats/${conversationId}`);
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
        const response = await apiClient.makeRequest('GET', `/api/v1/chats/${conversationId}/export?format=${format}`);

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
    // Restore saved provider/model selection
    try {
        const saved = Utils.getFromStorage('chat-ui-selection');
        if (saved) {
            const p = document.getElementById('chat-provider');
            const m = document.getElementById('chat-model');
            if (p && typeof saved.provider === 'string') p.value = saved.provider;
            if (m && typeof saved.model === 'string') m.value = saved.model;
        }
    } catch (_) {}
    // Persist changes to selection
    const pSel = document.getElementById('chat-provider');
    const mSel = document.getElementById('chat-model');
    const persist = () => {
        try { Utils.saveToStorage('chat-ui-selection', { provider: (pSel && pSel.value) || '', model: (mSel && mSel.value) || '' }); } catch (_) {}
    };
    if (pSel) pSel.addEventListener('change', persist);
    if (mSel) mSel.addEventListener('change', persist);

    // Apply default Save to DB preference from server config if available
    try {
        const saveEl = document.getElementById('chat-save-to-db');
        if (saveEl && window.apiClient && window.apiClient.loadedConfig) {
            const def = window.apiClient.loadedConfig?.chat?.default_save_to_db;
            if (typeof def === 'boolean') saveEl.checked = def;
        }
    } catch (_) {}

    // Restore sampling controls
    try {
        const savedS = Utils.getFromStorage('chat-ui-sampling');
        if (savedS) {
            const t = document.getElementById('chat-temp');
            const p = document.getElementById('chat-top-p');
            const m = document.getElementById('chat-max-tokens');
            if (t && typeof savedS.temperature !== 'undefined') t.value = String(savedS.temperature);
            if (p && typeof savedS.top_p !== 'undefined') p.value = String(savedS.top_p);
            if (m && typeof savedS.max_tokens !== 'undefined') m.value = String(savedS.max_tokens);
        }
        // Persist on change
        const tEl = document.getElementById('chat-temp');
        const pEl = document.getElementById('chat-top-p');
        const mEl = document.getElementById('chat-max-tokens');
        const persistSampling = () => {
            try { Utils.saveToStorage('chat-ui-sampling', {
                temperature: tEl && tEl.value ? parseFloat(tEl.value) : 0.7,
                top_p: pEl && pEl.value ? parseFloat(pEl.value) : 1,
                max_tokens: mEl && mEl.value ? parseInt(mEl.value) : 1000
            }); } catch (_) {}
        };
        if (tEl) tEl.addEventListener('change', persistSampling);
        if (pEl) pEl.addEventListener('change', persistSampling);
        if (mEl) mEl.addEventListener('change', persistSampling);
    } catch (_) {}
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
        const curlCommand = (typeof apiClient.generateCurlV2 === 'function'
            ? apiClient.generateCurlV2('POST', '/api/v1/prompts', { body: payload })
            : apiClient.generateCurl('POST', '/api/v1/prompts', { body: payload }));
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

// ---------------------------------------------------------------------------
// Embeddings Ledger Admin
// ---------------------------------------------------------------------------

async function embeddingsQueryLedgerStatus() {
    const idk = (document.getElementById('embeddingsLedger_idemp')?.value || '').trim();
    const ddk = (document.getElementById('embeddingsLedger_dedupe')?.value || '').trim();
    const out = document.getElementById('embeddingsLedgerStatus_response');
    if (!out) return;
    if (!idk && !ddk) {
        if (typeof Toast !== 'undefined' && Toast.warn) Toast.warn('Provide idempotency_key and/or dedupe_key');
        return;
    }
    try {
        const q = new URLSearchParams();
        if (idk) q.set('idempotency_key', idk);
        if (ddk) q.set('dedupe_key', ddk);
        const res = await apiClient.get(`/api/v1/embeddings/ledger/status?${q.toString()}`);
        out.textContent = Utils.syntaxHighlight(res);
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        if (typeof Toast !== 'undefined' && Toast.error) Toast.error('Failed to fetch ledger status');
    }
}

// Make sure functions are globally available
console.log('Tab functions loaded successfully');

// ---------------------------------------------------------------------------
// Re-embed Scheduler (Admin)
// ---------------------------------------------------------------------------

async function embeddingsScheduleReembed() {
    const midEl = document.getElementById('embeddingsReembed_media_id');
    const priEl = document.getElementById('embeddingsReembed_priority');
    const out = document.getElementById('embeddingsReembed_response');
    if (!midEl || !out) return;
    const media_id = parseInt(midEl.value || '0', 10);
    const priority = parseInt(priEl?.value || '50', 10);
    if (!media_id || media_id <= 0) {
        if (typeof Toast !== 'undefined' && Toast.warn) Toast.warn('Enter a valid media_id');
        return;
    }
    out.textContent = 'Scheduling...';
    try {
        const res = await apiClient.post('/api/v1/embeddings/reembed/schedule', { media_id, priority });
        out.textContent = Utils.syntaxHighlight(res);
        if (typeof Toast !== 'undefined' && Toast.success) Toast.success('Re-embed job scheduled');
    } catch (e) {
        out.textContent = JSON.stringify(e.response || e, null, 2);
        if (typeof Toast !== 'undefined' && Toast.error) Toast.error('Failed to schedule re-embed');
    }
}

// Quick helper to schedule re-embed for a specific media id from other tabs
async function scheduleReembedForMedia(media_id, priority = 50) {
    try {
        // Admin-only guard
        const ok = await isAdminCached();
        if (!ok) {
            if (typeof Toast !== 'undefined' && Toast.error) Toast.error('Admin required to schedule re-embed');
            return;
        }
        const res = await apiClient.post('/api/v1/embeddings/reembed/schedule', { media_id, priority });
        if (typeof Toast !== 'undefined' && Toast.success) Toast.success(`Re-embed scheduled for media ${media_id}`);
        return res;
    } catch (e) {
        if (typeof Toast !== 'undefined' && Toast.error) Toast.error(`Failed to schedule re-embed: ${(e && e.message) || 'error'}`);
        throw e;
    }
}

// ------------------------------
// Admin-only detection and reveal
// ------------------------------
let __isAdminFlag = null;
async function isAdminCached() {
    if (__isAdminFlag !== null) return __isAdminFlag;
    try {
        // Try an admin-only endpoint
        await apiClient.makeRequest('GET', '/api/v1/embeddings/stage/status');
        __isAdminFlag = true;
    } catch (e) {
        __isAdminFlag = false;
    }
    try { window.isAdminFlag = __isAdminFlag; } catch (_) {}
    return __isAdminFlag;
}

function revealAdminOnlyElements() {
    isAdminCached().then((isAdmin) => {
        if (!isAdmin) return;
        try {
            document.querySelectorAll('.admin-only').forEach(el => { el.style.display = ''; });
        } catch (e) { /* ignore */ }
    }).catch(() => {});
}

document.addEventListener('DOMContentLoaded', function() {
    // Try to reveal admin-only controls after initial load
    setTimeout(revealAdminOnlyElements, 600);
    // Restore recording caps from localStorage and bind change events
    try {
        const ttsMax = parseInt(localStorage.getItem('audio_tts_rec_max_seconds') || '', 10);
        if (!isNaN(ttsMax)) {
            window._audioRecMaxSec = Math.max(3, Math.min(60, ttsMax));
            const el = document.getElementById('audioTTS_rec_max');
            if (el) el.value = String(window._audioRecMaxSec);
        }
        const ttsMaxEl = document.getElementById('audioTTS_rec_max');
        if (ttsMaxEl) {
            ttsMaxEl.addEventListener('change', () => {
                try {
                    const v = Math.max(3, Math.min(60, parseInt(ttsMaxEl.value || '15', 10)));
                    window._audioRecMaxSec = v;
                    localStorage.setItem('audio_tts_rec_max_seconds', String(v));
                } catch(_) {}
            });
        }
    } catch (_) {}
    try {
        const ftMax = parseInt(localStorage.getItem('file_trans_rec_max_seconds') || '', 10);
        if (!isNaN(ftMax)) {
            window._fileTransRecMaxSec = Math.max(3, Math.min(60, ftMax));
            const el2 = document.getElementById('fileTrans_rec_max');
            if (el2) el2.value = String(window._fileTransRecMaxSec);
        }
        const ftMaxEl = document.getElementById('fileTrans_rec_max');
        if (ftMaxEl) {
            ftMaxEl.addEventListener('change', () => {
                try {
                    const v = Math.max(3, Math.min(60, parseInt(ftMaxEl.value || '15', 10)));
                    window._fileTransRecMaxSec = v;
                    localStorage.setItem('file_trans_rec_max_seconds', String(v));
                } catch(_) {}
            });
        }
    } catch (_) {}
    // Restore rec-settings collapsed state
    try {
        const openTTS = localStorage.getItem('rec_settings_open_audioTTS');
        const bodyTTS = document.getElementById('rec-settings-audioTTS');
        const caretTTS = document.getElementById('rec-settings-caret-audioTTS');
        if (bodyTTS) {
            const open = openTTS === '1';
            bodyTTS.style.display = open ? 'block' : 'none';
            if (caretTTS) caretTTS.textContent = open ? '▾' : '▸';
        }
    } catch(_) {}
    try {
        const openFT = localStorage.getItem('rec_settings_open_fileTrans');
        const bodyFT = document.getElementById('rec-settings-fileTrans');
        const caretFT = document.getElementById('rec-settings-caret-fileTrans');
        if (bodyFT) {
            const open = openFT === '1';
            bodyFT.style.display = open ? 'block' : 'none';
            if (caretFT) caretFT.textContent = open ? '▾' : '▸';
        }
    } catch(_) {}
});

// Toggle helpers for collapsible Recording Settings
function toggleAudioTTSRecSettings() {
    try {
        const body = document.getElementById('rec-settings-audioTTS');
        const caret = document.getElementById('rec-settings-caret-audioTTS');
        if (!body) return;
        const show = body.style.display === 'none' || body.style.display === '';
        body.style.display = show ? 'block' : 'none';
        if (caret) caret.textContent = show ? '▾' : '▸';
        try { localStorage.setItem('rec_settings_open_audioTTS', show ? '1' : '0'); } catch(_) {}
    } catch (_) {}
}

function toggleFileTransRecSettings() {
    try {
        const body = document.getElementById('rec-settings-fileTrans');
        const caret = document.getElementById('rec-settings-caret-fileTrans');
        if (!body) return;
        const show = body.style.display === 'none' || body.style.display === '';
        body.style.display = show ? 'block' : 'none';
        if (caret) caret.textContent = show ? '▾' : '▸';
        try { localStorage.setItem('rec_settings_open_fileTrans', show ? '1' : '0'); } catch(_) {}
    } catch (_) {}
}

// Reset helpers
function resetAudioTTSRecMax() {
    try {
        window._audioRecMaxSec = 15;
        localStorage.setItem('audio_tts_rec_max_seconds', '15');
        const el = document.getElementById('audioTTS_rec_max');
        if (el) el.value = '15';
    } catch(_) {}
}
function resetFileTransRecMax() {
    try {
        window._fileTransRecMaxSec = 15;
        localStorage.setItem('file_trans_rec_max_seconds', '15');
        const el = document.getElementById('fileTrans_rec_max');
        if (el) el.value = '15';
    } catch(_) {}
}

// -----------------------------------------------------------------------------
// Watchlists Tab Helpers
// -----------------------------------------------------------------------------

let _watchlistsSettingsLoaded = false;
let _watchlistsSourcesInitialized = false;
let _watchlistsScrapeAdvancedVisible = false;

function watchlistsSetResponse(elementId, data) {
    const el = document.getElementById(elementId);
    if (!el) return;
    if (data === null || data === undefined) {
        el.textContent = '---';
        return;
    }
    if (typeof data === 'string') {
        el.textContent = data;
        return;
    }
    el.textContent = Utils.formatJSON(data, 2);
}

function watchlistsParseJSON(inputId) {
    const field = document.getElementById(inputId);
    if (!field) return undefined;
    const raw = field.value.trim();
    if (!raw) return undefined;
    try {
        return JSON.parse(raw);
    } catch (err) {
        throw new Error(`Invalid JSON in ${inputId}: ${err.message}`);
    }
}

function watchlistsParseRecipients(value) {
    if (!value) return undefined;
    const parts = value.split(',').map((p) => p.trim()).filter(Boolean);
    return parts.length ? parts : undefined;
}

function watchlistsParseTags(value) {
    if (!value) return undefined;
    const parts = value.split(',').map((p) => p.trim()).filter(Boolean);
    return parts.length ? parts : undefined;
}

function watchlistsNormalizeSelectorsInput(value) {
    if (!value) return undefined;
    const lines = value
        .split('\n')
        .map((line) => line.trim())
        .filter((line) => line.length > 0);
    if (!lines.length) return undefined;
    return lines.length === 1 ? lines[0] : lines;
}

function watchlistsParseNumber(value, { allowZero = false } = {}) {
    if (value === undefined || value === null) return undefined;
    const trimmed = String(value).trim();
    if (!trimmed) return undefined;
    const num = Number(trimmed);
    if (Number.isNaN(num)) return undefined;
    if (!allowZero && num <= 0) return undefined;
    if (allowZero && num < 0) return undefined;
    return num;
}

async function watchlistsFetchSettings() {
    try {
        const res = await apiClient.get('/api/v1/watchlists/settings');
        if (res) {
            const defaultTTL = document.getElementById('watchlistsOutputs_defaultTTL');
            const tempTTL = document.getElementById('watchlistsOutputs_tempTTL');
            if (defaultTTL) defaultTTL.textContent = res.default_output_ttl_seconds ?? '0';
            if (tempTTL) tempTTL.textContent = res.temporary_output_ttl_seconds ?? '0';
        }
    } catch (err) {
        console.error('Failed to load watchlist settings', err);
    }
}

async function watchlistsRefreshTemplatePicker() {
    const picker = document.getElementById('watchlistsTemplatePicker');
    if (!picker) return;
    try {
        const res = await apiClient.get('/api/v1/watchlists/templates');
        while (picker.options.length > 1) {
            picker.remove(1);
        }
        if (res && Array.isArray(res.items)) {
            res.items.forEach((tpl) => {
                const opt = document.createElement('option');
                opt.value = tpl.name;
                opt.textContent = `${tpl.name} (${tpl.format})`;
                picker.appendChild(opt);
            });
        }
    } catch (err) {
        console.error('Failed to load templates', err);
    }
}

function watchlistsApplyTemplateSelection() {
    const picker = document.getElementById('watchlistsTemplatePicker');
    const input = document.getElementById('watchlistsOutput_templateName');
    if (picker && input && picker.value) {
        input.value = picker.value;
    }
}

async function initializeWatchlistsTab(contentId) {
    if (!_watchlistsSettingsLoaded) {
        await watchlistsFetchSettings();
        await watchlistsRefreshTemplatePicker();
        _watchlistsSettingsLoaded = true;
        if (!_watchlistsSourcesInitialized) {
            watchlistsResetSourceForm();
            await watchlistsListSources();
            _watchlistsSourcesInitialized = true;
        }
    }
    if (contentId === 'tabWatchlistsTemplates') {
        await watchlistsListTemplates(false);
    }
}

async function watchlistsListItems() {
    try {
        const params = {};
        const runId = document.getElementById('watchlistsItems_runId')?.value;
        const jobId = document.getElementById('watchlistsItems_jobId')?.value;
        const sourceId = document.getElementById('watchlistsItems_sourceId')?.value;
        const status = document.getElementById('watchlistsItems_status')?.value;
        const reviewed = document.getElementById('watchlistsItems_reviewed')?.value;
        const query = document.getElementById('watchlistsItems_query')?.value;
        const since = document.getElementById('watchlistsItems_since')?.value;
        const until = document.getElementById('watchlistsItems_until')?.value;
        const page = document.getElementById('watchlistsItems_page')?.value || '1';
        const size = document.getElementById('watchlistsItems_size')?.value || '50';

        if (runId) params.run_id = Number(runId);
        if (jobId) params.job_id = Number(jobId);
        if (sourceId) params.source_id = Number(sourceId);
        if (status) params.status = status;
        if (reviewed === 'true') params.reviewed = true;
        if (reviewed === 'false') params.reviewed = false;
        if (query) params.q = query;
        if (since) params.since = since;
        if (until) params.until = until;
        params.page = Number(page);
        params.size = Number(size);

        const res = await apiClient.get('/api/v1/watchlists/items', params);
        watchlistsSetResponse('watchlistsItems_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsItems_response', `Error: ${err.message}`);
    }
}

async function watchlistsUpdateItem() {
    try {
        const itemId = document.getElementById('watchlistsUpdate_itemId')?.value;
        if (!itemId) {
            throw new Error('Item ID is required');
        }
        const payload = {};
        const status = document.getElementById('watchlistsUpdate_status')?.value;
        const reviewed = document.getElementById('watchlistsUpdate_reviewed')?.value;
        if (status) payload.status = status;
        if (reviewed === 'true') payload.reviewed = true;
        if (reviewed === 'false') payload.reviewed = false;
        if (!Object.keys(payload).length) {
            throw new Error('Provide status or reviewed flag');
        }
        const res = await apiClient.patch(`/api/v1/watchlists/items/${Number(itemId)}`, payload);
        watchlistsSetResponse('watchlistsUpdate_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsUpdate_response', `Error: ${err.message}`);
    }
}

async function watchlistsListOutputs() {
    try {
        const params = {};
        const runId = document.getElementById('watchlistsOutputs_runId')?.value;
        const jobId = document.getElementById('watchlistsOutputs_jobId')?.value;
        const page = document.getElementById('watchlistsOutputs_page')?.value || '1';
        const size = document.getElementById('watchlistsOutputs_size')?.value || '50';
        if (runId) params.run_id = Number(runId);
        if (jobId) params.job_id = Number(jobId);
        params.page = Number(page);
        params.size = Number(size);
        const res = await apiClient.get('/api/v1/watchlists/outputs', params);
        watchlistsSetResponse('watchlistsOutputs_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsOutputs_response', `Error: ${err.message}`);
    }
}

async function watchlistsCreateOutput() {
    try {
        const runIdRaw = document.getElementById('watchlistsCreate_runId')?.value;
        if (!runIdRaw) {
            throw new Error('Run ID is required');
        }
        const payload = {
            run_id: Number(runIdRaw),
        };
        const itemIdsRaw = document.getElementById('watchlistsCreate_itemIds')?.value || '';
        if (itemIdsRaw.trim()) {
            const ids = itemIdsRaw.split(',').map((val) => Number(val.trim())).filter((val) => !Number.isNaN(val));
            if (ids.length) payload.item_ids = ids;
        }
        const title = document.getElementById('watchlistsCreate_title')?.value;
        if (title) payload.title = title;
        const templateName = document.getElementById('watchlistsOutput_templateName')?.value;
        if (templateName) payload.template_name = templateName;
        const fmt = document.getElementById('watchlistsCreate_format')?.value;
        if (fmt) payload.format = fmt;
        if (document.getElementById('watchlistsCreate_temporary')?.checked) payload.temporary = true;
        const retention = document.getElementById('watchlistsCreate_retention')?.value;
        if (retention) payload.retention_seconds = Number(retention);
        const metadata = watchlistsParseJSON('watchlistsCreate_metadata');
        if (metadata) payload.metadata = metadata;

        const deliveries = {};
        if (document.getElementById('watchlistsEmail_enabled')?.checked) {
            deliveries.email = {
                enabled: true,
                attach_file: !!document.getElementById('watchlistsEmail_attach')?.checked,
                body_format: document.getElementById('watchlistsEmail_bodyFormat')?.value || 'auto',
            };
            const recipients = watchlistsParseRecipients(document.getElementById('watchlistsEmail_recipients')?.value || '');
            if (recipients) deliveries.email.recipients = recipients;
            const subject = document.getElementById('watchlistsEmail_subject')?.value;
            if (subject) deliveries.email.subject = subject;
        }
        if (document.getElementById('watchlistsChat_enabled')?.checked) {
            deliveries.chatbook = { enabled: true };
            const chatTitle = document.getElementById('watchlistsChat_title')?.value;
            if (chatTitle) deliveries.chatbook.title = chatTitle;
            const description = document.getElementById('watchlistsChat_description')?.value;
            if (description) deliveries.chatbook.description = description;
            const conv = document.getElementById('watchlistsChat_conversation')?.value;
            if (conv) deliveries.chatbook.conversation_id = Number(conv);
            const chatMeta = watchlistsParseJSON('watchlistsChat_metadata');
            if (chatMeta) deliveries.chatbook.metadata = chatMeta;
        }
        if (Object.keys(deliveries).length) {
            payload.deliveries = deliveries;
        }

        const res = await apiClient.post('/api/v1/watchlists/outputs', payload);
        watchlistsSetResponse('watchlistsCreate_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsCreate_response', `Error: ${err.message}`);
    }
}

async function watchlistsLoadJobPrefs() {
    try {
        const jobIdRaw = document.getElementById('watchlistsPrefs_jobId')?.value;
        if (!jobIdRaw) {
            throw new Error('Job ID is required');
        }
        const res = await apiClient.get(`/api/v1/watchlists/jobs/${Number(jobIdRaw)}`);
        if (res && res.output_prefs) {
            const prefs = res.output_prefs;
            document.getElementById('watchlistsPrefs_defaultTTL').value = prefs.retention?.default_seconds ?? '';
            document.getElementById('watchlistsPrefs_tempTTL').value = prefs.retention?.temporary_seconds ?? '';
            document.getElementById('watchlistsPrefs_template').value = prefs.template?.default_name ?? '';
            document.getElementById('watchlistsPrefs_emailRecipients').value = (prefs.deliveries?.email?.recipients || []).join(', ');
            document.getElementById('watchlistsPrefs_emailSubject').value = prefs.deliveries?.email?.subject ?? '';
            document.getElementById('watchlistsPrefs_chatEnabled').checked = !!(prefs.deliveries?.chatbook?.enabled);
        }
        watchlistsSetResponse('watchlistsPrefs_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsPrefs_response', `Error: ${err.message}`);
    }
}

async function watchlistsSaveOutputPrefs() {
    try {
        const jobIdRaw = document.getElementById('watchlistsPrefs_jobId')?.value;
        if (!jobIdRaw) {
            throw new Error('Job ID is required');
        }
        const payload = { output_prefs: {} };
        const retention = {};
        const defaultTTL = document.getElementById('watchlistsPrefs_defaultTTL')?.value;
        const tempTTL = document.getElementById('watchlistsPrefs_tempTTL')?.value;
        if (defaultTTL) retention.default_seconds = Number(defaultTTL);
        if (tempTTL) retention.temporary_seconds = Number(tempTTL);
        if (Object.keys(retention).length) payload.output_prefs.retention = retention;

        const template = document.getElementById('watchlistsPrefs_template')?.value;
        if (template) {
            payload.output_prefs.template = { default_name: template };
        }

        const deliveries = {};
        const recipientsDef = watchlistsParseRecipients(document.getElementById('watchlistsPrefs_emailRecipients')?.value || '');
        const subjectDef = document.getElementById('watchlistsPrefs_emailSubject')?.value;
        if ((recipientsDef && recipientsDef.length) || subjectDef) {
            deliveries.email = {};
            if (recipientsDef && recipientsDef.length) deliveries.email.recipients = recipientsDef;
            if (subjectDef) deliveries.email.subject = subjectDef;
        }
        if (document.getElementById('watchlistsPrefs_chatEnabled')?.checked) {
            deliveries.chatbook = { enabled: true };
        }
        if (Object.keys(deliveries).length) {
            payload.output_prefs.deliveries = deliveries;
        }

        const res = await apiClient.patch(`/api/v1/watchlists/jobs/${Number(jobIdRaw)}`, payload);
        watchlistsSetResponse('watchlistsPrefs_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsPrefs_response', `Error: ${err.message}`);
    }
}

async function watchlistsListTemplates(silent = true) {
    try {
        const res = await apiClient.get('/api/v1/watchlists/templates');
        if (!silent) {
            watchlistsSetResponse('watchlistsTemplates_listResponse', res);
        }
        return res;
    } catch (err) {
        if (!silent) watchlistsSetResponse('watchlistsTemplates_listResponse', `Error: ${err.message}`);
        throw err;
    }
}

async function watchlistsGetTemplate() {
    try {
        const name = document.getElementById('watchlistsTemplate_name')?.value;
        if (!name) throw new Error('Template name required');
        const res = await apiClient.get(`/api/v1/watchlists/templates/${encodeURIComponent(name)}`);
        watchlistsSetResponse('watchlistsTemplate_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsTemplate_response', `Error: ${err.message}`);
    }
}

async function watchlistsDeleteTemplate() {
    try {
        const name = document.getElementById('watchlistsTemplate_name')?.value;
        if (!name) throw new Error('Template name required');
        await apiClient.delete(`/api/v1/watchlists/templates/${encodeURIComponent(name)}`);
        watchlistsSetResponse('watchlistsTemplate_response', 'Deleted');
        await watchlistsRefreshTemplatePicker();
        await watchlistsListTemplates();
    } catch (err) {
        watchlistsSetResponse('watchlistsTemplate_response', `Error: ${err.message}`);
    }
}

async function watchlistsCreateTemplate() {
    try {
        const name = document.getElementById('watchlistsTemplateCreate_name')?.value;
        if (!name) throw new Error('Name required');
        const fmt = document.getElementById('watchlistsTemplateCreate_format')?.value || 'md';
        const description = document.getElementById('watchlistsTemplateCreate_description')?.value;
        const overwrite = document.getElementById('watchlistsTemplateCreate_overwrite')?.checked;
        const content = document.getElementById('watchlistsTemplateCreate_content')?.value;
        if (!content) throw new Error('Template content required');
        const payload = {
            name,
            format: fmt,
            content,
            overwrite: !!overwrite,
        };
        if (description) payload.description = description;
        const res = await apiClient.post('/api/v1/watchlists/templates', payload);
        watchlistsSetResponse('watchlistsTemplateCreate_response', res);
        await watchlistsRefreshTemplatePicker();
        await watchlistsListTemplates();
    } catch (err) {
        watchlistsSetResponse('watchlistsTemplateCreate_response', `Error: ${err.message}`);
    }
}

function watchlistsSourceTypeChanged() {
    const typeEl = document.getElementById('watchlistsSource_type');
    const siteFields = document.getElementById('watchlistsSource_siteFields');
    const rssFields = document.getElementById('watchlistsSource_rssFields');
    if (!typeEl || !siteFields || !rssFields) return;
    const type = typeEl.value || 'site';
    if (type === 'rss') {
        rssFields.style.display = 'block';
        siteFields.style.display = 'none';
    } else {
        rssFields.style.display = 'none';
        siteFields.style.display = 'block';
    }
}

function watchlistsToggleScrapeAdvanced(forceState) {
    const container = document.getElementById('watchlistsSource_scrapeAdvanced');
    if (!container) return;
    if (typeof forceState === 'boolean') {
        _watchlistsScrapeAdvancedVisible = forceState;
    } else {
        _watchlistsScrapeAdvancedVisible = !_watchlistsScrapeAdvancedVisible;
    }
    container.style.display = _watchlistsScrapeAdvancedVisible ? 'block' : 'none';
}

function watchlistsSyncListUrl() {
    const urlEl = document.getElementById('watchlistsSource_url');
    const listEl = document.getElementById('watchlistsSource_listUrl');
    if (!urlEl || !listEl) return;
    if (!listEl.value || !listEl.value.trim()) {
        listEl.value = urlEl.value;
    }
}

function watchlistsResetSourceForm({ keepResponse = false } = {}) {
    const setValue = (id, value = '') => {
        const el = document.getElementById(id);
        if (el) el.value = value;
    };
    setValue('watchlistsSource_name');
    setValue('watchlistsSource_url');
    setValue('watchlistsSource_tags');
    setValue('watchlistsSource_rssLimit', '');
    setValue('watchlistsSource_topN', '');
    setValue('watchlistsSource_discover', 'auto');
    setValue('watchlistsSource_limit', '');
    setValue('watchlistsSource_listUrl', '');
    setValue('watchlistsSource_entrySelectors', '');
    setValue('watchlistsSource_linkSelectors', '');
    setValue('watchlistsSource_titleSelectors', '');
    setValue('watchlistsSource_summarySelectors', '');
    setValue('watchlistsSource_contentSelectors', '');
    setValue('watchlistsSource_authorSelectors', '');
    setValue('watchlistsSource_publishedSelectors', '');
    setValue('watchlistsSource_publishedFormat', '');
    setValue('watchlistsSource_summaryJoin', ' ');
    setValue('watchlistsSource_contentJoin', '\n\n');
    setValue('watchlistsSource_nextSelectors', '');
    setValue('watchlistsSource_nextAttr', 'href');
    setValue('watchlistsSource_maxPages', '2');
    const typeEl = document.getElementById('watchlistsSource_type');
    if (typeEl) typeEl.value = 'site';
    const activeEl = document.getElementById('watchlistsSource_active');
    if (activeEl) activeEl.checked = true;
    const skipEl = document.getElementById('watchlistsSource_skipArticle');
    if (skipEl) skipEl.checked = false;
    watchlistsSourceTypeChanged();
    watchlistsToggleScrapeAdvanced(false);
    if (!keepResponse) {
        watchlistsSetResponse('watchlistsSource_createResponse', '---');
    }
}

async function watchlistsListSources() {
    try {
        const page = document.getElementById('watchlistsSources_page')?.value || '1';
        const size = document.getElementById('watchlistsSources_size')?.value || '50';
        const tag = document.getElementById('watchlistsSources_tag')?.value || '';
        const params = {
            page: Number(page),
            size: Number(size),
        };
        const tagList = watchlistsParseTags(tag);
        if (tagList) params.tags = tagList;
        const res = await apiClient.get('/api/v1/watchlists/sources', params);
        watchlistsSetResponse('watchlistsSources_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsSources_response', `Error: ${err.message}`);
    }
}

async function watchlistsCreateSource() {
    try {
        const name = document.getElementById('watchlistsSource_name')?.value?.trim();
        const url = document.getElementById('watchlistsSource_url')?.value?.trim();
        if (!name || !url) {
            throw new Error('Name and URL are required');
        }
        const type = document.getElementById('watchlistsSource_type')?.value || 'site';
        const active = !!document.getElementById('watchlistsSource_active')?.checked;
        const tags = watchlistsParseTags(document.getElementById('watchlistsSource_tags')?.value || '');

        const payload = {
            name,
            url,
            source_type: type,
            active,
        };
        if (tags) payload.tags = tags;

        const settings = {};

        if (type === 'rss') {
            const limit = watchlistsParseNumber(document.getElementById('watchlistsSource_rssLimit')?.value);
            if (limit !== undefined) settings.limit = limit;
            // History config
            const hist = {};
            const strat = document.getElementById('watchlistsSource_histStrategy')?.value?.trim();
            if (strat) hist.strategy = strat;
            const maxPages = watchlistsParseNumber(document.getElementById('watchlistsSource_histMaxPages')?.value);
            if (maxPages !== undefined) hist.max_pages = maxPages;
            const perPage = watchlistsParseNumber(document.getElementById('watchlistsSource_histPerPage')?.value);
            if (perPage !== undefined) hist.per_page_limit = perPage;
            if (document.getElementById('watchlistsSource_histOn304')?.checked) hist.on_304 = true;
            if (document.getElementById('watchlistsSource_histStopOnSeen')?.checked) hist.stop_on_seen = true;
            if (Object.keys(hist).length > 0) settings.history = hist;
            // RSS content prefs
            const rssCfg = {};
            if (document.getElementById('watchlistsSource_rssUseFeed')?.checked) rssCfg.use_feed_content_if_available = true;
            const minChars = watchlistsParseNumber(document.getElementById('watchlistsSource_feedMinChars')?.value);
            if (minChars !== undefined) rssCfg.feed_content_min_chars = minChars;
            if (Object.keys(rssCfg).length > 0) settings.rss = rssCfg;
        } else {
            const topN = watchlistsParseNumber(document.getElementById('watchlistsSource_topN')?.value);
            if (topN !== undefined) settings.top_n = topN;
            const discover = document.getElementById('watchlistsSource_discover')?.value?.trim();
            if (discover) settings.discover_method = discover;
            const siteLimit = watchlistsParseNumber(document.getElementById('watchlistsSource_limit')?.value);
            const rules = {};
            const listUrlRaw = document.getElementById('watchlistsSource_listUrl')?.value?.trim();
            const listUrl = listUrlRaw || url;
            if (listUrl) rules.list_url = listUrl;
            if (siteLimit !== undefined) rules.limit = siteLimit;

            const entrySelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_entrySelectors')?.value || '');
            if (entrySelectors) rules.entry_xpath = entrySelectors;
            const linkSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_linkSelectors')?.value || '');
            if (linkSelectors) rules.link_xpath = linkSelectors;
            const titleSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_titleSelectors')?.value || '');
            if (titleSelectors) rules.title_xpath = titleSelectors;
            const summarySelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_summarySelectors')?.value || '');
            if (summarySelectors) rules.summary_xpath = summarySelectors;
            const contentSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_contentSelectors')?.value || '');
            if (contentSelectors) rules.content_xpath = contentSelectors;
            const authorSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_authorSelectors')?.value || '');
            if (authorSelectors) rules.author_xpath = authorSelectors;
            const publishedSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_publishedSelectors')?.value || '');
            if (publishedSelectors) rules.published_xpath = publishedSelectors;
            const publishedFormat = document.getElementById('watchlistsSource_publishedFormat')?.value?.trim();
            if (publishedFormat) rules.published_format = publishedFormat;
            const summaryJoin = document.getElementById('watchlistsSource_summaryJoin')?.value ?? '';
            if (summaryJoin.trim().length > 0) rules.summary_join_with = summaryJoin;
            const contentJoin = document.getElementById('watchlistsSource_contentJoin')?.value ?? '';
            if (contentJoin.trim().length > 0) rules.content_join_with = contentJoin;
            if (document.getElementById('watchlistsSource_skipArticle')?.checked) {
                rules.skip_article_fetch = true;
            }

            const pagination = {};
            const nextSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_nextSelectors')?.value || '');
            if (nextSelectors) pagination.next_xpath = nextSelectors;
            const nextAttr = document.getElementById('watchlistsSource_nextAttr')?.value?.trim();
            if (nextAttr && nextAttr !== 'href') {
                pagination.next_attribute = nextAttr;
            }
            const maxPages = watchlistsParseNumber(document.getElementById('watchlistsSource_maxPages')?.value);
            if (maxPages !== undefined) {
                pagination.max_pages = maxPages;
            }
            if (Object.keys(pagination).length > 0) {
                rules.pagination = pagination;
            }

            if (Object.keys(rules).length > 0) {
                settings.scrape_rules = rules;
            }
        }

        if (Object.keys(settings).length > 0) {
            payload.settings = settings;
        }

        const button = document.getElementById('watchlistsSource_createBtn');
        if (button) button.disabled = true;
        const res = await apiClient.post('/api/v1/watchlists/sources', payload);
        watchlistsSetResponse('watchlistsSource_createResponse', res);
        watchlistsResetSourceForm({ keepResponse: true });
        if (button) button.disabled = false;
        await watchlistsListSources();
    } catch (err) {
        const button = document.getElementById('watchlistsSource_createBtn');
        if (button) button.disabled = false;
        watchlistsSetResponse('watchlistsSource_createResponse', `Error: ${err.message}`);
    }
}

function watchlistsToggleRssAdvanced(forceState) {
    try {
        const el = document.getElementById('watchlistsSource_rssAdvanced');
        if (!el) return;
        if (typeof forceState === 'boolean') {
            el.style.display = forceState ? 'block' : 'none';
            return;
        }
        el.style.display = el.style.display === 'none' ? 'block' : 'none';
    } catch (err) {
        console.warn('toggle rss advanced failed', err);
    }
}

// Build settings-only payload from the current form (safe for PATCH)
function _watchlistsBuildSettingsPayloadFromForm() {
    const settings = {};
    const type = document.getElementById('watchlistsSource_type')?.value || 'site';

    if (type === 'rss') {
        const rssCfg = {};
        const limit = watchlistsParseNumber(document.getElementById('watchlistsSource_rssLimit')?.value);
        // For RSS, persist limit at the top-level settings to match create-time shape
        if (limit !== undefined) settings.limit = limit;

        const hist = {};
        const strat = document.getElementById('watchlistsSource_histStrategy')?.value?.trim();
        if (strat && strat !== 'auto') hist.strategy = strat;
        const maxPages = watchlistsParseNumber(document.getElementById('watchlistsSource_histMaxPages')?.value);
        if (maxPages !== undefined) hist.max_pages = maxPages;
        const perPage = watchlistsParseNumber(document.getElementById('watchlistsSource_histPerPage')?.value);
        if (perPage !== undefined) hist.per_page_limit = perPage;
        if (document.getElementById('watchlistsSource_histOn304')?.checked) hist.on_304 = true;
        if (document.getElementById('watchlistsSource_histStopOnSeen')?.checked) hist.stop_on_seen = true;
        if (Object.keys(hist).length > 0) settings.history = hist;

        if (document.getElementById('watchlistsSource_rssUseFeed')?.checked) rssCfg.use_feed_content_if_available = true;
        const minChars = watchlistsParseNumber(document.getElementById('watchlistsSource_feedMinChars')?.value);
        if (minChars !== undefined) rssCfg.feed_content_min_chars = minChars;
        if (Object.keys(rssCfg).length > 0) settings.rss = rssCfg;
    } else {
        const rules = {};
        const topN = watchlistsParseNumber(document.getElementById('watchlistsSource_topN')?.value);
        if (topN !== undefined) settings.top_n = topN;
        const discover = document.getElementById('watchlistsSource_discover')?.value?.trim();
        if (discover && discover !== 'auto') settings.discover_method = discover;
        const siteLimit = watchlistsParseNumber(document.getElementById('watchlistsSource_limit')?.value);
        if (siteLimit !== undefined) rules.limit = siteLimit;
        const listUrlRaw = document.getElementById('watchlistsSource_listUrl')?.value?.trim();
        if (listUrlRaw) rules.list_url = listUrlRaw;

        const entrySelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_entrySelectors')?.value || '');
        if (entrySelectors) rules.entry_xpath = entrySelectors;
        const linkSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_linkSelectors')?.value || '');
        if (linkSelectors) rules.link_xpath = linkSelectors;
        const titleSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_titleSelectors')?.value || '');
        if (titleSelectors) rules.title_xpath = titleSelectors;
        const summarySelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_summarySelectors')?.value || '');
        if (summarySelectors) rules.summary_xpath = summarySelectors;
        const contentSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_contentSelectors')?.value || '');
        if (contentSelectors) rules.content_xpath = contentSelectors;
        const authorSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_authorSelectors')?.value || '');
        if (authorSelectors) rules.author_xpath = authorSelectors;
        const publishedSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_publishedSelectors')?.value || '');
        if (publishedSelectors) rules.published_xpath = publishedSelectors;
        const publishedFormat = document.getElementById('watchlistsSource_publishedFormat')?.value?.trim();
        if (publishedFormat) rules.published_format = publishedFormat;
        const summaryJoin = document.getElementById('watchlistsSource_summaryJoin')?.value ?? '';
        if (summaryJoin.trim().length > 0) rules.summary_join_with = summaryJoin;
        const contentJoin = document.getElementById('watchlistsSource_contentJoin')?.value ?? '';
        if (contentJoin.trim().length > 0) rules.content_join_with = contentJoin;
        if (document.getElementById('watchlistsSource_skipArticle')?.checked) {
            rules.skip_article_fetch = true;
        }

        const pagination = {};
        const nextSelectors = watchlistsNormalizeSelectorsInput(document.getElementById('watchlistsSource_nextSelectors')?.value || '');
        if (nextSelectors) pagination.next_xpath = nextSelectors;
        const nextAttr = document.getElementById('watchlistsSource_nextAttr')?.value?.trim();
        if (nextAttr && nextAttr !== 'href') {
            pagination.next_attribute = nextAttr;
        }
        const maxPages = watchlistsParseNumber(document.getElementById('watchlistsSource_maxPages')?.value);
        if (maxPages !== undefined) pagination.max_pages = maxPages;
        if (Object.keys(pagination).length > 0) rules.pagination = pagination;

        if (Object.keys(rules).length > 0) settings.scrape_rules = rules;
    }
    return settings;
}

async function watchlistsUpdateSource() {
    try {
        const idRaw = document.getElementById('watchlistsSource_updateId')?.value;
        const sourceId = Number(idRaw || 0);
        if (!sourceId || sourceId < 1) throw new Error('Source ID required for update');

        const payload = {};
        const settings = _watchlistsBuildSettingsPayloadFromForm();
        if (Object.keys(settings).length > 0) payload.settings = settings;

        const btn = document.getElementById('watchlistsSource_updateBtn');
        if (btn) btn.disabled = true;
        const res = await apiClient.patch(`/api/v1/watchlists/sources/${sourceId}`, payload);
        watchlistsSetResponse('watchlistsSource_updateResponse', res);
        if (btn) btn.disabled = false;
        await watchlistsListSources();
    } catch (err) {
        const btn = document.getElementById('watchlistsSource_updateBtn');
        if (btn) btn.disabled = false;
        watchlistsSetResponse('watchlistsSource_updateResponse', `Error: ${err.message}`);
    }
}

async function watchlistsLoadSourceIntoForm() {
    try {
        const idRaw = document.getElementById('watchlistsSource_updateId')?.value;
        const sourceId = Number(idRaw || 0);
        if (!sourceId || sourceId < 1) throw new Error('Source ID required to load');
        const res = await apiClient.get(`/api/v1/watchlists/sources/${sourceId}`);
        // Basic fields
        const typeEl = document.getElementById('watchlistsSource_type');
        if (typeEl) typeEl.value = res.source_type || 'site';
        watchlistsSourceTypeChanged();

        const nameEl = document.getElementById('watchlistsSource_name');
        if (nameEl) nameEl.value = res.name || '';
        const urlEl = document.getElementById('watchlistsSource_url');
        if (urlEl) urlEl.value = res.url || '';
        const activeEl = document.getElementById('watchlistsSource_active');
        if (activeEl) activeEl.checked = !!res.active;
        const tagsEl = document.getElementById('watchlistsSource_tags');
        if (tagsEl && res.tags && Array.isArray(res.tags)) tagsEl.value = res.tags.join(', ');

        const settings = res.settings || {};
        // RSS/history
        const hist = (settings.history || {});
        const rss = (settings.rss || {});
        if (document.getElementById('watchlistsSource_histStrategy')) document.getElementById('watchlistsSource_histStrategy').value = hist.strategy || 'auto';
        if (document.getElementById('watchlistsSource_histMaxPages')) document.getElementById('watchlistsSource_histMaxPages').value = (hist.max_pages ?? 1);
        if (document.getElementById('watchlistsSource_histPerPage')) document.getElementById('watchlistsSource_histPerPage').value = (hist.per_page_limit ?? hist.per_page ?? '');
        if (document.getElementById('watchlistsSource_histOn304')) document.getElementById('watchlistsSource_histOn304').checked = !!hist.on_304;
        if (document.getElementById('watchlistsSource_histStopOnSeen')) document.getElementById('watchlistsSource_histStopOnSeen').checked = !!hist.stop_on_seen;
        if (document.getElementById('watchlistsSource_rssLimit')) document.getElementById('watchlistsSource_rssLimit').value = (settings.limit ?? rss.limit ?? '');
        if (document.getElementById('watchlistsSource_rssUseFeed')) document.getElementById('watchlistsSource_rssUseFeed').checked = !!rss.use_feed_content_if_available;
        if (document.getElementById('watchlistsSource_feedMinChars')) document.getElementById('watchlistsSource_feedMinChars').value = (rss.feed_content_min_chars ?? rss.feed_text_min_chars ?? 400);
        // Expand advanced when settings present
        const hasRssAdv = (Object.keys(hist).length > 0 || Object.keys(rss).length > 0);
        watchlistsToggleRssAdvanced(!!hasRssAdv);

        // Site scrape rules
        const rules = (settings.scrape_rules || {});
        if (document.getElementById('watchlistsSource_topN')) document.getElementById('watchlistsSource_topN').value = (settings.top_n ?? rules.top_n ?? '');
        if (document.getElementById('watchlistsSource_discover')) document.getElementById('watchlistsSource_discover').value = (settings.discover_method ?? rules.discovery ?? 'auto');
        if (document.getElementById('watchlistsSource_limit')) document.getElementById('watchlistsSource_limit').value = (rules.limit ?? '');
        if (document.getElementById('watchlistsSource_listUrl')) document.getElementById('watchlistsSource_listUrl').value = (rules.list_url ?? '');
        if (document.getElementById('watchlistsSource_entrySelectors')) document.getElementById('watchlistsSource_entrySelectors').value = (Array.isArray(rules.entry_xpath) ? rules.entry_xpath.join('\n') : (rules.entry_xpath || ''));
        if (document.getElementById('watchlistsSource_linkSelectors')) document.getElementById('watchlistsSource_linkSelectors').value = (Array.isArray(rules.link_xpath) ? rules.link_xpath.join('\n') : (rules.link_xpath || ''));
        if (document.getElementById('watchlistsSource_titleSelectors')) document.getElementById('watchlistsSource_titleSelectors').value = (Array.isArray(rules.title_xpath) ? rules.title_xpath.join('\n') : (rules.title_xpath || ''));
        if (document.getElementById('watchlistsSource_summarySelectors')) document.getElementById('watchlistsSource_summarySelectors').value = (Array.isArray(rules.summary_xpath) ? rules.summary_xpath.join('\n') : (rules.summary_xpath || ''));
        if (document.getElementById('watchlistsSource_contentSelectors')) document.getElementById('watchlistsSource_contentSelectors').value = (Array.isArray(rules.content_xpath) ? rules.content_xpath.join('\n') : (rules.content_xpath || ''));
        if (document.getElementById('watchlistsSource_authorSelectors')) document.getElementById('watchlistsSource_authorSelectors').value = (Array.isArray(rules.author_xpath) ? rules.author_xpath.join('\n') : (rules.author_xpath || ''));
        if (document.getElementById('watchlistsSource_publishedSelectors')) document.getElementById('watchlistsSource_publishedSelectors').value = (Array.isArray(rules.published_xpath) ? rules.published_xpath.join('\n') : (rules.published_xpath || ''));
        if (document.getElementById('watchlistsSource_publishedFormat')) document.getElementById('watchlistsSource_publishedFormat').value = (rules.published_format ?? '');
        if (document.getElementById('watchlistsSource_summaryJoin')) document.getElementById('watchlistsSource_summaryJoin').value = (rules.summary_join_with ?? ' ');
        if (document.getElementById('watchlistsSource_contentJoin')) document.getElementById('watchlistsSource_contentJoin').value = (rules.content_join_with ?? '\n\n');
        if (document.getElementById('watchlistsSource_skipArticle')) document.getElementById('watchlistsSource_skipArticle').checked = !!rules.skip_article_fetch;
        const pagination = (rules.pagination || {});
        if (document.getElementById('watchlistsSource_nextSelectors')) document.getElementById('watchlistsSource_nextSelectors').value = (Array.isArray(pagination.next_xpath) ? pagination.next_xpath.join('\n') : (pagination.next_xpath || ''));
        if (document.getElementById('watchlistsSource_nextAttr')) document.getElementById('watchlistsSource_nextAttr').value = (pagination.next_attribute ?? 'href');
        if (document.getElementById('watchlistsSource_maxPages')) document.getElementById('watchlistsSource_maxPages').value = (pagination.max_pages ?? '');
        // Expand scrape advanced if we populated any
        const hasScrapeAdv = (Object.keys(rules).length > 0);
        watchlistsToggleScrapeAdvanced(!!hasScrapeAdv);

        watchlistsSetResponse('watchlistsSource_createResponse', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsSource_createResponse', `Error: ${err.message}`);
    }
}

// --------------------
// Watchlists Runs (legacy UI surfacing)
// --------------------
async function watchlistsListRuns() {
    try {
        const q = (document.getElementById('watchlistsRuns_q')?.value || '').trim();
        const page = Number(document.getElementById('watchlistsRuns_page')?.value || 1);
        const size = Number(document.getElementById('watchlistsRuns_size')?.value || 50);
        const params = new URLSearchParams();
        if (q) params.set('q', q);
        params.set('page', String(page));
        params.set('size', String(size));
        const res = await apiClient.get(`/api/v1/watchlists/runs?${params.toString()}`);
        // Provide a compact table with history counters when present
        const items = Array.isArray(res?.items) ? res.items : [];
        let html = '';
        html += '<table class="simple-table">';
        html += '<thead><tr><th>Run ID</th><th>Job</th><th>Status</th><th>Started</th><th>Finished</th><th>Hist pages</th><th>StopOnSeen</th></tr></thead><tbody>';
        for (const r of items) {
            const hist = (r?.stats && r.stats.history) ? r.stats.history : {};
            const pages = (hist && typeof hist.pages_fetched !== 'undefined') ? hist.pages_fetched : '';
            const stop = (hist && typeof hist.stop_on_seen_triggered !== 'undefined') ? String(!!hist.stop_on_seen_triggered) : '';
            html += `<tr><td>${r.id}</td><td>${r.job_id}</td><td>${r.status||''}</td><td>${r.started_at||''}</td><td>${r.finished_at||''}</td><td>${pages}</td><td>${stop}</td></tr>`;
        }
        html += '</tbody></table>';
        const tableDiv = document.getElementById('watchlistsRuns_table');
        if (tableDiv) tableDiv.innerHTML = html;
        watchlistsSetResponse('watchlistsRuns_response', res);
    } catch (err) {
        watchlistsSetResponse('watchlistsRuns_response', `Error: ${err.message}`);
    }
}

async function watchlistsGetRun() {
    try {
        const id = Number(document.getElementById('watchlistsRun_id')?.value || 0);
        if (!id) throw new Error('Run ID required');
        const r = await apiClient.get(`/api/v1/watchlists/runs/${id}`);
        // History counters inline
        try {
            const hist = (r?.stats && r.stats.history) ? r.stats.history : null;
            const pages = document.getElementById('watchlistsRun_histPages');
            const stop = document.getElementById('watchlistsRun_histStopOnSeen');
            if (pages) pages.textContent = hist && typeof hist.pages_fetched !== 'undefined' ? String(hist.pages_fetched) : '-';
            if (stop) stop.textContent = hist && typeof hist.stop_on_seen_triggered !== 'undefined' ? String(!!hist.stop_on_seen_triggered) : '-';
        } catch (_) {}
        watchlistsSetResponse('watchlistsRun_response', r);
    } catch (err) {
        watchlistsSetResponse('watchlistsRun_response', `Error: ${err.message}`);
    }
}

// Best-effort: revoke any recording object URLs on tab unload to prevent leaks
try {
    window.addEventListener('beforeunload', () => {
        try { if (typeof _audioTTSRec !== 'undefined' && _audioTTSRec && _audioTTSRec.url) URL.revokeObjectURL(_audioTTSRec.url); } catch(_) {}
        try { if (typeof _fileTransRec !== 'undefined' && _fileTransRec && _fileTransRec.url) URL.revokeObjectURL(_fileTransRec.url); } catch(_) {}
    });
} catch (_) {}
