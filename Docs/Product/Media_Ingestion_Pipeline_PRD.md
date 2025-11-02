# Media Ingestion Pipeline PRD

Status: Foundations shipped (v0.2.x); Stage 1 roadmap in progress
Owner: Core Maintainers
Audience: Backend & infrastructure contributors

## 1. Summary
- **Problem:** tldw_server ingests heterogeneous media (audio/video/documents/web dumps) but the knowledge about validation, parsing, persistence, and downstream hooks is scattered across modules. Contributors struggle to evolve the pipeline safely, and cross-cutting features (watchlists, collections, RAG) depend on predictable ingestion guarantees.
- **Solution:** Define a cohesive Media Ingestion Pipeline charter that documents current capabilities, required invariants, integration points, and the staged roadmap toward a unified, observable, and scalable ingestion layer.
- **Status (2025-10-20):** Core processors live under `app/core/Ingestion_Media_Processing/`, FastAPI endpoints expose per-media workflows, persistence flows through `Media_DB_v2` and content collections, and watchlists/reading services reuse the same primitives. Validation (Upload_Sink), chunking, claims extraction, and embeddings enqueueing are operational; observability and multi-backend parity are partially implemented.

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
| Collections bridge | Watchlists and reading services dual-write to `content_items` and tag tables while linking the originating `media_id`. API-driven `/media` uploads currently persist to Media DB only (dual-write roadmap item). Embeddings queue integration uses `Collections.embedding_queue.enqueue_embeddings_job_for_item`. |
| Downstream hooks | Chunking triggers embeddings enqueue, optional claims extraction (`Claims/ingestion_claims.py`), and watchlist output generation. |
| API surface | `/api/v1/media/...` endpoints for upload + processing; `/api/v1/media/process-*` for ephemeral processing; watchlists and collections reuse ingestion helpers for scheduled scraping and manual saves. |
| Security | Size limits from config, MIME enforcement, Yara optional, basic HTML/XML sanitization stubs (TODO for stronger sanitization), quarantine paths for archive validation. |
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
- Validation occurs before any storage: the API saves uploads into temp dirs, delegates to `FileValidator`, and only proceeds on `ValidationResult.is_valid`.
- Processing modules encapsulate media-specific logic. They support both URL fetch and file upload paths, relying on helper utilities (e.g., yt-dlp wrappers, PDF parsers).
- Persistence logic lives mostly in API/service layers: create/update media records, attach versions, keywords, transcripts, claims, and push items to collections.
- Downstream hooks include embeddings enqueue, claims extraction, watchlist output generation, and optional notifications.

## 8. Data Model (SQLite default, Postgres optional)
- **Media DB v2 (per-user `Databases/user_databases/<user_id>/Media_DB_v2.db`):**
  - `Media`: canonical item record (title, url, type, status, metadata, favorite, soft delete).
  - `DocumentVersions`: versioned content body plus `safe_metadata`, prompts, analysis payloads.
  - `MediaChunks`: chunked text with embeddings metadata; triggers maintain `media_fts`.
  - `UnvectorizedMediaChunks`: pending chunks waiting on embeddings jobs.
  - `Keywords` & `MediaKeywords`: normalized tags and bridging table with BM25 scoring metadata.
  - `Transcripts`: audio/video transcripts with diarization metadata.
  - `Claims`: extracted claims + `claims_fts`.
  - `DocumentStructureIndex`: hierarchical section/paragraph offsets for structure-aware retrieval.
  - `sync_log`: change log for multi-device sync.
- **Collections DB (per user):** `content_items`, `content_item_tags`, `content_item_tag_links` share user IDs with watchlists/reading services. Watchlist/reading pipelines dual-write here today so `/api/v1/items` reflects those flows; `/media` uploads will join via a future dual-write stage.
- **Backends:** SQLite is default and fully supported; Postgres backend exists but some ingestion routines rely on SQLite-specific syntax (e.g., `INSERT OR IGNORE`). Stage 2 roadmap covers removing those assumptions.

## 9. API Surface (developer focus)
- `/api/v1/media/add` - process uploads/URLs and persist results (default path).
- `/api/v1/media/process-{audios|videos|documents|pdfs|ebooks|web-content|mediawiki}` - process without persistence (used by UI previews and external tooling).
- `/api/v1/media/process-code` - code-aware chunking pipeline.
- `/api/v1/media/ingest-web-content` - crawler/scraper entry that reuses watchlist fetchers.
- `/api/v1/media/mediawiki/...` - long-running MediaWiki ingestion with streaming responses.
- `/api/v1/media/{id}` - CRUD endpoints (fetch, update metadata, delete/restore).
- `/api/v1/watchlists/*` and `/api/v1/items` reuse ingestion outputs to list items and outputs.
- Future: `/api/v1/media/jobs/*` for asynchronous queued ingestion (Stage 2).

## 10. Functional Requirements (current + near term)
1. **Validation Guarantee:** No file reaches processors without passing `FileValidator`. Test fixtures must cover oversized, invalid MIME, malicious archives.
2. **Deterministic Metadata:** Each processor must populate `metadata` with the same core keys (`source_url`, `duration`, `page_count`, etc.) to support downstream consumers.
3. **Chunk Consistency:** When chunking is enabled, chunk metadata includes offsets and section titles when available; chunk count must match persisted rows.
4. **Idempotent Persistence:** Re-ingesting the same URL/file should update existing media versions rather than duplicating records; dedupe keyed by normalized URL + hash.
5. **Collections Sync:** Newly ingested media should enqueue conversions into `content_items` for unified search/filter endpoints.
6. **Embeddings Hook:** When chunks exist, enqueue `enqueue_embeddings_job_for_item` (best effort; safe to skip if queue disabled). Provide metadata for vector provenance.
7. **Claims Optionality:** Claims extraction must be feature-flagged (enabled via config). Failures should not abort ingestion but should log warnings.
8. **Observability:** Emit loguru events per ingestion stage; Stage 1 adds metrics for validation failures, processing durations, and downstream queue latency.

## 11. Integrations & Dependencies
- **Watchlists Pipeline:** Scheduled scraping uses ingestion processors for HTML extraction and persists through the same Media DB + collections pathway.
- **Reading Service:** Manual saves feed into ingestion for canonical URL/metadata extraction and share chunking logic when content body is available.
- **RAG/Search:** Media chunks feed FTS5 + vector store ingestion; structure index roadmap (Ingest-Plan-1) depends on accurate offsets from processors.
- **Notifications:** Email/Chatbook delivery hooks leverage ingestion metadata (titles, summaries) for templated outputs.
- **Infrastructure:** Redis queue (via `Infrastructure.redis_factory`) backs embeddings jobs, rate limiting, and watchlist scheduling.
- **AuthNZ:** Media actions gated by `MEDIA_CREATE`, `MEDIA_READ`, `MEDIA_DELETE` permissions and API key/JWT contexts.

## 12. Roadmap
### Stage 0 - Foundations (Complete)
- Core processors for major media formats.
- Upload validation with extension, size, optional Yara.
- Media DB persistence + claims extraction + chunking.
- Watchlists/collections integration and embeddings enqueue hook.

### Stage 1 - Observability & Job Control (In progress)
- Instrument per-media metrics (validation failures, processing duration, chunk counts).
- Normalize async task orchestration: background queues for long-running jobs (Large PDFs, yt-dlp).
- Introduce ingestion job registry with retry/backoff metadata stored in Media DB (or new table).
- Harden streaming ingestion (MediaWiki, large uploads) with resumable checkpoints.
- Ensure Content Collections pipeline receives consistent provenance metadata (run_id, source_id).
- Tighten sanitization (HTML/XML cleaning) and document safe defaults.

### Stage 2 - Backend Parity & Scaling
- Remove SQLite-specific SQL; add migrations for Postgres parity.
- Support distributed workers for heavy processing (audio transcription, OCR) with queue-based execution.
- Implement resource budgeting per user (size limits, concurrency) with metrics + limits surfaced to admin UI.
- Add structured structure-index writes (section hierarchy) per Ingest-Plan-1.
- Expand FTS/embedding parity (image captioning, table extraction).

### Stage 3 - Advanced Automation
- Agentic ingestion workflows (auto-derive follow-up fetches, domain-specific pipelines).
- Built-in summarization + highlight extraction stored alongside media versions.
- Inline quality scoring and remediation suggestions for failed ingestion.
- First-class support for streaming media (live transcripts) with partial persistence.

## 13. Metrics & Observability
- Proposed counters/gauges (Stage 1):
  - `ingestion_requests_total{media_type,outcome}`
  - `ingestion_processing_seconds_bucket{media_type,processor}` (histogram)
  - `ingestion_validation_failures_total{reason}`
  - `ingestion_chunks_total{media_type,chunk_method}`
  - `ingestion_embeddings_enqueue_total{outcome}`
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
1. Should we standardize on asynchronous worker queues for heavy processors (audio/video) in Stage 1 or defer to Stage 2?
2. How do we reconcile per-user SQLite databases with org-level Postgres deployments for shared watchlists?
3. Do we need a pluggable antivirus scan beyond Yara (e.g., ClamAV integration)?
4. What is the long-term strategy for storing raw binaries (S3/minio vs. filesystem) when Media DB references file paths?
5. How should we expose ingestion progress to clients (WebSockets vs. polling) for long operations?
6. Which sanitization library should replace current stubs, and how do we validate it across formats?

## 16. References
- Code: `tldw_Server_API/app/core/Ingestion_Media_Processing/` (processors, Upload_Sink).
- Database: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`; `Docs/Code_Documentation/Databases/Media_DB_v2.md`.
- Collections & Watchlists: `Docs/Product/Content_Collections_PRD.md`, `Docs/Product/Watchlist_PRD.md`.
- Ingestion guides: `Docs/Code_Documentation/Ingestion_Media_Processing.md`, `Docs/Code_Documentation/Ingestion_Pipeline_*.md`.
- Infrastructure: `Docs/Product/Infrastructure_Module_PRD.md` (Redis factory, metrics).
- Related plans: `Docs/Design/Ingest-Plan-1.md`, `Docs/Design/RAG_Plan.md`.
