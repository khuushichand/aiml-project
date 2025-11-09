# Getting Started — STT (Speech-to-Text) and TTS (Text-to-Speech)

This guide helps first-time users set up and test speech features with tldw_server.
It covers quick paths for both cloud-hosted and local backends, plus verification steps and troubleshooting.

## TL;DR Choices
- Fastest TTS (hosted): OpenAI TTS — requires `OPENAI_API_KEY`.
- Local TTS (offline): Kokoro ONNX — requires model files + eSpeak library.
- Local STT (offline): faster-whisper — requires FFmpeg; optional GPU.
- Advanced STT (optional): NeMo Parakeet/Canary, Qwen2Audio — larger setup, GPU recommended.

## Prerequisites
- Python environment with project installed
  - From repo root: `pip install -e .`
- FFmpeg (required for audio I/O)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt-get install -y ffmpeg`
  - Windows: install from ffmpeg.org and ensure it’s in PATH
- Start the server
  - `python -m uvicorn tldw_Server_API.app.main:app --reload`
  - API: <http://127.0.0.1:8000/docs>
  - WebUI: <http://127.0.0.1:8000/webui/>

Auth quick note
- Single-user mode: server prints an API key on startup; or set `SINGLE_USER_API_KEY`.
- Use header: `X-API-KEY: <your_key>` for all calls (or Bearer JWT in multi-user setups).

---

## Option A — OpenAI TTS (Hosted)
Best for immediate results; no local model setup.

1) Provide API key
- Export `OPENAI_API_KEY` in your shell or add it to `Config_Files/config.txt` (OpenAI section).

2) Verify TTS provider is enabled (optional)
- OpenAI TTS is enabled by default. To confirm or customize, see `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` under `providers.openai`.

3) Test voice catalog
```bash
curl -s http://127.0.0.1:8000/api/v1/audio/voices/catalog \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq
```

4) Generate speech
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "tts-1",
        "voice": "alloy",
        "input": "Hello from tldw_server",
        "response_format": "mp3"
      }' \
  --output out.mp3
```
- Play `out.mp3` in your player.

Troubleshooting
- 401/403: ensure `OPENAI_API_KEY` is set and valid, and you’re passing `X-API-KEY` (single-user) or Bearer token (multi-user).
- 429: OpenAI rate limit; retry after `retry-after` seconds.

---

## Option B — Kokoro TTS (Local, ONNX)
Offline TTS using Kokoro ONNX. Good quality and fast on CPU; optional GPU via ONNX Runtime.

1) Install dependencies
```bash
# Python packages (CPU)
pip install onnxruntime kokoro-onnx phonemizer espeak-phonemizer huggingface-hub

# Optional: GPU acceleration (replace onnxruntime above)
pip install onnxruntime-gpu

# System package for phonemizer (required):
# macOS (Homebrew):
brew install espeak-ng
# Ubuntu/Debian:
sudo apt-get update && sudo apt-get install -y espeak-ng
# Windows (PowerShell, example):
#  - Install eSpeak NG (from https://github.com/espeak-ng/espeak-ng/releases)
#  - Set PHONEMIZER_ESPEAK_LIBRARY to libespeak-ng.dll path

# eSpeak NG is auto-detected on most systems. Point the phonemizer to the library only if needed
# macOS (adjust if your Homebrew prefix differs)
export PHONEMIZER_ESPEAK_LIBRARY=/opt/homebrew/lib/libespeak-ng.dylib
# Linux example
export PHONEMIZER_ESPEAK_LIBRARY=/usr/lib/x86_64-linux-gnu/libespeak-ng.so.1
# Windows example (only if auto-detect fails)
# set PHONEMIZER_ESPEAK_LIBRARY=C:\\Program Files\\eSpeak NG\\libespeak-ng.dll
```

2) Download model files
- Place files under a `models/` folder at the repo root (example paths below).
- Recommended sources:
  - ONNX: `onnx-community/Kokoro-82M-v1.0-ONNX-timestamped` (contains `onnx/model.onnx` and a `voices/` directory of voice styles)
  - PyTorch (optional): `hexgrad/Kokoro-82M` (contains `kokoro-v1_0.pth`, `config.json`, and `voices/`)

Examples
```bash
# Create a local directory
mkdir -p models/kokoro

# Option A: huggingface-cli (ONNX v1.0)
pip install huggingface-hub
huggingface-cli download onnx-community/Kokoro-82M-v1.0-ONNX-timestamped onnx/model.onnx --local-dir models/kokoro/
huggingface-cli download onnx-community/Kokoro-82M-v1.0-ONNX-timestamped voices          --local-dir models/kokoro/

# Option B: direct URLs for ONNX (if CLI unavailable)
wget https://huggingface.co/onnx-community/Kokoro-82M-v1.0-ONNX-timestamped/resolve/main/onnx/model.onnx -O models/kokoro/onnx/model.onnx
# Then download the voices/ directory assets from the same repo (or use huggingface-cli above)
```

3) Enable and point config to your files
- Edit `tldw_Server_API/app/core/TTS/tts_providers_config.yaml`:
```yaml
providers:
  kokoro:
    enabled: true
    use_onnx: true
    model_path: "models/kokoro/onnx/model.onnx"
    voices_json: "models/kokoro/voices"   # use voices directory for v1.0 ONNX
    device: "cpu"    # or "cuda" if using onnxruntime-gpu
```
- Optional: move Kokoro earlier in `provider_priority` to prefer it.

4) Restart server and verify
```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
curl -s http://127.0.0.1:8000/api/v1/audio/voices/catalog \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq '.kokoro'
```

5) Generate speech with Kokoro
```bash
curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Content-Type: application/json" \
  -d '{
        "model": "kokoro",
        "voice": "af_bella",
        "input": "Testing local Kokoro TTS",
        "response_format": "mp3"
      }' \
  --output kokoro.mp3
```

Troubleshooting
- Missing dependencies
  - kokoro_onnx: `pip install kokoro-onnx`
  - onnxruntime: `pip install onnxruntime` (or `onnxruntime-gpu`)
  - phonemizer / espeak-phonemizer: `pip install phonemizer espeak-phonemizer`
- `voices assets not found` or `model not found`: fix `voices` directory or model path in YAML.
- `eSpeak lib not found`: install `espeak-ng` and set `PHONEMIZER_ESPEAK_LIBRARY` to the library path.
- Adapter previously failed and won’t retry: we enable retry by default (`performance.adapter_failure_retry_seconds: 300`). Or restart the server after fixing assets.

Notes
- PyTorch variant (hexgrad/Kokoro-82M): set `use_onnx: false`, set `model_path: models/kokoro/kokoro-v1_0.pth`, ensure `config.json` sits alongside it, and set `voice_dir: models/kokoro/voices`. Requires `torch` and a compatible Kokoro PyTorch package. Set `device` to `cuda` or `mps` if available.

---

## Option C — faster-whisper STT (Local)
Fast, local transcription compatible with the OpenAI `/audio/transcriptions` API.

1) Install dependencies
```bash
pip install faster-whisper
# Optional (GPU): pip install torch --index-url https://download.pytorch.org/whl/cu121
```
- FFmpeg must be installed (see prerequisites).

2) Transcribe an audio file
```bash
# Replace sample.wav with your file
curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/transcriptions \
  -H "X-API-KEY: $SINGLE_USER_API_KEY" \
  -H "Accept: application/json" \
  -F "file=@sample.wav" \
  -F "model=whisper-large-v3" \
  -F "language=en" | jq
```
- The `model` value is OpenAI-compatible; the server maps to your configured local backend.
- For simple text response, set `-H "Accept: text/plain"`.

3) Real-time streaming STT (WebSocket)
- Endpoint: `WS /api/v1/audio/stream/transcribe`
- Example (with `wscat`):
```bash
wscat -c ws://127.0.0.1:8000/api/v1/audio/stream/transcribe \
  -H "X-API-KEY: $SINGLE_USER_API_KEY"
# Then send base64-encoded audio chunks per the server protocol
```

Troubleshooting
- Long files: prefer shorter clips or chunk client-side.
- Out-of-memory: try a smaller model (e.g., `whisper-medium`), or run on GPU.

---

## Verifying Setup via WebUI
- Open <http://127.0.0.1:8000/webui/>
- Tabs:
  - Audio → Transcription (STT): upload a short clip and transcribe
  - Audio → TTS: enter text, pick a voice/model, and synthesize
- The WebUI auto-detects single-user mode and populates the API key.

---

## Common Errors & Fixes
- 401/403 Unauthorized
  - Use `X-API-KEY` (single-user) or Bearer JWT (multi-user). Check server logs on startup.
- 404 / Model or voice not found
  - Verify provider is enabled and files exist; check YAML paths and voice IDs.
- `kokoro_onnx` or `kokoro` missing
  - `pip install kokoro-onnx` (ONNX) or install the PyTorch package for Kokoro.
- eSpeak library missing (Kokoro ONNX)
  - Install `espeak-ng` and set `PHONEMIZER_ESPEAK_LIBRARY` to the library path.
- FFmpeg not found
  - Install FFmpeg and ensure it’s accessible in PATH.
- Network/API errors with OpenAI
  - Verify `OPENAI_API_KEY`. Check rate limits; proxy/corporate networks may block.

---

## Tips & Configuration
- Provider priority
  - `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` → `provider_priority`
  - Put your preferred provider first (e.g., `kokoro` before `openai`).
- Adapter retry
  - `performance.adapter_failure_retry_seconds: 300` allows periodic re-init after failures.
- Streaming errors as audio vs HTTP errors
  - `performance.stream_errors_as_audio: false` (recommended for production APIs).
- GPU acceleration
  - For PyTorch-based backends (Kokoro PT, NeMo), install appropriate CUDA builds and set `device: cuda`.

---

## Privacy & Security
- tldw_server is designed for local/self-hosted use. Audio data stays local unless you call hosted APIs (e.g., OpenAI).
- Never commit API keys; prefer environment variables or `.env`.

---

## Appendix — Sample Kokoro YAML Snippet
```yaml
provider_priority:
  - kokoro
  - openai
providers:
  kokoro:
    enabled: true
    use_onnx: true
    model_path: "models/kokoro/onnx/model.onnx"
    voices_json: "models/kokoro/voices"
    device: "cpu"
performance:
  adapter_failure_retry_seconds: 300
  stream_errors_as_audio: false
```

If you would like, we can configure a setup checker that validates models, voices, FFmpeg, and environment keys, and reports fixes before you run your first request.

---

## Additional TTS Backends (Advanced/Optional)

These providers are supported via adapters. Many require large model downloads and work best with a GPU.

### ElevenLabs (Hosted)
- Enable in YAML and set `ELEVENLABS_API_KEY`.
```yaml
providers:
  elevenlabs:
    enabled: true
    api_key: ${ELEVENLABS_API_KEY}
    model: "eleven_monolingual_v1"
```
- Test: `model: eleven_monolingual_v1`, `voice: rachel` (or a voice from your catalog).

### Higgs Audio V2 (Local)
- Deps: `pip install torch torchaudio soundfile huggingface_hub`; `pip install git+https://github.com/boson-ai/higgs-audio.git`
- YAML:
```yaml
providers:
  higgs:
    enabled: true
    model_path: "bosonai/higgs-audio-v2-generation-3B-base"
    tokenizer_path: "bosonai/higgs-audio-v2-tokenizer"
    device: "cuda"
```
- Test: `model: higgs`, `voice: narrator`.

### Dia (Local, dialogue specialist)
- Deps: `pip install torch transformers accelerate safetensors sentencepiece soundfile huggingface_hub`
- YAML:
```yaml
providers:
  dia:
    enabled: true
    model_path: "nari-labs/dia"
    device: "cuda"
```
- Test: `model: dia`, `voice: speaker1`.

### VibeVoice (Local, expressive multi-speaker)
- Deps: `pip install torch torchaudio sentencepiece soundfile huggingface_hub`
- Install (official):
  ```bash
  git clone https://github.com/microsoft/VibeVoice.git libs/VibeVoice
  cd libs/VibeVoice && pip install -e .
  cd ../..
  ```
- YAML:
```yaml
providers:
  vibevoice:
    enabled: true
    auto_download: true
    device: "cuda"  # or mps/cpu
```
- Test: `model: vibevoice`, `voice: 1` (speaker index).

### NeuTTS Air (Local, voice cloning)
- Deps: `pip install neucodec>=0.0.4 librosa phonemizer transformers` (optional streaming: `pip install llama-cpp-python`)
- YAML:
```yaml
providers:
  neutts:
    enabled: true
    backbone_repo: "neuphonic/neutts-air"
    backbone_device: "cpu"
    codec_repo: "neuphonic/neucodec"
    codec_device: "cpu"
```
- Test: `model: neutts` and provide a base64 `voice_reference` in the JSON body.

### IndexTTS2 (Local, expressive zero-shot)
- Place checkpoints under `checkpoints/index_tts2/`.
- YAML:
```yaml
providers:
  index_tts:
    enabled: true
    model_dir: "checkpoints/index_tts2"
    cfg_path: "checkpoints/index_tts2/config.yaml"
    device: "cuda"
```
- Test: `model: index_tts` (some voices require reference audio).

---

## Additional STT Backends (Advanced/Optional)

### NVIDIA NeMo — Parakeet and Canary
- Deps (standard backend): `pip install 'nemo_toolkit[asr]'>=1.23.0`
- Alternative backends (optional):
  - ONNX: `pip install onnxruntime>=1.16.0 huggingface_hub soundfile librosa numpy`
  - MLX (Apple Silicon): `pip install mlx mlx-lm`
- Usage with `/api/v1/audio/transcriptions`:
  - `model=nemo-parakeet-1.1b` or `model=nemo-canary`
  - Language: set `language=en` (or appropriate code) when known.

### Qwen2Audio (Local)
- Deps: `pip install torch transformers accelerate soundfile sentencepiece`
- Optional: use the setup installer to prefetch assets.
- Usage with `/api/v1/audio/transcriptions`:
  - `model=qwen2audio`

Notes
- Some media endpoints expose more granular backend choices (e.g., Parakeet backends); for `/audio/transcriptions` the `model` is typically sufficient.

---

## Model Hints (At-a-Glance)
- TTS models: `tts-1` (OpenAI), `kokoro`, `eleven_monolingual_v1`, `higgs`, `dia`, `vibevoice`, `neutts`, `index_tts`.
- STT models: `whisper-1` (faster-whisper), `whisper-large-v3` and `*-ct2` variants, `nemo-canary`, `nemo-parakeet-1.1b`, `qwen2audio`.
