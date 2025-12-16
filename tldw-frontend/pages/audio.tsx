import { useEffect, useRef, useState } from 'react';
import { Layout } from '@/components/layout/Layout';
import { Button } from '@/components/ui/Button';
import { Input } from '@/components/ui/Input';
import { buildAuthHeaders, getApiBaseUrl } from '@/lib/api';
import { useToast } from '@/components/ui/ToastProvider';
import { Tabs } from '@/components/ui/Tabs';
import JsonViewer from '@/components/ui/JsonViewer';
import HotkeysOverlay from '@/components/ui/HotkeysOverlay';

function httpToWs(url: string) {
  return url.replace(/^http/, 'ws');
}

const tabs = [
  { key: 'tts', label: 'TTS' },
  { key: 'stt', label: 'Streaming STT' },
  { key: 'chat', label: 'Voice Chat (WS)' },
] as const;

type TabKey = (typeof tabs)[number]['key'];

export default function AudioPage() {
  const [tab, setTab] = useState<TabKey>('tts');
  return (
    <Layout>
      <div className="mx-auto max-w-3xl space-y-4">
        <HotkeysOverlay
          entries={[
            { keys: 'R', description: 'Start/Stop recording (when connected)' },
            { keys: '?', description: 'Toggle shortcuts help' },
          ]}
        />
        <div className="flex items-center justify-between">
          <h1 className="text-2xl font-bold text-gray-900">Audio</h1>
          <div className="w-1/2">
            <Tabs
              items={tabs}
              value={tab}
              onChange={(k)=>setTab(k as TabKey)}
            />
          </div>
        </div>
        <div className="rounded-md border bg-white p-4 transition-all duration-150">
          {tab === 'tts' ? <TTSSection/> : tab === 'stt' ? <StreamingSTTSection/> : <VoiceChatStreamSection/>}
        </div>
      </div>
    </Layout>
  );
}

function TTSSection() {
  const { show } = useToast();
  const [model, setModel] = useState('tts-1');
  const [voice, setVoice] = useState('alloy');
  const [text, setText] = useState('Hello from TLDW Server');
  const [loading, setLoading] = useState(false);
  const audioRef = useRef<HTMLAudioElement>(null);
  const blobUrlRef = useRef<string | null>(null);
  const [respInfo, setRespInfo] = useState<any>(null);

  const fetchVoices = async () => {
    try {
      const resp = await fetch(`${getApiBaseUrl()}/audio/voices`, { headers: buildAuthHeaders('GET') });
      if (!resp.ok) return;
      const json = await resp.json();
      const voices = json?.voices || json || [];
      if (voices.length && voices[0]?.name) setVoice(voices[0].name);
    } catch {}
  };
  useEffect(() => { fetchVoices(); }, []);

  useEffect(() => {
    return () => {
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
    };
  }, []);

  const speak = async () => {
    setLoading(true);
    setRespInfo(null);
    try {
      const url = `${getApiBaseUrl()}/audio/speech`;
      const body = JSON.stringify({ model, voice, input: text });
      const headers: Record<string,string> = { ...buildAuthHeaders('POST','application/json'), Accept: 'audio/mpeg' };
      const resp = await fetch(url, { method: 'POST', headers, body });
      setRespInfo({ status: resp.status, type: resp.headers.get('Content-Type') });
      if (!resp.ok) {
        const errText = await resp.text();
        show({ title: 'TTS failed', description: errText.slice(0,200), variant: 'danger' });
        return;
      }
      const buf = await resp.arrayBuffer();
      const blob = new Blob([buf], { type: resp.headers.get('Content-Type') || 'audio/mpeg' });
      if (blobUrlRef.current) URL.revokeObjectURL(blobUrlRef.current);
      const urlBlob = URL.createObjectURL(blob);
      blobUrlRef.current = urlBlob;
      if (audioRef.current) {
        audioRef.current.src = urlBlob;
        await audioRef.current.play();
      }
      show({ title: 'Playing preview', variant: 'success' });
    } catch (e: any) {
      show({ title: 'TTS error', description: e?.message || 'Failed', variant: 'danger' });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
        <Input label="Model" value={model} onChange={(e)=>setModel(e.target.value)} />
        <Input label="Voice" value={voice} onChange={(e)=>setVoice(e.target.value)} />
        <div className="flex items-end"><Button onClick={speak} loading={loading} disabled={loading}>Generate & Play</Button></div>
      </div>
      <div>
        <label className="mb-1 block text-sm font-medium text-gray-700">Text</label>
        <textarea className="h-24 w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={text} onChange={(e)=>setText(e.target.value)} />
      </div>
      <audio ref={audioRef} controls className="w-full" />
      {respInfo && (
        <div className="rounded border bg-gray-50 p-2 text-xs">
          <JsonViewer data={respInfo} />
        </div>
      )}
    </div>
  );
}

function StreamingSTTSection() {
  const { show } = useToast();
  const [connected, setConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  const [model, setModel] = useState<'parakeet'|'canary'|'whisper'>('whisper');
  const [language, setLanguage] = useState('');
  const [sampleRate, setSampleRate] = useState(16000);
  const [partial, setPartial] = useState('');
  const [finals, setFinals] = useState<string[]>([]);
  const wsRef = useRef<WebSocket|null>(null);
  const ctxRef = useRef<AudioContext|null>(null);
  const bufferRef = useRef<number[]>([]);
  const startTimeRef = useRef<number>(0);
  const debugRef = useRef<string[]>([]);
  const [debugView, setDebugView] = useState<string[]>([]);
  const animTimer = useRef<any>(null);
  const canvasRef = useRef<HTMLCanvasElement|null>(null);
  const analyserRef = useRef<AnalyserNode|null>(null);
  const [showWave, setShowWave] = useState(true);
  const [vadEnabled, setVadEnabled] = useState(true);
  const [vadThreshold, setVadThreshold] = useState(0.02); // RMS threshold
  const [autoCommit, setAutoCommit] = useState(true);
  const [silenceMs, setSilenceMs] = useState(2000);
  const lastActiveRef = useRef<number>(0);
  const [volume, setVolume] = useState(0);
  const [autoStop, setAutoStop] = useState(true);
  const autoStoppedRef = useRef<boolean>(false);
  const [autoStopOnFinal, setAutoStopOnFinal] = useState(true);
  const recordingRef = useRef(false);
  const streamRef = useRef<MediaStream | null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode | null>(null);
  const procRef = useRef<ScriptProcessorNode | null>(null);

  const cleanupAudio = () => {
    recordingRef.current = false;
    if (procRef.current) {
      try {
        procRef.current.disconnect();
      } catch {}
      procRef.current = null;
    }
    if (sourceRef.current) {
      try {
        sourceRef.current.disconnect();
      } catch {}
      sourceRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (ctxRef.current) {
      try {
        ctxRef.current.close();
      } catch {}
      ctxRef.current = null;
    }
    if (animTimer.current) {
      cancelAnimationFrame(animTimer.current);
      animTimer.current = null;
    }
  };

  const addDebug = (s: string) => {
    const line = `${new Date().toLocaleTimeString()} ${s}`;
    debugRef.current.push(line);
    if (debugRef.current.length > 200) debugRef.current.shift();
    setDebugView([...debugRef.current]);
  };

  const connect = async () => {
    try {
      let wsUrl = httpToWs(`${getApiBaseUrl()}/audio/stream/transcribe`);
      // Attempt to include auth in query params for WS if server supports it
      try {
        const token = localStorage.getItem('access_token');
        const xk = localStorage.getItem('x_api_key');
        const urlObj = new URL(wsUrl);
        if (token) urlObj.searchParams.set('token', token);
        if (xk) urlObj.searchParams.set('x-api-key', xk);
        wsUrl = urlObj.toString();
      } catch {}
      const headers = buildAuthHeaders('GET');
      // Attach auth headers as query params (fallback) if server supports; primarily rely on cookies/headers.
      const ws = new WebSocket(wsUrl);
      wsRef.current = ws;
      ws.onopen = () => {
        setConnected(true);
        addDebug('WebSocket connected');
        // Send config
        const cfg = { type: 'config', model, sample_rate: sampleRate, language: language || undefined } as any;
        ws.send(JSON.stringify(cfg));
        addDebug(`Sent config: ${JSON.stringify(cfg)}`);
        show({ title: 'Connected to STT', variant: 'success' });
      };
      ws.onmessage = (ev) => {
        try {
          const msg = JSON.parse(ev.data);
          if (msg.type === 'partial') setPartial(msg.text || '');
          else if (msg.type === 'final' || msg.type === 'transcription') {
            setFinals((f)=>[...f, msg.text || '']);
            setPartial('');
            if (autoStopOnFinal && !autoStoppedRef.current) {
              autoStoppedRef.current = true;
              addDebug('Auto-stop on final result');
              stop();
            }
          }
          else if (msg.type === 'status') addDebug(`Status: ${msg.state || ''}`);
          else if (msg.type === 'error') { show({ title: 'STT error', description: msg.message || 'Error', variant: 'danger' }); addDebug(`Error: ${msg.message}`); }
        } catch { addDebug(`RX: ${String(ev.data).slice(0,100)}`); }
      };
      ws.onerror = (e) => { addDebug('WebSocket error'); };
      ws.onclose = () => {
        cleanupAudio();
        recordingRef.current = false;
        setConnected(false);
        setRecording(false);
        addDebug('WebSocket closed');
      };
    } catch (e: any) {
      show({ title: 'Connect failed', description: e?.message || 'Failed', variant: 'danger' });
    }
  };

  const start = async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) { show({title:'Not connected',variant:'warning'}); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      streamRef.current = stream;
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;
      const proc = ctx.createScriptProcessor(16384, 1, 1);
      procRef.current = proc;
      source.connect(proc); proc.connect(ctx.destination);
      // Setup analyser for visualization
      const analyser = ctx.createAnalyser(); analyser.fftSize = 2048;
      source.connect(analyser); analyserRef.current = analyser;
      // Draw loop
      if (showWave && canvasRef.current) {
        const canvas = canvasRef.current; const c = canvas.getContext('2d');
        const draw = () => {
          if (!c || !analyserRef.current) return;
          const bufferLength = analyserRef.current.fftSize;
          const dataArray = new Uint8Array(bufferLength);
          analyserRef.current.getByteTimeDomainData(dataArray);
          // Compute RMS based on time domain for volume meter
          let sum = 0; for (let i=0;i<bufferLength;i++){ const v = (dataArray[i]/128)-1; sum+= v*v; }
          const rms = Math.sqrt(sum / bufferLength);
          setVolume(Math.max(0, Math.min(1, rms*3))); // scale for UI
          c.clearRect(0, 0, canvas.width, canvas.height);
          c.strokeStyle = '#2563eb'; c.lineWidth = 2; c.beginPath();
          const sliceWidth = canvas.width / bufferLength; let x = 0;
          for (let i=0;i<bufferLength;i++) {
            const v = dataArray[i] / 128.0 - 1.0; const y = (v * canvas.height) / 2 + canvas.height/2;
            if (i===0) c.moveTo(x,y); else c.lineTo(x,y);
            x += sliceWidth;
          }
          c.stroke();
          animTimer.current = requestAnimationFrame(draw);
        };
        draw();
      }
      bufferRef.current = [];
      startTimeRef.current = Date.now();
      const targetSamples = sampleRate * (model === 'whisper' ? 5 : 2);
      proc.onaudioprocess = (ev: AudioProcessingEvent) => {
        if (!recordingRef.current) return;
        const input = ev.inputBuffer.getChannelData(0);
        // Resample if needed (naive interpolation)
        let data = input;
        if (ctx.sampleRate !== sampleRate) {
          const ratio = sampleRate / ctx.sampleRate;
          const newLen = Math.floor(input.length * ratio);
          const out = new Float32Array(newLen);
          for (let i=0;i<newLen;i++){
            const srcIndex = i/ratio;
            const lo = Math.floor(srcIndex);
            const hi = Math.min(lo+1, input.length-1);
            const frac = srcIndex - lo;
            out[i] = input[lo]*(1-frac)+input[hi]*frac;
          }
          data = out;
        }
        for (let i = 0; i < data.length; i++) {
          bufferRef.current.push(data[i]);
        }
        if (bufferRef.current.length >= targetSamples) {
          const chunk = new Float32Array(bufferRef.current.slice(0, targetSamples));
          const overlap = Math.floor(targetSamples*0.1);
          bufferRef.current = bufferRef.current.slice(targetSamples-overlap);
          const b64 = arrayBufferToBase64(chunk.buffer);
          // VAD gating: compute RMS and compare to threshold
          if (vadEnabled) {
            let sum = 0; for (let i=0;i<chunk.length;i++){ const v = chunk[i]; sum += v*v; }
            const rms = Math.sqrt(sum / chunk.length);
            const now = Date.now();
            if (rms < vadThreshold) {
              // silence chunk
              if (autoCommit && lastActiveRef.current && (now - lastActiveRef.current) > silenceMs) {
                if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
                  wsRef.current.send(JSON.stringify({ type: 'commit' }));
                }
                addDebug(`Auto-commit after ${silenceMs}ms silence`);
                lastActiveRef.current = now; // prevent repeated commits
              }
              if (autoStop && !autoStoppedRef.current && lastActiveRef.current && (now - lastActiveRef.current) > silenceMs * 2) {
                autoStoppedRef.current = true;
                addDebug(`Auto-stop after ${(silenceMs*2)}ms silence`);
                stop();
              }
              addDebug(`VAD: skip chunk rms=${rms.toFixed(4)}`);
              return;
            }
            // voice detected
            lastActiveRef.current = now;
          }
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'audio', data: b64 }));
          }
        }
      };
      recordingRef.current = true;
      setRecording(true);
      show({ title: 'Recording started', variant: 'success' });
    } catch (e: any) {
      show({ title: 'Mic failed', description: e?.message || 'Permission error', variant: 'danger' });
    }
  };

	  const stop = () => {
	    recordingRef.current = false;
	    setRecording(false);
      cleanupAudio();
	    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'commit' }));
      }
	    autoStoppedRef.current = false;
	    show({ title: 'Recording stopped', variant: 'info' });
	  };

	  const disconnect = () => {
      cleanupAudio();
	    try { wsRef.current?.close(); } catch {}
	    wsRef.current = null;
      setConnected(false);
      setRecording(false);
      recordingRef.current = false;
	  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Model</label>
          <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={model} onChange={(e)=>setModel(e.target.value as any)}>
            <option value="whisper">Whisper</option>
            <option value="parakeet">Parakeet</option>
            <option value="canary">Canary</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Sample Rate</label>
          <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={sampleRate} onChange={(e)=>setSampleRate(parseInt(e.target.value))}>
            <option value={16000}>16000 Hz</option>
            <option value={22050}>22050 Hz</option>
            <option value={32000}>32000 Hz</option>
          </select>
        </div>
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">Language</label>
          <input className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={language} onChange={(e)=>setLanguage(e.target.value)} placeholder="Empty = auto" />
        </div>
        <div className="flex items-end space-x-2">
          {!connected ? (
            <Button onClick={connect}>Connect</Button>
          ) : (
            <Button variant="secondary" onClick={disconnect}>Disconnect</Button>
          )}
          {!recording ? (
            <Button onClick={start} disabled={!connected}>Start</Button>
          ) : (
            <Button variant="secondary" onClick={stop}>Stop</Button>
          )}
        </div>
      </div>
      <div className="rounded border bg-gray-50 p-3">
        <div className="text-xs text-gray-500">Partial</div>
        <div className="rounded bg-white p-2 text-sm min-h-10">{partial}</div>
      </div>
      <div className="rounded border bg-gray-50 p-3">
        <div className="mb-2 flex items-center justify-between">
          <div className="text-xs text-gray-500">Waveform</div>
          <div className="flex items-center space-x-3 text-sm">
            <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={showWave} onChange={(e)=>setShowWave(e.target.checked)} /><span>Show</span></label>
            <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={vadEnabled} onChange={(e)=>setVadEnabled(e.target.checked)} /><span>VAD</span></label>
            <div className="flex items-center space-x-2"><span>Thresh</span><input type="range" min={0.005} max={0.1} step={0.005} value={vadThreshold} onChange={(e)=>setVadThreshold(parseFloat(e.target.value))} /></div>
            <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={autoCommit} onChange={(e)=>setAutoCommit(e.target.checked)} /><span>Auto-commit</span></label>
            <div className="flex items-center space-x-2"><span>Silence</span><input type="number" min={500} step={100} className="w-20 rounded border p-1" value={silenceMs} onChange={(e)=>setSilenceMs(parseInt(e.target.value||'2000'))} /><span>ms</span></div>
            <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={autoStop} onChange={(e)=>setAutoStop(e.target.checked)} /><span>Auto-stop</span></label>
            <label className="inline-flex items-center space-x-2"><input type="checkbox" checked={autoStopOnFinal} onChange={(e)=>setAutoStopOnFinal(e.target.checked)} /><span>Stop on final</span></label>
          </div>
        </div>
        <canvas ref={canvasRef} width={640} height={120} className="w-full rounded bg-white" />
        <div className="mt-2 h-2 w-full rounded bg-gray-200">
          <div className="h-2 rounded bg-blue-500 transition-all" style={{ width: `${Math.min(100, Math.round(volume*100))}%` }} />
        </div>
        <div className="mt-2 flex items-center space-x-1">
          {Array.from({ length: 10 }).map((_, i) => {
            const threshold = (i + 1) / 10;
            const on = volume >= threshold;
            const color = i < 6 ? 'bg-green-500' : i < 8 ? 'bg-yellow-500' : 'bg-red-500';
            return <span key={i} className={`inline-block h-2 w-4 rounded-sm ${on ? color : 'bg-gray-300'}`} />;
          })}
        </div>
      </div>
      <div className="rounded border bg-gray-50 p-3">
        <div className="text-xs text-gray-500">Transcript</div>
        <div className="whitespace-pre-wrap rounded bg-white p-2 text-sm min-h-24 max-h-64 overflow-auto">{finals.join('\n')}</div>
      </div>
      <div className="rounded border bg-gray-50 p-3">
        <div className="text-xs text-gray-500">Debug</div>
        <div className="max-h-40 overflow-auto font-mono text-xs">{debugView.map((l,i)=>(<div key={i}>{l}</div>))}</div>
      </div>
    </div>
  );
}

function VoiceChatStreamSection() {
  const { show } = useToast();
  const [connected, setConnected] = useState(false);
  const [recording, setRecording] = useState(false);
  const [sttModel, setSttModel] = useState<'parakeet'|'canary'|'whisper'>('whisper');
  const [llmProvider, setLlmProvider] = useState('openai');
  const [llmModel, setLlmModel] = useState('gpt-4o-mini');
  const [ttsVoice, setTtsVoice] = useState('af_heart');
  const [ttsFormat, setTtsFormat] = useState<'mp3'|'opus'|'pcm'>('mp3');
  const [sessionId, setSessionId] = useState('');
  const [actionName, setActionName] = useState('');
  const [partial, setPartial] = useState('');
  const [transcripts, setTranscripts] = useState<string[]>([]);
  const [assistant, setAssistant] = useState('');
  const [status, setStatus] = useState('');
  const [assistantInfo, setAssistantInfo] = useState<any>(null);
  const wsRef = useRef<WebSocket|null>(null);
  const ctxRef = useRef<AudioContext|null>(null);
  const bufferRef = useRef<number[]>([]);
  // Accumulates raw TTS audio chunks (ArrayBuffers) from the server.
  const ttsChunksRef = useRef<ArrayBuffer[]>([]);
  const audioUrlRef = useRef<string|null>(null);
  const audioRef = useRef<HTMLAudioElement|null>(null);
  const recordingRef = useRef(false);
  const streamRef = useRef<MediaStream|null>(null);
  const sourceRef = useRef<MediaStreamAudioSourceNode|null>(null);
  const procRef = useRef<ScriptProcessorNode|null>(null);
  const sampleRate = 16000;

  const cleanupAudio = () => {
    recordingRef.current = false;
    bufferRef.current = [];
    if (procRef.current) {
      try { procRef.current.disconnect(); } catch {}
      procRef.current = null;
    }
    if (sourceRef.current) {
      try { sourceRef.current.disconnect(); } catch {}
      sourceRef.current = null;
    }
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((t) => t.stop());
      streamRef.current = null;
    }
    if (ctxRef.current) {
      try { ctxRef.current.close(); } catch {}
      ctxRef.current = null;
    }
  };

  useEffect(() => {
    return () => {
      cleanupAudio();
      try { wsRef.current?.close(); } catch {}
      if (audioUrlRef.current) URL.revokeObjectURL(audioUrlRef.current);
    };
  }, []);

  const resetTtsBuffers = () => {
    if (audioUrlRef.current) { URL.revokeObjectURL(audioUrlRef.current); audioUrlRef.current = null; }
    ttsChunksRef.current = [];
  };

  // For TTS format "pcm", the server streams raw 16‑bit mono PCM
  // (audio/L16; rate=24000; channels=1). Browsers cannot play raw
  // PCM directly via <audio>, so wrap it in a minimal RIFF/WAVE
  // header client‑side before creating the Blob.
  const wrapPcmChunksAsWav = (chunks: ArrayBuffer[], sampleRate: number, channels: number, bitsPerSample: number): ArrayBuffer => {
    const bytesPerSample = bitsPerSample / 8;
    const totalBytes = chunks.reduce((acc, buf) => acc + buf.byteLength, 0);
    const headerSize = 44;
    const buffer = new ArrayBuffer(headerSize + totalBytes);
    const view = new DataView(buffer);
    let offset = 0;

    const writeString = (s: string) => {
      for (let i = 0; i < s.length; i += 1) {
        view.setUint8(offset, s.charCodeAt(i));
        offset += 1;
      }
    };
    const writeUint32LE = (value: number) => {
      view.setUint32(offset, value, true);
      offset += 4;
    };
    const writeUint16LE = (value: number) => {
      view.setUint16(offset, value, true);
      offset += 2;
    };

    const blockAlign = channels * bytesPerSample;
    const byteRate = sampleRate * blockAlign;

    writeString('RIFF');
    writeUint32LE(36 + totalBytes);
    writeString('WAVE');
    writeString('fmt ');
    writeUint32LE(16); // PCM subchunk size
    writeUint16LE(1); // audio format = PCM
    writeUint16LE(channels);
    writeUint32LE(sampleRate);
    writeUint32LE(byteRate);
    writeUint16LE(blockAlign);
    writeUint16LE(bitsPerSample);
    writeString('data');
    writeUint32LE(totalBytes);

    const out = new Uint8Array(buffer);
    let dataOffset = headerSize;
    for (const buf of chunks) {
      out.set(new Uint8Array(buf), dataOffset);
      dataOffset += buf.byteLength;
    }

    return buffer;
  };

  const playTts = () => {
    if (!ttsChunksRef.current.length) return;
    let blob: Blob;
    if (ttsFormat === 'pcm') {
      // Server sends raw PCM (audio/L16; rate=24000; channels=1); wrap as WAV for browser playback.
      const wavBuffer = wrapPcmChunksAsWav(ttsChunksRef.current, 24000, 1, 16);
      blob = new Blob([wavBuffer], { type: 'audio/wav' });
    } else {
      const mime = ttsFormat === 'mp3' ? 'audio/mpeg' : ttsFormat === 'opus' ? 'audio/opus' : 'audio/wav';
      blob = new Blob(ttsChunksRef.current, { type: mime });
    }
    audioUrlRef.current = URL.createObjectURL(blob);
    if (audioRef.current) {
      audioRef.current.src = audioUrlRef.current;
      audioRef.current.play().catch(() => {});
    }
  };

  const connect = async () => {
    try {
      let wsUrl = httpToWs(`${getApiBaseUrl()}/audio/chat/stream`);
      try {
        const token = localStorage.getItem('access_token');
        const xk = localStorage.getItem('x_api_key');
        const urlObj = new URL(wsUrl);
        if (token) urlObj.searchParams.set('token', token);
        if (xk) urlObj.searchParams.set('x-api-key', xk);
        wsUrl = urlObj.toString();
      } catch {}

      const ws = new WebSocket(wsUrl);
      ws.binaryType = 'arraybuffer';
      wsRef.current = ws;
      ws.onopen = () => {
        setConnected(true);
        setStatus('Connected');
        setPartial('');
        setTranscripts([]);
        setAssistant('');
        setAssistantInfo(null);
        resetTtsBuffers();
        const cfg: any = {
          type: 'config',
          session_id: sessionId || undefined,
          stt: { model: sttModel, sample_rate: sampleRate, enable_vad: true },
          llm: { provider: llmProvider, model: llmModel },
          tts: { voice: ttsVoice, format: ttsFormat },
        };
        if (actionName) cfg.metadata = { action: actionName };
        ws.send(JSON.stringify(cfg));
      };
      ws.onmessage = async (ev) => {
        if (typeof ev.data === 'string') {
          let msg: any;
          try { msg = JSON.parse(ev.data); } catch { return; }
          switch (msg.type) {
            case 'partial':
              setPartial(msg.text || '');
              break;
            case 'full_transcript':
              setTranscripts((t)=>[...t, msg.text || '']);
              setPartial('');
              setAssistant('');
              setAssistantInfo(null);
              resetTtsBuffers();
              break;
            case 'llm_delta':
              setAssistant((t)=>t + (msg.delta || ''));
              break;
            case 'llm_message':
              setAssistant(msg.text || '');
              break;
            case 'assistant_summary':
              setAssistantInfo(msg);
              break;
            case 'tts_start':
              resetTtsBuffers();
              setStatus('Streaming TTS…');
              break;
            case 'tts_done':
              playTts();
              setStatus('Turn complete');
              break;
            case 'warning':
              setStatus(msg.message || 'Warning');
              break;
            case 'error':
              setStatus(msg.message || 'Error');
              show({ title: 'Voice chat error', description: msg.message || 'Streaming failed', variant: 'danger' });
              break;
            case 'action_result':
              setAssistantInfo((prev)=>({ ...(prev || {}), action: msg }));
              setStatus(`Action: ${msg.status || 'ok'}`);
              break;
            default:
              break;
          }
        } else {
          const buf = ev.data instanceof Blob ? await ev.data.arrayBuffer() : ev.data;
          if (buf) ttsChunksRef.current.push(buf);
        }
      };
      ws.onerror = () => {
        setStatus('WebSocket error');
        show({
          title: 'WebSocket error',
          description: 'Voice chat connection failed or interrupted',
          variant: 'danger',
        });
      };
      ws.onclose = () => {
        cleanupAudio();
        setConnected(false);
        setRecording(false);
        setStatus('Disconnected');
      };
    } catch (e: any) {
      show({ title: 'Connect failed', description: e?.message || 'Failed', variant: 'danger' });
    }
  };

  const start = async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) {
      show({ title: 'Not connected', description: 'Connect first', variant: 'warning' });
      return;
    }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      streamRef.current = stream;
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      sourceRef.current = source;
      const proc = ctx.createScriptProcessor(8192, 1, 1);
      procRef.current = proc;
      source.connect(proc); proc.connect(ctx.destination);
      bufferRef.current = [];
      proc.onaudioprocess = (ev: AudioProcessingEvent) => {
        if (!recordingRef.current) return;
        let data = ev.inputBuffer.getChannelData(0);
        if (ctx.sampleRate !== sampleRate) {
          const ratio = sampleRate / ctx.sampleRate;
          const newLen = Math.floor(data.length * ratio);
          const out = new Float32Array(newLen);
          for (let i=0;i<newLen;i++){
            const srcIndex = i/ratio;
            const lo = Math.floor(srcIndex);
            const hi = Math.min(lo+1, data.length-1);
            const frac = srcIndex - lo;
            out[i] = data[lo]*(1-frac)+data[hi]*frac;
          }
          data = out;
        }
        for (let i = 0; i < data.length; i++) {
          bufferRef.current.push(data[i]);
        }
        const target = sampleRate * 2;
        if (bufferRef.current.length >= target) {
          const chunk = new Float32Array(bufferRef.current.slice(0, target));
          bufferRef.current = bufferRef.current.slice(target);
          const b64 = arrayBufferToBase64(chunk.buffer);
          if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
            wsRef.current.send(JSON.stringify({ type: 'audio', data: b64 }));
          }
        }
      };
      recordingRef.current = true;
      setRecording(true);
      setStatus('Recording…');
    } catch (e: any) {
      cleanupAudio();
      setRecording(false);
      show({ title: 'Mic failed', description: e?.message || 'Permission error', variant: 'danger' });
    }
  };

  const stop = () => {
    recordingRef.current = false;
    setRecording(false);
    cleanupAudio();
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'commit' }));
    }
  };

  const disconnect = () => {
    stop();
    try {
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: 'stop' }));
      }
    } catch {}
    try { wsRef.current?.close(); } catch {}
    wsRef.current = null;
    setConnected(false);
    setRecording(false);
    setStatus('Disconnected');
  };

  const commit = () => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'commit' }));
    }
  };

  return (
    <div className="space-y-3">
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">STT Model</label>
          <select
            className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500"
            value={sttModel}
            onChange={(e)=>setSttModel(e.target.value as any)}
          >
            <option value="whisper">Whisper</option>
            <option value="parakeet">Parakeet</option>
            <option value="canary">Canary</option>
          </select>
        </div>
        <Input label="Session ID (optional)" value={sessionId} onChange={(e)=>setSessionId(e.target.value)} />
        <Input label="LLM Provider" value={llmProvider} onChange={(e)=>setLlmProvider(e.target.value)} />
        <Input label="LLM Model" value={llmModel} onChange={(e)=>setLlmModel(e.target.value)} />
        <Input label="TTS Voice" value={ttsVoice} onChange={(e)=>setTtsVoice(e.target.value)} />
        <div>
          <label className="mb-1 block text-sm font-medium text-gray-700">TTS Format</label>
          <select className="w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500" value={ttsFormat} onChange={(e)=>setTtsFormat(e.target.value as any)}>
            <option value="mp3">mp3</option>
            <option value="opus">opus</option>
            <option value="pcm">pcm</option>
          </select>
        </div>
        <Input label="Action (optional)" value={actionName} onChange={(e)=>setActionName(e.target.value)} placeholder="action/tool name" />
      </div>
      <div className="flex flex-wrap items-center gap-2">
        {!connected ? (
          <Button onClick={connect}>Connect</Button>
        ) : (
          <Button variant="secondary" onClick={disconnect}>Disconnect</Button>
        )}
        {!recording ? (
          <Button onClick={start} disabled={!connected}>Start</Button>
        ) : (
          <Button variant="secondary" onClick={stop}>Stop & Commit</Button>
        )}
        <Button variant="ghost" onClick={commit} disabled={!connected}>Commit</Button>
      </div>
      <div className="rounded border bg-gray-50 p-3">
        <div className="text-xs text-gray-500">Status</div>
        <div className="rounded bg-white p-2 text-sm min-h-10">{status || 'Idle'}</div>
      </div>
      <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
        <div className="rounded border bg-gray-50 p-3">
          <div className="text-xs text-gray-500">Partial</div>
          <div className="rounded bg-white p-2 text-sm min-h-12">{partial}</div>
        </div>
        <div className="rounded border bg-gray-50 p-3">
          <div className="text-xs text-gray-500">Assistant (streaming)</div>
          <div className="whitespace-pre-wrap rounded bg-white p-2 text-sm min-h-12 max-h-48 overflow-auto">{assistant}</div>
        </div>
      </div>
      <div className="rounded border bg-gray-50 p-3">
        <div className="text-xs text-gray-500">Transcripts</div>
        <div className="whitespace-pre-wrap rounded bg-white p-2 text-sm min-h-16 max-h-60 overflow-auto">{transcripts.map((t,i)=>(<div key={i} className="mb-2"><strong className="text-gray-500">User:</strong> {t}</div>))}</div>
      </div>
      {assistantInfo && (
        <div className="rounded border bg-gray-50 p-3 text-xs">
          <div className="mb-1 text-gray-500">Assistant summary</div>
          <JsonViewer data={assistantInfo} />
        </div>
      )}
      <div className="rounded border bg-gray-50 p-3">
        <div className="mb-1 text-xs text-gray-500">TTS Preview</div>
        <audio ref={audioRef} controls className="w-full" />
      </div>
    </div>
  );
}

function arrayBufferToBase64(buffer: ArrayBuffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
