# PRD: Supertonic ONNX TTS Provider (Current State + Gaps)

## 1. Overview

This PRD documents the **current implementation state** of the Supertonic ONNX TTS provider and identifies remaining gaps for follow-up work.

- Provider key: `supertonic`
- Adapter class: `SupertonicOnnxAdapter`
- Scope in this PRD:
  - What is already implemented and shipped
  - Behavioral contracts that must remain stable
  - Explicit gaps/future work and de-risk checklist

This document supersedes "new implementation" framing for Supertonic v1.

## 2. Status Summary

### 2.1 Implemented (as of current code)

- Adapter implemented: `tldw_Server_API/app/core/TTS/adapters/supertonic_adapter.py`
- Registry + enum wiring implemented:
  - `TTSProvider.SUPERTONIC`
  - default adapter mapping in `adapter_registry.py`
- Model-to-provider routing implemented in `TTSAdapterFactory.MODEL_PROVIDER_MAP`:
  - `tts-supertonic-1`
  - `supertonic`
  - `supertonic-onnx`
- Provider hint inference implemented:
  - `tldw_Server_API/app/core/Audio/tts_service.py`
  - `tldw_Server_API/app/services/audiobook_jobs_worker.py`
- Provider validation limits implemented in `tts_validation.py`
- Provider config block implemented in `Config_Files/tts_providers_config.yaml`
- Installer helper exists:
  - `Helper_Scripts/TTS_Installers/install_tts_supertonic.py`

### 2.2 Not Yet Implemented / Deferred

- True incremental low-latency streaming from Supertonic engine (current mode is pseudo-streaming)
- Production-grade GPU path with explicit capability guarantees
- Batch generation API for multi-segment/multi-voice requests

## 3. Product Goals (Current)

- Keep Supertonic as a first-class local provider in the unified TTS stack.
- Preserve compatibility with OpenAI-style `/api/v1/audio/speech` requests.
- Expose Supertonic voices in unified voice catalog endpoints.
- Maintain clear local-first behavior: no provider-side network inference.

## 4. Current Architecture Fit

### 4.1 Integration Points

- Adapter contract: `tldw_Server_API/app/core/TTS/adapters/base.py`
- Supertonic adapter: `tldw_Server_API/app/core/TTS/adapters/supertonic_adapter.py`
- Registry/factory/model routing: `tldw_Server_API/app/core/TTS/adapter_registry.py`
- Validation and provider limits: `tldw_Server_API/app/core/TTS/tts_validation.py`
- Audio endpoint routing + sanitization flow:
  - `tldw_Server_API/app/api/v1/endpoints/audio/audio_tts.py`
  - `tldw_Server_API/app/core/Audio/tts_service.py`
- Config source: `tldw_Server_API/Config_Files/tts_providers_config.yaml`

### 4.2 Provider Identity

- Logical provider key: `supertonic`
- Display/provider capability name: `Supertonic`
- Default model alias for docs/examples: `tts-supertonic-1`

## 5. Functional Behavior (Normative)

### 5.1 Request Mapping

Supertonic uses the standard `TTSRequest` fields:

- `text`
- `voice`
- `format` (supported: `mp3`, `wav`)
- `speed`
- `stream`
- `extra_params.total_step` (quality/speed tradeoff)

### 5.2 Request-Level Path Overrides (Security Decision)

Request-level path overrides are **not allowed**.

- Disallowed request parameters:
  - `extra_params.onnx_dir`
  - `extra_params.voice_style_file`
  - any other request-provided filesystem path selector for Supertonic assets
- Asset paths must come from server config only:
  - provider `model_path`
  - provider `extra_params.voice_styles_dir`

Rationale: prevent path-based abuse and keep trust boundaries server-side.

### 5.3 Speed Behavior (Final Decision)

Supertonic speed is **reject-only**, not clamp-and-continue.

- Allowed range: `0.9 <= speed <= 1.5`
- If outside range, validation fails with HTTP 400 via `TTSValidationError` path.
- Tests and docs must treat this as the single supported behavior.

Note: `TTSRequest.__post_init__` applies global envelope clamping, but provider-aware validation uses original requested speed and rejects out-of-range values for Supertonic.

### 5.4 Streaming Semantics

- `supports_streaming=True` is supported as **pseudo-streaming**:
  - Full audio synthesized first
  - Encoded bytes chunked and yielded asynchronously
- Expected TTFB is closer to non-streaming engines than true incremental streaming engines.

### 5.5 Voice Mapping and Defaults

- Voices are loaded from configured `voice_files` mapping (`voice_id -> filename`).
- Missing non-default mapped voice file: skipped with warning.
- Missing default voice style file: initialization error (`TTSModelNotFoundError`).

### 5.6 Concurrency and Safety

- Engine invocation is lock-protected (`asyncio.Lock`) to avoid concurrent unsafe access.
- Model/voice style loading failures surface as typed TTS exceptions.

## 6. Configuration Contract

Current canonical shape (already present in config file):

```yaml
providers:
  supertonic:
    enabled: false
    model_path: "models/supertonic/onnx"
    sample_rate: 24000
    device: "cpu"
    extra_params:
      voice_styles_dir: "models/supertonic/voice_styles"
      default_voice: "supertonic_m1"
      voice_files:
        supertonic_m1: "M1.json"
        supertonic_f1: "F1.json"
      default_total_step: 5
      default_speed: 1.05
      n_test: 1
```

Implementation notes:

- Keep `enabled: false` in default config to avoid broken out-of-box startup on hosts without assets.
- `sample_rate` should align with engine-reported sample rate unless explicitly tested otherwise.

## 7. Validation Contract

Provider limits for `supertonic` must remain aligned across:

- `ProviderLimits.LIMITS["supertonic"]`
- `TTSInputValidator.MAX_TEXT_LENGTHS["supertonic"]`
- `TTSInputValidator.SUPPORTED_LANGUAGES["supertonic"]`
- `TTSInputValidator.SUPPORTED_FORMATS["supertonic"]`

Current expected limits:

- max text length: 15000
- languages: `en`
- formats: `mp3`, `wav`
- speed: `0.9` to `1.5` (reject-only)

## 8. Testing Expectations

### 8.1 Unit

- Adapter init success with mocked vendor functions
- Missing ONNX dir -> `TTSModelNotFoundError`
- Missing default voice style -> `TTSModelNotFoundError`
- Non-default missing style -> warning + skip behavior
- Generate path returns bytes for `wav` and `mp3`
- Streaming path yields multiple chunks
- Speed outside `[0.9, 1.5]` for provider -> validation failure (no clamp behavior test)

### 8.2 Integration

- `/api/v1/audio/speech` model alias routing to Supertonic provider
- `stream: true` returns chunked response bytes
- `/api/v1/audio/voices/catalog` includes Supertonic voices when assets/config enabled

## 9. Known Gaps / Future Work

- True incremental streaming from engine output
- Explicitly tested GPU execution path and capability reporting
- Batch API design and workload scheduling semantics
- Expanded language/format support only after engine-level validation

## 10. De-Risk Checklist (Pre-Merge)

- [ ] Ensure this PRD remains framed as **current state + gaps**, not a new implementation plan.
- [ ] Remove any language suggesting Supertonic enum/adapter/registry/config/installer still need to be added.
- [ ] Keep provider-hint references pointed to:
  - `tldw_Server_API/app/core/Audio/tts_service.py`
  - `tldw_Server_API/app/services/audiobook_jobs_worker.py`
- [ ] Remove/forbid any request-level path override examples (`onnx_dir`, `voice_style_file`, etc.).
- [ ] Keep Supertonic speed behavior explicitly **reject-only (400)** for out-of-range values.
- [ ] Keep test guidance aligned: no clamp-and-continue test cases for Supertonic speed.
- [ ] Keep default config snippet with `enabled: false`.
- [ ] Keep section numbering/order consistent.

## 11. Non-Goals

- Training or fine-tuning Supertonic models
- Bundling or redistributing proprietary model assets in repository
- Voice cloning via Supertonic in current scope

## 12. Licensing and Distribution

- The project ships integration code only.
- Users must obtain and place Supertonic model/style assets according to upstream license/terms.
- Installer helper is opt-in and must not run automatically.
