# Visual RAG PRD

## Goal

Add visual/vision-aware retrieval to the existing RAG pipeline so that images, figures, screenshots, and video frames can be searched and used as context alongside text. Start with a text-centric representation (captions/OCR) that plugs into the current hybrid RAG, then layer in proper visual embeddings and image-as-query support without disrupting existing API consumers.

## Success Criteria

- Images extracted from ingested media (PDFs, HTML, videos, uploads) are represented as retrievable “documents” in the RAG pipeline.
- `/api/v1/rag/search` can optionally return image-based results (with captions and source references) when relevant to a text query.
- When image-based hits are selected as context for chat, the chat pipeline can surface them as structured context (caption + image reference) without breaking existing text-only flows.
- Visual RAG is *incrementally* adoptable:
  - Phase 1: text-only representation (captions/OCR) with the existing FTS5 + embeddings stack.
  - Phase 2: visual embeddings and cross-modal retrieval for text→image and image→image.
- Visual RAG can be disabled via config/env without impacting existing ingestion or RAG behavior.

## In Scope

- Representation and indexing for image-derived content:
  - Captions generated via an image captioning model (or similar vision model).
  - OCR of text inside images when feasible.
  - Basic metadata (media ID, page/frame index, timestamps, type tags).
- Integration with the existing RAG pipeline:
  - Add “image documents” into full-text and vector indices (Phase 1).
  - Add a dedicated visual embedding collection (Phase 2).
  - Extend RAG search to merge text and visual hits.
- Query handling:
  - Text queries that can surface relevant images as candidates for context.
  - Optional *image-as-query* support (upload or URL) once visual embeddings exist.
- Configuration, observability, and testing for visual RAG.

## Out of Scope (Initial Iteration)

- Full multimodal LLM reasoning in the backend (e.g., sending raw pixels directly to the model in all RAG calls).
- Training/fine-tuning custom vision models.
- A separate visual search UI; initial work focuses on backend capabilities and structured responses.
- Advanced layout-aware reasoning on complex documents (tables, multi-panel figures) beyond what captioning/OCR can provide.

## User Stories

- As a researcher, when I ask “show me the architecture diagram for System X”, the system can retrieve the slide/figure image and present it as part of the answer, not just surrounding text.
- As a user working with a PDF full of charts and plots, I can search “revenue over time” and get both text and the relevant chart images back in the same RAG call.
- As a user analyzing a video, when I search “login screen” or “error popup”, I can get back the corresponding frames with short descriptions.
- As a developer integrating with the API, I can opt into visual RAG via flags/parameters and receive structured metadata describing which images were used and where they came from.

## Constraints and Assumptions

- Existing RAG stack (SQLite FTS5 + Chroma + reranking) remains the primary retrieval engine for text; Visual RAG is layered on top.
- Captioning/OCR may be relatively expensive; the ingestion pipeline must support batching and optional disablement.
- Vision models may require GPU/Metal or be optional extras; deployments without them must still function correctly (Visual RAG disabled or text-only via OCR).
- Storage and retention:
  - Visual documents and embeddings live alongside existing content in the per-user Media DB (`Media_DB_v2`) and per-user embedding spaces.
  - We store image metadata, captions, OCR text, and embeddings, not full-resolution copies beyond existing media storage.
  - Visual documents are deleted or marked deleted when their parent media is soft/hard deleted, following existing soft-delete/versioning patterns.
  - There is a configurable cap on images per media item and optional background cleanup for over-quota visual docs.
- Any visual model selection/config follows existing configuration patterns (config.txt + env overrides).

## Architecture and Design

### Conceptual Model

- **Visual Document**: A logical unit representing an image-derived artifact, stored per user in the existing Media DB (`Media_DB_v2`):
  - `image_id` (primary key within the per-user media DB).
  - `media_id` (link to underlying PDF/video/html/file).
  - `location` (page number / frame index / timestamp).
  - `caption` (generated description).
  - `ocr_text` (optional text recognized in the image).
  - `tags` (e.g., `diagram`, `slide`, `code`, `screenshot`).
- **Text Representation**:
  - A derived text field: `caption + ocr_text + tags`.
  - Indexed in existing FTS5 and embedded into the existing Chroma collection (phase 1).
- **Visual Embedding** (Phase 2):
  - A vector computed from the image itself using a CLIP/SigLIP-like model.
  - Stored in a dedicated “visual” embedding collection keyed by `image_id`.

### Ingestion Flow

- Extend existing ingestion modules (`app/core/Ingestion_Media_Processing/`) with a *VisualIngestion* helper:
  - **PDF/EPUB/HTML**:
    - When parsing pages, extract images/figures where feasible.
    - For each image:
      - Run OCR (for text-like images).
      - Generate a caption using a configured captioning model (if enabled).
      - Compute visual embedding (if visual model configured; phase 2).
      - Persist `VisualDocument` record and index into text/vector stores.
  - **Video/Audio with frames**:
    - Sample frames based on heuristics (e.g., every N seconds, or slide-change detection when available).
    - Treat each sampled frame as a `VisualDocument` with a timestamp.
  - **Uploaded images**:
    - Treat as standalone `VisualDocument` tied to a synthetic `media_id`.

### Database and Indexing

- **Media DB**:
  - Add a `visual_documents` table (or extend an existing table) with columns:
    - `id` (image_id), `media_id`, `location` (page/frame/time), `caption`, `ocr_text`, `tags`, `created_at`.
  - Use existing DB abstractions in `app/core/DB_Management` for access.
- **Full-text Index**:
  - Insert each visual document as a row in the FTS5 table, with:
    - `content_type = 'image'`.
    - `content = caption + ocr_text + tags`.
    - `metadata` referencing `image_id`, `media_id`, `location`.
- **Vector Embeddings (Text)**:
  - For phase 1, use the existing text embedding model to embed `caption + ocr_text`.
  - Store in the existing Chroma collection with additional metadata `{"modality": "image", "image_id": ..., "media_id": ...}`.
- **Vector Embeddings (Visual)**:
  - Introduce a separate “visual” collection in Chroma (or reuse existing infrastructure with a `modality` flag).
  - Embeddings computed via a visual encoder model that supports text and image encoders:
    - `f_image(image) -> embedding`.
    - `f_text_visual(text) -> embedding`.

### Query and Retrieval

#### Text Queries (Phase 1)

- Use current RAG pipeline:
  - FTS5 search over all text documents + visual documents.
  - Vector search over text embeddings (documents + image captions).
  - Reranker (if enabled) processes both text and visual-doc pseudo-text.
- When image-backed results are selected:
  - Surface structured context entries:
    - `{"type": "image", "caption": "...", "image_id": ..., "media_id": ..., "location": ...}`.
  - Clients can choose to fetch thumbnails or previews using existing media APIs or a new helper.

#### Text Queries (Phase 2: Visual Embeddings)

- For a text query:
  - Run standard text RAG as above.
  - Additionally compute `visual_query = f_text_visual(query)` and query the visual embedding collection for top-K images.
  - Merge the candidate sets:
    - Normalize scores (e.g., per-source z-score).
    - Deduplicate via source or rank.
    - Optionally tag each result with its source (`text`, `visual`, `hybrid`).

#### Image-as-Query

- For supported endpoints (new or extended):
  - Accept an uploaded image or an image URL.
  - Compute:
    - `image_query = f_image(query_image)` and search against visual embeddings.
    - Optional OCR + caption for the query image, then text-RAG using that text.
  - Return:
    - Top image hits with captions/metadata.
    - Optionally, relevant text chunks from associated documents.

### Reranking and Context Packaging

- **Reranking (optional)**:
  - For top-N candidates (text + visual), rerank with:
    - A cross-encoder on `(query_text, caption)` or
    - A lightweight similarity heuristic tuned for visual captions.
- **Context packaging for chat**:
  - When passing context to chat:
    - Represent visual hits as structured items:
      - `{"type": "image", "caption": "...", "description": "...", "image_ref": "...", "source": {...}}`.
    - Include a short text description suitable for models that cannot natively see images.
  - Downstream:
    - Chat endpoints can use these objects to format prompts:
      - “The user is also looking at this image: [caption]. It shows: [description].”

## API Surface

### Configuration

- Add a `[Visual-RAG]` section or equivalent config:
  - `enable_visual_rag` (bool; default false).
  - `visual_caption_model` (string; optional).
  - `visual_ocr_enabled` (bool; default true).
  - `visual_embedding_model` (string; optional).
  - `max_images_per_media` (int).
  - `video_frame_sampling_interval_seconds` (int; default e.g. 5 or 10).
  - Environment-variable overrides where appropriate (`VISUAL_RAG_ENABLE`, `VISUAL_RAG_CAPTION_MODEL`, etc.).
- If no visual model is configured and `enable_visual_rag` is true:
  - Use OCR+caption-only text representations (no visual embeddings).
 - Visual model providers are split into:
   - **Local-only**: models that run on the same host (e.g., local CLIP/vision models, on-device OCR).
   - **Remote-allowed**: optional remote captioning/vision providers, configured like other external providers with API keys in `.env` or `config.txt`, and exercised under `external_api` test markers.

### Ingestion

- No new public endpoints required; visual ingestion runs as part of:
  - `/api/v1/media/process` workflows.
  - Any existing background jobs that re-index or re-chunk content.
- Potential extension: a maintenance endpoint to backfill visual documents for existing media (`/api/v1/media/reindex/visual`).

### RAG Search

- Extend existing `/api/v1/rag/search` schema:
  - Add flags:
    - `include_images: bool` (default false).
    - `visual_only: bool` (optional; return only visual hits).
    - `max_image_results: int` (optional).
  - Response shape:
    - `results`: list of entries, each with:
      - `type: "text" | "image"`.
      - `score`.
      - `text` (for text or caption/ocr).
      - `image_metadata` when `type == "image"`:
        - `image_id`, `media_id`, `location`, `thumbnail_url` (if available).
      - `source` (existing media source info).
  - Default behavior (`include_images=false`) preserves current response shapes and semantics; callers that do not opt in to visual RAG continue to see only text-backed results.

### Future (Optional) Endpoints

- Dedicated visual search endpoint:
  - `POST /api/v1/rag/search/visual`:
    - Accepts text or image query.
    - Returns image-heavy results with optional linked text.

## Validation and Testing

- **Unit Tests**:
  - Visual document creation from synthetic images and text (captions + OCR).
  - FTS5 entry generation for visual documents.
  - Embedding pipeline for visual documents (text embeddings and visual embeddings).
  - Merge logic for text and visual search results.
- **Integration Tests**:
  - Ingest a small PDF/HTML with images and verify:
    - `/api/v1/rag/search` with `include_images=true` returns image-backed hits.
  - Ingest a short video (or synthetic frame set) and verify:
    - Frame-based images are created and retrievable by text queries.
  - Where hardware permits, an optional `@pytest.mark.local_llm_service` style test that exercises a real visual embedding model.
- **Performance/Regression**:
  - Measure additional ingestion time for captioning/OCR.
  - Measure search latency with and without visual RAG enabled.
  - Ensure visual RAG does not materially degrade baseline RAG performance when disabled.

## Observability

- Metrics:
  - `visual_docs_indexed_total` (per media type).
  - `visual_rag_queries_total` and latency histograms.
  - `visual_rag_hits_per_query` distribution (for tuning thresholds).
- Logging:
  - Debug logs when visual models are unavailable/configured incorrectly.
  - Summaries of how many images per media were processed and indexed.
  - Optional tracing hooks for end-to-end RAG flows including visual components.

## Security and Privacy

- Images and derived captions/OCR may contain sensitive data.
  - Respect existing data handling policies and AuthNZ model (per-user DBs).
  - Do not send images to remote captioning/vision services unless explicitly configured by the user and documented; remote providers follow the same API key and provider-config conventions as other external LLM/RAG services.
- For deployments that cannot process images:
  - `enable_visual_rag=false` ensures no extra processing is done.
  - Visual ingestion paths should be fully no-op when disabled.

## Resource Governance and Limits

- Visual ingestion (captioning/OCR/visual embeddings) and visual RAG queries participate in the existing Resource Governance (RG) framework:
  - Visual operations are wrapped in `RGRequest`-style accounting where appropriate, with per-tenant/provider quotas aligned to RAG and Media ingestion policies.
  - Configurable limits (e.g., `max_images_per_media`, max visual docs per user) are enforced at ingestion time, with deterministic failure or graceful degradation (skip extra images) when exceeded.
- Visual RAG should not introduce new ungoverned code paths that bypass RG, rate limiting, or usage tracking.

## Error Handling

- If captioning/visual models are misconfigured or unavailable:
  - Log a warning and fall back to OCR-only or no visual document generation.
  - RAG search should still function with text-only results.
- If visual embedding computation fails for a given image:
  - Skip visual embedding for that image, but keep text representation.
- RAG search errors:
  - Keep existing error contract; visual RAG should not introduce new failure modes for callers that do not request images.

## Rollout Plan

1. **Phase 1: Text-only Visual RAG**
   - Implement visual document representation, DB schema, and FTS5/text embedding indexing.
   - Wire basic image-backed results into `/api/v1/rag/search` with `include_images` flag.
   - Add minimal tests and metrics.
2. **Phase 2: Visual Embeddings and Cross-Modal Retrieval**
   - Integrate a configurable vision encoder (CLIP/SigLIP or similar).
   - Add visual embedding collection and dual-path retrieval (text + visual).
   - Implement optional image-as-query support.
   - Add reranking and additional tests.
3. **Phase 3: UX and Documentation**
   - Document configuration keys, limitations, and hardware expectations.
   - Provide API examples for text and image queries and how clients should render visual results.
   - Iterate based on feedback, adjust defaults (e.g., frame sampling rate, max images per media).

## Open Questions

- Which vision models should be recommended by default (performance vs. quality trade-offs)?
- How aggressive should frame extraction be for videos (time-based vs. scene-change-based)?
- How should visual results be ordered relative to text results by default (e.g., interleaved vs. separate sections)?
- Should we expose per-user or per-workspace visual RAG limits (max images, storage quotas)?
