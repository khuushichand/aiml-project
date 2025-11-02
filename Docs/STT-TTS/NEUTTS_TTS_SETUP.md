# NeuTTS Air Integration (Local, Voice Cloning)

NeuTTS Air is a high-quality on-device TTS with instant voice cloning. This guide explains how to enable and use the NeuTTS adapter in tldw_server.

## Overview

- Provider key: `neutts`
- Supports: English (`en`, `en-us`, `en-gb`)
- Output sample rate: 24 kHz
- Voice cloning: Required (reference audio + matching reference text)
- Streaming: Only when using GGUF backbones with `llama-cpp-python`
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
This installs: `librosa`, `phonemizer`, `transformers`, `torch`, `neucodec>=0.0.4`, `resemble-perth`, and optional `onnxruntime`, `llama-cpp-python`.

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

NeuTTS has been added to the TTS config and enabled by default in:
`tldw_Server_API/app/core/TTS/tts_providers_config.yaml`

Key settings:
```
providers:
  neutts:
    enabled: true
    backbone_repo: "neuphonic/neutts-air"           # or GGUF: neuphonic/neutts-air-q8-gguf
    backbone_device: "cpu"                           # "gpu" if llama-cpp with GPU
    codec_repo: "neuphonic/neucodec"                 # or neucodec-onnx-decoder
    codec_device: "cpu"
    sample_rate: 24000
```

Provider priority includes `neutts` after `kokoro` by default.

## Using the API

Endpoint: `POST /api/v1/audio/speech`

Required request fields for NeuTTS voice cloning:
- `voice_reference`: Base64 encoded reference audio (3-15 seconds, mono, 16-44 kHz). Alternatively, pre-encode to codes.
- `extra_params.reference_text`: Text spoken in the reference sample (must correspond to the audio).

Recommended formats: `wav`, `mp3`, `opus`, `flac`, `pcm`.

Example (non-streaming):
```
curl -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-air",
    "input": "My name is Dave, and I\'m from London.",
    "response_format": "wav",
    "stream": false,
    "voice_reference": "<BASE64-WAV-BYTES>",
    "extra_params": {
      "reference_text": "This is Dave speaking in this sample."
    }
  }' --output speech.wav
```

Example (streaming; requires GGUF + llama-cpp):
```
curl -X POST 'http://127.0.0.1:8000/api/v1/audio/speech' \
  -H 'Authorization: Bearer <API_KEY>' \
  -H 'Content-Type: application/json' \
  -d '{
    "model": "neutts-air-q8-gguf",
    "input": "This will stream progressively.",
    "response_format": "mp3",
    "stream": true,
    "voice_reference": "<BASE64-WAV-BYTES>",
    "extra_params": {
      "reference_text": "Sample text spoken in the reference clip."
    }
  }'
```

### Pre-encoding Reference Codes (optional)

If you want to avoid sending raw audio every time, pre-compute codes using the upstream example and then pass them in `extra_params.ref_codes` along with `extra_params.reference_text`:
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

## Security and Privacy

All generation occurs locally. No telemetry is collected. Do not upload sensitive reference audio unless you control the environment.
