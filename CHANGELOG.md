# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to Some kind of Versioning


## [Version] Date

### Added
-

### Changed
-

### Removed
- 

### Fixed
-


## [0.1.21] 2026-02-X

### Added
- New security and regression tests for:
  - Scheduler payload format/ref validation and legacy compatibility behavior.
  - Web dedupe JSON persistence and controlled legacy migration.
  - Placeholder-service guardrails and route isolation.
  - Loguru formatting guardrail.
- Operations runbook documenting secure defaults, compatibility flags, and migration steps.
- Added a startup/CI route guard that fails fast when duplicate `(path, method)` routes are registered.
- Added regression tests for duplicate-route detection, CORS guardrails, ULTRA_MINIMAL health routing, and OpenAPI CORS behavior.
- Skills
  - End-to-end Skills API workflow tests covering create, list/get, versioned update with supporting-file add/remove, execute preview, context payload, export, zip re-import, delete, and seed flows.
  - Seed endpoint integration test coverage for idempotency (`overwrite=false`) and overwrite restoration (`overwrite=true`).
  - Deterministic unit tests for built-in skill seeding: recursive directory copy (including nested files), no-overwrite preservation, and overwrite replacement behavior.
- Admin Backup Bundles
  - Added API contract coverage for admin bundle import error detail shapes:
  - `restore_failed` responses must return structured `detail` objects (`error_code`, `message`, optional `rollback_failures`).
  - Standard import validation failures (for example checksum mismatches) must continue returning string `detail`.
- Web UI/Extension UX audit gating and regression coverage:
  - Added Stage 2 route-contract smoke spec for audited navigation destinations.
  - Added Stage 3 rendering-resilience smoke spec for max-depth, template-leak, and retry/timeout assertions.
  - Added Stage 4 mobile-sidebar and accessibility smoke specs, plus Axe high-risk route matrix coverage.
  - Added Stage 5 audited-route release gate smoke spec and `e2e:smoke:stage5` script.
  - Added deterministic admin smoke fixture profile/route mocks to remove skip behavior and backend-state dependency.
- UX gate process updates:
  - Added PR checklist items for UX smoke gate, console-budget checks, and WebUI/extension parity validation.
  - Added shared sanitized server-error message utility with correlation-ID log-hint support for user-facing error states.
  - Added dedicated core route identity regression tests for `/`, `/setup`, and `/onboarding-test`.
  - Added media route guard/boundary coverage for `media-multi` and `media-trash` paths.
  - Added knowledge QA golden-layout and interaction guardrails to preserve high-quality search/history UX.
  - Added workspace/playground positive-pattern guardrail tests (Data Tables, Evaluations, Chunking, Workspace desktop layout).
  - Added explicit home theme-toggle control and associated unit/E2E coverage.

### Changed
- Normalized Loguru formatting across tldw_Server_API/app from %-style placeholders to {} style.
- Added CI/test guard to prevent reintroduction of %-style Loguru placeholders.
- Sync client defaults now align with server routes (`/api/v1/sync/send` and `/api/v1/sync/get`) and support configurable auth headers (`Authorization` bearer and `X-API-KEY`).
- Moved local LLM manager initialization out of import-time setup into lifespan startup, with lazy initialization behavior where applicable.
- ULTRA_MINIMAL mode now uses control-plane health endpoints only (`/health`, `/ready`, `/health/ready`) to avoid duplicate route ownership.
- Skills
  - `SkillsService.seed_builtin_skills()` now copies full built-in skill directories recursively instead of recreating skills from `SKILL.md` only.
  - Seed overwrite flow now force-syncs registry state and handles pre-existing soft-deleted rows before copy.
- Admin Backup Bundles
  - Admin bundle create/import concurrency control now uses an atomic non-blocking lock path to fail fast with `409 bundle_operation_in_progress` instead of race-prone check-then-acquire behavior.
  - Bundle import disk-space preflight now checks all real write targets (system temp, upload temp location, and live DB target directories from manifest datasets).
  - `retention_hours` is now enforced for bundle creation: expired bundles are pruned after create within the same bundle scope (`user_id` scoped, including global `None` scope).
  - Bundle import success/dry-run payloads now consistently include `rollback_failures` for schema stability.
- Circuit Breaker
  - Unified admin circuit breaker endpoint: `GET /api/v1/admin/circuit-breakers` with RBAC protection (`admin` role + `system.logs` permission), deterministic sorting, and filters (`state`, `category`, `service`, `name_prefix`).
  - Unified admin circuit breaker response contract with explicit `source` values: `memory`, `persistent`, and `mixed`.
  - Cross-worker HALF_OPEN probe lease coordination in shared registry storage, including lease TTL, cleanup, and release-on-completion behavior.
  - Optimistic-lock conflict observability metric: `circuit_breaker_persist_conflicts_total{category,service,operation,mutation}`.
  - New endpoint test coverage for admin circuit breaker listing, filtering, and authorization behavior.
  - Circuit breaker shared-state persistence now uses bounded merge/retry semantics on optimistic-lock conflicts to avoid dropping local mutations under contention.
  - Circuit breaker operator documentation now includes new env knobs and tuning guidance:
    - `CIRCUIT_BREAKER_REGISTRY_MODE`
    - `CIRCUIT_BREAKER_REGISTRY_DB_PATH`
    - `CIRCUIT_BREAKER_PERSIST_MAX_RETRIES`
    - `CIRCUIT_BREAKER_HALF_OPEN_LEASE_TTL_SECONDS`
  - Monitoring/admin docs now explicitly describe `source="mixed"` as expected when persistence is enabled for active in-process breakers.
  - Circuit breaker unification PRD status updated to reflect implemented state and delivered hardening follow-on work.
- Web UI/Extension parity:
  - Shared `WebLayout` now defaults to collapsed rail on mobile (`<768px`) and opens navigation via header drawer toggle.
  - Shared media-query initialization now reads `matchMedia` on first client render to prevent desktop-rail flash on mobile.
  - Section 2 audited wrong-content routes now resolve to intended content or explicit “Coming Soon” placeholders instead of silent misrouting.
  - Changed settings information architecture to be more navigable, searchable, and less badge-saturated, with tighter route-to-page mapping.
  - Changed settings routing to restore/cover `/settings/ui`, `/settings/image-generation`, and `/settings/image-gen` behavior via proper wrappers/alias handling.
  - Changed guardian settings behavior to show explicit unsupported-endpoint guidance instead of noisy repeated backend failures.
  - Changed admin route behavior so admin sub-routes render route-specific content/placeholder contracts instead of collapsing to Server Admin.
  - Changed admin diagnostics presentation to human-readable units for memory/byte and retry-window values.
  - Changed admin error handling to sanitize implementation details and gate controls when prerequisites are missing.
  - Changed chat disconnected-state messaging to remove redundancy and provide one clear user path.
  - Changed chat agent empty-state/workspace affordances to clarify prerequisites and next steps.
  - Changed chat mobile composer/toolbars to enforce 44x44 touch targets and improve control discoverability.
  - Changed chat/persona language from jargon (`k=n`) to user-facing memory-result wording.
  - Changed `/chat/settings` behavior to canonical redirect (`/chat/settings` -> `/settings/chat`) and aligned strict release-gate expectations.
  - Changed audio route identity so `/tts`, `/stt`, and `/speech` have distinct intended surfaces.
  - Changed TTS/STT/Speech loading lifecycle to include explicit timeout, actionable error states, and retry UX.
  - Changed workspace/playground mobile copy and layout behavior, including Sources tab wording, chunking mobile order, and workflow-editor responsive drawer behavior.
  - Changed workflow editor control semantics with improved labeling/aria clarity and consistent LLM casing.
  - Changed flashcards/quiz/kanban/watchlists/documentation empty/content states for intent clarity and first-use correctness.
  - Changed media/knowledge/characters/chatbooks error states to be recoverable, actionable, and sanitized.
  - Changed core onboarding/layout behavior to improve mobile readability, hide sidebar where appropriate, and clarify ambiguous connection-status wording.
- Accessibility and UX consistency:
  - Standardized dismissible beta-badge behavior in shared settings navigation with persisted hide state (`tldw:settings:hide-beta-badges`).
  - Added explicit labels/tooltips for previously icon-only controls in Document Workspace and Workflow Editor.
- AntD/Markdown modernization:
  - Migrated deprecated AntD usage in shared UI (`Drawer.width`, `Space.direction`, `Alert.message`, `Dropdown.Button`, and notification `message`) to current APIs.
  - Aligned shared markdown dependency stack to ReactMarkdown v10 parity across WebUI and extension (`react-markdown`, `remark-gfm`, `remark-math`, `rehype-katex`).
  - Updated shared markdown wrappers for ReactMarkdown v10 API compatibility (styling moved off direct `ReactMarkdown` `className` prop).
- CI gating:
  - Frontend UX gates workflow now runs the Stage 5 audited-route smoke gate before the broad all-pages smoke job.

### Removed
- UI
  - Removed `apps/tldw-frontend/pages/chat/settings.tsx` after replacing with server-side route redirect strategy.
  - Removed duplicate chat disconnected guidance surfaces that previously showed overlapping connection messages.
  - Removed user-visible unresolved template placeholder rendering across audited chat/audio/documentation surfaces.

### Fixed
- Auth/API: deprecated `PUT /api/v1/users/me` now returns `404 User not found` when the backing `users` row is missing, instead of returning a false-success profile payload.
- Test isolation: hardened MediaDB2 `torch` stubs with minimal `Tensor`/`nn.Module` attributes so cross-suite pytest runs no longer fail during SciPy/NLTK import checks.
- fix(audio-ws): make transcribe startup resilient to Nemo probe failures
- Treat Nemo availability probe import errors as non-fatal in `websocket_transcribe`
- Default to Whisper when Nemo probing cannot be resolved at runtime
- Prevent WS startup aborts that caused downstream quota/metrics/concurrency test failures
- Document the fail-safe fallback behavior in the audio streaming protocol docs
- Hardening: Prompts/Sync/Workflows/Services
  - Improved production safety and reliability across prompt collections, sync, workflow placeholders, and ephemeral processing.
  - Documented /api/v1/prompts/collections/* as production-backed, user-scoped endpoints.
  - Enforced and documented strict /api/v1/sync/send entity validation (Media, Keywords, MediaKeywords).
  - Hardened sync error handling: internal failures stay 500; /api/v1/sync/get now fails closed on invalid sync rows instead of silently skipping.
  - Confirmed workflow process_media placeholder kinds (ebook, xml, podcast) return explicit not_implemented.
  - Added and documented ephemeral store controls (EPHEMERAL_STORE_TTL_SECONDS, EPHEMERAL_STORE_MAX_ENTRIES, EPHEMERAL_STORE_MAX_BYTES).
  - Fixed XML placeholder temp-file lifecycle (always cleaned up) and preserved intended HTTP status behavior.
  - Added regression tests for XML cleanup/error paths and rate-limiter type-hint/datetime integrity.
- Fixed several backend reliability and API-behavior issues across Prompt DB lifecycle, sync processing, and service cleanup.
  - Removed import-time async worker startup in prompts DB dependencies; worker lifecycle now starts safely under app runtime.
  - Hardened /sync/send and /sync/get error handling:
    - preserved HTTP exceptions instead of wrapping them into generic 500s,
    - restored correct 400 classification for client validation errors (including disallowed sync entities),
    - prevented silent partial /sync/get responses when invalid sync rows are encountered.
  - Expanded sync conflict timestamp parsing to support ISO-8601 Z, fractional Z, +00 (line 0), and non-UTC offsets (normalized to UTC before LWW comparison).
  - Fixed XML processing temp-file leak by ensuring cleanup on both success and failure paths.
  - Removed deprecated FastAPI 422 fallback usage to eliminate import-time deprecation warnings in exception handling.
  - Added regression coverage for all fixes, with targeted suite passing (69 passed).
- Auth/API: deprecated `PUT /api/v1/users/me` no longer returns a false-success payload when the backing `users` row is missing; it now returns `404 User not found`.
- Regression coverage: added legacy `/users/me` update tests for both missing-row (`404`) and successful update (`200`) paths.
- Test stability: hardened MediaDB2 test `torch` stubs with minimal `Tensor`/`nn.Module` attributes to prevent cross-suite import failures during SciPy/NLTK initialization.
- Security
  - Hardened API key exposure paths:
    - /api/v1/config/docs-info now always returns a safe placeholder key and api_key_configured status.
    - Startup API key logging is masked by default (full key only when explicitly enabled).
  - Hardened scheduler payload handling:
    - External payload storage now uses safe JSON serialization by default.
    - Added strict payload reference validation and payload header bounds checks.
    - Disabled legacy pickle payload deserialization by default.
  - Hardened web scraping dedupe persistence:
    - Dedupe hashes now persist as JSON instead of pickle by default.
    - Legacy pickle hash loading is disabled by default.
  - Isolated placeholder processing services:
    - Placeholder document/ebook/podcast/xml services are now blocked in production-like environments even if enabled.
- Hardened deprecated `GET /api/v1/users/me` so missing-user fallback is only allowed in single-user mode; multi-user now correctly rejects missing backing users.
- Prevented ephemeral-store “unusable key” behavior by rejecting payloads that exceed configured max-bytes before insertion.
- Improved `/api/v1/sync/get` resilience: malformed sync rows are now logged and skipped while valid rows are still returned (partial success instead of full failure).
- Added regression coverage for user fallback rules, sync client route/auth behavior, sync malformed-row handling, and ephemeral-store size-limit enforcement.
- CORS now fails closed when enabled and `ALLOWED_ORIGINS` resolves to an explicit empty list (`[]`); a non-empty explicit origin list is required unless CORS is disabled.
- Startup now rejects invalid CORS configuration when `ALLOWED_ORIGINS` includes `"*"` while credentials are enabled.
- OpenAPI CORS handling no longer reflects disallowed origins.
- `ALLOWED_ORIGINS=""` (empty string) now logs a warning and falls back to local default origins for backward compatibility.
- Security hardening (Scheduler): fixed symlink-path validation bypass so base_path now rejects symlink ancestors (including symlink/child) instead of only direct symlink paths.
- Regression coverage (Scheduler): updated test_security_fixes.py to match current backend detection (pool-based Postgres detection) and async DB mocks (AsyncMock + awaited call assertions).
- Deprecation headers: replaced hardcoded fallback sunset dates with a shared UTC helper (build_deprecation_headers) used by auth, users, and legacy character-chat endpoints, with DEPRECATION_SUNSET_DAYS support and dynamic fallback computation.
- WebSearch Module: improved reliability and diagnostics across aggregation, provider dispatch, and parsing. Aggregate mode now validates LLM configuration (returns `422` when missing and reuses `final_answer_llm` for relevance analysis when provided), Google now correctly handles `google_domain`/`googlehost`, result-language parsing (`lr` with `hl` fallback), and multi-domain blacklist behavior, Kagi endpoint construction and Searx safesearch mapping were corrected, subquery generation/parsing now sanitizes and deduplicates model output, and provider `processing_error` values are surfaced in response `error`/`warnings` instead of being silently dropped. Added regression coverage across unit and integration WebSearch paths.
- Hardened chunked image handling to reject unsupported MIME types and invalid image payloads in large `data:` image paths.
- Changed chunked image processing failure behavior from fail-open to fail-closed, preventing invalid bytes from being treated as valid images.
- Fixed `run_cpu_bound_thread()` so keyword arguments are supported correctly via `functools.partial`.
- Corrected `load_prompt()` semantics for markdown prompts: missing keys now return `None` instead of falling back to the first fenced block.
- Removed `shell=True` usage in CUDA detection (`nvidia-smi` now called with direct subprocess args).
- Added backward-compatible chat dictionary endpoint re-exports for legacy imports/tests.
- Updated telemetry dummy span compatibility (`set_attributes`, broader `record_exception` signature).
- Skills
  - Fixed built-in seed behavior so supporting and nested files are preserved during seeding.
  - Fixed overwrite seeding edge cases where soft-deleted registry rows could prevent seeded skills from being visible after overwrite.
- Admin Backup Bundles
  - Fixed restore failure error reporting so rollback diagnostics are no longer collapsed to generic `import_error` behavior.
  - `restore_failed` import errors now preserve structured rollback context for API consumers.
  - Endpoint import response now properly propagates `rollback_failures` from service results.
  - Retention cleanup now safely skips unreadable/corrupt manifests without crashing bundle creation and keeps ZIP/sidecar cleanup consistent.
- Circuit Breaker
  - AuthNZ integration assertion for circuit breaker `source` is now environment-safe by accepting both `memory` and `mixed` (persistent mode).
- Resolved web-mode extension API runtime failures by guarding `chrome.storage` access and preventing `chrome is not defined`/`chrome.storage` uncaught exceptions.
- Removed unresolved `{{...}}` template leaks from shared UI labels/tooltips on audited routes.
- Hardened shared timeout/retry flows for admin stats and STT/TTS catalog discovery to prevent permanent-loading states.
- Removed temporary Stage 5 warning allowlist (`m5-react-defaultprops-warning`) after root-cause remediation.
- Revalidated audited smoke quality gates after remediation:
  - Stage 5 gate: `11 passed`
  - Full all-pages smoke: `165 expected, 0 unexpected, 0 flaky`
- UI
  - Fixed catastrophic extension-shim/runtime overlay impact on audited routes by driving closeout to `withErrorOverlay: 0` and `withChromeRuntimeErrors: 0` in final smoke artifact.
  - Fixed wrong-content navigation defects by closing route-contract expectations across audited settings/admin/connectors/profile/config destinations.
  - Fixed audited navigation 404 regressions (Section 2 list) to zero for in-scope UX routes.
  - Fixed unresolved template-variable leaks (`{{...}}`) across previously affected chat, audio, and documentation surfaces (`templateLeakRoutes: 0` at closeout).
  - Fixed max-update-depth/infinite-rerender class regressions on critical routes (`maxDepthRoutes: 0`, `maxDepthEvents: 0` in closeout artifact).
  - Fixed permanently-loading skeleton experiences on key admin/audio surfaces via timeout + error + retry state transitions.
  - Fixed mobile interaction issues across prioritized flows (touch-target sizing, toolbar discoverability, responsive parity gaps).
  - Fixed core route identity duplication so home/setup/onboarding-test have distinct purpose and route contracts.
  - Fixed release-readiness reliability with passing gate suite reruns at closeout: Stage 5 (`12 passed`), Stage 6 (`6 passed`), Stage 7 (`4 passed`).
  - Fixed program-level UX closure criteria by completing all nine UX implementation plans and finalizing the overarching oversight plan status to complete.


## [0.1.20] 2026-02-07

### Added
- webui/extension fixes+improvements
  - New Guardian settings page
- **FVA Pipeline (Falsification-Verification Alignment)**: New claim verification enhancement that actively searches for contradicting evidence to provide more robust verification results. Implements the FVA-RAG paper (arXiv:2512.07015).
  - New `CONTESTED` verification status for claims with significant evidence both supporting and contradicting
  - Anti-context retrieval generates counter-queries (negation, contrary, alternative) to find contradicting evidence
  - Adjudication weighs supporting vs contradicting evidence using NLI and LLM-based stance assessment
  - API endpoints: `POST /api/v1/claims/verify/fva` and `GET /api/v1/claims/verify/fva/settings`
  - Configurable via config.txt: FVA_ENABLED, FVA_CONFIDENCE_THRESHOLD, FVA_CONTESTED_THRESHOLD, etc.
  - 9 new Prometheus metrics for observability (falsification triggers, status changes, adjudication scores, timeouts)
  - Budget management to prevent runaway costs on large claim sets
- Speech Playground history now shows metadata (duration, model/voice/provider, params summary) with a detail tooltip.
- History entries now persist STT/TTS params (task, temp, response format, segmentation, speed, split, streaming, mode) so metadata reflects actual runs.
- Global TS typecheck fixed across UI (EPUB viewer/search typings, document chat/store shapes, KnowledgeQA response normalization, MCP path typing, chunking options, safe config typing, xterm ambient types, SpeechPlayground ordering/import issues).
- Implemented TTS history end-to-end:
	- Write path (non-streaming, streaming, jobs) with status, metadata, artifacts, and error handling.
	- Read path: list/detail/favorite/delete endpoints with filters, cursor pagination, total count.
	- Retention: scheduled purge by days and max rows; artifact reference cleanup.
	- Observability: read/write counters and latency histograms (no text logging).
	- Added schema + migrations for tts_history and supporting indexes.
- Added tests:
	- Unit: schema and API list/favorite/delete, q/text_exact behavior.
	- Integration: streaming failure writes history, artifact purge updates history, cursor pagination sanity.
	- Fixed test infrastructure shims for audio/tokenizer/transcription helpers.
- Server/API
  - RAG upgrades: Doc-Researcher features (granularity router, evidence accumulator, evidence chains), batch + resume endpoints, web fallback with query rewrite, retrieval metrics, FlashRank model support.
  - Character chat: per‑chat settings + prompt preview endpoint, greeting picker/inclusion toggle, generation presets, multi‑character turn‑taking, message steering controls, pinned messages pathing.
  - Watchlists: dedup/seen inspect & reset tools; scheduler controls; performance/limits docs.
  - Guardian/Self‑monitoring: new Guardian_DB and API surfaces.
  - ACP sandbox: SSH-enabled runner and bridge; new Dockerfile + entrypoint.
  - New “Skills” framework and Kanban endpoints/modules.

### Changed
- DBs modified
	- Media DB v2: per-user SQLite DB at Media_DB_v2.db (and Postgres equivalent when configured).
- MCP Unified hardening:
  - `/api/v1/mcp/auth/refresh` now requires body-based `refresh_token` payloads (query-token transport rejected).
  - Write-tool idempotency now binds each `idempotencyKey` to the initial argument fingerprint and returns `INVALID_PARAMS` on mismatched replays.
  - Module registry lookups now use concurrency-safe snapshots to prevent `dictionary changed size during iteration` under concurrent module registration churn.
  - Sandbox stream Redis fanout now requires explicit `SANDBOX_WS_REDIS_FANOUT` opt-in (no implicit enablement from global Redis settings).
- Evaluations module hardening:
  - Parallel batch mode now enforces strict fail-fast when `continue_on_error=false` by canceling remaining tasks and stopping new scheduling.
  - Evaluation runner now safely normalizes `metrics` values, including `metrics=None`, across execution and aggregate/stat calculations.
  - RAG pipeline eval runs now use per-run user context for ephemeral vector index creation/cleanup and pipeline calls.
  - OCR-PDF usage accounting now records against the correct limiter namespace (`evals:ocr_pdf`).
  - Access policy aligned: `/api/v1/evaluations/health` remains public, `/api/v1/evaluations/metrics` is authenticated (`EVALS_READ`), and dataset endpoints enforce `EVALS_READ`/`EVALS_MANAGE` consistently.
- Server/API
  - Admin endpoints modularized: tldw_Server_API/app/api/v1/endpoints/admin/* (replaces single admin.py).
  - Audio split: new audio submodule endpoints (tts, tokenizer, streaming, history).
- Web UI/Extension
  - Document Workspace: PDF/EPUB viewers overhauled (virtualized PDF single-page mode, thumbnails, TOC keyboard nav), DocumentPicker modal, richer metadata, TTS panel improvements, retry logic.
  - Knowledge QA: web-search fallback settings, local/server threads, richer history filtering; new “All options” settings section.
  - Playground/Chat UX: composer extracted into components, Notes Dock, greeting picker, pin/steering controls, MCP tool catalog/filter UX.
  - Workflow Editor: dynamic step registry + schema-driven fields, icons, dynamic options; new tests.
  - TTS Playground: multi-voice roles, background job progress UI, presets.
  - ACP Playground: Workspace terminal tab (xterm.js).
  - Extension e2e hardening; pdf.worker exposed via web_accessible_resources.
- Tooling/ops/docs
  - Lint only-changed target and script; large doc set added/updated (PRDs, guides).
  - FlashRank reranker model vendored under models/flashrank with unignore rules.
  - New env vars for ACP sandbox, TTS history, and RAG FlashRank cache/model selection.
- Web Scraping Module
  - Hardened legacy fallback contracts in web_scraping_service.py (line 46) and web_scraping_service.py (line 276).
  - Added explicit fallback metadata (engine, fallback_context) in web_scraping_service.py (line 392) and web_scraping_service.py (line 497).
  - Added predictable fallback max_pages cap for legacy URL Level/Sitemap in web_scraping_service.py (line 340).
  - Preserved request max_pages pass-through in ingest orchestration in web_scraping_service.py (line 721) and web_scraping_service.py (line 772).
  - Added fallback-focused tests in test_legacy_fallback_behavior.py (line 44).
  - Fixed auth header fixture for friendly ingest crawl-flag tests in test_friendly_ingest_crawl_flags.py (line 19) by merging default headers and adding X-API-KEY.

### Removed

### Fixed
- Workspace selector remove handler now uses the imported MouseEvent type instead of the React namespace.
- Audit read paths no longer return empty results on DB failures; `/api/v1/audit/export` and `/api/v1/audit/count` now surface server errors when reads fail.
- Audit fallback replay now quarantines malformed JSONL lines into `audit_fallback_queue.bad.jsonl` instead of silently dropping them.
- Audit export now rejects non-positive `max_rows`, `audit_operation` ignores reserved kwarg collisions safely, and shared-audit migration stats counters now track read/inserted/skipped events correctly.
- CodeQL Bugfixes
- ruff and mypy fixes


## [0.1.19] 2026-01-31

### Added
- Soft delete support for notes/character cards
- Qwen3-STT
- JSON validation utilities with detailed error positioning (line/column information)
- [WebUI] Character generation prompt templates for full and single-field generation 
- [WebUI] Flashcard undo functionality with Ctrl/Cmd+Z shortcut
- [WebUI] Media review selection and focus settings
- [WebUI] TldwApiClient methods for character export, restore, and bulk world book operations
- Comprehensive test coverage for Qwen3-ASR, Gemini tools, and character generation
- [WebUI] Documentation updates including PRD for Characters Playground UX improvements, healthcare-focused UX review prompts, and Qwen3-ASR setup guide
- README restructuring with improved formatting and version 0.1.18 release notes
- 70+ new adapters for workflows module
- [WebUI] Added Document Workspace
- [WebUI] Added Writing Playground

### Changed
- Implemented httpx/aiohttp transport adapters with centralized policy enforcement in http_client.
- Added httpx client caching and shutdown cleanup to align with aiohttp lifecycle handling.
- Formalized streaming behavior with first‑byte/idle timeouts and mid‑stream retry support.
- Expanded http_client tests for adapters, cache reuse, and streaming timeout coverage.
- [WebUI] e2e test work

### Removed

### Fixed
- Workspace selector remove handler now uses the imported MouseEvent type instead of the React namespace.


## [0.1.18] 2026-01-29

### Added
- Slides Module
- TTS:
  - Added NeuTTS, PocketTTS (ONNX), EchoTTS, Qwen3-TTS, LuxTTS, VibeVoice-ASR docs; updated streaming/format rules, default voice behavior, and setup guides.
- Moved the tldw_Browser_Assistant project and the tldw-frontent folder into the '/apps/' folder, as moving forward they will share the same base.
  - As a result, new frontend!
- New monorepo development guide, shared UI package scaffold, ambient typings, and testing guide for extension/web UI.
- Image creation API via files 

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
- Kanban: vector search integration, activity logging with filtering, rate limiting on endpoints
- Reading Collections: async import jobs workflow with job monitoring endpoints
- Workflows: LLM step type with MCP tool allowlist and scope validation

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
