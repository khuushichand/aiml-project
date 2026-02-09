# Media Ingestion Pipeline PRD

Status: Foundations and Stage 1 hardening shipped (v0.2.x); Stage 2+ roadmap in progress
Owner: Core Maintainers
Audience: Backend & infrastructure contributors

## 1. Summary
- **Problem:** tldw_server ingests heterogeneous media (audio/video/documents/web dumps) but the knowledge about validation, parsing, persistence, and downstream hooks is scattered across modules. Contributors struggle to evolve the pipeline safely, and cross-cutting features (watchlists, collections, RAG) depend on predictable ingestion guarantees.
- **Solution:** Define a cohesive Media Ingestion Pipeline charter that documents current capabilities, required invariants, integration points, and the staged roadmap toward a unified, observable, and scalable ingestion layer.
- **Status (2026-02-09):** Core processors live under `app/core/Ingestion_Media_Processing/`, FastAPI endpoints expose per-media workflows, and persistence flows through `Media_DB_v2`. Watchlists/reading services and `/api/v1/media/add` now dual-write successful items to collections. Async ingestion jobs (`/api/v1/media/ingest/jobs`) and MediaWiki checkpoints are implemented; validation parity, embeddings dispatch, metadata/chunk contracts, ingestion metrics, and sanitization/archive hardening defaults are standardized.

## 2. Problem Statement
Contributors must support new media types, improve processing fidelity, and connect ingestion outputs to Retrieval/RAG, watchlists, and collections. Without a shared plan, changes risk breaking DB invariants, duplicating validation logic, or bypassing downstream consumers (embeddings, claims, notifications). We need a PRD that articulates the ingestion contract and future stages so that the module evolves coherently.

## 3. Goals and Non-Goals
### Goals
1. Capture the end-to-end ingestion responsibilities (validation → processing → persistence → downstream notifications).
2. Provide clear instructions for adding new processors, plugging into Media DB + collections, and ensuring embeddings/search parity.
3. Establish a roadmap toward improved observability, scalability (async workers, resumable jobs), and Postgres parity.
4. Document interactions with watchlists, reading list/collections, RAG, MCP, and notifications so contributors understand dependencies.

### Non-Goals
- Defining UI/UX for upload experiences (covered elsewhere).
- Replacing core storage (Media DB v2) or collections DB in this stage.
- Designing the full embeddings/vector-store architecture (refer to RAG/Collections PRDs).
- Implementing ops/deployment automation (covered by Deployment docs).

## 4. Personas / Stakeholders
- **Ingestion Maintainers:** Extend processors, add validations, manage performance.
- **RAG & Search Developers:** Depend on consistent chunking/metadata to build indexes.
- **Watchlists & Collections Owners:** Need deterministic ingestion hooks to populate `content_items` and downstream outputs.
- **Infra/Ops:** Care about resource usage (ffmpeg, yt-dlp), observability, and scaling knobs.
- **QA/CI Engineers:** Require deterministic fixtures, hermetic tests, and fast validation paths.

## 5. Success Metrics
- Ingestion success rate per media type (requests vs. failures).
- Average processing time per media type and per file size buckets.
- Time-to-availability for downstream consumers (collections rows, embeddings job enqueued, claims stored).
- Coverage of automated tests per media type (unit + integration).
- Alerts for validation bypasses, oversize uploads, or failed chunking.

## 6. Current Scope (v0.2 foundations)
| Capability | Details |
| --- | --- |
| Upload validation | `Upload_Sink.FileValidator` enforces extension, size, MIME (puremagic), optional Yara scanning, safe archive inspection. Exposed via API deps (`file_validator_instance`). |
| Processing modules | Structured by media: `Audio`, `Video`, `PDF`, `Books`, `Plaintext`, `MediaWiki`, `OCR`, `VLM`, code ingestion. Each returns structured dicts (`status`, `content`, `chunks`, `analysis`, `metadata`). |
| External tooling | `ffmpeg`, `yt-dlp`, optional `faster_whisper`, `NVIDIA NeMo`, `Qwen2Audio`, `pymupdf4llm`, `docling`, `pypandoc`, system Tesseract. |
| Persistence | API layer persists into `Media_DB_v2` (per-user SQLite default) creating `Media`, `DocumentVersions`, `MediaChunks`, `Keywords`, transcripts, `Claims`, and `sync_log` entries. Soft deletes + optimistic concurrency enforced. |
| Collections bridge | Watchlists, reading services, and successful `/api/v1/media/add` writes dual-write to `content_items` and tag tables while linking the originating `media_id`. Sync failures are surfaced as non-fatal warnings in `/media/add` responses. |
| Downstream hooks | Claims extraction is optional/feature-flagged and non-fatal. Embeddings dispatch uses a shared orchestration contract with configurable mode selection (`jobs`, `background`, `auto`) plus provenance metadata for traceability. |
| API surface | `/api/v1/media/...` endpoints for upload + processing; `/api/v1/media/process-*` for ephemeral processing; watchlists and collections reuse ingestion helpers for scheduled scraping and manual saves. |
| Security | Size limits from config, MIME enforcement, Yara optional, HTML/XML sanitization defaults enabled with config controls, and quarantine paths for archive validation. |
| Testing | Extensive unit tests per processor, integration tests for media endpoints, watchlists pipeline tests, and collection ingestion tests. Some flows skip when ffmpeg/yt-dlp unavailable. |

## 7. Architecture Overview
```
┌────────────┐       ┌───────────────────┐       ┌──────────────────────┐       ┌────────────────────────────┐
│ User Input │ ────► │ Upload Validation │ ────► │ Media Processors     │ ────► │ Persistence & Downstream   │
│ (upload/url│       │ (Upload_Sink)     │       │ (Audio/PDF/etc.)      │       │ Hooks                      │
└────────────┘       └───────────────────┘       └─────────┬────────────┘       └───────┬─────────────┬───────┘
                                                           │                            │             │
                                                           ▼                            ▼             ▼
                                               Chunking & Metadata         Media DB v2 / Collections   Embeddings Queue,
                                               (segments, analysis)        (`media`, `content_items`)   Claims, Notifications
```
- Upload path validation occurs before processing: the API saves uploads into temp dirs, delegates to `FileValidator`, and only proceeds on `ValidationResult.is_valid`.
- URL path validation applies download guards (egress policy, extension/content-type checks, size limits) and a shared post-download `FileValidator` pass for document-like, audio, and video flows.
- Processing modules encapsulate media-specific logic. They support both URL fetch and file upload paths, relying on helper utilities (e.g., yt-dlp wrappers, PDF parsers).
- Persistence logic lives mostly in API/service layers: create/update media records, attach versions, keywords, transcripts, and claims.
- Collections writes are guaranteed in watchlists/reading flows and successful `/media/add` ingestion via the dual-write bridge.
- Downstream hooks include claims extraction, watchlist output generation, and embeddings integration via shared dispatch semantics.

## 8. Data Model (SQLite default, Postgres optional)
- **Media DB v2 (per-user `<USER_DB_BASE_DIR>/<user_id>/Media_DB_v2.db`):**
  - `Media`: canonical item record (title, url, type, status, metadata, favorite, soft delete).
  - `DocumentVersions`: versioned content body plus `safe_metadata`, prompts, analysis payloads.
  - `MediaChunks`: chunked text with embeddings metadata; triggers maintain `media_fts`.
  - `UnvectorizedMediaChunks`: pending chunks waiting on embeddings jobs.
  - `Keywords` & `MediaKeywords`: normalized tags and bridging table with BM25 scoring metadata.
  - `Transcripts`: audio/video transcripts with diarization metadata.
  - `Claims`: extracted claims + `claims_fts`.
  - `DocumentStructureIndex`: hierarchical section/paragraph offsets for structure-aware retrieval.
  - `sync_log`: change log for multi-device sync.
- **Collections DB (per user):** `content_items`, `content_item_tags`, `content_item_tag_links` share user IDs with watchlists/reading services. Watchlist/reading pipelines and successful `/api/v1/media/add` ingestion dual-write here so `/api/v1/items` reflects those flows; remaining ingestion entry points can join in future stages as needed.
- **Backends:** SQLite is default and fully supported; Postgres backend exists but some ingestion routines rely on SQLite-specific syntax (e.g., `INSERT OR IGNORE`). Stage 2 roadmap covers removing those assumptions.

`USER_DB_BASE_DIR` is defined in `tldw_Server_API.app.core.config` (defaults to `Databases/user_databases/` under the project root). Override via environment variable or `Config_Files/config.txt` as needed.

## 9. API Surface (developer focus)
- `/api/v1/media/add` - process uploads/URLs and persist results (default path).
- `/api/v1/media/process-{audios|videos|documents|pdfs|ebooks|emails}` - process without persistence (used by UI previews and external tooling).
- `/api/v1/media/process-code` - code-aware chunking pipeline.
- `/api/v1/media/process-web-scraping` and `/api/v1/media/ingest-web-content` - crawler/scraper ingestion endpoints that reuse watchlist fetchers.
- `/api/v1/media/mediawiki/{process-dump|ingest-dump}` - long-running MediaWiki ingestion endpoints (`process-dump` stream-first path, `ingest-dump` ingest path).
- `/api/v1/media/{media_id}` - CRUD endpoints (fetch, update metadata, delete/restore).
- `/api/v1/media/{media_id}/reprocess` - rebuild chunks and/or regenerate embeddings for persisted media.
- `/api/v1/watchlists/*` and `/api/v1/items` reuse ingestion outputs to list items and outputs.
- Async jobs (implemented): `/api/v1/media/ingest/jobs`, `/api/v1/media/ingest/jobs/{job_id}` (submit/status/list/cancel).
- Future: optional route aliasing to `/api/v1/media/jobs/*` if endpoint simplification is desired.

## 10. Functional Requirements (current + near term)
1. **Validation Guarantee (path-specific):**
   - Upload inputs MUST pass `FileValidator` before processing.
   - URL inputs MUST pass download guardrails (egress policy, extension/content-type, max-size) and MUST run shared post-download `FileValidator` checks for document-like, audio, and video flows.
2. **Deterministic Metadata:** Processors SHOULD populate stable core metadata keys (`source_url`, `duration`, `page_count`, etc. when applicable). Stage 1 adds an explicit metadata contract test matrix per media type.
3. **Chunk Consistency:** When chunking is enabled, chunk metadata SHOULD include offsets/section context when available. Chunk-count parity assertions between in-memory chunk outputs and persisted rows are enforced via policy (`off|warn|error`).
4. **Idempotent Persistence:** Re-ingesting equivalent media SHOULD update/touch existing records rather than duplicating rows. Current dedupe is URL and/or content hash (with source-hash checks in some paths); Stage 1 defines normalized URL + hash parity behavior.
5. **Collections Sync (path-specific):** Watchlists, reading services, and successful `/media/add` persistence MUST dual-write to `content_items`, with non-fatal warning semantics on sync failures.
6. **Embeddings Hook (path-specific):** Ingestion embeddings dispatch MUST follow the unified dispatch/provenance contract (`jobs|background|auto`) across entry points.
7. **Claims Optionality:** Claims extraction MUST be feature-flagged (enabled via config). Failures MUST not abort ingestion and SHOULD emit warnings.
8. **Observability:** Emit loguru events per ingestion stage. Existing upload/processor metrics remain valid; standardized `ingestion_*` counters/histograms and queue-latency visibility are emitted for core ingestion paths.

## 11. Integrations & Dependencies
- **Watchlists Pipeline:** Scheduled scraping uses ingestion processors for HTML extraction and persists through the same Media DB + collections pathway.
- **Reading Service:** Manual saves feed into ingestion for canonical URL/metadata extraction and share chunking logic when content body is available.
- **RAG/Search:** Media chunks feed FTS5 + vector store ingestion; structure index roadmap (Ingest-Plan-1) depends on accurate offsets from processors.
- **Notifications:** Email/Chatbook delivery hooks leverage ingestion metadata (titles, summaries) for templated outputs.
- **Infrastructure:** Redis queue (via `Infrastructure.redis_factory`) backs embeddings jobs, rate limiting, and watchlist scheduling.
- **AuthNZ:** Media actions gated by `MEDIA_CREATE`, `MEDIA_READ`, `MEDIA_DELETE` permissions and API key/JWT contexts.

## 12. Roadmap
### Stage 0 - Foundations (Complete)
- Core processors for major media formats.
- Upload validation with extension, size, optional Yara.
- Media DB persistence + claims extraction + chunking.
- Watchlists/collections integration and embeddings enqueue hook.

### Stage 1 - Observability & Job Control (In Progress)
- [Shipped] Introduce async ingestion jobs endpoints and worker (`/api/v1/media/ingest/jobs`) with retry/backoff.
- [Shipped/Partial] Harden long-running ingestion with checkpoints (MediaWiki implemented; parity for other long flows pending).
- [Shipped] Instrument standardized per-media metrics (`ingestion_*`) for validation failures, processing duration, and chunk counts.
- [Shipped] Ensure collections provenance metadata consistency (`run_id`, `source_id`, origin tags) across ingestion pathways.
- [Shipped] Add URL-path post-download validator parity with upload-path `FileValidator` for document-like, audio, and video paths.
- [Shipped] Add `/media/add` -> collections dual-write bridge and align embeddings path with queue metadata contract.
- [Shipped] Tighten/document sanitization defaults for HTML/XML and archive-driven inputs (enabled by default with config controls, plus archive-member guardrails for email archive ingestion).

### Stage 2 - Backend Parity & Scaling
- Remove SQLite-specific SQL; add migrations for Postgres parity.
- Support distributed workers for heavy processing (audio transcription, OCR) with queue-based execution.
- Implement resource budgeting per user (size limits, concurrency) with metrics + limits surfaced to admin UI.
- Add structured structure-index writes (section hierarchy) per Ingest-Plan-1.
- Expand FTS/embedding parity (image captioning, table extraction).

### Stage 3 - Advanced Automation
- Agentic ingestion workflows (auto-derive follow-up fetches, domain-specific pipelines).
- Built-in summarization + highlight extraction stored alongside media versions.
- Inline quality scoring and remediation suggestions for failed ingestion.
- First-class support for streaming media (live transcripts) with partial persistence.

## 13. Metrics & Observability
- Current metrics observed in ingestion paths include upload/storage counters and processor-specific timers (e.g., `uploads_total`, `upload_bytes_total`, `pdf_processing_duration`).
- Standardized counters/histograms implemented in Stage 1:
  - `ingestion_requests_total{media_type,outcome}`
  - `ingestion_processing_seconds{media_type,processor}` (histogram)
  - `ingestion_validation_failures_total{reason,path_kind}`
  - `ingestion_chunks_total{media_type,chunk_method}`
  - `ingestion_embeddings_enqueue_total{path_kind,outcome}`
- Logs: structured loguru fields (`media_type`, `source`, `duration_ms`, `chunk_count`, `warnings`).
- Tracing: optional OpenTelemetry spans per stage (validation, download, parse, chunk).
- Alerting: high validation failure rate, stuck processing jobs, embeddings enqueue backlog.

## 14. Security & Compliance
- Enforce file size limits and timeouts configured in `Config_Files/config.txt` (`media_processing` section).
- Support Yara scanning when rules present; provide guidance for rule maintenance.
- Ensure temp directories are per-request and cleaned after use; quarantine suspicious files for analysis.
- Sanitization: HTML/XML sanitizers must strip scripts/forms; PDF/Doc ingestion should guard against embedded executables.
- Audit logging: Media DB `sync_log` captures create/update/delete attribution.
- Secrets: avoid logging API keys, cookies, credentials when fetching remote content.

## 15. Open Questions
1. Should we standardize on asynchronous worker queues for heavy processors (audio/video) in Stage 1 or defer to Stage 2?
2. How do we reconcile per-user SQLite databases with org-level Postgres deployments for shared watchlists?
3. Do we need a pluggable antivirus scan beyond Yara (e.g., ClamAV integration)?
4. What is the long-term strategy for storing raw binaries (S3/minio vs. filesystem) when Media DB references file paths?
5. How should we expose ingestion progress to clients (WebSockets vs. polling) for long operations?
6. Should URL downloads run through the same `FileValidator` pipeline for every media subtype (including edge handlers), or should some media types retain specialized URL guardrails?

## 16. References
- Code: `tldw_Server_API/app/core/Ingestion_Media_Processing/` (processors, Upload_Sink).
- Database: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`; `Docs/Code_Documentation/Databases/Media_DB_v2.md`.
- Collections & Watchlists: `Docs/Product/Content_Collections_PRD.md`, `Docs/Product/Watchlist_PRD.md`.
- Ingestion guides: `Docs/Code_Documentation/Ingestion_Media_Processing.md`, `Docs/Code_Documentation/Ingestion_Pipeline_*.md`.
- Infrastructure: `Docs/Product/Infrastructure_Module_PRD.md` (Redis factory, metrics).
- Related plans: `Docs/Design/Ingest-Plan-1.md`, `Docs/Design/RAG_Plan.md`.
