**STT Module PRD v1.0**

- **Project Summary**
  - Speech-to-Text (STT) powers `/api/v1/audio/transcriptions` and `/api/v1/audio/stream/transcribe`.
  - Current providers live under `tldw_Server_API/app/core/Ingestion_Media_Processing/Audio/` and include faster-whisper (CPU/GPU), NVIDIA NeMo (Parakeet/Canary), and Qwen2Audio.
  - The STT module should unify these providers, expose consistent REST/WebSocket behaviors, and integrate cleanly with Jobs, Media ingestion, Embeddings, and AuthNZ.

- **Problem Statement**
  Contributors need a single, predictable STT subsystem that accepts uploaded or streamed audio, selects the appropriate provider, and yields normalized transcripts plus metadata suitable for RAG pipelines. The current implementation mixes provider-specific logic, lacks full streaming parity, and provides limited observability.

- **Goals**
  - Unified provider interface for batch and streaming STT with plug-and-play expansion.
  - Deterministic REST & WS behavior (same features, shared validation, consistent outputs).
  - Rich transcript artifacts: timestamps, speaker labels, confidence, diarization flags, language detection.
  - Robust operational profile: retries, queue integration, observability, audit support.
  - Reproducible developer experience-fixtures, docs, and tests that don’t depend on proprietary hardware.

- **Non-Goals**
  - No SIP ingestion, telephony gateways, or mobile SDKs in this release.
  - No training or fine-tuning workflows; assume pre-trained models.
  - No automatic summarization of transcripts (handled by downstream RAG).

- **Primary Users**
  - Backend contributors extending STT or adding providers.
  - Worker authors (GPU/CPU) using the Worker SDK.
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
  - REST endpoint handles multipart uploads and remote links (yt-dlp pipeline).
  - Streaming endpoint supports partial results, clients can pause/resume/stop, respects lease enforcement.
  - Transcript schema includes segments with timestamps, speaker labels, confidence, optional diarization, usage stats.
  - Persist transcripts and metadata into Media DB (`Media.transcript`, accompanying `analysis_details`, chunk tables).
  - Config-driven defaults with request-level overrides (bounded validation).
  - Rate limiting via SlowAPI/global plus per-provider thresholds.
  - Retry/backoff policy with provider-specific fatal vs retriable errors.
  - Metrics and audit: emit `audio.stt.*` counters/histograms, hook into unified audit service for lifecycle events.
  - Worker SDK updates: strict worker_id/lease_id enforcement, explicit completion tokens, provider context metadata.

- **Non-Functional Requirements**
  - Performance: <10s latency for 5-minute clip on GPU; <250ms token latency for streaming partials.
  - Accuracy: allow measurement hooks for WER; enforce provider-specific thresholds in tests.
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
  - Provider registry with configuration metadata (name, model, streaming support, hardware requirements).
  - Standard methods: `transcribe_batch`, `transcribe_stream`, `detect_language`, `healthcheck`.
  - Config via `.env`/`config.txt` with defaults for beam size, temperature, chunk length.
  - Provide local stubs/mocks (e.g., text fixture provider) for offline testing.
  - Fallback order: try preferred provider, fallback chain depending on capabilities.

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
  - **Streaming Events**: `start`, `partial`, `final`, `error`, `end` with same segment structure.
  - **Job Payload**: audio reference, provider override, diarization flag, chunk config, audit context.
  - **Database Fields**: transcripts stored in `Media.transcript`, segments in analysis JSON, chunk tables updated if chunking on.

- **Configuration & Deployment**
  - `.env` / `Config_Files/.env`: `DEFAULT_STT_PROVIDER`, provider API keys, `STT_MAX_FILE_SIZE_MB`, concurrency caps, `STT_FORCE_CPU`.
  - `Config_Files/config.txt` `STT-Settings` section: default provider, diarization boolean, streaming toggles, prompt biasing if needed.
  - Feature flags: `STT_ENABLE_DIARIZATION`, `STT_STREAMING_ENABLED`, `STT_DEBUG_DUMP_AUDIO`.
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
  - Counters: `audio.stt.requests`, `audio.stt.streaming_sessions`, `audio.stt.errors`, per-provider successes/failures.
  - Histograms: `audio.stt.latency`, `audio.stt.queue_wait`, `audio.stt.streaming_token_latency`.
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
  1. **M1 - Baseline Documentation & Inventory**: capture current STT endpoints, provider configurations, and worker topology in docs; ensure contributors know existing touchpoints.
  2. **M2 - Provider Interface Formalization**: refactor existing providers under a shared interface, add deterministic mock provider for CI.
  3. **M3 - Streaming Parity**: finalize WebSocket pipeline (partial results, flow control, acknowledgement semantics).
  4. **M4 - Persistence & Audit Enhancements**: diarization metadata, chunk table updates, audit event coverage.
  5. **M5 - Observability & Testing Improvements**: metrics instrumentation, fixtures, offline evaluation scripts.
  6. **M6 - Performance Tuning & Benchmarks**: GPU/CPU profiling, regression thresholds, publish benchmark scripts.

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
