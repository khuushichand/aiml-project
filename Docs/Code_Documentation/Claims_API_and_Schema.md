# Claims API and Schema

## Overview

The claims subsystem extracts concise, verifiable factual statements ("claims") from ingested content and makes them searchable and rebuildable. Two usage modes exist:
- Ingestion-time: After chunking, optionally extract a small number of claims per chunk and store them in the Media DB for search/RAG pipelines.
- Answer-time: Extract and verify claims from generated answers (see Claims Engine in design docs), not covered by these endpoints.

This page documents the database schema, configuration, ingestion hook, background service, and the Claims API.

## Database Schema (Media DB v2)

Table: `Claims`
- `id` INTEGER PRIMARY KEY AUTOINCREMENT
- `media_id` INTEGER NOT NULL (FK -> Media.id, ON DELETE CASCADE)
- `chunk_index` INTEGER NOT NULL
- `span_start` INTEGER NULL
- `span_end` INTEGER NULL
- `claim_text` TEXT NOT NULL
- `confidence` REAL NULL
- `extractor` TEXT NOT NULL (e.g., heuristic|llm|auto|provider)
- `extractor_version` TEXT NOT NULL
- `chunk_hash` TEXT NOT NULL (sha256 of the source chunk text)
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

FTS (SQLite)
- `claims_fts` (FTS5) with `claim_text`, `content='Claims'`, `content_rowid='id'`
- Triggers keep `claims_fts` synchronized on INSERT/UPDATE/DELETE of `Claims`.

Helpers (MediaDatabase)
- `upsert_claims(rows) -> int`
- `get_claims_by_media(media_id, limit=100) -> List[dict]`
- `soft_delete_claims_for_media(media_id) -> int`
- `rebuild_claims_fts() -> int`

## Configuration

Env or `[Claims]` in `Config_Files/config.txt`:
- `ENABLE_INGESTION_CLAIMS` (bool, default: false)
- `CLAIM_EXTRACTOR_MODE` (heuristic|llm|auto|<provider>, default: heuristic)
- `CLAIMS_MAX_PER_CHUNK` (int, default: 3)
- `CLAIMS_EMBED` (bool, default: false)
- `CLAIMS_EMBED_MODEL_ID` (string, optional)
- `CLAIMS_LLM_PROVIDER`, `CLAIMS_LLM_MODEL`, `CLAIMS_LLM_TEMPERATURE` (used when an LLM extractor is selected)

Provider resolution for ingestion LLM extraction follows this order:
- Use `CLAIMS_LLM_PROVIDER`, `CLAIMS_LLM_MODEL`, `CLAIMS_LLM_TEMPERATURE` when set.
- Otherwise use `RAG.default_llm_provider` and `RAG.default_llm_model`.
- Finally use `default_api` with a conservative temperature (default `0.1`).

## Ingestion Hook

If `ENABLE_INGESTION_CLAIMS=True`, the embeddings pipeline (`ChromaDB_Library`) will:
- Extract claims from generated chunks using the configured extractor mode.
- Store them in `Claims` and maintain `claims_fts`.
- Optionally embed claims into a dedicated Chroma collection when `CLAIMS_EMBED=True`.

## Background Service

`ClaimsRebuildService` runs in the background to rebuild claims for media items by:
- Chunking saved content
- Extracting claims (`heuristic|llm|auto|provider`)
- Soft-deleting old entries and inserting new rows with chunk hashes

Exposed via API endpoints to enqueue work per media or in bulk.

## API Endpoints

Base prefix: `/api/v1/claims`

- `GET /{media_id}` - List claims for a media item
  - Optional query params:
    - `limit` (default 100)
    - `offset` (default 0)
    - `envelope` (default false) - when true, returns an envelope instead of a bare list
    - `user_id` (admin only) to select another user’s media DB
  - Response:
    - when `envelope=false`: `List[ClaimRow]` (DB rows excluding `deleted`), ordered by `chunk_index` then `id`
    - when `envelope=true`: `{ "items": List[ClaimRow], "next_offset": int|null, "total": int, "total_pages": int, "next_link": string|null }`
      - `next_link` is a simple link preserving `limit`, `offset`, `envelope`, and `absolute_links`; includes `user_id` when admin overrides are used.
      - Add `absolute_links=true` to return a fully qualified `next_link`.

- `POST /{media_id}/rebuild` - Enqueue rebuild for a media item
  - Optional (admin): `user_id` to target another user DB
  - Response: `{ "status": "accepted", "media_id": <id> }`

- `POST /rebuild/all` - Enqueue rebuild across media
  - Query param `policy`: `missing` (default)|`all`|`stale`
  - Optional (admin): `user_id`
  - Response: `{ "status": "accepted", "enqueued": <count>, "policy": "..." }`

- `POST /rebuild_fts` - Rebuild `claims_fts` from `Claims`
  - Optional (admin): `user_id`
  - Response: `{ "status": "ok", "indexed": <count> }`

Security & tenancy
- Endpoints operate on the current user’s Media DB by default.
- Admins can override target user via `user_id` for maintenance tasks.

## Examples

List claims
```bash
curl -s -H "Authorization: Bearer <JWT>" \
  "http://127.0.0.1:8000/api/v1/claims/123?limit=50"
```
Response (truncated)
```json
[
  {
    "id": 42,
    "media_id": 123,
    "chunk_index": 5,
    "span_start": null,
    "span_end": null,
    "claim_text": "Alice founded Acme in 2020.",
    "confidence": null,
    "extractor": "heuristic",
    "extractor_version": "v1",
    "chunk_hash": "...",
    "created_at": "...",
    "uuid": "...",
    "last_modified": "...",
    "version": 1,
    "client_id": "SERVER_API_V1"
  }
]
```

Enqueue rebuild for a single item
```bash
curl -s -X POST -H "Authorization: Bearer <JWT>" \
  "http://127.0.0.1:8000/api/v1/claims/123/rebuild"
```

Bulk rebuild for missing claims
```bash
curl -s -X POST -H "Authorization: Bearer <JWT>" \
  "http://127.0.0.1:8000/api/v1/claims/rebuild/all?policy=missing"
```

Rebuild FTS
```bash
curl -s -X POST -H "Authorization: Bearer <JWT>" \
  "http://127.0.0.1:8000/api/v1/claims/rebuild_fts"
```

## Notes

- Ingestion-time extraction can be enabled selectively; not all ingestion paths invoke it by default.
- The answer-time Claims Engine (APS/LLM extractor + Hybrid verifier) is documented in design and is separate from these API endpoints.
- `GET /status` - Claims rebuild worker status (admin only)
  - Response: `{ "status": "ok", "stats": { "enqueued": int, "processed": int, "failed": int }, "queue_length": int, "workers": int }`
