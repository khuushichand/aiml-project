# Ingestion-Time Claims (Factual Statements) - Design

## Goal

Precompute concise, verifiable factual statements ("claims") for each chunk at ingestion time so that:
- Retrieval can target claims (FTS and optionally vectors) to improve precision for fact-seeking queries.
- RAG factuality workflows can leverage pre-extracted claims to reduce runtime cost.

This feature is optional, gated by settings, and designed to be reversible and low-risk. It is wired into the embeddings pipeline and can also be rebuilt asynchronously.

## Scope

- Add schema support for storing claims in the Media database (SQLite by default; PostgreSQL supported).
- Create FTS table for claims and keep it synchronized. SQLite uses FTS5 with triggers; PostgreSQL uses a tsvector column.
- Provide minimal CRUD/helpers to insert, search, and rebuild the FTS index.

Later stages (already partially implemented): background processing, embedding claims into Chroma, retriever integration, and RAG usage.

## Data Model

Table: `Claims`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `media_id` INTEGER NOT NULL (FK -> Media.id, ON DELETE CASCADE)
- `chunk_index` INTEGER NOT NULL
- `span_start` INTEGER NULL
- `span_end` INTEGER NULL
- `claim_text` TEXT NOT NULL
- `confidence` REAL NULL
- `extractor` TEXT NOT NULL (heuristic|llm|auto)
- `extractor_version` TEXT NOT NULL
- `chunk_hash` TEXT NOT NULL
- `created_at` DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
- `uuid` TEXT UNIQUE NOT NULL
- `last_modified` DATETIME NOT NULL
- `version` INTEGER NOT NULL DEFAULT 1
- `client_id` TEXT NOT NULL
- `deleted` BOOLEAN NOT NULL DEFAULT 0
- `prev_version` INTEGER NULL
- `merge_parent_uuid` TEXT NULL

Indexes
- `idx_claims_media_id` on `(media_id)`
- `idx_claims_media_chunk` on `(media_id, chunk_index)`
- `idx_claims_uuid` UNIQUE on `(uuid)`
- `idx_claims_deleted` on `(deleted)`

FTS
- `claims_fts` (FTS5) with `claim_text`, `content='Claims'`, `content_rowid='id'` (SQLite)
- SQLite triggers keep `claims_fts` synchronized on INSERT/UPDATE/DELETE of `Claims`.
- PostgreSQL maintains a `claims_fts_tsv` column (tsvector) and rebuild support is provided.

## Configuration

- `ENABLE_INGESTION_CLAIMS` (bool, default: false)
- `CLAIM_EXTRACTOR_MODE` (heuristic|llm|auto, default: heuristic)
- `CLAIMS_MAX_PER_CHUNK` (default: 3)
- `CLAIMS_EMBED` (bool, default: false)
- `CLAIMS_EMBED_MODEL_ID` (string)
- `CLAIMS_LLM_PROVIDER`, `CLAIMS_LLM_MODEL`, `CLAIMS_LLM_TEMPERATURE` (used when `CLAIM_EXTRACTOR_MODE` uses an LLM)

## Pipeline Hook

After chunking and before/alongside embedding, optionally run a lightweight extractor (heuristic first by default) and store results in `Claims`. See `tldw_Server_API.app.core.Embeddings.ChromaDB_Library` for the integration behind `ENABLE_INGESTION_CLAIMS`. Optionally, claims can be embedded into a separate collection when `CLAIMS_EMBED=True`.

## Testing

- Verify `Claims` table and `claims_fts` exist and triggers are installed for SQLite.
- Insert and read back claims tied to a media row; confirm `claims_fts` reflects changes.
- Exercise rebuild endpoints and background service.

## Rollback

Feature is additive. If disabled, code paths do not write to `Claims`. Removing the table is not required for rollback.

## APIs & Services

- `GET /api/v1/claims/{media_id}` - list claims for a media item
- `POST /api/v1/claims/{media_id}/rebuild` - enqueue rebuild for a media item
- `POST /api/v1/claims/rebuild/all` - enqueue rebuild for all items (policies: `missing|all|stale`)
- `POST /api/v1/claims/rebuild_fts` - rebuild `claims_fts` from `Claims`

Background service: `ClaimsRebuildService` manages a worker thread that rebuilds claims by chunking, extracting (`heuristic|llm|auto`), and storing with chunk hashes. See `tldw_Server_API.app.services.claims_rebuild_service`.
