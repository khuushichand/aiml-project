## Stage 1: Visual Document Scaffolding (aligns with Phase 1 in Visual RAG PRD)
**Goal**: Introduce a first-class VisualDocument concept, DB schema, and minimal ingestion hooks that create caption/OCR-based records without yet wiring into search.

**Success Criteria**:
- A VisualDocument (or equivalent) schema exists in the per-user Media DB (`Media_DB_v2`) with fields for `image_id`, `media_id`, `location`, `caption`, `ocr_text`, `tags`, and timestamps.
- Ingestion paths for PDFs/HTML (and at least one additional media type) can optionally extract images/figures and persist VisualDocument rows, guarded by a config flag (e.g., `enable_visual_rag`).
- Visual ingestion is a no-op when disabled and does not affect existing ingestion behavior or tests.
- Schema migrations for VisualDocument/visual tables are implemented using existing migration helpers and are additive (no destructive changes to existing tables).

**Tests**:
- Unit tests for VisualDocument creation helpers (given synthetic image metadata and caption/OCR text, verify correct DB rows are produced).
- Unit tests for ingestion hooks that, when `enable_visual_rag=true`, call the visual ingestion helper for at least one media type and do nothing when disabled.
- Migration/DB tests that ensure VisualDocument tables are created and queried through the existing DB abstraction layer without impacting other tables.

**Status**: Not Started

---

## Stage 2: Text-Only Visual RAG Integration (aligns with Phase 1 in Visual RAG PRD)
**Goal**: Index VisualDocuments into the existing RAG pipeline using captions/OCR as text so that images become retrievable pseudo-documents in FTS5 and the text embedding store.

**Success Criteria**:
- VisualDocuments are inserted into the FTS5 index with appropriate `content_type`/metadata so they can be retrieved alongside text chunks.
- The text embedding pipeline embeds `caption + ocr_text` for VisualDocuments using the existing RAG embedding model, with modality metadata stored in Chroma.
- The core RAG search flow (FTS5 + embeddings + reranking) can surface VisualDocuments when `include_images=true` or equivalent flag is set, without changing default behavior when the flag is false.

**Tests**:
- Unit tests for FTS5 record construction from VisualDocuments (verify `content`, `content_type`, and metadata fields).
- Unit tests for text-embedding indexing of VisualDocuments (verify embeddings are created and written with modality metadata).
- Integration test: ingest a small synthetic document with at least one image, then call `/api/v1/rag/search` with a query that should match the image caption and `include_images=true`; verify that at least one image-backed result is present with correct metadata.
- Simple performance test or benchmark check that compares ingestion time with `enable_visual_rag` on vs off (on a small fixture) to ensure overhead is understood and within acceptable bounds.
- Tests marked with appropriate markers (e.g., `local_llm_service` or `external_api`) when they depend on external captioning/OCR services, with skips when models/services are not configured.
- (Optional or deferred) Backfill test: if a backfill job/endpoint is implemented, verify that running it on existing media produces VisualDocuments consistent with ingestion-time behavior; otherwise, explicitly document that backfill is out-of-scope for v1.

**Status**: Not Started

---

## Stage 3: Visual Embeddings and Cross-Modal Retrieval (aligns with Phase 2 in Visual RAG PRD)
**Goal**: Add a configurable vision encoder and visual embedding collection to support text→image and image→image retrieval, and merge visual hits into the existing RAG result set.

**Success Criteria**:
- A vision encoder can be configured via config/env (e.g., CLIP/SigLIP or equivalent) with a clear “off” state where visual embeddings are not computed.
- A visual embedding collection exists (in Chroma or equivalent) keyed by `image_id`, populated during ingestion when the visual encoder is enabled.
- RAG search can:
  - For text queries: compute a visual text embedding and retrieve top-K images from the visual collection.
  - Optionally accept image queries (uploaded image/URL) and retrieve similar images.
- Merging logic combines text-based and visual-based candidates into a single ranked set, with source/modality metadata preserved.

**Tests**:
- Unit tests for visual embedding helper functions (given a mock encoder or stub, verify that image/ caption inputs lead to expected embedding writes).
- Unit tests for merge logic that takes text and visual candidate lists and produces a stable combined ranking with correct metadata.
- Integration tests (behind `local_llm_service` or similar marker) that, when a visual encoder is available, ingest a small dataset and verify that:
  - Text queries can retrieve images via visual embeddings.
  - Image queries can retrieve similar images.
- Fallback tests verifying that when visual models are disabled or unavailable, RAG search still functions and visual paths are cleanly skipped.
- Failure-path tests that cover:
  - Misconfigured vision encoder (invalid model name, missing weights) leading to logged warnings and fallback to text-only VisualDocuments without crashing ingestion.
  - Visual embedding failures for individual images (e.g., OOM or decode errors) causing those images to be skipped while ingestion continues for the rest.
  - RAG search with `include_images=true` when no visual embeddings exist (returns either text-only visual docs or an empty image section without errors).

**Status**: Not Started

---

## Stage 4: API Surface, UX, and Documentation (aligns with Phase 3 in Visual RAG PRD)
**Goal**: Expose visual RAG capabilities in the API in a controlled, backwards-compatible way, and document configuration, limitations, and usage patterns.

**Success Criteria**:
- `/api/v1/rag/search` (or a closely related endpoint) accepts flags such as `include_images`, `visual_only`, and `max_image_results` with sane defaults.
- Search responses can include both text and image-backed results using a consistent schema (`type`, `score`, `text`, `image_metadata`, `source`), and existing clients remain compatible when ignoring new fields.
- Chat context-building code can consume image-backed results and emit structured context entries suitable for LLM prompts (without requiring models to be natively multimodal).
- Documentation in `Docs/Product/Vision-RAG-add-PRD.md` is complemented by user-facing docs (e.g., under `Docs/RAG` or `Docs/User_Guides`) that show how to configure and use visual RAG.

**Tests**:
- API-level tests that exercise `/api/v1/rag/search` with and without visual flags, verifying response shape and backwards compatibility.
- Tests for chat context-building that, given a mix of text and image-backed search results, produce stable and safe prompt text for downstream LLM calls.
- Docs lint/checks (where applicable) to ensure new docs are included in navigation and that configuration keys are accurate.
- Config validation tests that ensure `[Visual-RAG]` settings are parsed correctly (including invalid model names/flags), and that `enable_visual_rag=false` results in no visual ingestion and no changes to RAG behavior even when visual models are configured.
- Governance tests (unit or integration) that verify visual ingestion and search participate in Resource Governance (RG) and rate-limiting where appropriate (e.g., Visual RAG requests are counted similarly to text RAG).

---

## Roll-Forward / Rollback Considerations

- Schema additions for Visual RAG are additive and backward compatible; existing deployments can run migrations without changing behavior until `enable_visual_rag=true` is set.
- Disabling `enable_visual_rag` (and related flags) fully reverts runtime behavior to baseline text-only RAG, leaving only the additional tables/columns in place.
- Visual embedding collections and indices can be safely ignored or garbage-collected if the feature is rolled back, provided the RAG pipeline continues to treat missing visual indexes as “visual disabled”.

**Status**: Not Started
