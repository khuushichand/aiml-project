import { useEffect, useMemo, useRef, useState } from 'react';
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

export default function AudioPage() {
  const [tab, setTab] = useState<'tts'|'stt'>('tts');
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
          <div className="w-1/2"><Tabs items={[{key:'tts',label:'TTS'},{key:'stt',label:'Streaming STT'}]} value={tab} onChange={(k)=>setTab(k as any)} /></div>
        </div>
        <div className="rounded-md border bg-white p-4 transition-all duration-150">
          {tab === 'tts' ? <TTSSection/> : <StreamingSTTSection/>}
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
      const urlBlob = URL.createObjectURL(blob);
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
      ws.onclose = () => { setConnected(false); setRecording(false); addDebug('WebSocket closed'); };
    } catch (e: any) {
      show({ title: 'Connect failed', description: e?.message || 'Failed', variant: 'danger' });
    }
  };

  const start = async () => {
    if (!wsRef.current || wsRef.current.readyState !== WebSocket.OPEN) { show({title:'Not connected',variant:'warning'}); return; }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: { channelCount: 1, echoCancellation: true, noiseSuppression: true } });
      const ctx = new (window.AudioContext || (window as any).webkitAudioContext)();
      ctxRef.current = ctx;
      const source = ctx.createMediaStreamSource(stream);
      const proc = ctx.createScriptProcessor(16384, 1, 1);
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
        if (!recording) return;
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
        bufferRef.current.push(...data);
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
              wsRef.current?.send(JSON.stringify({ type: 'commit' }));
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
          wsRef.current?.send(JSON.stringify({ type: 'audio', data: b64 }));
        }
      };
      setRecording(true);
      show({ title: 'Recording started', variant: 'success' });
    } catch (e: any) {
      show({ title: 'Mic failed', description: e?.message || 'Permission error', variant: 'danger' });
    }
  };

  const stop = () => {
    setRecording(false);
    if (ctxRef.current) { try { ctxRef.current.close(); } catch {} ctxRef.current = null; }
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'commit' }));
    if (animTimer.current) { cancelAnimationFrame(animTimer.current); animTimer.current = null; }
    autoStoppedRef.current = false;
    show({ title: 'Recording stopped', variant: 'info' });
  };

  const disconnect = () => {
    try { wsRef.current?.close(); } catch {}
    wsRef.current = null; setConnected(false); setRecording(false);
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

function arrayBufferToBase64(buffer: ArrayBuffer) {
  let binary = '';
  const bytes = new Uint8Array(buffer);
  const len = bytes.byteLength;
  for (let i = 0; i < len; i++) {
    binary += String.fromCharCode(bytes[i]);
  }
  return btoa(binary);
}
