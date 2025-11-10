(() => {
  const API_BASE = () => document.getElementById('api-url').value;
  const API_KEY = () => document.getElementById('api-key').value;

  // Simple HTML escaping function to prevent XSS from error messages
  function escapeHTML(str) {
    return String(str).replace(/[&<>"']/g, function (m) {
      return ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#39;'
      })[m];
    });
  }

  async function checkHealth() {
    const statusDiv = document.getElementById('health-status');
    statusDiv.style.display = 'block';
    statusDiv.className = 'status info';
    statusDiv.innerHTML = 'Checking provider health...';

    try {
      const response = await fetch(`${API_BASE()}/audio/health`, {
        headers: API_KEY() ? { 'Authorization': `Bearer ${API_KEY()}` } : {}
      });
      if (!response.ok) throw new Error(`HTTP ${response.status}`);

      const data = await response.json();
      if (data.status === 'healthy') {
        statusDiv.className = 'status success';
        let html = '<strong>System Status: Healthy</strong><br>';
        if (data.providers) {
          html += `<br>Total Providers: ${data.providers.total}<br>`;
          html += `Available: ${data.providers.available}<br><br>`;
          if (data.providers.details) {
            html += '<strong>Provider Details:</strong><br>';
            for (const [provider, info] of Object.entries(data.providers.details)) {
              const status = info.status || 'unknown';
              const emoji = status === 'available' ? '✅' : '❌';
              html += `${emoji} ${provider}: ${status}<br>`;
            }
          }
        }
        html && (statusDiv.innerHTML = html);
      } else {
        statusDiv.className = 'status error';
        statusDiv.innerHTML = `System Status: ${data.status}`;
      }
    } catch (error) {
      statusDiv.className = 'status error';
      statusDiv.innerHTML = `Error checking health: ${escapeHTML(error.message)}`;
    }
  }

  async function testProvider(provider) {
    const text = document.getElementById('test-text').value;
    const voiceSel = document.getElementById(`${provider}-voice`);
    const voice = voiceSel ? voiceSel.value : 'default';
    const statusDiv = document.getElementById(`${provider}-status`);
    const audioEl = document.getElementById(`${provider}-audio`);

    statusDiv.className = 'status info';
    statusDiv.innerHTML = 'Generating speech...';

    try {
      let request = { input: text, voice, response_format: 'mp3', stream: false };
      switch (provider) {
        case 'vibevoice': request.model = 'vibevoice:1.5B'; break;
        case 'kokoro': request.model = 'kokoro'; break;
        case 'higgs': request.model = 'higgs'; break;
        case 'chatterbox': request.model = 'chatterbox'; break;
        case 'openai': request.model = 'tts-1'; break;
        case 'elevenlabs': request.model = 'elevenlabs'; break;
        case 'neutts': {
          const modelSel = document.getElementById('neutts-model');
          const fmtSel = document.getElementById('neutts-format');
          const streamChk = document.getElementById('neutts-stream');
          const fileInput = document.getElementById('neutts-ref-audio');
          const refText = document.getElementById('neutts-ref-text').value.trim();
          const recBlob = window._neuttsRecBlob || null;
          if (!fileInput.files[0] && !recBlob) throw new Error('Please record or select a reference audio file for NeuTTS');
          if (!refText) throw new Error('Please enter reference text matching the audio');
          const blob = recBlob || fileInput.files[0];
          const wavBlob = await ensureWav(blob);
          const b64 = await blobToBase64(wavBlob);
          request.model = modelSel.value;
          request.response_format = fmtSel.value;
          request.stream = !!streamChk.checked;
          request.voice_reference = b64;
          request.extra_params = { reference_text: refText };
          break;
        }
      }

      const response = await fetch(`${API_BASE()}/audio/speech`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', ...(API_KEY() ? { 'Authorization': `Bearer ${API_KEY()}` } : {}) },
        body: JSON.stringify(request)
      });
      if (!response.ok) {
        const error = await response.text();
        throw new Error(error || `HTTP ${response.status}`);
      }
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      audioEl.src = url;
      audioEl.style.display = 'block';
      try { await audioEl.play(); } catch(_){}
      statusDiv.className = 'status success';
      statusDiv.innerHTML = `✅ Success! Audio generated (${(blob.size / 1024).toFixed(2)} KB)`;
    } catch (error) {
      statusDiv.className = 'status error';
      statusDiv.innerHTML = `❌ Error: ${escapeHTML(error.message)}`;
      audioEl.style.display = 'none';
    }
  }

  async function testAllProviders() {
    const providers = ['vibevoice', 'kokoro', 'higgs', 'chatterbox', 'openai', 'elevenlabs'];
    const batchStatus = document.getElementById('batch-status');
    batchStatus.className = 'status info';
    batchStatus.innerHTML = 'Testing all providers...';
    const results = [];
    for (const provider of providers) {
      try { await testProvider(provider); results.push(`✅ ${provider}`); }
      catch { results.push(`❌ ${provider}`); }
      // Delay between tests
      // eslint-disable-next-line no-await-in-loop
      await new Promise(res => setTimeout(res, 1000));
    }
    batchStatus.className = 'status success';
    batchStatus.innerHTML = '<strong>Batch Test Complete:</strong><br>' + results.join('<br>');
  }

  // ---- Simple recorder + helpers for NeuTTS ----
  let _rec = { mr: null, chunks: [], stream: null };
  window._neuttsRecBlob = null;
  async function startNeuTTSRecording() {
    try {
      if (_rec.mr) return;
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: 'audio/webm' });
      _rec.stream = stream; _rec.chunks = []; _rec.mr = mr;
      document.getElementById('neutts-rec-status').textContent = 'Recording...';
      document.getElementById('neutts-rec-start').disabled = true;
      document.getElementById('neutts-rec-stop').disabled = false;
      mr.ondataavailable = (e)=>{ if (e.data && e.data.size) _rec.chunks.push(e.data); };
      mr.onstop = () => {
        const blob = new Blob(_rec.chunks, { type: 'audio/webm' });
        window._neuttsRecBlob = blob;
        const url = URL.createObjectURL(blob);
        const audio = document.getElementById('neutts-rec-playback');
        audio.src = url; audio.style.display='block';
        document.getElementById('neutts-rec-status').textContent = 'Recorded';
        document.getElementById('neutts-rec-start').disabled = false;
        document.getElementById('neutts-rec-stop').disabled = true;
        stream.getTracks().forEach(t=>t.stop());
        _rec.mr = null; _rec.stream = null;
      };
      mr.start();
    } catch(e) {
      console.error('rec start failed', e);
      document.getElementById('neutts-rec-status').textContent = 'Recording failed';
    }
  }
  function stopNeuTTSRecording() {
    try { if (_rec.mr) _rec.mr.stop(); } catch(e) { console.error(e); }
  }

  async function blobToBase64(blob) {
    const buf = await blob.arrayBuffer();
    let binary=''; const bytes=new Uint8Array(buf); const step=0x8000;
    for(let i=0;i<bytes.length;i+=step){ binary+=String.fromCharCode.apply(null, bytes.subarray(i,i+step)); }
    return btoa(binary);
  }
  async function ensureWav(blob) {
    if (blob.type && (blob.type.includes('wav'))) return blob;
    const buf = await blob.arrayBuffer();
    const ac = new (window.AudioContext||window.webkitAudioContext)();
    const audioBuffer = await ac.decodeAudioData(buf);
    const wavView = encodeWav(audioBuffer);
    return new Blob([wavView], { type: 'audio/wav' });
  }
  function encodeWav(audioBuffer) {
    const ch = audioBuffer.numberOfChannels>1?mixToMono(audioBuffer):audioBuffer.getChannelData(0);
    const pcm = floatTo16(ch);
    const sr = audioBuffer.sampleRate;
    const ab = new ArrayBuffer(44 + pcm.length*2); const view = new DataView(ab);
    writeStr(view,0,'RIFF'); view.setUint32(4,36+pcm.length*2,true); writeStr(view,8,'WAVE');
    writeStr(view,12,'fmt '); view.setUint32(16,16,true); view.setUint16(20,1,true);
    view.setUint16(22,1,true); view.setUint32(24,sr,true); view.setUint32(28,sr*2,true);
    view.setUint16(32,2,true); view.setUint16(34,16,true); writeStr(view,36,'data'); view.setUint32(40,pcm.length*2,true);
    let off=44; for(let i=0;i<pcm.length;i++,off+=2){ view.setInt16(off, pcm[i], true); }
    return view;
  }
  function floatTo16(input){ const out=new Int16Array(input.length); for(let i=0;i<input.length;i++){ let s=Math.max(-1,Math.min(1,input[i])); out[i]=s<0?s*0x8000:s*0x7FFF;} return out; }
  function mixToMono(buf){ const l=buf.length; const a=buf.getChannelData(0), b=buf.getChannelData(1), o=new Float32Array(l); for(let i=0;i<l;i++) o[i]=0.5*(a[i]+b[i]); return o; }
  function writeStr(view, offset, str){ for (let i=0;i<str.length;i++) view.setUint8(offset+i, str.charCodeAt(i)); }

  window.addEventListener('DOMContentLoaded', () => {
    // Initial health check
    setTimeout(checkHealth, 500);
    // Bind health button
    document.getElementById('check-health-btn')?.addEventListener('click', checkHealth);
    // Bind provider test buttons
    document.querySelectorAll('.provider-test-btn').forEach(btn => {
      const provider = btn.getAttribute('data-provider');
      if (!provider) return;
      btn.addEventListener('click', () => testProvider(provider));
    });
    // Bind batch test
    document.getElementById('test-all-btn')?.addEventListener('click', testAllProviders);
    // Bind NeuTTS recorder controls
    document.getElementById('neutts-rec-start')?.addEventListener('click', startNeuTTSRecording);
    document.getElementById('neutts-rec-stop')?.addEventListener('click', stopNeuTTSRecording);
  });
})();

