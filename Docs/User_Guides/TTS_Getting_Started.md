# TTS Providers Getting Started Guide

This guide helps new operators bring text-to-speech (TTS) online inside `tldw_server`. It walks through the supported providers (cloud + local), required dependencies, configuration files, and verification commands so you can decide which adapter to enable and confirm it works end to end.

## YAML Quick Start

Minimal configuration to get going. Save to `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` (or use one of the supported locations).

```yaml
# Provider selection / fallback order
provider_priority:
  - openai
  - kokoro

providers:
  # Hosted (requires env: OPENAI_API_KEY)
  openai:
    enabled: true
    api_key: ${OPENAI_API_KEY}
    model: tts-1

  # Local ONNX example
  kokoro:
    enabled: true
    use_onnx: true
    model_path: models/kokoro/onnx/model.onnx
    voices_json: models/kokoro/voices
    device: cpu

  # Local VibeVoice example (opt-in; downloads disabled by default)
  vibevoice:
    enabled: false           # set true to enable
    auto_download: false     # set true to allow HF downloads
    model_path: microsoft/VibeVoice-1.5B
    device: auto             # cuda | mps | cpu | auto

performance:
  max_concurrent_generations: 4
  stream_errors_as_audio: false
```

Notes:
- Local providers will not download model assets unless you explicitly set `auto_download: true` (or export `TTS_AUTO_DOWNLOAD=1` / `VIBEVOICE_AUTO_DOWNLOAD=1`).
- You can override API keys and some settings via `Config_Files/config.txt` or environment variables.

## One-Command Installers
Run these from the project root to install a single TTS backend (deps + models where applicable):

```bash
# Kokoro (v1.0 ONNX + voices)
python Helper_Scripts/TTS_Installers/install_tts_kokoro.py

# NeuTTS (deps; optional prefetch)
python Helper_Scripts/TTS_Installers/install_tts_neutts.py --prefetch

# Dia / Higgs / VibeVoice
python Helper_Scripts/TTS_Installers/install_tts_dia.py
python Helper_Scripts/TTS_Installers/install_tts_higgs.py
python Helper_Scripts/TTS_Installers/install_tts_vibevoice.py --variant 1.5B

# IndexTTS2 (deps + checkpoints folder)
python Helper_Scripts/TTS_Installers/install_tts_index_tts2.py

# Chatterbox (deps only)
python Helper_Scripts/TTS_Installers/install_tts_chatterbox.py [--with-lang]
```

Installer flags:
- `TLDW_SETUP_SKIP_PIP=1` to skip pip installs
- `TLDW_SETUP_SKIP_DOWNLOADS=1` to skip model downloads

## Key Files & Paths
- `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` — canonical provider settings + priority list.
- `Config_Files/config.txt` — optional INI overrides (e.g., `[TTS-Settings]` block).
- `tldw_Server_API/app/core/TTS/adapters/` — implementation for each backend.
- `tldw_Server_API/app/core/TTS/TTS-README.md` — deep dive on architecture + adapter matrix.

## Quick Reference (Choose Your Provider)

| Provider | Type | Install / Extras | Voice Cloning | Reference |
| --- | --- | --- | --- | --- |
| OpenAI `tts-1` | Hosted API | `OPENAI_API_KEY` | No | [Getting Started](https://github.com/rmusser01/tldw_server/blob/main/Docs/Getting-Started-STT_and_TTS.md#option-a--openai-tts-hosted) |
| ElevenLabs | Hosted API | `ELEVENLABS_API_KEY` | Yes (via ElevenLabs voices) | [TTS Setup Guide](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/TTS-SETUP-GUIDE.md#commercial-providers) |
| Kokoro ONNX | Local ONNX | `pip install -e ".[TTS_kokoro_onnx]"` + `espeak-ng` | No | [Getting Started](https://github.com/rmusser01/tldw_server/blob/main/Docs/Getting-Started-STT_and_TTS.md#option-b--kokoro-tts-local-onnx) |
| NeuTTS Air | Local hybrid | `pip install -e ".[TTS_neutts]"` + `espeak-ng` | **Required** (reference audio + text) | [NeuTTS Runbook](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/NEUTTS_TTS_SETUP.md) |
| Chatterbox | Local PyTorch | `pip install -e ".[TTS_chatterbox]"` (+ `.[TTS_chatterbox_lang]` for multilingual) | Yes (5–20 s) | [Chatterbox Runbook](https://github.com/rmusser01/tldw_server/blob/main/Docs/Published/User_Guides/Chatterbox_TTS_Setup.md) |
| VibeVoice | Local PyTorch | `pip install -e ".[TTS_vibevoice]"` + clone [VibeVoice](https://github.com/microsoft/VibeVoice) | Yes (3–30 s) | [VibeVoice Guide](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/VIBEVOICE_GETTING_STARTED.md) |
| Higgs Audio V2 | Local PyTorch | `pip install -e ".[TTS_higgs]"` + install `bosonai/higgs-audio` | Yes (3–10 s) | [TTS Setup Guide](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/TTS-SETUP-GUIDE.md#higgs-audio-v2-setup) |
| Dia | Local PyTorch | `pip install torch transformers accelerate nltk spacy` | Yes (dialogue prompts) | [TTS Setup Guide](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/TTS-SETUP-GUIDE.md#dia-setup) |
| IndexTTS2 | Local PyTorch | Download checkpoints to `checkpoints/index_tts2/` | Yes (zero-shot, 12 GB+ VRAM) | [TTS README](https://github.com/rmusser01/tldw_server/blob/main/tldw_Server_API/app/core/TTS/TTS-README.md#indextts2-adapter) |

> Tip: Keep cloud providers (`openai`, `elevenlabs`) high in `provider_priority` for instant results, and add local fallbacks underneath.

## Baseline Prerequisites
1. **Install the project**
   ```bash
   pip install -e .
   ```
   Add extras per provider (see table above).
2. **System packages**
   - FFmpeg (`brew install ffmpeg` or `apt-get install -y ffmpeg`)
   - eSpeak NG for phonemizer-backed models (`brew install espeak-ng` / `apt-get install -y espeak-ng`)
3. **Model cache helpers**
   `pip install huggingface-hub` and log in if you need gated repos.
4. **Runtime**
   Start the API:
   ```bash
   python -m uvicorn tldw_Server_API.app.main:app --reload
   ```
   Note the printed `X-API-KEY` when running in single-user mode.

## Recommended Setup Flow
1. **Pick providers** you care about and install their extras.
2. **Download models** proactively (use `huggingface-cli download ... --local-dir ...` for offline hosts).
3. **Edit `tts_providers_config.yaml`**
   - Enable providers, point to local paths, and adjust `device`, `sample_rate`, etc.
   - Adjust `provider_priority` so preferred backends run first.
   - Note: Local providers will not download models unless you explicitly set `auto_download: true` per provider (or export `TTS_AUTO_DOWNLOAD=1`).
4. **Optional overrides** in `Config_Files/config.txt` (`[TTS-Settings]`) if you need environment-specific toggles.
5. **Set secrets/env vars** (API keys, `TTS_AUTO_DOWNLOAD`, device hints).
6. **Restart the server** and watch logs for `adapter initialized`.
7. **Verify** with `curl` (samples below) or via the WebUI ➜ Audio ➜ TTS tab.

---

## Hosted Providers

### OpenAI
1. Export your key or add it to `config.txt`:
   ```bash
   export OPENAI_API_KEY=sk-...
   ```
2. (Optional) Change the default model (`tts-1-hd`) or base URL (self-hosted proxies) inside `tts_providers_config.yaml`.
3. Verify:
   ```bash
   curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
     -H "X-API-KEY: $SINGLE_USER_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"tts-1","voice":"alloy","input":"Hi from OpenAI","response_format":"mp3"}' \
     --output openai.mp3
   ```

### ElevenLabs
1. Set `ELEVENLABS_API_KEY` and enable the provider in the YAML:
   ```yaml
   providers:
     elevenlabs:
       enabled: true
       api_key: ${ELEVENLABS_API_KEY}
       model: "eleven_monolingual_v1"
   ```
2. Use `GET /api/v1/audio/voices/catalog?provider=elevenlabs` to list available voices (includes your custom voices from ElevenLabs).
3. Generate speech (non-streaming shown):
   ```bash
   curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
     -H "X-API-KEY: $SINGLE_USER_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"eleven_monolingual_v1","voice":"rachel","input":"Testing ElevenLabs"}' \
     --output elevenlabs.mp3
   ```

---

## Local Providers

Each section highlights installation, configuration, and a smoke test.

### Kokoro ONNX
- **Install**: Prefer the installer (auto-detects eSpeak NG):
  ```bash
  python Helper_Scripts/TTS_Installers/install_tts_kokoro.py
  ```
  Or manually: `pip install -e ".[TTS_kokoro_onnx]"` and install `espeak-ng`. The env var `PHONEMIZER_ESPEAK_LIBRARY` is only needed for non-standard library paths.
- **Models** (v1.0): download from `onnx-community/Kokoro-82M-v1.0-ONNX-timestamped` — use `onnx/model.onnx` and the `voices/` directory, placed under `models/kokoro/`.
- **Config**:
  ```yaml
  providers:
    kokoro:
      enabled: true
      use_onnx: true
      model_path: "models/kokoro/onnx/model.onnx"
      voices_json: "models/kokoro/voices"
      device: "cpu"  # or "cuda"
  ```
- **Verify**:
  ```bash
  curl -s http://127.0.0.1:8000/api/v1/audio/voices/catalog \
    -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq '.kokoro'
  curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
    -H "X-API-KEY: $SINGLE_USER_API_KEY" \
    -H "Content-Type: application/json" \
    -d '{"model":"kokoro","voice":"af_bella","input":"Local Kokoro test","response_format":"mp3"}' \
    --output kokoro.mp3
  ```

### NeuTTS Air
- **Install**: `pip install -e ".[TTS_neutts]"`; ensure `espeak-ng` is installed for phonemizer support.
- **Config**:
  ```yaml
  providers:
    neutts:
      enabled: true
      backbone_repo: "neuphonic/neutts-air"          # or GGUF variant for streaming
      backbone_device: "cpu"
      codec_repo: "neuphonic/neucodec"
      codec_device: "cpu"
  ```
- **Voice cloning**: every request must include a base64 `voice_reference` clip (3–15 s) plus `extra_params.reference_text` that exactly matches the spoken content.
- **Verify**: use the sample curl from [NeuTTS Runbook](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/NEUTTS_TTS_SETUP.md) and confirm the WAV plays back.

### Chatterbox
- **Install**: `pip install -e ".[TTS_chatterbox]"`; add `.[TTS_chatterbox_lang]` if you plan to enable `use_multilingual`. The repo vendors a `chatterbox/` package, so no extra clone is needed.
- **Models**: cache `ResembleAI/chatterbox` locally with `huggingface-cli download ...`.
- **Config**:
  ```yaml
  providers:
    chatterbox:
      enabled: true
      device: "cuda"
      use_multilingual: false
      disable_watermark: true
      target_latency_ms: 200
  ```
- **Voice cloning**: send `voice_reference` (5–20 s, 24 kHz) and optional `emotion` + `emotion_intensity` to tune delivery.
- **Reference**: see [Chatterbox Runbook](https://github.com/rmusser01/tldw_server/blob/main/Docs/Published/User_Guides/Chatterbox_TTS_Setup.md) for streaming examples and troubleshooting.

### VibeVoice
- **Install**: `pip install -e ".[TTS_vibevoice]"`; clone the upstream repo into `libs/VibeVoice` and `pip install -e .` there. Optional: `bitsandbytes`, `flash-attn`, `ninja` for CUDA optimizations.
- **Config**:
  ```yaml
  providers:
    vibevoice:
      enabled: true
      auto_download: true               # Explicitly enable downloads (default is false)
      model_path: "microsoft/VibeVoice-1.5B"  # or vibevoice/VibeVoice-7B, FabioSarracino/VibeVoice-Large-Q8
      device: "cuda"
      use_quantization: true
      voices_dir: "./voices"
      speakers_to_voices:
        "1": "en-Alice_woman"
  ```
- **Voice cloning**: drop samples into `voices_dir`, upload via API, or send `voice_reference`. Use `extra_params.speakers_to_voices` to map scripted speakers to files or uploaded IDs.
- **Reference**: [VibeVoice Getting Started](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/VIBEVOICE_GETTING_STARTED.md).

### Higgs Audio V2
- **Install**: `pip install -e ".[TTS_higgs]"` and install the upstream repo (`git clone https://github.com/boson-ai/higgs-audio && pip install -e .`).
- **Config**:
  ```yaml
  providers:
    higgs:
      enabled: true
      model_path: "bosonai/higgs-audio-v2-generation-3B-base"
      tokenizer_path: "bosonai/higgs-audio-v2-tokenizer"
      device: "cuda"
      use_fp16: true
  ```
- **Voice cloning**: accepts 3–10 s voice samples at 24 kHz (WAV/MP3/FLAC). Include `voice_reference` + `voice` = `"clone"`.
- **Reference**: [Higgs section](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/TTS-SETUP-GUIDE.md#higgs-audio-v2-setup).

### Dia
- **Install**: `pip install torch torchaudio transformers accelerate nltk spacy` plus `python -m spacy download en_core_web_sm`.
- **Config**:
  ```yaml
  providers:
    dia:
      enabled: true
      model_path: "nari-labs/dia"
      device: "cuda"
      auto_detect_speakers: true
      max_speakers: 5
  ```
- **Usage**: best for dialogue transcripts (`Speaker 1:`, `Speaker 2:`). Supports voice cloning with per-speaker references.

### IndexTTS2
- **Install/Assets**: place model checkpoints + configs under `checkpoints/index_tts2/`. Follow the adapter instructions in [TTS-README](../../tldw_Server_API/app/core/TTS/TTS-README.md#indextts2-adapter) for expected filenames.
- **Config**:
  ```yaml
  providers:
    index_tts:
      enabled: true
      model_dir: "checkpoints/index_tts2"
      cfg_path: "checkpoints/index_tts2/config.yaml"
      device: "cuda"
      use_fp16: true
      interval_silence: 200
  ```
- **Hardware**: plan for 12 GB+ VRAM. Every request must include a `voice_reference` clip (zero-shot cloning).

---

## YAML Configuration Reference

Location precedence (first found is used):
- `tldw_Server_API/Config_Files/tts_providers_config.yaml` (project-level override)
- `tldw_Server_API/app/core/TTS/tts_providers_config.yaml` (in-repo default)
- `./tts_providers_config.yaml` (current working directory)
- `~/.config/tldw/tts_providers_config.yaml` (user config)

Key sections:
- `provider_priority`: ordered list used for fallback
- `providers.<name>`: per-provider settings
  - `enabled` (bool): must be true to initialize
  - `auto_download` (bool): when true, allow HF downloads if local files are missing
  - Model path fields (e.g., `model_path`, `model_dir`, `cache_dir`)
  - Device and performance fields (e.g., `device`, `use_fp16`, `use_quantization`)
- `performance`, `fallback`, `logging`: global behavior

Example (VibeVoice 7B):
```yaml
providers:
  vibevoice:
    enabled: true
    auto_download: true
    variant: "7B"         # or "7B-Q8" for quantized community model
    model_path: "vibevoice/VibeVoice-7B"
    device: "cuda"
```

Environment overrides:
- `TTS_AUTO_DOWNLOAD=1` (global), or `VIBEVOICE_AUTO_DOWNLOAD=1` (provider-specific)
- `TTS_DEFAULT_PROVIDER`, `TTS_DEFAULT_VOICE`, `TTS_DEVICE`, etc.

## Voice Management & Reference Audio
- Upload reusable samples:
  ```bash
  curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/voices/upload \
    -H "X-API-KEY: $SINGLE_USER_API_KEY" \
    -F "file=@/path/to/voice.wav" \
    -F "name=Frank" \
    -F "provider=vibevoice"
  ```
  The API returns a `voice_id`; reuse it via `"voice": "custom:<voice_id>"`.
- Inline references: set `"voice_reference": "<base64 audio>"` directly on the TTS request.
- Duration & quality (see `tldw_Server_API/app/core/TTS/TTS-VOICE-CLONING.md`):
  - Higgs: 3–10 s @ 24 kHz, mono.
  - Chatterbox: 5–20 s @ 24 kHz, mono.
  - VibeVoice: 3–30 s @ 22.05 kHz (adapter resamples).
  - NeuTTS: 3–15 s @ 24 kHz **plus** matching `reference_text`.
  - IndexTTS2: 3–15 s @ 24 kHz, or precomputed `ref_codes`.

---

## Auto-Download & Environment Switches
| Variable | Purpose |
| --- | --- |
| `TTS_AUTO_DOWNLOAD` | Global toggle for all local providers (`1` to allow HF downloads). |
| `KOKORO_AUTO_DOWNLOAD`, `HIGGS_AUTO_DOWNLOAD`, `DIA_AUTO_DOWNLOAD`, `CHATTERBOX_AUTO_DOWNLOAD`, `VIBEVOICE_AUTO_DOWNLOAD` | Per-provider overrides when you need strict offline mode. |
| `TTS_DEFAULT_PROVIDER` / `TTS_DEFAULT_VOICE` | Overrides the provider/voice when the client omits them. |
| `TTS_DEVICE` | Forces a device hint (e.g., `cuda`, `cpu`) across adapters that respect it. |
| `TTS_STREAM_ERRORS_AS_AUDIO` | When `1`, embed adapter errors into the stream (OpenAI compatibility); default `0` for normal HTTP errors. |

All env vars above are documented in `Env_Vars.md`.

---

## Verification Checklist
1. **Provider discovery**
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/audio/providers \
     -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq
   ```
2. **Voice catalog**
   ```bash
   curl -s http://127.0.0.1:8000/api/v1/audio/voices/catalog \
     -H "X-API-KEY: $SINGLE_USER_API_KEY" | jq
   ```
3. **Synthesis smoke test** (replace `model` + `voice` per provider):
   ```bash
   curl -sS -X POST http://127.0.0.1:8000/api/v1/audio/speech \
     -H "X-API-KEY: $SINGLE_USER_API_KEY" \
     -H "Content-Type: application/json" \
     -d '{"model":"kokoro","voice":"af_bella","input":"Hello from tldw_server","response_format":"mp3","stream":true}' \
     --output tts-test.mp3
   ```
4. **WebUI**: Open the Next.js WebUI (`apps/tldw-frontend`) and use the Audio page to pick a provider and synthesize sample text.

---

## Troubleshooting Cheatsheet
- **`ImportError` / missing modules** — re-run the correct extra install (e.g., `pip install -e ".[TTS_vibevoice]"`).
- **Auto-download blocked** — set `TTS_AUTO_DOWNLOAD=0` (or per provider) and pre-populate `models/` via `huggingface-cli download`.
- **`eSpeak` not found** — install `espeak-ng`; on macOS export `PHONEMIZER_ESPEAK_LIBRARY=/opt/homebrew/lib/libespeak-ng.dylib`.
- **CUDA OOM** — enable quantization (VibeVoice), lower `vibevoice_variant`, or move the provider lower in `provider_priority` so lighter backends run first.
- **Voice cloning rejects sample** — ensure duration/sample rate matches provider requirements and send mono audio.
- **401/403** — confirm `X-API-KEY` header (single-user) or Bearer JWT (multi-user) plus upstream API keys.
- **Adapter marked unhealthy** — see logs for circuit-breaker status; restart the server or wait for `performance.adapter_failure_retry_seconds` to elapse.

---

## Additional Resources
- [TTS-SETUP-GUIDE](https://github.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/TTS-SETUP-GUIDE.md) — exhaustive installer for every backend.
- [Getting-Started-STT_and_TTS](https://github.com/rmusser01/tldw_server/blob/main/Docs/Getting-Started-STT_and_TTS.md) — fast-start for OpenAI + Kokoro + STT.
- [TTS-VOICE-CLONING](https://github.com/rmusser01/tldw_server/blob/main/tldw_Server_API/app/core/TTS/TTS-VOICE-CLONING.md) — in-depth reference requirements per provider.
- [TTS-DEPLOYMENT](https://github.com/rmusser01/tldw_server/blob/main/tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md) — GPU sizing, smoke tests, and monitoring.

Use this guide as the high-level checklist, then jump into the linked runbooks for deeper tuning.
