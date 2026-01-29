# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Some kind of Versioning

## [Version] Date

### Added

### Changed

### Removed

### Fixed
- Workspace selector remove handler now uses the imported MouseEvent type instead of the React namespace.



## [0.1.18] 2026-01-25

### Added
- Slides Module
- TTS:
  - Added NeuTTS, PocketTTS (ONNX), EchoTTS, Qwen3-TTS, LuxTTS, VibeVoice-ASR docs; updated streaming/format rules, default voice behavior, and setup guides.
- moved the tldw_Browser_Assistant project and the tldw-frontent folder into the '/apps/' folder, as moving forward they will share the same base.
  - As a result, new frontend!
  - Kanban: vector search integration, activity logging with filtering, rate limiting on endpoints
  - Reading Collections: async import jobs workflow with job monitoring endpoints
  - Workflows: LLM step type with MCP tool allowlist and scope validation
- New monorepo development guide, shared UI package scaffold, ambient typings, and testing guide for extension/web UI.

### Changed
- Workflows Module
  - New "llm" step type (distinct from "prompt")
  - MCP tool allowlist and scope validation
  - Stricter approve/reject permission checks
  - Configurable LLM retry cap
- Admin-UI Updates
- New frontend, tldw-frontend
- New Storage API guide, Voice Assistant API (REST & WebSocket), Watchlists API docs, Anthropic Messages API docs, and expanded /llm/models metadata (image backends & filters).
- Wide-ranging documentation additions and edits (OCR backends, image generation, storage, benchmarks, guides, link dumps, examples).

### Removed
- Legacy webui

### Fixed


## [0.1.17] 2026-01-19

### Added
- File Artifacts System: Comprehensive implementation of file artifact management with support for multiple export formats (iCalendar, Markdown tables, HTML tables, XLSX, data tables) including export lifecycle management, garbage collection, and validation
- Data Tables Module: Complete backend implementation with LLM-based table generation, async job workers, database schema (tables, columns, rows, sources), REST API endpoints, and export functionality
- Media Ingestion Cancellation: Added cancellation support across audio and video processing pipelines with subprocess monitoring and graceful error handling
- Content Import Preservation: Enhanced database layer to preserve existing metadata during reimport operations with preserve_existing_on_null parameter and improved full-text search with fallback candidates
- File Adapter Registry: Dynamic adapter management system supporting multiple file types with validation, normalization, and export capabilities
- Presentation Templates: New Reveal.js slide templates and CSS styling for presentation generation with bundle export support
- API Enhancements: New endpoints for file artifacts management, data table generation/export/management, and media ingest job listing with async job tracking
- Comprehensive Test Coverage: Integration and unit tests for file artifacts, data tables, media ingestion cancellation, and database operations
- NeuTTS Support
- TTS voice registry

### Changed

### Removed

### Fixed


## [0.1.16] - 2026-01-17 / Broken Bugs

### Added
- Jobs Postgres RLS policy setup now supports `JOBS_PG_RLS_DEBUG` for policy output and `JOBS_PG_RLS_ROLE` role overrides.
- Jobs prune scheduler for retention-based cleanup (env-gated, internal scheduler).
- `CHAT_COMMANDS_ASYNC_ONLY` flag to force async chat orchestration (`achat`) and block sync `chat(...)`.
- Chat command concurrency integration test and PERF-gated p50 latency smoke test.

### Changed
- Jobs Postgres tests now default to the shared per-test Postgres fixture by wiring `JOBS_DB_URL` and ensuring Jobs tables/counters.
- Jobs RLS policy setup uses negotiated Postgres DSNs for compatibility across server versions.
- Sync `chat(...)` now offloads to a worker when invoked from a running event loop (non-streaming).

### Removed
- Legacy `command_router.dispatch_command` path (now raises with migration hint).

### Fixed
- Jobs RLS debug output now reports distinct settings fields without clobbering values.
- Fixing of 200+ bugs


## [0.1.15] - 2026-01-10

### Added

### Changed
- Jobs adapters now ignore legacy read-backend flags; Chatbooks/Prompt Studio are core Jobs only, embeddings read fallback is disabled.
- Documentation updated to reflect core Jobs defaults and the current embeddings execution modes.

### Removed

### Fixed
- Legacy AuthNZ rate limiting now bypasses only when an RG policy is attached, and cancellations propagate correctly in rate limit fallbacks.
- ChaChaNotes shutdown now drains default-character tasks and waits for the executor to prevent SQLite close races (fixes Jobs web UI TTL test segfaults).


## [0.1.14] - 2026-01-06

### Added
- Added tldw-admin react frontend for admin Mgmt of the server. Very much WIP. 
- Extended feedback system/schema - Added a unified feedback system (explicit/implicit) across chat and search, integrates message IDs into chat history and streaming, 
- introduced API key KDF/key_id, 
- added admin effective-config endpoint/UI,

### Changed
- Centralized per-user path utilities for storage safety and consistency
- Migrated ingress rate limiting to Resource Governance (RG), removed SlowAPI decorators
- Enhanced feedback system with explicit endpoint, schemas, and idempotent merge rules
- Expanded chat streaming metadata to include system and assistant message IDs
- Integrated UI feedback across chat and search (rating, source feedback, implicit events)
- Updated documentation and configuration for feedback system and config management
- Comprehensive test coverage for feedback, chat metadata, and UI integration

### Removed
- slowapi usage


### Fixed
- Lots of Bugs


## [0.1.13] - 2025-12-29

### Added
- Next.js WebUI (apps/tldw-frontend)
- admin-ui - Full Admin UI: dashboard, users/orgs/teams, roles & permissions, API keys, jobs, usage analytics, budgets, BYOK, flags, incidents, logs, monitoring panels.
- Content Review: draft editor, sidebar, reattach-source flow, commit/review workflows.
- BYOK improvements: scoped resolution, validation, dashboard and key management.
- Option for review of media prior to ingestion.

### Changed
- Claims module expanded

### Removed
- N/A

### Fixed
- Improved frontend/backend error handling and type safety; more robust API interactions.


## [0.1.12] - 2025-12-20

### Added
- Full Kanban API (boards, lists, cards, labels, checklists, comments, import/export, bulk ops, card linking) with hybrid search (FTS vector).
- Self‑service Organizations & Teams (invites preview/redeem) and org admin flows.
- Billing & subscriptions (plans, checkout/portal, invoices, usage) and Stripe webhook handling.
- BYOK (per‑user and shared provider keys) with admin management and testing.
- TTS providers onboarding and user TTS guide.

### Changed
- Adds a full billing/subscription system (plans, limits, Stripe integration, webhooks), BYOK (per‑user and shared provider keys) with admin tooling, invitations/org/team RBAC, a Kanban module with per‑user DB FTS/vector search, many new endpoints/schemas/repos, DB migrations, audit/auth dependency changes, media visibility, and extensive docs/config updates.

### Removed
- A sense of failure.

### Fixed
- 500bugs

## [0.1.11] - 2025-11-27

### Added
- Guidance on stress testing chat server

### Changed
- RAG Documentation

### Removed

### Fixed


## [0.1.10] - 2025-11-27

### Added
- ChaChaNotes health snapshot surfaced in `/api/v1/health` to monitor init attempts/failures and cache state.
- MLX local provider scaffolding (Apple Silicon): adapters admin lifecycle endpoints, metrics parity, and config keys/tests with non-Apple skips.
- `LLM_MLX` extra in `pyproject.toml` to install `mlx-lm`/`mlx` for Apple Silicon users.
- Config-driven llama.cpp handler: `LLMInferenceManager` now constructs `LlamaCppHandler` when `[LlamaCpp]` is enabled in `config.txt` or via env, and `/llamacpp` endpoints are wired to the managed handler.
- ChaChaNotes schema v10 adds conversation metadata (state with `in-progress` default/backfill, topic labels, clusters) plus backlinks on notes (`conversation_id`, `message_id`) with covering indexes and SQLite/Postgres migrations.
- Templated hierarchical chunking for incoming documents/emails across `/api/v1/media/process_*` endpoints, including TemplateClassifier-based auto-selection of chunking templates and optional section trees.
- Streaming chunker/runtime helpers now honor shared chunking options via `prepare_chunking_options_dict`/`apply_chunking_template_if_any` for consistent behavior across document, PDF, video, audio, ebook, and email processing.
- User-facing documentation for templated chunking (`Templated_Chunking_Incoming_Documents_HowTo.md`) and the Project 2025 RAG workflow guide for policy/document ingestion.
- Chat diagnostics endpoints: `GET /api/v1/chat/queue/status` and `GET /api/v1/chat/queue/activity` exposing queue metrics and recent job activity, RBAC-gated to `system.logs` in multi-user mode.

### Changed
- Conversation title search now applies global BM25 normalization so pagination returns stable, deterministic ordering across the entire result set.
- Chunking engine improvements for streaming text and Markdown: better whitespace handling for word/semantic/token chunking and promotion of bold-only headings into hierarchical subsections under their parent section.
- ChaChaNotes dependency now ensures per-user DB directories are created, optional `message_metadata` is initialized, and default-character warmup tasks are tracked so the health snapshot accurately reflects warm starts.
- Llama.cpp integration: `LLMInferenceManager` logs model-directory creation failures instead of silently swallowing them, and `/llamacpp` endpoints resolve the manager from `app.state.llm_manager` (falling back to the module-level instance) with a clear 503 when not configured.
- Workflows and scheduler workflow routers are always mounted (without an `/api/v1` prefix) inside minimal/test apps so tests and tooling can call them consistently.

### Fixed
- ChaChaNotes warmup no longer leaves orphaned default-character tasks; background tasks are tracked and cleaned up when complete, improving shutdown and health reporting.
- Visual document ingestion from audio/video analysis now persists slide/visual artifacts via a thread executor, avoiding event-loop blocking during heavy analysis.
- MLX local provider concurrency: `MLXSessionRegistry.session_scope` snapshots the semaphore per context so dynamic concurrency updates cannot corrupt in-flight sessions.
- Media re-chunking for documents and emails remains best-effort but now logs failures at debug level instead of silently swallowing errors, making template issues easier to diagnose.
- Async chunker and template processor now handle multi-operation stages safely and preserve whitespace between overlapping chunks for all space-delimited methods.
- `/api/v1/health` now logs ChaChaNotes snapshot failures and resource-governance policy file read errors while still reporting a degraded health state instead of failing the endpoint.
- Chat queue status/activity endpoints avoid shadowing FastAPI's `status` module and enforce RBAC correctly, so authentication/authorization failures return the intended HTTP codes instead of spurious 500s.


## [0.1.9]

### Added
- ChaChaNotes health snapshot surfaced in `/api/v1/health` to monitor init attempts/failures and cache state.

### Changed
- ChaChaNotes dependency now initializes in a dedicated executor with WAL/busy-timeout tuning and background default-character creation; request path reduced to cache lookup health probe.
- Startup warms the single-user ChaChaNotes instance to avoid first-request blocking; shutdown now closes cached instances and stops the ChaChaNotes executor to prevent lingering threads.

### Removed

### Fixed


## [0.1.8] - 2025-11-22

### Added
- Auto-streaming for large audit exports exceeding configured threshold
- CSV streaming support for audit exports
- Model discovery for local LLM endpoints
- Audit event replay mechanism for failed exports
- Enhanced HTTP error handling for DNS resolution failures
- SuperSonicTTS support setup script
- STT:
  - `get_stt_config()` helper in `config.py` to centralize resolution of `[STT-Settings]` for all STT modules.
  - Documentation for `speech_to_text(...)` (segment-based) and `transcribe_audio(...)` (waveform-based) as the two canonical STT entrypoints, including guidance on error sentinel handling.

### Changed
- Audio:
  - Replace Parakeet-specific transcriber/config usage with unified UnifiedStreamingTranscriber/UnifiedStreamingConfig; add _LegacyWebSocketAdapter to adapt legacy WS to unified handler; defer imports and update tests to use unified stubs.
  - Move desktop/live audio helpers (LiveAudioStreamer, system-audio utilities) into `Audio/ARCHIVE/Desktop_Live_Audio_Samples.py` so core STT modules no longer depend on optional PyAudio/sounddevice at import time.
- Audit:
  - Add config-driven auto-stream threshold, support streaming for json/jsonl/csv, force streaming when max_rows exceeds threshold; CSV streaming generator; non-stream export caps; API-key hashing; fallback JSONL queue with background replay task; tests for streaming and replay.
- LLM:
  - Add local model discovery (short timeouts, TTL cache, candidate endpoints), get_configured_providers_async and integrate async provider loading into startup and web UI config; provider payloads include is_configured and endpoint_only.
- TTS
  - WAV output now buffered and deferred until finalize with in-memory threshold and disk spill; StreamingAudioWriter.__init__ adds max_in_memory_bytes; tests validate spill and finalize behavior.
- Web Scraping
  - Use defusedxml, broaden sitemap parse error handling, add test-mode egress bypass, add conditional process_web_scraping_task import/export, and preserve HTTPException semantics in ingestion endpoint.
- Tests
  - Extensive test updates (unified WS stub, fake HTTP client for RSS, env snapshot/restore, admin override fixtures, watchlists full-app fixture, connectors pre-mounting); CI embedding cache key changed to a static key.
  - STT unit tests for Parakeet/Qwen2Audio `return_language` branches now exercise the provider branches directly and avoid unintended Whisper fallbacks by normalizing file-path arguments.

### Removed
- Hopes, Dreams.

### Deprecated
- Efficiency.

### Fixed
- Improved WebSocket disconnect handling
- Consistent error handling in session cleanup and web ingestion
- Better network error resilience with graceful fallbacks
- Add _is_dns_resolution_error detection and mark DNS resolution errors non-retriable (DNSResolutionError signal); tests verify DNS errors are not retried while other network errors follow retry policy.
- My life.


## [0.1.6] - 2025-11-14
### Fixed
- HTTP-redirect loop
- test bugs

### Added
- Option for HTTP redirect adherence in media ingestion endpoints added in config.txt


## [0.1.5] - 2025-11-13
### Fixed
- Ollama API system_prompt
- Other stuff

### Added
- Updated WebUI
- Added PRD/initial work for cli installer/setup wizard
  - Auto-title notes
- Notes Graph CRUD
- Documentation/PRDs
- (From Gemini) New Chatbook Tools: Implemented a suite of new tools for Chatbooks, including sandboxed template variables for dynamic content in chat dictionary replacements, user-invoked slash commands (e.g., /time, /weather) for pre-LLM context enrichment, and a comprehensive dictionary validation tool (CLI and API) to lint schemas, regexes, and template syntax.


## [0.1.4] - 2025-11-9
### Fixed
- Numpy requirement in base install
- Default API now respected via config/not just ENV var.
- Too many issues to count.

### Added
- Unified requests module
- Added Resource governance module
- Moved all streaming requests to a unified pipeline (will need to revisit)
- WebUI CSP-related stuff
- Available models loaded/checked from `model_pricing.json`
- Rewrote TTS install/setup scripts (all TTS modules are likely currently broken)


## [0.1.3.0] - 2025-X
### Fixed
- Bugfixes
-

## [0.1.2.0] - 2025-X
### Fixed
- Bugfixes


## [0.1.1.0] - 2025-X
### Breaking
- Prometheus scraping for MCP metrics now requires authentication with the `system.logs` permission; `MCP_PROMETHEUS_PUBLIC` no longer enables public access, is deprecated, and will be removed. Migration: update Prometheus scrape configs to send a Bearer token (API key or JWT) that includes `system.logs` (see `Docs/Deployment/Monitoring/Metrics_Cheatsheet.md` migration note and scrape_config example).
### Features
- Version 0.1
### Fixed
- Use of gradio
