# NeuTTS (Nano/Air) Integration (Local, Voice Cloning)

NeuTTS is a high-quality on-device TTS with instant voice cloning. This guide explains how to enable and use the NeuTTS adapter in tldw_server.

## Overview

- Provider key: `neutts`
- Models: `neutts-nano`, `neutts-air`, plus GGUF variants (for streaming)
- Supports: English (`en`, `en-us`, `en-gb`)
- Output sample rate: 24 kHz
- Voice cloning: Uses stored references by default; per-request override is optional
- Streaming: GGUF backbones only (`llama-cpp-python`)
- Streaming formats: PCM/MP3/OPUS (WAV streaming is not supported)
- Watermarking: Uses Perth (optional; no-op if not installed)

## Prerequisites

System dependencies:
- espeak-ng (required by phonemizer)
  - macOS: `brew install espeak`
  - Ubuntu/Debian: `sudo apt-get install espeak-ng`
  - Windows: set environment variables if needed (see phonemizer docs)

Python dependencies (install extra group):
```
pip install -e '.[TTS_neutts]'
```

Notes:
- GGUF streaming requires `llama-cpp-python`.
- ONNX decoder requires `onnxruntime` and `neucodec>=0.0.4`.
- macOS users might need to set the espeak library path:
  ```python
  # If phonemizer cannot find espeak automatically
  from phonemizer.backend.espeak.wrapper import EspeakWrapper
  EspeakWrapper.set_library('/opt/homebrew/Cellar/espeak/1.48.04_1/lib/libespeak.1.1.48.dylib')
  ```

## Enable Provider

NeuTTS is present in the TTS config but disabled by default. It requires explicit opt-in after setup to avoid unexpected downloads or resource usage.

Config file:
`tldw_Server_API/Config_Files/tts_providers_config.yaml`

Default settings:
```
providers:
  neutts:
    enabled: false
    backbone_repo: "neuphonic/neutts-nano"          # or "neuphonic/neutts-air"
                                                   # or GGUF: neuphonic/neutts-*-q8-gguf
    backbone_device: "cpu"                           # "gpu" if llama-cpp with GPU
    codec_repo: "neuphonic/neucodec"                 # or neucodec-onnx-decoder
    codec_device: "cpu"
    sample_rate: 24000
    auto_download: false                             # Offline-first; enable explicitly to allow downloads
```

Notes:
- `auto_download` is disabled by default for NeuTTS to keep the path offline.
- When `auto_download` is false, you must point `backbone_repo`/`codec_repo` to local paths.

### Re-enabling NeuTTS after setup (opt-in)

1. Open `tldw_Server_API/Config_Files/tts_providers_config.yaml`.
2. Set `providers.neutts.enabled: true`.
3. Restart the tldw_server API service.

## Default Voice Setup

The bundled default voice is loaded from:
- `/Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.wav`

Optional reference text sidecar:
- `/Helper_Scripts/Audio/Sample_Voices/Sample_Voice_1.txt`

On first use, the server registers the default voice as `custom:default` and auto-encodes reference codes when reference text is available.

## Using the API

Endpoint: `POST /api/v1/audio/speech`

Default request pattern:
- Use `voice: "custom:default"` (or another stored `custom:<voice_id>`).
- Stored voices carry reference audio + reference text.

Optional per-request override fields:
- `voice_reference`: Base64 reference audio (3-15 seconds, mono, 16-44 kHz).
- `extra_params.reference_text`: Text spoken in the reference sample (must match the audio).

Recommended formats:
- Non-streaming: `wav`, `mp3`, `opus`, `flac`, `pcm`.
- Streaming: `pcm`, `mp3`, `opus` (non-WAV).

Example (non-streaming, default voice):
```
curl -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-nano",
    "input": "My name is Dave, and I\'m from London.",
    "response_format": "wav",
    "stream": false,
    "voice": "custom:default"
  }' --output speech.wav
```

Example (streaming; requires GGUF + llama-cpp, PCM/MP3/OPUS):
```
curl -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-nano-q8-gguf",
    "input": "This will stream progressively.",
    "response_format": "pcm",
    "stream": true,
    "voice": "custom:default"
  }'
```

## Sanity Check

Run a quick non-streaming request and confirm the output file plays.

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-nano",
    "input": "NeuTTS sanity check.",
    "response_format": "wav",
    "stream": false,
    "voice": "custom:default"
  }' --output neutts_sanity.wav
```

Expected: `neutts_sanity.wav` is a playable WAV file and logs show a NeuTTS generation.

To verify streaming (GGUF + llama-cpp required), run:

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-nano-q8-gguf",
    "input": "NeuTTS streaming sanity check.",
    "response_format": "pcm",
    "stream": true,
    "voice": "custom:default"
  }' --output neutts_streaming.pcm
```

Expected: `neutts_streaming.pcm` contains non-empty raw PCM audio (24kHz mono int16).

MP3 streaming check:

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-nano-q8-gguf",
    "input": "NeuTTS streaming MP3 sanity check.",
    "response_format": "mp3",
    "stream": true,
    "voice": "custom:default"
  }' --output neutts_streaming.mp3
```

Expected: `neutts_streaming.mp3` is a playable MP3 file.

OPUS streaming check:

```bash
curl -sS -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-nano-q8-gguf",
    "input": "NeuTTS streaming OPUS sanity check.",
    "response_format": "opus",
    "stream": true,
    "voice": "custom:default"
  }' --output neutts_streaming.opus
```

Expected: `neutts_streaming.opus` is a playable OPUS file.

### Upload a Custom Voice (stored references)

Upload a reference clip and transcript once, then reuse via `custom:<voice_id>`. NeuTTS auto-encodes `ref_codes` when `reference_text` is provided.

```
curl -X POST 'http://127.0.0.1:8000/api/v1/audio/voices/upload' \
  -H 'Authorization: Bearer <API_KEY>' \
  -F 'name=MyVoice' \
  -F 'provider=neutts' \
  -F 'reference_text=This is the reference transcript.' \
  -F 'file=@/path/to/reference.mp3'
```

Use the returned `voice_id`:
```
{
  "model": "neutts-nano",
  "input": "Hello from my cloned voice.",
  "voice": "custom:VOICE_ID",
  "response_format": "wav",
  "stream": false
}
```

### Per-request Override (optional)

```
{
  "model": "neutts-nano",
  "input": "Ad-hoc voice override.",
  "voice": "custom:VOICE_ID",
  "response_format": "wav",
  "stream": false,
  "voice_reference": "<BASE64-AUDIO>",
  "extra_params": {
    "reference_text": "Text spoken in the reference clip."
  }
}
```

### Pre-encoding Reference Codes (optional)

Force (re)encoding via:
```
curl -X POST 'http://127.0.0.1:8000/api/v1/audio/voices/encode' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "voice_id": "VOICE_ID",
    "provider": "neutts",
    "reference_text": "Reference transcript"
  }'
```

Then pass codes in `extra_params.ref_codes`:
```
extra_params: {
  "ref_codes": [12, 34, 56, ...],
  "reference_text": "..."
}
```

## Common Issues

- Import errors (`neucodec`, `phonemizer`, `transformers`, `torch`): ensure `pip install -e '.[TTS_neutts]'` completed successfully.
- Phonemizer/espeak not found: install `espeak-ng` and set library path if required.
- Streaming unavailable: only supported with GGUF backbones via `llama-cpp-python`.
- WAV streaming not supported: use `response_format: pcm|mp3|opus` when `stream: true`.

## Security and Privacy

All generation occurs locally. No telemetry is collected. Do not upload sensitive reference audio unless you control the environment.
