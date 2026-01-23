# PRD: Echo-TTS Adapter (Streaming, Caching, CUDA-Only)

## Problem Statement
Users want Echo-TTS available through the unified TTS registry so they only supply model/config (similar to Kokoro/PocketTTS). Echo-TTS must support streaming audio generation, cache repeated speaker conditioning, and enforce CUDA-only usage by default.

## Goals
- Add a new `echo_tts` provider adapter in the TTS registry.
- Enable non-streaming and streaming generation through existing `/api/v1/audio/*` endpoints.
- Require voice reference audio (speaker conditioning) and reuse it across requests via an LRU cache.
- Enforce CUDA-only usage; adapter refuses to initialize without CUDA.

## Non-Goals
- Training or fine-tuning Echo-TTS models.
- UI changes beyond existing endpoints.
- A generic streaming engine for all providers (Echo-TTS only).

## User Stories
- As a user, I can send `/audio/speech` with `model: "echo-tts"` and get audio without specifying an adapter.
- As a user, I can stream Echo-TTS audio via `/audio/stream/tts` without waiting for the full render.
- As an admin, I can enable Echo-TTS via config and set defaults for model and sampling parameters.

## Functional Requirements

### 1) Provider Registration
- Add `ECHO_TTS` to `TTSProvider` enum.
- Register adapter in `DEFAULT_ADAPTERS`.
- Add model aliases in `MODEL_PROVIDER_MAP`:
  - `echo-tts`, `echo_tts`, `jordand/echo-tts-base`.

### 2) Provider Config
- New provider config under `providers.echo_tts` in TTS YAML/config.
- Alias mapping in registry similar to Kokoro/PocketTTS:
  - `model` -> `echo_tts_model`
  - `model_path` -> `echo_tts_model_path`
  - `device` -> `echo_tts_device`
  - `module_path` -> `echo_tts_module_path` (default `../echo-tts`)
  - `sample_rate` -> `echo_tts_sample_rate` (default 44100)
  - `extra_params` for sampler settings (see below)
  - `cache_size`, `cache_ttl_sec`

### 3) Model Loading
- Adapter loads:
  - `EchoDiT` model via `load_model_from_hf()`.
  - Fish autoencoder via `load_fish_ae_from_hf()`.
  - PCA state via `load_pca_state_from_hf()`.
- If import fails, insert `module_path` into `sys.path` (like PocketTTS).
- Lazy initialization with an async lock.
- Echo-TTS requires CUDA. If `device == "cpu"` or CUDA is unavailable, adapter must refuse to initialize with a clear error.
- If `device == "auto"`, resolve to `cuda` (do not silently fall back to CPU).

### 4) Voice Reference Handling (Required)
- `voice_reference` is required for every request (no "no-reference" preset).
- Accept `voice_reference` bytes or base64.
- Process with `process_voice_reference_async()`:
  - Validate duration (1-300s).
  - Convert to 44.1 kHz mono WAV.
- If missing or invalid, raise `TTSInvalidVoiceReferenceError` and return HTTP 422 (unprocessable entity).

### 5) Request Mapping
- `TTSRequest.extra_params` used for:
  - `num_steps`, `cfg_scale_text`, `cfg_scale_speaker`
  - `cfg_min_t`, `cfg_max_t`
  - `sequence_length`
  - `truncation_factor`, `rescale_k`, `rescale_sigma`
  - `speaker_kv_scale`, `speaker_kv_min_t`, `speaker_kv_max_layers`
  - `fish_ae_repo`, `pca_state_file`
  - `normalize_text` (default true)
- Enforce a UTF-8 byte-length cap for text input:
  - Max 767 bytes (BOS token adds 1 to reach 768).
  - If exceeded, raise `TTSValidationError` and return HTTP 422.

### 6) Streaming (Blockwise)
- Implement `generate_stream()` using Echo-TTS blockwise sampling.
- Use `inference_blockwise.sample_blockwise_euler_cfg_independent_guidances`, but note it returns a full latent tensor today.
- Streaming plan:
  - Implement an internal blockwise loop (copy/refactor blockwise logic) that yields one block at a time.
  - Split `sequence_length` into fixed internal block sizes (no config surface).
  - For each block:
    - Run blockwise sampler with continuation latents.
    - Decode block latents via AE.
    - Normalize to int16 PCM, convert to requested format with `StreamingAudioWriter`.
    - Yield bytes per chunk.
  - Call `StreamingAudioWriter` finalize once after the last block to avoid multiple headers/trailers.
- If blockwise module missing, disable streaming in capabilities and return a clear error if streaming is requested.

### 7) Caching
- LRU cache keyed by:
  - Hash of processed voice_reference bytes + model + device + sample_rate.
- Cache values:
  - `(speaker_latent, speaker_mask)` tensors.
- Default storage: CPU tensors; move to GPU on hit (reduces VRAM pressure).
- Optional config flag `cache_on_device=true` to keep tensors on GPU.
- `cache_size` default 8; `cache_ttl_sec` default 3600.
- Integrate with `tts_resource_manager`:
  - If memory is critical, bypass cache inserts and evict oldest entries.
- Size estimate (default): speaker_latent ~ (1, 6400, 80) float32 ~= 2 MB + mask; 8 entries ~= ~16-20 MB on CPU (smaller in bf16).
- On hit, skip `get_speaker_latent_and_mask()`.

### 8) Validation
- Update `tts_validation.py`:
  - `MAX_TEXT_LENGTHS["echo_tts"] = 768`
  - `SUPPORTED_LANGUAGES["echo_tts"] = {"en"}`
  - `SUPPORTED_FORMATS["echo_tts"] = {MP3, WAV, FLAC, OPUS, AAC, PCM}`
- Add voice reference requirements in `audio_utils.py`.
- Add explicit `echo_tts` rule: `voice_reference` is required; missing value returns 422 with a clear error message.

### 9) Capabilities
- `supports_streaming = True` if blockwise is available.
- `supports_voice_cloning = True` and voice reference required.
- `sample_rate = 44100`.
- `default_format = WAV`.

## Non-Functional Requirements
- Latency: streaming should emit first audio chunk within ~3-5s on CUDA.
- Memory: cache size configurable; no unbounded growth.
- Reliability: adapter failures must not crash service; use existing fallback logic.

## API Surface (Unchanged Endpoints)
- `/api/v1/audio/speech`:
  - `model: "echo-tts"` routes to Echo-TTS adapter.
  - `voice_reference` required; missing value returns HTTP 422.
  - `extra_params` accepted and forwarded.
- `/api/v1/audio/stream/tts`:
  - Same request format; streaming yields audio chunks.
- `/api/v1/audio/providers` and `/voices/catalog`:
  - Echo-TTS shows as provider; no fixed voice catalog.

## Dependencies
- Add new optional extra in `pyproject.toml`:
  - `TTS_echo_tts = ["torch>=2.x", "torchaudio>=2.x", "torchcodec>=0.8.1", "safetensors", "huggingface_hub"]`
- Optional: add to installer (`TTS_ENGINES`, `TTS_DEPENDENCIES`).

## Telemetry / Logging
- Log:
  - Adapter init (device, repo, sample_rate).
  - Streaming fallback (if blockwise missing).
- Metrics:
  - Reuse existing TTS metrics (provider label `echo_tts`).

## Testing Plan
- Unit:
  - Provider registry mapping for `echo_tts`.
  - Config alias mapping.
  - LRU cache hit/miss behavior.
  - Voice reference required error.
- Integration:
  - `/audio/speech` with `model=echo-tts` returns audio when voice_reference is provided.
  - `/audio/stream/tts` yields chunks on GPU.
  - Missing voice_reference returns validation error.
- Performance:
  - Streaming chunk latency on GPU.
  - Cache reduces repeated request time.

## Rollout / Docs
- Add Echo-TTS section to TTS docs (setup + config example).
- Default: disabled unless explicitly enabled in config.

## Acceptance Criteria
- Sending `/audio/speech` with `model: "echo-tts"` and voice_reference returns valid audio.
- Streaming returns multiple chunks and finalizes correctly.
- Repeated voice_reference reduces latency due to cached speaker_latent.
- `device="auto"` resolves to `cuda` and fails fast if CUDA is unavailable.
