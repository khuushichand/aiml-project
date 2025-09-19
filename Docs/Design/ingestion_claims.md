# Ingestion-Time Claims (Factual Statements) — Design

## Goal

Precompute concise, verifiable factual statements ("claims") for each chunk at ingestion time so that:
- Retrieval can target claims (FTS and optionally vectors) to improve precision for fact-seeking queries.
- RAG factuality workflows can leverage pre-extracted claims to reduce runtime cost.

This feature is optional, gated by settings, and designed to be reversible and low-risk.

## Scope (Stage 1)

- Add schema support for storing claims in the Media database (SQLite, default).
- Create optional FTS table for claims. No triggers or auto-sync in Stage 1 (search integration comes later).
- Provide minimal CRUD/helpers to insert and read claims.

Later stages (not in this change): background processing, embedding claims into Chroma, retriever integration, and RAG usage.

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

FTS (optional for Stage 1)
- `claims_fts` (FTS5) with `claim_text`, `content='Claims'`, `content_rowid='id'`
- Stage 1: created but not yet synchronized via triggers; insertion helpers may update FTS explicitly in later stages.

## Configuration (future)

- `ENABLE_INGESTION_CLAIMS` (bool, default: false)
- `CLAIM_EXTRACTOR_MODE` (heuristic|llm|auto, default: heuristic)
- `CLAIMS_MAX_PER_CHUNK` (default: 3)
- `CLAIMS_EMBED` (bool, default: false)
- `CLAIMS_EMBED_MODEL_ID` (string)

## Pipeline Hook (future)

After chunking and before/alongside embedding, optionally run a lightweight extractor (heuristic first) and store results in `Claims`. Embedding and retriever integration will follow in later stages.

## Testing (Stage 1)

- Verify `Claims` table and `claims_fts` exist for new DBs and are created for existing DBs at initialization.
- Insert and read back claims tied to a media row.

## Rollback

Feature is additive. If disabled, code paths do not write to `Claims`. Removing the table is not required for rollback.

