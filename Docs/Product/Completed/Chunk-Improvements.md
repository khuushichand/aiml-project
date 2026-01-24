# Chunk-Improvements: Unified Chunk Metadata and Citation Enhancements

## Goal
- Unify chunk metadata across ingestion, embeddings, and RAG to enable:
  - Reliable filtering by `chunk_type` (text, table, list, code, media)
  - Precise citation and UI highlighting using offsets/page/timestamps
  - Cleaner hierarchy context (`ancestry_titles`, `section_path`)
  - Compact, JSON-safe payloads for Chroma while keeping heavy details in SQL

## Scope
- Map external “Block” models to tldw_server metadata keys
- Extend chunker outputs with normalized fields (plaintext first)
- Persist plaintext chunks and enable chunk-level FTS search
- Ensure RAG pipeline can filter and surface new fields
- Backfill/migrate minimal metadata for existing embeddings (best-effort)

Non-Goals
- Replacing current chunking strategies
- Rewriting the vector store or DB schema
- Moving large binary/geometry metadata into Chroma

## Implementation Status (Snapshot)
- Stage 1 (schema + adapters): Implemented (RAGChunkMetadata/CitationSpan + block adapter + tests).
- Stage 2 (chunker normalization): Implemented (`chunk_type` now set in flattened hierarchical chunks).
- Stage 2.5 (plaintext chunk persistence + FTS): Implemented (chunk-level FTS wiring + integration test).
- Stage 3 (embedding metadata enrichment): Implemented (Chroma metadata enriched with chunk + citation fields).
- Stage 4 (RAG retrieval + filtering): Implemented (metadata mapping + filter + chunk citations test).
- Stage 5 (backfill): Implemented (optional backfill script available).

## Current State (Relevant Touch-Points)
- Hierarchical chunk metadata produced in chunker:
  - `ancestry_titles`, `section_path`, `paragraph_kind`, offsets
  - File: `tldw_Server_API/app/core/Chunking/chunker.py:361`
  - File: `tldw_Server_API/app/core/Chunking/chunker.py:405`
- Embedding upsert sets core metadata per chunk:
  - `media_id`, `file_name`, `chunk_index`, `total_chunks`, `start_char`, `end_char`
  - Optional contextual header/summary
  - File: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py:936`
  - File: `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py:901`
- RAG supports metadata filtering on `chunk_type`:
  - File: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:835`
- RAG `Document` supports citation spans and location fields:
  - File: `tldw_Server_API/app/core/RAG/rag_service/types.py:122`
- Chunk-level FTS exists and is selectable via `fts_level`:
  - File: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py:1972`
  - File: `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py:279`
  - File: `tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py:133`
- Plaintext chunks persisted with `chunk_type` + offsets (SQL):
  - File: `tldw_Server_API/app/core/Ingestion_Media_Processing/persistence.py:1104`

## Proposed Metadata (Normalized)

Top-level (stored in Chroma metadata):
- `media_id: str` - lineage
- `file_name: str`
- `chunk_index: int`, `total_chunks: int`
- `start_char: int?`, `end_char: int?` - text offsets
- `chunk_type: "text"|"table"|"list"|"code"|"media"|"heading"|"vlm"`
- `section_path: str?`, `ancestry_titles: list[str]?`
- `language: str?`
- `code_language: str?` (when `chunk_type=code`)
- `list_style: str?` (bullet, numbered) (when `chunk_type=list`)
- `table_row: int?`, `table_col: int?` (when `chunk_type=table`)
- `context_header: str?`, `contextual_summary_ref: str?` (contextual chunking)

Nested citation object (compact scalars only):
- `citation.page_number: int?`, `paragraph_number: int?`, `line_number: int?`
- `citation.slide_number: int?`
- `citation.row_number: int?`, `citation.column_number: int?`, `citation.sheet_name: str?`
- `citation.start_timestamp_ms: int?`, `citation.end_timestamp_ms: int?`
- `citation.bbox_quad: list[{x: float, y: float}]?` (4 points max)

Heavier or verbose fields (images, full table structures, long annotations) stay in SQL.

## Mapping from External Block Schema
- BlockType → `chunk_type`
  - TEXT/PARAGRAPH/TEXTSECTION/HEADING → `text` (or `heading` for headings)
  - TABLE/TABLE_ROW/TABLE_CELL → `table`
  - BULLET_LIST/NUMBERED_LIST → `list`
  - CODE → `code`
  - IMAGE/VIDEO/AUDIO/FILE → `media`
- CodeMetadata.language → `code_language`
- ListMetadata.list_style → `list_style`
- TableCell/Row → `table_row`, `table_col`
- CitationMetadata.* → `citation.*` (normalize timestamps to ms; keep bbox 4 points)

## Design Notes
- Keep Chroma metadata small and flat for performance; nest only under `citation`.
- Always set `chunk_type` to unlock existing filter support.
- Offsets (`start_char`, `end_char`) align with RAG `Document` for precise citation rendering.
- When contextual chunking is enabled, also store `context_header` and `contextual_summary_ref`.
- FTS-first emphasis: plaintext chunk storage + FTS drives retrieval; vector search remains optional and secondary.
- Canonical `chunk_type` values are listed above; normalize synonyms:
  - `header`, `header_atx`, `header_line` -> `heading`
  - `paragraph` -> `text`
  - VLM hint chunks (non-table) -> `vlm` (or `media` if they represent a true media artifact)

## Configuration
- Default FTS granularity can be set globally:
  - Env: `RAG_DEFAULT_FTS_LEVEL=media|chunk` (media is default)
  - Config file: `tldw_Server_API/Config_Files/config.txt`
    - `[RAG]` section: `default_fts_level = media` or `chunk`
- Request override: API consumers may send `fts_level` in the body to override the default per request.

## Implementation Stages

### Stage 1: Schema + Adapters
Goal: Define types and mapping helpers.
Success Criteria:
- Pydantic models validate normalized metadata
- Conversion util maps external Block payloads to flattened chunks with our metadata
Status: Complete
Changes:
- Add `RAGChunkMetadata` and `CitationSpan` models under `tldw_Server_API/app/core/RAG/` (schema helper module)
- Add `block_to_chunks.py` adapter (pure function) to map Blocks → [{text, metadata}]
Tests:
- `tldw_Server_API/tests/RAG_NEW/unit/test_block_to_chunks.py`

### Stage 2: Chunker Output Normalization
Goal: Ensure `chunk_type` is set and offsets propagate consistently.
Success Criteria:
- Hierarchical paths populate `section_path`/`ancestry_titles`
- `chunk_type` present on all chunks (derived from paragraph kind / strategy)
Status: Complete
Changes:
- Extend `chunk_text_hierarchical_flat` path to add `chunk_type` from `paragraph_kind`
- Keep existing offsets and titles intact
Files:
- `tldw_Server_API/app/core/Chunking/chunker.py:342`
- `tldw_Server_API/app/core/Chunking/chunker.py:396`
Tests:
- `tldw_Server_API/tests/Chunking/test_chunker_v2.py`

### Stage 2.5: Plaintext Chunk Persistence + FTS (Primary)
Goal: Persist normalized plaintext chunks and enable chunk-level FTS search.
Success Criteria:
- `UnvectorizedMediaChunks` receives records with `chunk_type`, `start_char`, `end_char`, and compact `metadata` JSON
- Optionally, a chunk-level FTS virtual table exists and is populated (or a retrieval path that searches chunk text directly)
- RAG retrieval can run FTS on chunk text (media-level remains available)
Status: Complete
Changes:
- Use `MediaDatabase.update_media(..., chunks=[...])` to persist chunks (auto-inserts into `UnvectorizedMediaChunks`)
  - File: `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py:3305`
- Add a minimal worker/utility to (re)build chunk-level FTS if adopted, e.g.,
  - `CREATE VIRTUAL TABLE IF NOT EXISTS unvectorized_chunks_fts USING fts5(chunk_text, media_id UNINDEXED, chunk_index UNINDEXED, content='UnvectorizedMediaChunks', content_rowid='id');`
  - After inserts, run `INSERT INTO unvectorized_chunks_fts(unvectorized_chunks_fts) VALUES('rebuild');` or maintain via triggers.
- Retrieval: extend `MediaDBRetriever` or add `MediaChunkFTSRetriever` to query chunk-level FTS when `fts_level='chunk'`.
- API: expose a parameter (e.g., `fts_level: 'media'|'chunk'`) in RAG unified requests (default 'media').
Tests:
- `tldw_Server_API/tests/RAG_NEW/unit/test_chunk_fts_integration.py`

### Stage 3 (Optional): Embedding Metadata Enrichment
Goal: Upsert normalized metadata to Chroma consistently.
Success Criteria:
- Upserts include `chunk_type`, offsets, and optional `citation` fields
- Contextual header stored when enabled
Status: Complete
Changes:
- Merge new fields into `meta` before `store_in_chroma`
Files:
- `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py:936`
- `tldw_Server_API/app/core/Embeddings/ChromaDB_Library.py:901`
Tests:
- `tldw_Server_API/tests/ChromaDB/unit/test_chromadb_manager.py`

### Stage 4: RAG Retrieval & Filtering (FTS-first)
Goal: Leverage `chunk_type` and surfaces citation/location in responses.
Success Criteria:
- `chunk_type_filter` works against enriched metadata
- Retrieved `Document` objects carry location fields mapped from metadata
Status: Complete
Changes:
- Ensure database/vector adapters pass through metadata unmodified
- Map `start_char`, `end_char`, `page_number`, etc., into `Document` (if not already)
Files:
- `tldw_Server_API/app/core/RAG/rag_service/database_retrievers.py:236`
- `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py:835`
Tests:
- `tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline.py`

### Stage 5: Backfill (Optional)
Goal: Opportunistic metadata enrichment for existing collections.
Success Criteria:
- Script can patch `chunk_type` heuristically (based on `paragraph_kind` substrings)
Status: Complete (script added; optional to run)
Changes:
- Add a maintenance script that scans collections and updates metadatas in place (guarded and idempotent)
Tests:
- `tldw_Server_API/tests/Embeddings/test_chunk_metadata_backfill.py`
Notes:
- Backfill script: `Helper_Scripts/backfill_chunk_metadata.py`
- Dry-run example: `python Helper_Scripts/backfill_chunk_metadata.py --user-id 1 --all --dry-run`
- Apply to one collection: `python Helper_Scripts/backfill_chunk_metadata.py --user-id 1 --collection user_1_media_embeddings`

## Test Plan
- Unit: adapter mapping, metadata models, hierarchical flattening chunk_type
- Integration: plaintext persistence writes rows; FTS queries return expected chunks; RAG filter returns only requested `chunk_type`
- Property tests: metadata keys remain JSON-safe, no large payloads in Chroma

## Migration / Compatibility
- New fields are additive; existing clients unaffected
- RAG filter already guards missing `chunk_type`; default to include all
- Backfill optional

## Metrics & Logging
- Observe proportion of chunks with `chunk_type`
- Track average metadata size per upsert
- Log citation fields presence for multi-modal sources

## Risks & Mitigations
- Chroma metadata bloat → keep fields compact; move heavy data to SQL
- Inconsistent `chunk_type` from sources → normalize via adapter and chunker
- PDF bbox variability → constrain to 4-point quads only

## Open Questions
- Do we want a dedicated UI overlay for table cell/row citations? - In Next.js WebUI: yes
- Should we persist contextualized text in Chroma’s documents or keep only original + header? - 

## Rollout Checklist
- [x] Stage 1 merged with unit tests
- [x] Stage 2 chunker outputs `chunk_type`
- [x] Stage 2.5 plaintext chunk persistence + FTS wired
- [x] Stage 3 embedding metadata enriched
- [x] Stage 4 e2e RAG filter and citations validated
- [ ] (Optional) Backfill run on key collections (script available)
