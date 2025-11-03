# TTS (Text-to-Speech) Module

## 1. Descriptive of Current Feature Set

- Purpose: Unified, production-grade TTS across local and cloud engines with OpenAI-compatible APIs, streaming, and voice management.
- Capabilities:
  - Multi-provider adapters: OpenAI, ElevenLabs, Kokoro (local ONNX), Higgs, Dia, Chatterbox, VibeVoice, IndexTTS2, NeuTTS; mock provider for tests.
  - Streaming-first synthesis with graceful fallback and configurable error streaming-as-audio.
  - Voice cloning support and user voice management (upload, list, delete, preview).
  - Unified config with provider priority and per-provider settings; env/config.txt/YAML layering.
  - Metrics, rate limiting, and scope-aware auth on endpoints.
- Inputs/Outputs:
  - Input: Text and optional voice reference metadata; OpenAI-compatible JSON (see schema).
  - Output: Streaming or buffered audio bytes in mp3, opus, aac, flac, wav, or raw pcm.
- Related Endpoints:
  - tldw_Server_API/app/api/v1/endpoints/audio.py:249 — POST /api/v1/audio/speech
  - tldw_Server_API/app/api/v1/endpoints/audio.py:1131 — GET /api/v1/audio/voices/catalog
  - tldw_Server_API/app/api/v1/endpoints/audio.py:1957 — POST /api/v1/audio/voices/upload
  - tldw_Server_API/app/api/v1/endpoints/audio.py:2031 — GET /api/v1/audio/voices
  - tldw_Server_API/app/api/v1/endpoints/audio.py:2066 — GET /api/v1/audio/voices/{voice_id}
  - tldw_Server_API/app/api/v1/endpoints/audio.py:2103 — DELETE /api/v1/audio/voices/{voice_id}
  - tldw_Server_API/app/api/v1/endpoints/audio.py:2142 — POST /api/v1/audio/voices/{voice_id}/preview
- Related Schemas:
  - tldw_Server_API/app/api/v1/schemas/audio_schemas.py:44 — OpenAISpeechRequest
  - tldw_Server_API/app/core/TTS/voice_manager.py:74 — VoiceUploadRequest
  - tldw_Server_API/app/core/TTS/voice_manager.py:89 — VoiceInfo
  - tldw_Server_API/app/core/TTS/voice_manager.py:104 — VoiceUploadResponse

Provider support snapshot (indicative): OpenAI (cloud), ElevenLabs (cloud, cloning), Kokoro (local), Higgs/Dia/Chatterbox/VibeVoice/NeuTTS (local, cloning), IndexTTS2 (cloud/local). See adapters/ for exact capabilities.

## 2. Technical Details of Features

- Architecture & Data Flow:
  - Entrypoint `TTSServiceV2` orchestrates provider selection, fallback, and streaming; adapters implement provider specifics.
  - `TTSAdapterRegistry` lazily resolves adapters from dotted paths, honors enablement, and manages retry windows for failed initializations.
  - `tts_validation` sanitizes text and validates voice references before generation; `voice_manager` enforces provider-specific sample constraints and quotas.
  - `tts_resource_manager` tracks shared resources (HTTP clients, temp files, memory/GPU) and performs cleanup; circuit breakers guard providers.
- Key Classes/Functions:
  - tldw_Server_API/app/core/TTS/tts_service_v2.py:1 — TTSServiceV2, get_tts_service_v2()
  - tldw_Server_API/app/core/TTS/adapter_registry.py:1 — TTSAdapterRegistry, TTSProvider
  - tldw_Server_API/app/core/TTS/adapters/base.py:1 — TTSAdapter interface and request/response models
  - tldw_Server_API/app/core/TTS/tts_validation.py:1 — Input validation utilities
  - tldw_Server_API/app/core/TTS/voice_manager.py:1 — Upload, registry, quotas for voices
- Configuration:
  - YAML: tldw_Server_API/app/core/TTS/tts_providers_config.yaml:1 (providers, priority, performance, fallback, logging)
  - Config file: `Config_Files/config.txt` → [TTS-Settings] (default provider/voice/speed/device)
  - Environment:
    - `TTS_STREAM_ERRORS_AS_AUDIO` — override streaming error behavior
    - Secrets via `${ENV_VAR}` in YAML
- Concurrency & Performance:
  - Global semaphore `performance.max_concurrent_generations` (default 4); provider-specific limits may apply inside adapters.
  - Streaming chunk size and connection pools are configurable; backoff on retryable failures; optional caching hooks.
- Error Handling:
  - Rich exception taxonomy in `tts_exceptions.py` with retry classification; circuit breaker integration; optional streaming of errors as audio.
- Security:
  - Endpoints use `require_token_scope` and per-route rate limits; inputs validated and sanitized; uploads validated for type/size/path.
- Metrics:
  - Registered counters/histograms (e.g., `tts_requests_total`, `tts_request_duration_seconds`, `tts_fallback_attempts`, text length/audio size metrics) via Metrics registry.

## 3. Developer-Related/Relevant Information for Contributors

- Folder Structure:
  - adapters/ — concrete providers (cloud + local) using `adapters/base.py` contract
  - tts_service_v2.py — orchestration (selection, fallback, streaming, metrics)
  - adapter_registry.py — registry/factory and provider enum
  - tts_config.py — unified configuration manager (env/config.txt/YAML)
  - voice_manager.py — user voice storage/validation/quotas + preview
  - audio_converter.py, streaming_audio_writer.py — format conversion and stream shaping
- Extension Points:
  - Add a provider by creating `adapters/<name>_adapter.py` implementing `TTSAdapter` methods, register in `adapter_registry.py` (enum + DEFAULT_ADAPTERS), and add defaults to YAML.
  - Expose capabilities and supported formats via `get_capabilities()` so voice catalog and routing behave correctly.
- Tests:
  - Suites: `tldw_Server_API/tests/TTS/`, `tldw_Server_API/tests/TTS_NEW/`
  - Run: `python -m pytest tldw_Server_API/tests/TTS -v` and `python -m pytest tldw_Server_API/tests/TTS_NEW -v`
  - Adapters: see `tldw_Server_API/tests/TTS/adapters/` for mocks and integration stubs.
- Local Dev Tips:
  - Verify ffmpeg and soundfile availability; configure provider keys in `.env` or YAML; set `TTS_STREAM_ERRORS_AS_AUDIO=0` to use HTTP error codes during development.
  - Quick synth: POST `/api/v1/audio/speech` with `OpenAISpeechRequest` JSON; for streaming, set `stream=true`.
- Pitfalls & Gotchas:
  - Some providers require specific sample rates or short reference durations (e.g., Higgs 3–10s); voice uploads enforce provider constraints.
  - Missing or misconfigured adapters are skipped after failure; optional retry window controlled by `adapter_failure_retry_seconds`.
  - Quotas/rate limits may short-circuit requests; check Usage/Audio quota logs when debugging.
- Roadmap/TODOs:
  - AllTalk adapter; adaptive chunk shaping; provider health probes and proactive warmups; richer voice metadata unification.

Example: programmatic usage

```python
from tldw_Server_API.app.core.TTS.tts_service_v2 import get_tts_service_v2
from tldw_Server_API.app.api.v1.schemas.audio_schemas import OpenAISpeechRequest

async def synthesize():
    service = await get_tts_service_v2()
    req = OpenAISpeechRequest(input="Hello from TLDW", model="tts-1", voice="alloy", response_format="mp3", stream=True)
    async for chunk in service.generate_speech(req):
        handle(chunk)
```

Additional References

- tldw_Server_API/app/core/TTS/TTS-DEPLOYMENT.md:1
- tldw_Server_API/app/core/TTS/TTS-VOICE-CLONING.md:1
- Docs/STT-TTS/TTS-SETUP-GUIDE.md:1
- Docs/Design/TTS_Module_PRD.md:1

