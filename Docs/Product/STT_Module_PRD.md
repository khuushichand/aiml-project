**STT Module PRD v1.0**

- **Meta**
  - Owner: Core Voice & API Team
  - Status: In Progress (see `Docs/Product/STT_Module_IMPLEMENTATION_PLAN.md` for staged execution and status details)
  - Implementation Progress:
    - Provider registry + adapters implemented (`stt_provider_adapter.py`) and used by REST `/api/v1/audio/transcriptions`, ingestion persistence, and Jobs (CPU and GPU workers).
    - Normalized STT artifact shape in place (`to_normalized_stt_artifact`, adapter `transcribe_batch`) and used internally by REST, `/media/add` ingestion, and Jobs; transcripts now upserted into `Transcripts` keyed by `(media_id, whisper_model)` with the full artifact stored in `Transcripts.transcription`.
    - Unified batch helpers for ingestion and Jobs (`run_stt_batch_via_registry`, `run_stt_job_via_registry`) wired into `perform_transcription` and `audio_jobs_worker`/`audio_transcribe_gpu_worker`; remaining WS streaming/metrics work are still pending.

- **Project Summary**
  - Speech-to-Text (STT) powers `/api/v1/audio/transcriptions` and `/api/v1/audio/stream/transcribe`.
  - Current providers live under `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/` and include faster-whisper (CPU/GPU), NVIDIA NeMo (Parakeet/Canary), and Qwen2Audio.
  - The STT module should unify these providers, expose consistent REST/WebSocket behaviors, and integrate cleanly with Jobs, Media ingestion, Embeddings, and AuthNZ.

- **Problem Statement**
  Contributors need a single, predictable STT subsystem that accepts uploaded or streamed audio, selects the appropriate provider, and yields normalized transcripts plus metadata suitable for RAG pipelines. Current state: REST + WS parity exists, PCM TTS is available, and STT/TTS/voice-to-voice metrics are wired. Remaining gaps: turn detection/auto-commit, phoneme/lexicon overrides for Kokoro, an optional WS TTS endpoint, and a documented harness to validate latency end-to-end.

- **Goals**
  - Complete turn detection/auto-commit in unified WS STT for lower final latency (fail-open if VAD unavailable).
  - Add phoneme/lexicon overrides for Kokoro (per-request/provider/global precedence).
  - Add optional WS TTS endpoint with backpressure/auth parity.
  - Provide a small latency harness (voice-to-voice) and refreshed docs so contributors can validate the metrics that now exist.
  - Keep unified provider interface and deterministic REST/WS behavior with normalized transcript artifacts (timestamps, diarization, confidence, language detection) and existing observability intact.

- **Non-Goals**
  - No SIP ingestion, telephony gateways, or mobile SDKs in this release.
  - No training or fine-tuning workflows; assume pre-trained models.
  - No automatic summarization of transcripts (handled by downstream RAG).

- **Primary Users**
  - Backend contributors extending STT or adding providers.
  - Worker authors (GPU/CPU) using the Jobs/worker helpers (informally the Worker SDK).
  - QA engineers writing API and WebSocket tests.
  - DevOps configuring deployments and monitoring.

- **Use Cases**
  - Upload or URL-based transcription returning transcript + job artifact.
  - Live streaming transcription with partial results and controllable latency.
  - Background jobs triggered by media ingestion (priority queue).
  - Benchmarking/evaluation across providers (accuracy, latency).
  - Replay transcripts for downstream embeddings and RAG.

- **Functional Requirements**
  - Provider abstraction located in `app/core/Ingestion_Media_Processing/Audio` implements batch, stream, diarization, and capability discovery.
  - REST STT endpoint (`/api/v1/audio/transcriptions`) handles multipart uploads (OpenAI-compatible); URL-based and yt-dlp flows remain in media ingestion endpoints that call into the shared STT module.
  - Streaming endpoint supports partial/interim updates and final transcripts, accepts `auth`/`config`/`audio`/`commit` messages as in the current unified WS implementation, and respects lease/quota enforcement; any additional status/warning frames remain backward compatible with existing clients.
  - Transcript schema includes segments with timestamps, speaker labels, confidence, optional diarization, and usage stats; shape aligns with the existing REST/WS schemas, with optional extra metadata for diagnostics.
  - Persist transcripts and metadata into Media DB v2: normalized STT artifacts (including `text`, `segments`, `language`, `diarization`, `usage`, `metadata`) serialized into the `Transcripts` table (`transcription`), keyed by `(media_id, whisper_model)` (provider/model), with `Media.transcription_model` tracking the effective/default model. Segments/chunks are written via `MediaChunks`/`UnvectorizedMediaChunks`; ingestion result JSON continues to carry transcript content/segments in the established shape and may include `normalized_stt` for internal consumers.
  - Config-driven defaults with request-level overrides (bounded validation).
  - Rate limiting via RG ingress policies plus per-provider thresholds.
  - Retry/backoff policy with provider-specific fatal vs retriable errors; fallbacks must not mask auth/quota/validation failures and should be configurable per environment.
  - Metrics and audit: emit `audio.stt.*` counters/histograms, hook into unified audit service for lifecycle events; STT/TTS/voice-to-voice metrics labels documented.
  - Failure modes: fail-open when VAD/diarization unavailable (log once, continue streaming) rather than blocking; record a clear metric/log label when operating in fail-open mode so latency/quality are interpreted correctly.
  - Worker SDK updates: strict worker_id/lease_id enforcement, explicit completion tokens, provider context metadata.

- **Non-Functional Requirements**
  - Performance: on the reference setup described in `Docs/Product/STT-IMPLEMENTATION_PLAN.md`, target p50 <10s latency for a 5-minute clip on GPU-backed models; target p50 <250ms end-of-speech → partial-result latency for unified WS streaming. Reference setup is: 8-core CPU, optional NVIDIA GPU (Parakeet GPU path), macOS 14 or Ubuntu 22.04, Python 3.11, ffmpeg ≥6.0, av ≥11.0.0, localhost loopback, 10s 16 kHz float32 single-speaker fixture with 250 ms trailing silence.
  - Accuracy: allow measurement hooks for WER; prefer baseline comparisons or non-blocking checks over hard per-provider thresholds in unit tests.
  - Scalability: multi-worker queue processing, horizontal scaling with Jobs; avoid single-node bottlenecks.
  - Resilience: fallback from GPU to CPU or alternate provider with clear logging.
  - Security: authenticated endpoints (API key/JWT), MIME/type validation, file size limits, sanitized metadata.
  - Compatibility: Python 3.10+, works on macOS/Linux/Windows; GPU use optional.
  - Observability: structured logging (loguru), trace correlation, optional OpenTelemetry when available.

- **Architecture Overview**
  1. **API Layer (`app/api/v1/endpoints/audio.py`)**
     - Validates requests, resolves provider, triggers Jobs or direct processing.
     - Shared schemas in `schemas/audio_schemas.py` to keep OpenAPI consistent.
  2. **Service Layer (`app/services/audio_transcribe_*` and helpers in `app/core/Ingestion_Media_Processing/Audio/`)**
     - Provider selection, chunking, diarization, metadata assembly.
     - Works with Jobs manager for background processing; streaming path handled via WebSocket handler.
  3. **Providers (modules such as `Audio_Transcription_Lib.py`, `Audio_Transcription_Nemo.py`, `Audio_Transcription_External_Provider.py`)**
     - Implement provider logic; expose capability metadata, config parsing, health checks.
  4. **Workers (`app/services/audio_jobs_worker.py`, `audio_transcribe_gpu_worker.py`)**
     - Poll Jobs queue, enforce leases, call providers, push transcripts, emit metrics.
  5. **Storage & Integration**
     - Media DB (`Media_DB_v2`) for transcript storage, `UnvectorizedMediaChunks` for pending embedding data.
     - Embeddings pipeline triggered on completion when configured.
     - Audit bridge logs creation/completion/failure events when audit enabled.
  6. **Observability**
     - Metrics: counters, histograms; logs with request IDs; optional audit records.

- **Provider Specifications**
  - Provider registry with configuration metadata (name, model, streaming support, hardware requirements), backed by a concrete adapter interface (e.g., `SttProviderAdapter` in `app/core/Ingestion_Media_Processing/Audio`).
  - Standard adapter methods (final names to match the implementation): synchronous/async batch entry point (e.g., `transcribe_batch`), streaming entry point (e.g., `transcribe_stream` or equivalent chunk handler), optional `detect_language`, and `healthcheck` for readiness.
  - Config via config loader (`core/config`) reading `.env` and `config.txt` `[STT-Settings]`, with defaults for beam size, temperature, chunk length, and device/variant selection per provider.
  - Fallback order: try preferred provider, then a bounded, explicitly configured fallback chain depending on capabilities and error type (never fallback on auth/quota/validation errors).

- **Data Contracts**
  - **Transcription Response**
    ```
    {
      "text": str,
      "language": str,
      "segments": [
        {"start": float, "end": float, "speaker": str | None, "confidence": float | None, "text": str}
      ],
      "diarization": {"enabled": bool, "speakers": int | None},
      "usage": {"duration_ms": int, "tokens": int | None},
      "metadata": {"provider": str, "model": str, "queue_latency_ms": int, ...}
    }
    ```
  - Internal normalized artifact: this response shape is used inside ingestion/Jobs as the normalized STT transcript; the public OpenAI-compatible `/api/v1/audio/transcriptions` endpoint continues to use the `OpenAITranscriptionResponse` schema in `audio_schemas.py`.
  - **Streaming Events**: partial/interim results (e.g., `partial`/`transcription`), final/full transcripts (e.g., `final`/`full_transcript`), and `error` frames as in the current unified WS implementation; additional `status`/`warning` frames may be emitted for diagnostics (e.g., diarization/VAD availability, persistence issues) without breaking existing clients.
  - **Job Payload**: audio reference, provider override, diarization flag, chunk config, audit context.
  - **Database Fields**: transcripts stored in `Transcripts.transcription` (keyed by `media_id` and provider/model) with `Media.transcription_model` tracking the effective model; segments/chunks persisted via `MediaChunks`/`UnvectorizedMediaChunks` when chunking is enabled.

- **Configuration & Deployment**
  - Process environment: provider API keys and STT-related env flags (e.g., `STT_SKIP_AUDIO_PREVALIDATION`, transcript-cache bounds); see `tldw_Server_API/Config_Files/README.md` and `Docs/Published/Env_Vars.md` for the curated list. Optional `.env` / `Config_Files/.env` files may be loaded via the existing config/secret helpers.
  - `Config_Files/config.txt` `STT-Settings` section: default provider/transcriber, diarization boolean, streaming toggles, buffering and model-variant settings, prompt biasing if needed.
  - Feature flags: `STT_ENABLE_DIARIZATION`, `STT_STREAMING_ENABLED`, `STT_DEBUG_DUMP_AUDIO` (debug dumping is dev/test only, writes into a configurable debug directory, and must remain disabled in shared/production deployments).
  - Deployment checklist: FFmpeg installed, CUDA (optional), model weights downloaded, Jobs workers configured, network egress allowed for remote providers.

- **Testing Strategy**
  - Unit tests: provider adapters (success, failure, retry, parameter validation), chunking helpers, metadata cleaning (no empty arrays).
  - Integration tests: REST upload using small fixtures, Jobs pipeline end-to-end, WebSocket streaming (use deterministic mock provider).
  - Property tests: ensure timestamps monotonic, segments cover audio duration, transcripts normalized (no control chars).
  - Contract tests: DB writes align with schema; ensure transcripts survive round-trip.
  - Load tests (optional): evaluate throughput under concurrency.
  - CI: default to mock providers; allow opt-in runs with real providers (guarded by env).
  - Manual QA: real audio on GPU, long-form streaming with network interruptions, diarization accuracy sampling.

- **Metrics & Observability**
  - Counters: track STT requests, streaming sessions, and errors (including per-provider successes/failures) via the central metrics manager.
  - Histograms: `stt_final_latency_seconds{model,variant,endpoint}`, `tts_ttfb_seconds{provider,voice,format}`, `voice_to_voice_seconds{provider,route}`.
  - Gauges: active workers, GPU memory usage (if available).
  - Logs: include request/job ID, provider, timing, errors.
  - Audit: create, updated, failed transcripts recorded when audit bridge enabled.
  - Alerts: high error rate, backlog growth, extreme latency, no transcripts returned.

- **Security & Privacy**
  - Input validation: MIME/type check, duration limit, safe temporary storage, optional virus scan hook.
  - Authentication: enforce API key/JWT per AuthNZ mode.
  - Secret handling: never log raw keys; sanitize provider responses.
  - Data retention: config to delete original audio after transcription; redact transcripts if `STT_REDACT_PII` enabled (future).
  - Multi-tenant: respect user IDs in path sanitization, separate storage directories.

- **Dependencies & Integration Points**
  - Jobs manager (enqueue, lease, completion).
  - Worker SDK (lease enforcement, metrics).
  - Media ingestion & DB (store transcripts).
  - Embeddings service (optional follow-up).
  - AuthNZ settings (single user vs multi).
  - Filesystem for temp storage; FFmpeg/yt-dlp for preprocessing.
  - Config loader (`core/config`) for provider settings.

- **Milestones**
  1. **M1 - Turn Detection/Auto-Commit**: Silero VAD-driven turn detection in unified WS STT; auto-commit finals within target latency on reference audio (fail-open if VAD missing).
     - **Acceptance**: On the reference fixture, p50 `stt_final_latency_seconds` for unified WS STT ≤ 600ms with VAD enabled; fail-open mode emits a clear metric/log label and does not regress quotas/auth.
     - **Status**: Implemented in unified WS path (fail-open); needs real-world threshold tuning + doc polish.
  2. **M2 - Phoneme/Lexicon Overrides**: configurable pronunciation maps for Kokoro with safe defaults and precedence rules; demo request shows changed pronunciation.
     - **Acceptance**: Given a documented test phrase and phoneme map, Kokoro output changes as expected in at least one integration fixture; added latency from applying overrides is ≤ 5% vs baseline on the reference setup.
     - **Status**: Not started.
 3. **M3 - Optional WS TTS**: `/api/v1/audio/stream/tts` with backpressure/auth/quota parity and PCM streaming; passes slow-reader/disconnect tests. Ownership split with TTS PRD; delivery blocked until TTS team signs off.
     - **Acceptance**: p50 `tts_ttfb_seconds` over WS ≤ 200ms on the reference setup; slow-reader and disconnect tests complete without resource leaks and emit `audio_stream_underruns_total`/error metrics as expected.
     - **Status**: Not started (coordination with TTS PRD required).
 4. **M4 - Docs & Harness**: refreshed STT/TTS docs plus a lightweight voice-to-voice latency harness consuming existing metrics; documented CLI/outputs.
     - **Acceptance**: `Helper_Scripts/voice_latency_harness/run.py --out out.json --short` (or equivalent) runs against the reference setup and outputs JSON with at least p50/p90 for `stt_final_latency_seconds`, `tts_ttfb_seconds`, and `voice_to_voice_seconds`; short mode suitable for CI; docs reference the harness and the VAD/metrics knobs.
     - **Status**: Not started (metrics are wired; harness outstanding).

- **Risks & Mitigations**
  - Provider downtime/unavailability → multi-provider fallbacks, local deterministic mock, error escalation.
  - GPU resource contention → configurable concurrency, CPU fallback, preflight health checks.
  - Large audio causing timeouts → enforce max duration, chunk processing with partial saves, send progress updates.
  - Streaming resource leaks → ensure queue shutdown, WebSocket cleanup, tests verifying teardown.
  - Sensitive data in transcripts → provide configuration for redaction or manual review before storage.

- **Open Questions**
  1. Should prompt biasing/custom vocabulary be part of v1 or deferred?
  2. How aggressively do we support diarization (default on/off, provider coverage)?
  3. Where should transcripts live when multiple transformations occur (versioning, delta storage)?
  4. Do we ship sample models/providers as dev dependencies or expect manual installation?
  5. How do we expose quality metrics (WER) to contributors-CI dashboards, logs, or manual scripts?

- **Documentation Deliverables**
  - `/Docs/Audio_STT_Module.md`: architecture, provider setup, API/WS diagrams, troubleshooting.
  - Sample worker scripts (e.g., `Helper_Scripts/Samples/Jobs/batch_worker_example.py` as a template for STT workers).
  - Integration examples for REST & WebSocket clients.
  - Troubleshooting matrix (common errors, diagnostics, remediation).
  - Migration notes for legacy Gradio STT flows.

- **Future Work & vNext**
  - Additional enhancements that go beyond the current implementation—richer WS STT control/status protocol, explicit transcript run history, extended streaming diagnostics, STT-specific retention/PII knobs, and more granular STT metrics—are tracked in `Docs/Product/STT_Module_vNext_PRD.md` and, for end-to-end voice latency and WS TTS, in `Docs/Product/Realtime_Voice_Latency_PRD.md`.
