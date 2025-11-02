# Chatterbox TTS Setup Runbook

This runbook explains how to enable and operate the Chatterbox TTS provider inside the tldw_server backend. It covers installation, model downloads, configuration, API usage, WebUI steps, and troubleshooting.

## Overview
- Provider: Resemble AI Chatterbox (English and Multilingual variants)
- Integration: Adapter `ChatterboxAdapter` maps repo requests to upstream Chatterbox generate() calls
- Features: Emotion “exaggeration”, optional voice cloning from a reference clip, streaming output via progressive encoding, optional multilingual mode (23 languages)

Key files:
- Adapter: `tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py:1`
- Provider config (YAML): `tldw_Server_API/app/core/TTS/tts_providers_config.yaml:59`
- Provider registry/mapping: `tldw_Server_API/app/core/TTS/adapter_registry.py:560`
- TTS endpoint (OpenAI-compatible): `tldw_Server_API/app/api/v1/endpoints/audio.py:120`

## Requirements
- Python 3.11 recommended
- FFmpeg installed and on PATH (audio resampling/conversion)
- PyTorch 2.0+ (CUDA or MPS optional, CPU supported)
- Internet access for first-time model download, or pre-download for offline mode

## Install Options

Option A - Use repo’s extras (dependencies) + vendored chatterbox module (recommended for dev):
```bash
pip install -e .[TTS_chatterbox]
# Optional language preprocessing utilities for multilingual
pip install -e .[TTS_chatterbox_lang]
```
The repo contains a `chatterbox/` package at the root, so `import chatterbox` resolves locally.

Option B - Install upstream package (when available):
```bash
pip install chatterbox-tts
# Or from source
git clone https://github.com/resemble-ai/chatterbox
cd chatterbox
pip install -e .
```

## Model Weights
The adapter loads upstream weights via `ChatterboxTTS.from_pretrained()` or `ChatterboxMultilingualTTS.from_pretrained()` which download assets from Hugging Face on first use.

Pre-download (recommended for servers/CI):
```bash
# Populates the local HF cache and a mirror directory
huggingface-cli download ResembleAI/chatterbox --local-dir ./models/chatterbox
```

Offline mode (use only local cache):
```bash
export CHATTERBOX_AUTO_DOWNLOAD=0
export TTS_AUTO_DOWNLOAD=0
export HF_HUB_OFFLINE=1
export TRANSFORMERS_OFFLINE=1
```

Notes:
- The adapter will set HF offline flags automatically when `auto_download` is disabled.
- Ensure your HF cache contains these files: `ve.safetensors`, `t3_cfg.safetensors`, `s3gen.safetensors`, `tokenizer.json`, `conds.pt`.

## Configuration

Primary provider config lives in YAML at `tldw_Server_API/app/core/TTS/tts_providers_config.yaml:59` under the `providers.chatterbox` section. Example:
```yaml
providers:
  chatterbox:
    enabled: true            # Enable provider
    device: "cuda"           # "cuda", "mps", or "cpu"
    use_multilingual: false  # true enables 23-language model
    sample_rate: 24000
    disable_watermark: true  # Adapter replaces upstream watermarker (no watermark)
    target_latency_ms: 200   # Streaming chunking hint
    auto_download: true      # Optional: let the adapter fetch models on first use
```

Additional behavior controlled by env:
- `CHATTERBOX_AUTO_DOWNLOAD` / `TTS_AUTO_DOWNLOAD` - override auto-download at runtime
- `HF_HUB_OFFLINE`, `TRANSFORMERS_OFFLINE` - force offline cache usage

What the adapter reads:
- Device selection & multilingual: `chatterbox_device`, `chatterbox_use_multilingual`
- Watermarking toggle: `chatterbox_disable_watermark` (default true)
- Defaults for generation: `chatterbox_default_exaggeration`, `chatterbox_cfg_weight`, `chatterbox_temperature`, `chatterbox_repetition_penalty`, `chatterbox_min_p`, `chatterbox_top_p`

See adapter for details: `tldw_Server_API/app/core/TTS/adapters/chatterbox_adapter.py:108`.

## Start the Server
```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
# API docs: http://127.0.0.1:8000/docs
# Web UI:   http://127.0.0.1:8000/webui/
```

Verify provider availability:
```bash
curl http://127.0.0.1:8000/api/v1/audio/tts/providers
```
You should see Chatterbox listed with its capabilities once the adapter imports successfully.

## API Usage

Streaming request (OpenAI-compatible) to `POST /api/v1/audio/speech` (`audio.py:120`):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chatterbox",
    "input": "Hello from Chatterbox!",
    "voice": "default",
    "response_format": "mp3",
    "stream": true
  }' --output out.mp3
```

Voice cloning (send base64-encoded reference; ideal duration 5-20s at 24kHz):
```bash
BASE64_AUDIO=$(base64 -i my_voice_24k.wav)
curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d "{\
    \"model\": \"chatterbox\",\
    \"input\": \"This should sound like my reference.\",\
    \"voice\": \"clone\",\
    \"voice_reference\": \"$BASE64_AUDIO\",\
    \"response_format\": \"wav\"\
  }" --output clone.wav
```

Multilingual synthesis (enable `use_multilingual: true` in YAML):
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chatterbox",
    "input": "Bonjour, comment ça va?",
    "language": "fr",
    "response_format": "mp3",
    "stream": true
  }' --output fr.mp3
```

Tuning generation (adapter maps emotion+intensity -> `exaggeration`):
- `emotion`: one of neutral, happy, sad, angry, surprised, fearful, disgusted, excited, calm, confused
- `emotion_intensity`: 0.0-2.0 (defaults scaled to `exaggeration` in [0.0-1.0])
- Extra params accepted: `cfg_weight`, `temperature`, `repetition_penalty`, `min_p`, `top_p`

Example:
```bash
curl -X POST "http://127.0.0.1:8000/api/v1/audio/speech" \
  -H "Authorization: Bearer <TOKEN>" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "chatterbox",
    "input": "I am thrilled to be here!",
    "emotion": "excited",
    "emotion_intensity": 1.5,
    "extra_params": {"cfg_weight": 0.5, "temperature": 0.8},
    "response_format": "mp3"
  }' --output excited.mp3
```

## WebUI Usage
1. Start the server and open `http://127.0.0.1:8000/webui/`.
2. Go to the Audio tab, select “Chatterbox”.
3. Provide input text; optionally upload/mic-record a reference clip.
4. Adjust emotion intensity (exaggeration), CFG weight, and sampling parameters.
5. Click Generate to preview.

The WebUI uses the same `/api/v1/audio/speech` endpoint under the hood and will stream results.

## Performance & Devices
- Device selection order: configured `device` -> CUDA if available -> CPU; supports Apple Silicon `mps`.
- Recommended: 4GB+ VRAM for smooth GPU inference; CPU and MPS are supported with higher latency.
- Adapter streams by encoding waveform into small chunks (~200ms) for immediate playback.

## Offline & Caching Checklist
- Pre-download model with `huggingface-cli` (see above).
- Set `CHATTERBOX_AUTO_DOWNLOAD=0`, `TTS_AUTO_DOWNLOAD=0`.
- Set `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`.
- Ensure HF cache contains required safetensors and tokenizer files.

## Troubleshooting
1) Import error: `chatterbox` not found
- Install upstream package: `pip install chatterbox-tts`, or use repo’s vendored module with `pip install -e .[TTS_chatterbox]`.

2) Model download blocked/offline
- Pre-download via `huggingface-cli download ResembleAI/chatterbox --local-dir ./models/chatterbox` and set offline env vars.

3) Voice cloning fails or sounds wrong
- Use 5-20s single-speaker WAV/FLAC at 24kHz; avoid noisy or clipped audio.
- Convert with ffmpeg:
  ```bash
  ffmpeg -i input.wav -ar 24000 -ac 1 -t 15 ref_24k.wav
  ```

4) Latency too high
- Use `device: cuda` if available; reduce `temperature`; ensure no CPU throttling.
- Adjust CFG weight (~0.3-0.5) for more stable pacing.

5) Multilingual outputs have incorrect accent
- Set `cfg_weight: 0.0` for language transfer if the reference is a different language.

6) Watermarking
- The adapter disables watermarking by default (`disable_watermark: true`). If you need watermarking, use the upstream models directly outside the adapter.

## Notes for Developers
- The adapter lazily loads English vs Multilingual models based on `language` in the request and `use_multilingual` in config. See `chatterbox_adapter.py:193` and `_get_model`.
- Provider model name mapping includes `"chatterbox"` and `"chatterbox-emotion"`. See `adapter_registry.py:560`.
- Streaming uses `waveform_streamer.stream_encoded_waveform(...)` with ~0.2s chunks.
