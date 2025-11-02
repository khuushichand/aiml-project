Audio Streaming Protocol (Core Parakeet)
=======================================

Overview
- WebSocket-based real-time transcription using the Parakeet Core Streaming module.
- Supports model variants, partial/final frames, live insights (optional), and diarization (optional).

WebSocket Endpoint
- Unified endpoint: `/api/v1/audio/stream/transcribe` (primary; includes auth/quotas/fallback)
- Core demo endpoint: `/core/parakeet/stream` (portable router; no auth/quotas)

Config Frame
- Send this JSON as the first message to configure the session. All fields are optional unless noted.

{
  "type": "config",                       // required
  "model": "parakeet",                    // default: parakeet
  "model_variant": "standard|onnx|mlx",   // default: standard
  "sample_rate": 16000,                    // default: 16000
  "chunk_duration": 2.0,                   // seconds per final segment
  "overlap_duration": 0.5,                 // seconds kept as context between segments
  "language": "en",                       // optional language hint
  "enable_partial": true,                  // emit partial results on a cadence
  "insights": { ... },                     // optional live insights configuration
  "diarization": true                      // or "diarize": true; enable speaker diarization
}

Audio Frame
- Base64-encoded float32 mono PCM audio samples.

{
  "type": "audio",
  "data": "<base64 float32 mono>"
}

Partial Frame
- Emitted periodically when `enable_partial` is true and buffer has enough audio.

{
  "type": "partial",
  "text": "...",
  "is_final": false,
  // Segment metadata (example keys)
  "segment_id": 1,
  "segment_start": 0.0,
  "segment_end": 0.8,
  "buffer_duration": 0.8,
  "cumulative_audio": 0.0
}

Final Frame
- Emitted when `chunk_duration` is reached; includes detailed segment metadata.

{
  "type": "final",
  "text": "...",
  "is_final": true,
  // Segment metadata
  "segment_id": 1,
  "segment_start": 0.0,
  "segment_end": 1.0,
  "chunk_duration": 1.0,
  "overlap": 0.0,
  "chunk_start": 0.0,
  "chunk_end": 1.0,
  "new_audio_duration": 1.0,
  "cumulative_audio": 1.0
}

Commit & Full Transcript
- After sending `{ "type": "commit" }`, the server flushes remaining audio and returns the full transcript.
- When diarization is enabled and available, a `diarization_summary` frame is also emitted.

// Flush response (if any pending text)
{ "type": "final", "text": "...", "is_final": true, ...metadata }

// Full transcript
{ "type": "full_transcript", "text": "..." }

// Optional diarization summary
{
  "type": "diarization_summary",
  "speaker_map": [
    { "segment_id": 1, "speaker_id": 0, "speaker_label": "SPEAKER_00" }
  ],
  "audio_path": null,
  "speakers": [ {"speaker_id": 0, "label": "SPEAKER_00"} ]
}

Other Control Frames
- Reset: `{ "type": "reset" }` → `{ "type": "status", "state": "reset" }`
- Stop: `{ "type": "stop" }` → closes session
- Ping/Pong: `{ "type": "ping" }` → `{ "type": "pong" }`

Notes
- Custom vocabulary post-processing applies to text results when enabled (see `Audio_Custom_Vocabulary`).
- Unified endpoint handles auth, quotas, Whisper fallback, and integrates the same core transcriber via an adapter.

Client Examples
---------------

Python (websockets) - base64 JSON frames

import asyncio, json, base64, numpy as np
import websockets

async def main():
    url = "ws://127.0.0.1:8000/api/v1/audio/stream/transcribe?token=YOUR_API_KEY"
    async with websockets.connect(url, max_size=2**23) as ws:
        # 1) Send config
        await ws.send(json.dumps({
            "type": "config",
            "model": "parakeet",
            "model_variant": "onnx",  # or standard|mlx
            "sample_rate": 16000,
            "chunk_duration": 2.0,
            "overlap_duration": 0.5,
            "enable_partial": True,
            "diarization": True,
            "insights": {"enabled": True}
        }))

        # 2) Send audio frames as base64 float32 mono
        sr = 16000
        samples = (np.zeros(sr//2, dtype=np.float32)).tobytes()  # 0.5s silence
        payload = base64.b64encode(samples).decode("ascii")
        await ws.send(json.dumps({"type": "audio", "data": payload}))

        # 3) Commit
        await ws.send(json.dumps({"type": "commit"}))
        while True:
            msg = await ws.recv()
            print(json.loads(msg))

asyncio.run(main())

Node.js (ws) - base64 JSON frames

const WebSocket = require('ws');
const sr = 16000;
const zeros = Buffer.alloc((sr/2)*4); // 0.5s float32 zeros
const ws = new WebSocket('ws://127.0.0.1:8000/api/v1/audio/stream/transcribe?token=YOUR_API_KEY');

ws.on('open', () => {
  ws.send(JSON.stringify({
    type: 'config', model: 'parakeet', model_variant: 'standard', sample_rate: 16000,
    chunk_duration: 2.0, overlap_duration: 0.5, enable_partial: true
  }));
  ws.send(JSON.stringify({ type: 'audio', data: zeros.toString('base64') }));
  ws.send(JSON.stringify({ type: 'commit' }));
});
ws.on('message', (data) => console.log(JSON.parse(data)));

Python - raw float32 usage (library-level)
- If you embed the core transcriber in your own service, pass `numpy.float32` arrays directly. The Parakeet core transcriber accepts raw float32 and handles chunking, overlap, and metadata.

from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.transcriber import ParakeetCoreTranscriber
from tldw_Server_API.app.core.Ingestion_Media_Processing.Audio.Parakeet_Core_Streaming.config import StreamingConfig
import numpy as np, asyncio

async def run_local():
    cfg = StreamingConfig(sample_rate=16000, chunk_duration=2.0, overlap_duration=0.5,
                          model='parakeet', model_variant='standard', enable_partial=True)
    def decode_fn(audio_np, sr):
        # Your Parakeet decode here
        return "hello"
    tx = ParakeetCoreTranscriber(cfg, decode_fn=decode_fn)
    audio = np.zeros(24000, dtype=np.float32)  # 1.5s
    frame = await tx.process_audio_chunk(audio)
    print(frame)
    frame2 = await tx.flush()
    print(frame2)

asyncio.run(run_local())

Deployment Notes
----------------

Dependencies
- Parakeet variants
  - standard (NeMo): `pip install nemo_toolkit[asr]`
  - onnx: `pip install onnxruntime` (+ model/tokenizer loader in the codebase)
  - mlx (Apple Silicon): `pip install mlx parakeet-mlx`
- Whisper fallback (unified handler): `pip install faster-whisper` and `ffmpeg`
- Diarization (optional): depends on `Diarization_Lib` backends; if unavailable, diarization is disabled gracefully.

Quotas and Redis (optional)
- Per-user quotas for concurrent streams and daily minutes are tracked in-process or via Redis.
- Redis enables TTL-based leak safety for abrupt disconnects; configuration precedence:
  - Env `AUDIO_STREAM_TTL_SECONDS`
  - Config `[Audio-Quota].stream_ttl_seconds`
  - Default 120s (clamped to 30-3600)
- Without Redis, concurrency counters are in-process only.

Health
- Check variant availability: `GET /api/v1/audio/stream/status`
- Lists available models (feature probe) and the streaming WS endpoint.
