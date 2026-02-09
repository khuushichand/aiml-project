# Media Ingestion Pipeline Completed Checklist

Status: Archived complete as of 2026-02-09 (items 1-8 shipped)
Owner: Core Maintainers
Scope: Delivered gap closure for `/api/v1/media/add`, watchlists/reading ingestion, collections bridge, embeddings, and observability

## How to Use
- Treat this as the completed execution companion to `Docs/Product/Completed/Media_Ingestion_Pipeline_Completed_PRD.md`.
- Use `Docs/Product/Media_Ingestion_Pipeline_Implementation_Checklist.md` for active remaining work.
- Keep this document immutable except for historical correction notes.

## Gap Closure Items

### 1) URL Validation Parity with Upload Validation
- Priority: P1
- Status: Complete (`process_document_like_item`, `process_audio_files`, and `process_single_video` now run shared post-download `FileValidator` checks before processor execution)
- Goal: Ensure URL-downloaded files receive equivalent validation guarantees to upload files.
- Current behavior:
  - Upload path: `FileValidator` enforced before processing.
  - URL path: egress policy + extension/content-type/max-size checks plus shared post-download `FileValidator` pass.
- Target behavior:
  - Add optional or mandatory post-download `FileValidator` pass before processor invocation for applicable media types.
  - Preserve existing URL guardrails.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/download_utils.py`
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/Upload_Sink.py`
- Acceptance criteria:
  - URL ingestion rejects invalid MIME/extension payloads under same policy baseline as uploads.
  - Existing URL tests still pass for allowed content.
- Test requirements:
  - Unit tests for post-download validation branch.
  - Integration tests for URL ingest success/failure with representative file types.

### 2) `/media/add` to Collections Dual-Write
- Priority: P1
- Status: Complete (`/media/add` now dual-writes successful items into Collections `content_items` via `sync_media_add_results_to_collections`, returning `collections_item_id`/`collections_origin` on success and non-fatal warnings on sync failures)
- Goal: Align `/api/v1/media/add` with watchlists/reading by writing `content_items` and related tags/metadata.
- Current behavior:
  - Watchlists/reading dual-write to collections.
  - `/media/add` persists to Media DB only.
- Target behavior:
  - Successful `/media/add` persistence creates/updates corresponding `content_items` row(s) with `media_id` link.
  - Metadata includes origin and stable provenance fields.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - `tldw_Server_API/app/core/Collections/*`
- Acceptance criteria:
  - Newly ingested `/media/add` items are visible in collections list/search endpoints without separate ingest path.
- Test requirements:
  - Integration test for `/media/add` -> collections visibility (`tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_add_collections_visibility.py`).
  - Unit coverage for collections dual-write payload/warning behavior (`tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_collections_dual_write.py`).
  - Regression tests for watchlists/reading unaffected.

### 3) Embeddings Path Unification and Provenance Contract
- Priority: P1
- Status: Complete (`/media/add` embeddings now use unified dispatch orchestration with a shared provenance contract and mode selection: `jobs`, `background`, or `auto` (jobs-first fallback). Jobs payloads now carry provenance metadata for traceability)
- Goal: Converge embeddings orchestration semantics across ingestion paths.
- Current behavior:
  - Watchlists/reading: `enqueue_embeddings_job_for_item` with metadata.
  - `/media/add`: direct background `generate_embeddings_for_media` call.
- Target behavior:
  - Define and implement a single contract for queue/provenance fields (`origin`, `run_id`, `source_id`, etc.), or document intentional split with strict criteria.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - `tldw_Server_API/app/core/Watchlists/pipeline.py`
  - `tldw_Server_API/app/core/Collections/reading_service.py`
- Acceptance criteria:
  - Embeddings jobs are traceable by provenance across all ingestion entry points.
- Test requirements:
  - Unit tests for metadata payload construction (`tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_embeddings_dispatch.py`).
  - Integration test asserting enqueue/background behavior selected per configured mode (`tldw_Server_API/tests/MediaIngestion_NEW/integration/test_media_add_embeddings_dispatch_modes.py`).

### 4) Metadata Contract Enforcement per Media Type
- Priority: P2
- Status: Complete (`persistence.py` now enforces a per-media metadata contract matrix (`audio`, `video`, `document`, `json`, `pdf`, `ebook`, `email`) with policy-driven behavior (`MEDIA_METADATA_CONTRACT_POLICY` / `metadata_contract_policy`: `off|warn|error`) before persistence in both batch AV and document-like flows. Violations are logged, surfaced as warnings or hard errors per policy, and emitted via `ingestion_validation_failures_total{reason=\"metadata_contract\",path_kind=...}`)
- Goal: Make metadata keys deterministic and testable.
- Current behavior:
  - Metadata population varies by processor; no strict contract enforcement matrix.
- Target behavior:
  - Define required/optional metadata keys by media class.
  - Validate processor outputs against contract prior to persistence.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/*`
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
- Acceptance criteria:
  - Contract violations are logged and surfaced as warnings or errors per policy.
- Test requirements:
  - Parametrized unit tests by processor/media type (`tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_metadata_contract.py`), plus regression coverage in existing ingestion unit suites.

### 5) Chunk Consistency Assertions
- Priority: P2
- Status: Complete (`persistence.py` now enforces post-persist chunk parity checks with policy-driven behavior (`MEDIA_CHUNK_CONSISTENCY_POLICY` / `chunk_consistency_policy`: `off|warn|error`) across AV/document/email-child persistence paths. It compares expected chunk counts against active `UnvectorizedMediaChunks` rows, skips intentional non-write outcomes (`already exists`/`url canonicalized`), emits `ingestion_validation_failures_total{reason=\"chunk_consistency\",path_kind=...}` on mismatches, and surfaces warnings/errors in result payloads. `Media_DB_v2.get_unvectorized_chunk_count` provides the DB abstraction used by the check.)
- Goal: Prevent silent mismatch between computed chunks and persisted chunk rows.
- Current behavior:
  - Chunking is re-derived before persistence in several flows; no explicit parity assertion.
- Target behavior:
  - Add consistency checks and clear warning/error semantics for mismatch conditions.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- Acceptance criteria:
  - Chunk count mismatch is detectable and observable.
- Test requirements:
  - Unit tests for mismatch handling branches (`tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_chunk_consistency.py`) and DB chunk-count helper coverage (`tldw_Server_API/tests/MediaDB2/test_unvectorized_chunk_count.py`).

### 6) Dedupe Normalization Clarification
- Priority: P2
- Status: Complete (`normalize_media_dedupe_url` + `media_dedupe_url_candidates` now enforce canonical HTTP(S) dedupe URL normalization (via `normalize_for_crawl`) across `/media/add` pre-check and `Media_DB_v2.add_media_with_keywords` URL/hash dedupe paths; URL scheme matching is now case-insensitive in pre-check routing)
- Goal: Define and enforce dedupe keys consistently (normalized URL + content/source hash policy).
- Current behavior:
  - Mixed dedupe behavior across URL/content hash with media-type-specific pre-checks.
- Target behavior:
  - Publish canonical URL normalization rules and apply uniformly where intended.
- Primary code areas:
  - `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
- Acceptance criteria:
  - Repeat ingest scenarios yield consistent update/touch semantics across paths.
- Test requirements:
  - Unit/integration coverage for duplicate URL variants and identical content with differing URL forms (`tldw_Server_API/tests/MediaDB2/test_dedupe_url_normalization.py`, `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_process_batch_media_url_dedupe_normalization.py`).

### 7) Metrics Taxonomy Standardization
- Priority: P2
- Status: Complete (`ingestion_requests_total`, `ingestion_processing_seconds`, `ingestion_validation_failures_total`, `ingestion_chunks_total`, and `ingestion_embeddings_enqueue_total` now registered and emitted across `/media/add`, URL/upload validation failures, chunk persistence, and embeddings dispatch outcomes while preserving existing upload/security counters; unit coverage added in `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_ingestion_metrics.py`, `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_persistence_embeddings_dispatch.py`, and `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_process_document_like_item_url_limits.py`)
- Goal: Add unified `ingestion_*` metrics while preserving existing counters during migration.
- Current behavior:
  - Mix of upload counters and processor-specific metrics.
- Target behavior:
  - Standardized ingestion metrics for requests, processing duration, validation failures, chunk totals, embeddings enqueue outcomes.
- Primary code areas:
  - `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py`
  - `tldw_Server_API/app/core/Metrics/metrics_manager.py`
- Acceptance criteria:
  - Dashboard-ready counters/histograms available with stable labels.
- Test requirements:
  - Unit tests for metric emission labels and no-throw behavior.

### 8) API Surface and Docs Consistency
- Priority: P3
- Status: Complete (route audit completed against `tldw_Server_API/app/api/v1/endpoints/media/*` and PRD API surface updated to match implemented endpoints: `/process-{audios|videos|documents|pdfs|ebooks|emails}`, `/process-web-scraping`, `/ingest-web-content`, and `/mediawiki/{process-dump|ingest-dump}` while preserving `/api/v1/media/ingest/jobs*` as the implemented async jobs route family)
- Goal: Keep docs aligned with implemented ingestion job routes.
- Current behavior:
  - Jobs endpoint exists as `/api/v1/media/ingest/jobs*`.
- Target behavior:
  - PRD and related docs consistently reference implemented routes; aliases only if intentionally added.
- Primary code areas:
  - `Docs/Product/Media_Ingestion_Pipeline_PRD.md`
  - `Docs/Product/*` (related references)
- Acceptance criteria:
  - No stale route names in product/design docs.
- Test requirements:
  - Docs review in PR checklist plus route-name grep audit over `Docs/Product`.

## Suggested Delivery Order
1. URL validation parity (Item 1)
2. `/media/add` collections dual-write (Item 2)
3. Embeddings/provenance unification (Item 3)
4. Dedupe clarification + tests (Item 6)
5. Chunk consistency assertions (Item 5)
6. Metadata contract enforcement (Item 4)
7. Metrics standardization (Item 7)
8. Final docs consistency sweep (Item 8)

## Definition of Done for This Checklist
- Each completed item includes:
  - Code changes
  - Unit/integration tests
  - Updated docs and migration notes (if behavior changes)
  - Clear rollback or feature-flag strategy for risky path changes
