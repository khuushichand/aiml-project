# Text-to-Speech (TTS) Module - Developer PRD

## 1. Background
- The TTS stack powers `/api/v1/audio/speech` as an OpenAI-compatible endpoint with streaming and non-streaming modes (`tldw_Server_API/app/api/v1/endpoints/audio/audio_tts.py`).
- `TTSServiceV2` orchestrates provider selection, validation, generation, fallback, and metrics while adapters encapsulate individual providers (`tldw_Server_API/app/core/TTS/tts_service_v2.py`).
- A unified configuration layer merges YAML, `config.txt`, and environment overrides to enable/disable providers and tune performance (`tldw_Server_API/app/core/TTS/tts_config.py`, `tldw_Server_API/Config_Files/tts_providers_config.yaml`).
- Voice management supports upload, encode, list, get, delete, and preview of custom voices for cloning-capable engines (`tldw_Server_API/app/api/v1/endpoints/audio/audio_voices.py`, `tldw_Server_API/app/core/TTS/voice_manager.py`).
- Refactor phases 1-2 completed (exceptions, validation, resource manager, circuit breaker); phases 3-5 (testing, observability, hardening) remain open (`Docs/Development/TTS-Refactor-3.md`).

## 2. Objectives & Success Criteria
- Deliver a production-ready, extensible TTS layer with pluggable providers, real-time streaming, and voice cloning.
- Maintain API compatibility with OpenAI Speech endpoints while exposing richer provider-specific options.
- Guarantee resilient failover when a provider is unavailable via circuit breaker + retries.
- Track key metrics (latency, fallback counts, audio sizes) to support capacity planning.
- Ensure local providers respect resource limits (VRAM, disk, concurrency) with predictable cleanup.
- Provide a clear integration surface for contributors adding adapters, voices, or tooling.

## 3. Personas & Use Cases
- **LLM Application Developer**: needs OpenAI-compatible TTS for immediate integration plus toggles for local/offline fallbacks.
- **Audio Researcher / Power User**: experiments with custom voices, new local providers, and fine-grained provider settings.
- **Ops / SRE**: monitors provider health, enforces quotas, and performs incident response when upstream APIs fail.
- **Contributor / Adapter Author**: adds new providers or extends validation/voice tooling while staying aligned with project conventions.

## 4. Scope
### In Scope
- Request validation, sanitization, and provider-specific limit enforcement (`tts_validation.py`).
- Provider abstraction via adapter registry + factory (`adapter_registry.py`) including fallback order and capability discovery.
- Real-time and batch synthesis, audio encoding, and streaming utilities (`waveform_streamer.py`, `streaming_audio_writer.py`).
- TTS endpoints for speech generation, metadata, and long-form job submission/artifacts (`audio_tts.py`).
- Voice management endpoints (upload/encode/list/get/delete/preview) with quota enforcement and provider-specific preprocessing (`audio_voices.py`, `voice_manager.py`).
- Configuration ingestion from YAML/config.txt/env plus runtime overrides (`tts_config.py`).
- Resource management for HTTP pools, memory, and concurrency caps (`tts_resource_manager.py`).
- Circuit breaker and retry behaviours for provider failover (`circuit_breaker.py`).

### Out of Scope (v1)
- Automated per-request caching, response deduplication, or CDN integration.
- Cross-user shared voice libraries or enterprise tenancy isolation.
- Hard real-time SLAs >30 req/s per node without horizontal scaling plan.
- Provider onboarding workflows (self-service UI) beyond current config-driven approach.
- Audio analytics beyond existing metrics (e.g., phoneme scoring, MOS evaluation).

## 5. Architecture Overview
1. **API Layer** (`audio.py`, `audio_tts.py`, `audio_voices.py`)
   - Converts OpenAI JSON payloads to `TTSRequest`, injects auth/rate limits, and streams generator output.
   - Offers speech and management endpoints: `/speech`, `/speech/metadata`, `/speech/jobs`, `/speech/jobs/{job_id}/artifacts`, `/providers`, `/voices/catalog`, `/voices/upload`, `/voices/encode`, `/voices`, `/voices/{id}`, `/voices/{id}/preview`.
2. **Service Layer** (`tts_service_v2.py`)
   - Validates requests, selects adapters from registry, enforces concurrency (`asyncio.Semaphore`), and wraps calls in circuit breaker.
   - Handles fallback attempts, metrics emission, and optional “error-as-audio” compatibility mode.
3. **Adapter Registry & Factory** (`adapter_registry.py`)
   - Lazily instantiates adapters using dotted-path spec and merged config.
   - Tracks provider status to avoid repeated initialization attempts.
4. **Adapters** (`app/core/TTS/adapters/*.py`)
   - Implement provider-specific authentication, API/model invocation, streaming, and capability reporting.
   - Current adapters: OpenAI, ElevenLabs, Kokoro, Higgs, Dia, Chatterbox, VibeVoice, NeuTTS (plus TODO placeholders).
5. **Resource Manager** (`tts_resource_manager.py`)
   - Manages HTTP connection pools, GPU/CPU memory checks, streaming session accounting, and graceful shutdown.
6. **Circuit Breaker** (`circuit_breaker.py`)
   - Tracks failure rates, enforces exponential backoff, and coordinates half-open probing before re-enabling providers.
7. **Configuration & Voice Mapping** (`tts_config.py`, `tts_providers_config.yaml`, `Config_Files/config.txt`)
   - Defines provider priority, voice aliases, fallback rules, and performance logging.
8. **Voice Manager** (`voice_manager.py`)
   - Stores user voices under `<USER_DB_BASE_DIR>/<uid>/voices`, performs format/duration validation, and exposes preview integration.
   - `USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root). Override via environment variable or `Config_Files/config.txt` as needed.

## 6. Functional Requirements
### 6.1 API Surface
- **POST `/api/v1/audio/speech`**: Generate speech; supports `stream`, `voice_reference`, `extra_params`, `response_format`, `return_download_link`.
- **POST `/api/v1/audio/speech/metadata`**: Generate speech and return metadata payload when available.
- **POST `/api/v1/audio/speech/jobs`**: Submit long-form TTS job.
- **GET `/api/v1/audio/speech/jobs/{job_id}/artifacts`**: List generated artifacts for a long-form TTS job.
- **GET `/api/v1/audio/voices/catalog`**: Aggregate voice listings across providers with optional filter.
- **POST `/api/v1/audio/voices/upload`**, **POST `/api/v1/audio/voices/encode`**, **GET `/api/v1/audio/voices`**, **GET/DELETE `/api/v1/audio/voices/{voice_id}`**, **POST `/api/v1/audio/voices/{voice_id}/preview`**: Manage user-uploaded voices with rate limiting.
- **GET `/api/v1/audio/providers`**: Introspect provider capabilities.

### 6.2 Provider Abstraction & Selection
- Primary provider determined via request `model` or configured default; registry honours `provider_priority` and `fallback` rules.
- Adapters must implement:
  - `initialize()`, `get_capabilities()`, `generate()`, `generate_stream()`.
  - Provider metadata: default voices, supported formats, streaming support (`adapters/base.py`).
- Circuit breaker integrates with adapters to classify errors and trip per provider; fallback attempts recorded via metrics.
- Resource manager ensures HTTP clients and model sessions respect concurrency + memory thresholds.

### 6.3 Voice Management & Cloning
- Upload pipeline validates filename, size, duration, format, and provider-specific constraints; converts audio into provider-compatible form.
- Registry keeps in-memory mapping per user; filesystem persists originals and processed artifacts using the generated UUID prefixed to the sanitized filename (for example, `voice_id_filename.ext`).
- Preview endpoint uses requested provider and stored voice reference to synthesize sample audio via `TTSServiceV2`.

### 6.4 Validation & Security
- `tts_validation.py` sanitizes text (XSS/SQL/command injection patterns), enforces per-provider max text length, format, voice, speech rate bounds.
- Voice reference bytes validated for MIME, size, duration; rejects unsupported content.
- Speech and voice endpoints leverage FastAPI deps for JWT/API-key auth, endpoint-level rate limiting (`check_rate_limit`), scope checks (`require_token_scope`), and quota enforcement for uploads.
- Config-specified provider enablement gating ensures disabled providers cannot be invoked.

### 6.5 Observability & Metrics
- Metrics registry records:
  - `tts_requests_total`, `tts_request_duration_seconds`, `tts_audio_size_bytes`, `tts_text_length_characters`, `tts_active_requests`, `tts_fallback_attempts`.
- Logging config options (`tts_providers_config.yaml`) control verbosity, request/response logging, and performance metrics toggles.

### 6.6 Streaming & Audio Encoding
- Streaming path writes chunked audio via `StreamingAudioWriter` while optionally normalizing waveform data.
- Non-streaming path accumulates encoded bytes before responding.
- `OpenAISpeechRequest.stream` defaults to `True` for compatibility; `stream_errors_as_audio` toggle controls error emission mode.

## 7. Non-Functional Requirements
- **Performance**: default `max_concurrent_generations` = 4; target <1.5s latency for short (<200 tokens) OpenAI requests; streaming chunk cadence ~200ms.
- **Reliability**: Circuit breaker thresholds configurable; fallback attempts limited by `fallback.max_attempts`, `retry_delay_ms`.
- **Scalability**: Adapters must free resources on shutdown; resource manager monitors memory/connection usage; horizontal scaling requires sticky caches disabled by default.
- **Security & Compliance**: Respect AuthNZ roles, enforce upload quotas, sanitize inputs, avoid logging raw voice data or API keys.
- **Resilience**: Provide best-effort fallback to local/offline providers when cloud APIs fail; degrade gracefully when all providers unavailable.
- **Testing**: Maintain unit + integration coverage for adapters, service, validation, voice manager; property tests exist for audio chunking (`tldw_Server_API/tests/TTS_NEW`).

## 8. Configuration & Deployment
- YAML (`tts_providers_config.yaml`) defines provider priority, enablement, model paths, auto-download flags, fallback + logging settings.
- `Config_Files/config.txt` `[TTS-Settings]` supplies defaults for legacy paths (OpenAI voice, ElevenLabs params, local device).
- Environment overrides (`TTS_AUTO_DOWNLOAD`, `KOKORO_AUTO_DOWNLOAD`, etc.) prevail at runtime (`Docs/STT-TTS/TTS-SETUP-GUIDE.md`).
- System dependencies: `ffmpeg`, `espeak-ng` for normalization, optional GPU toolchains (CUDA, flash-attn) per provider doc.
- Python extras: `pyproject.toml` defines `TTS_All`, `TTS_kokoro`, etc. for selective installs.

## 9. Data & Storage
- Voice uploads stored under `<USER_DB_BASE_DIR>/<user_id>/voices/{uploads,processed,temp,metadata}` with per-voice metadata JSON files (`voice_manager.py`).
- Runtime voice registry remains in-memory, but it is synchronized from shared filesystem snapshots for list/get/delete/rate-limit paths to keep multi-instance views consistent.
- Voice delete lifecycle removes processed/upload files, removes metadata JSON, and best-effort unregisters `generated_files` voice_clone entries to keep storage accounting aligned.
- Provider runtime artifacts (models, caches) follow paths in YAML/config; respect auto-download toggles to avoid surprise network calls.

## 10. Integrations & Dependencies
- External APIs: OpenAI, ElevenLabs (HTTP via `httpx`).
- Local models: Kokoro ONNX, Higgs (Transformers), Dia, Chatterbox, VibeVoice, NeuTTS (vendored packages under `tldw_Server_API/app/core/TTS/vendors`).
- Resource manager relies on `aiohttp`/`httpx` pools, GPU memory introspection (torch), disk monitoring.
- Voice processing uses `ffmpeg`/`ffprobe` via subprocess for duration checks.

## 11. Testing Strategy
- Existing suites (`tldw_Server_API/tests/TTS_NEW`) cover service initialization, adapter mocks, streaming, provider management, plus adapter-specific unit tests.
- Voice-manager unit coverage includes filesystem-sync behavior for external add/remove, cold-registry delete recovery, and filesystem-backed voice-count limits.
- Remaining open debt (per Phase 3 plan):
  - Validation edge cases, dangerous pattern detection.
  - Resource manager limits and circuit breaker state transitions.
  - Integration smoke tests per provider (mock HTTP, local model fixtures).
- CI should run with `TTS_AUTO_DOWNLOAD=0` to avoid network, leveraging mocks/fakes.
- Add property-based tests for waveform streaming and voice upload sanitization to guard regressions.

## 12. Monitoring & Operations
- Metrics exported via central registry; ensure Prometheus/Grafana dashboards include TTS counters/gauges.
- Circuit breaker exposes stats (failure count, state) for ops inspection; consider dedicated health endpoint in future.
- Logs: turn on request/performance logging in config when debugging provider issues; default INFO-level recommended.
- Rate limits: speech and voice routes are limiter-decorated; monitor for abuse and quota evasion patterns.

## 13. Risks & Open Issues
- Configuration duplication (YAML vs `config.txt`) still needs consolidation + validation schema.
- Test coverage incomplete for new exception/resource/circuit components.
- Provider auto-download may still trigger unintended network calls if toggles misconfigured.
- Adapter TODOs: AllTalk stub, provider-specific features (emotion control, SSML) not fully exposed.
- Observability gaps: no structured tracing, fallback successes not correlated with upstream error categories yet.

## 14. Roadmap
- **Near Term (Phase 3)**:
  - Unify config pipeline with validation + explicit precedence rules.
  - Expand unit/integration tests for validation edge cases, resource manager, and circuit breaker transitions.
  - Add provider-level integration smoke tests (mock-first with local fixtures where practical).
  - Implement retry logic with exponential backoff and health-check endpoint.
  - Enhance logging + metrics (provider error taxonomy, streaming duration).
- **Mid Term (Phase 4)**:
  - Implement response caching/batching hooks.
  - Optimize local model lifecycle (lazy load/unload, memory reclamation).
  - Publish operations runbook + provider setup docs updates.
  - Add rate limiting per API key + audit logging for voice operations.
- **Long Term (Phase 5)**:
  - Load testing across providers with failover scenarios.
  - Persistent voice registry backing store (SQLite/DB) for multi-node deployments.
  - Remove legacy `OLD_*` TTS files, finalize documentation, and certify production readiness checklist.
