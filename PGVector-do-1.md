# PGVector-do-1 — Enable pgvector as an embeddings datastore

Status: In Progress • Owner: Platform • Related: Docs/Design/scale_to_millions.md, docker-compose.pg.yml

## Executive Summary

We will enable PostgreSQL + pgvector as a first‑class embeddings datastore across the API and worker paths while preserving the existing Chroma mode for small/local installs. The codebase already ships a pluggable VectorStore layer and a working `PGVectorAdapter`; the work focuses on unifying storage writes in the embeddings pipeline, validating retrieval, migration tooling, and production hardening (observability, indexes, and CI).

Target outcome: prod‑ready pgvector path with clear config, safe migration/rollback, and test coverage.

---

## Scope

In scope
- Use `PGVectorAdapter` for reads/writes in the Vector Store API and storage worker.
- Config wiring and docs for `RAG.vector_store_type=pgvector` and connection params.
- Indexing defaults (HNSW or IVFFLAT fallback), session `ef_search` control.
- Soft‑delete propagation and dimension enforcement via adapter.
- Minimal migration helper (Chroma → pgvector) and dev stack (docker compose).
- Focused tests (unit + live opts) and optional CI job with Postgres service.

Out of scope (v0)
- Full Postgres unification for all runtime DBs (Media_DB_v2 remains SQLite by default).
- Multi‑tenant RLS setup in Postgres (documented as optional).

---

## Current State (as of this plan)

- Adapter/factory present:
  - `tldw_Server_API/app/core/RAG/rag_service/vector_stores/base.py:1` (interface)
  - `tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py:1` (pgvector)
  - `tldw_Server_API/app/core/RAG/rag_service/vector_stores/factory.py:1` (registry + settings)
- Config support: `tldw_Server_API/app/core/config.py:2034` (RAG.pgvector block)
- Vector Store API already uses the adapter (works with pgvector):
  - `tldw_Server_API/app/api/v1/endpoints/vector_stores_openai.py:591`
- Storage worker still uses Chroma collection calls; adapter selected but not used for writes:
  - `tldw_Server_API/app/core/Embeddings/workers/storage_worker.py:320`
- Devops: `docker-compose.pg.yml` (pgvector image), migration helper `Helper_Scripts/pgvector_migrate_hnsw.py`
- Tests: unit helpers + opt‑in live smoke (PG_TEST_DSN)

---

## Plan & Deliverables

### Phase 0 — Infra & Config (1 day) ✅ Complete
Goal: Stand up pgvector locally; verify adapter path via Vector Store API.

- Tasks
  - Bring up Postgres + pgvector: `docker-compose -f docker-compose.pg.yml up -d`.
  - Configure settings: `RAG.vector_store_type=pgvector`, `RAG.pgvector.{dsn|host,port,database,user,password,sslmode}`.
  - Verify OpenAI‑compatible Vector Store API (create store, upsert, search, index_info).

- Acceptance
  - `POST /api/v1/vector_stores` succeeds (pg tables created; HNSW or IVFFLAT index present).
  - `POST /api/v1/vector_stores/{id}/vectors` and `/query` work end‑to‑end.

Quick start (local dev)
- docker-compose -f docker-compose.pg.yml up -d
- export PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/tldw
- Set RAG.vector_store_type=pgvector and create/query a store via WebUI or API.

### Phase 1 — Unify Storage Writes via Adapter (0.5–1 day) ✅ Complete
Goal: Make the embeddings storage worker write through `VectorStoreAdapter` (pgvector or chroma).

- Changes
  - In `storage_worker.py`, add an adapter‑backed path when `RAG.vector_store_type=pgvector`:
    - Resolve adapter via `_get_adapter_for_user(user_id, embedding_dim)`
    - Ensure collection via `adapter.create_collection(...)`
    - Upsert with `adapter.upsert_vectors(collection_name, ids, vectors, documents, metadatas)`
    - Soft‑delete path deletes by metadata via paged `list_vectors_paginated` + `delete_vectors`
  - Retain dimension enforcement, embedder/version tagging, and idempotency ledger logic.

- Acceptance
  - Unit test that `StorageWorker` invokes adapter.upsert for batches (to be added).
  - Live smoke (optional): with PG_TEST_DSN, stored vectors are queryable.

### Phase 2 — Soft-Delete Propagation (0.5 day) ✅ Complete
Goal: Ensure deletions propagate to pgvector.

- Changes
  - When media is soft‑deleted (detected in worker), delete vectors via adapter:
    - MVP: list ids by filter (`metadata.media_id = X`) and call `delete_vectors(ids)`.
    - Optional: add `delete_by_filter(filter)` helper on adapters for efficiency (pgvector uses JSONB `@>`).

- Acceptance
  - Unit: soft‑delete path issues delete calls for matching vectors.
  - Manual: verify table row count drops after soft‑delete event.

### Phase 3 — Migration Tooling (1 day) ✅ Complete
Goal: Copy existing Chroma collections to pgvector.

- _Status (2025-10-16): Migration helper executed end‑to‑end against a real Chroma store and local pgvector. Row counts validated; index rebuilt._

- Deliverable: helper script `Helper_Scripts/chroma_to_pgvector_migrate.py` that:
  - Reads from a Chroma collection (via `ChromaDBManager`) page-wise.
  - Writes to pgvector via `PGVectorAdapter.upsert_vectors` with dimension checks.
  - Optionally re-builds HNSW/ANALYZE.
  - Optional `--seed-demo` to populate an in-memory Chroma stub (CHROMADB_FORCE_STUB=true) for quick smoke.
  - Emits warnings when embedder metadata differs across batches to flag mixed collections.

- Acceptance
  - Dry‑run and sample migration for a test collection.
  - Row counts match for a known collection.

CLI usage
```bash
# Seed demo in stub and migrate to local pgvector
export PGVECTOR_DSN=postgresql://postgres:postgres@localhost:5432/tldw
export CHROMADB_FORCE_STUB=true
python Helper_Scripts/chroma_to_pgvector_migrate.py --user-id 1 --collection demo_cli --seed-demo --page-size 100 --rebuild-index hnsw
```

Live run (no seed, no dry‑run)
```bash
python3 Helper_Scripts/chroma_to_pgvector_migrate.py \
  --user-id 1 \
  --collection user_1_media_embeddings \
  --dest-collection user_1_media_embeddings \
  --page-size 500 \
  --rebuild-index hnsw \
  --drop-dest \
  --pgvector-dsn 'postgresql://tldw_user:TestPassword123!@localhost:5432/tldw_users'
```

Observed output
- Warnings surfaced for embedder metadata mismatches (expected when collection contains mixed sources):
  - "Warning: multiple embedder_name values detected in metadata: ['mismatch', 'persistent']"
  - "Warning: multiple embedder_version values detected in metadata: ['v1', 'v9']"
- Migration summary: `source_count=5`, `written=5` and destination count confirmed `5`.
- Index rebuild performed with HNSW and `ANALYZE` executed.

Tuning notes
- Postgres: set `maintenance_work_mem` higher during index build; ensure autovacuum is active.
- pgvector index
  - HNSW (>=0.7): lower build latency and memory tunable via `m` and `ef_construction`.
  - IVFFLAT: set `lists` according to table size for recall/latency tradeoffs.
- JSONB queries: prefer equality and `$in` operators; complex predicates may be slower.

### Phase 4 — Retrieval Validation (0.5 day) ✅ Complete
Goal: Confirm RAG retriever works with pgvector adapter.

- Changes
  - MediaDBRetriever now routes wildcard/list `index_namespace` to `multi_search` and accepts `metadata_filter`, combining it with `kind` and optional `media_type` via `$and`.
  - PGVectorAdapter filter builder hardened:
    - Only uses JSONB containment fast‑path for plain equality maps (no operators/nested values).
    - `$in` now uses `= ANY(%s)` for safe array parametrization.
  - New integration test exercises multi‑search with JSONB filters across two collections:
    - `tldw_Server_API/tests/RAG_NEW/integration/test_retriever_pgvector_multi_search.py`

- Acceptance
  - Test passes against live pgvector: expected hits are returned with `{ "$or": [{"tag":"b"},{"num":{"$gte":2}}] }`.

- CI
  - Added the test to the pgvector local service job in `.github/workflows/embeddings-tests.yml` and updated the change filter to trigger the job when this test or pgvector adapter changes.

### Phase 5 — Observability & Tuning (0.5 day) ✅ Complete
Goal: Operational knobs and visibility.

- Changes
  - Admin API: Verified `POST /api/v1/vector_stores/admin/hnsw_ef_search` wires to `PGVectorAdapter.set_ef_search`.
  - PG adapter `get_index_info` now returns `ef_search` along with `backend/index_type/ops/dimension/count`.
  - Tests:
    - Unit: admin endpoint set returns value (`test_vector_store_admin_endpoints_pg.py`).
    - Integration (PG): Added session-persistent ef_search check using a shared adapter instance:
      - `tldw_Server_API/tests/VectorStores/integration/test_vector_store_admin_ef_search_pg.py`.
    - Integration (PG): Added JSONB filter edge cases (empty $in; nested $and/$or).

- Operational notes
  - HNSW ef_search is session-scoped; use the admin endpoint to adjust per worker/session during experimentation. Persist desired defaults via runtime config (RAG.pgvector.hnsw_ef_search).
  - Post-bulk operations: run `ANALYZE` (adapter already attempts this best-effort after index builds). Ensure autovacuum is enabled.
  - Index tradeoffs:
    - HNSW (pgvector >=0.7): lower latency, tunable `m`, `ef_construction`; use higher `ef_search` for recall at the cost of latency.
    - IVFFLAT: good for large tables; tune `lists` by table size; consider rebuilding as datasets grow.
  - JSONB filters: equality and `$in` are fastest; complex nested predicates can impact latency — monitor and index hot JSONB keys where appropriate.

- Acceptance
  - `/api/v1/vector_stores/admin/hnsw_ef_search` returns the configured value for pgvector; Chroma path accepts the call but is effectively a no-op.

### Phase 6 — Docs & WebUI polish (0.5 day) ✅ Complete
Goal: Smooth operator experience.

- Changes
  - Env docs updated to clarify pgvector runtime config is sourced from `config.txt` (no env override for server), while tests/scripts may use env DSNs:
    - `Env_Vars.md` under “Vector Store: pgvector”.
  - Deployment guide now includes a `config.txt` snippet and notes for pgvector selection and tuning knobs:
    - `Docs/Published/Deployment/Embeddings-Deployment-Guide.md`.
  - WebUI Vector Stores tab copy updated to reflect adapter-agnostic backend and ef_search notice for pgvector:
    - `tldw_Server_API/WebUI/tabs/vector_stores_content.html`.
  - README mentions pluggable vector backends and how to select pgvector in config.

- Acceptance
  - WebUI shows backend in badges (`index: … • backend: …`) and ef_search note; docs reflect authoritative config path for pgvector.

### Phase 7 — CI & Release (0.5–1 day)
Goal: Ensure ongoing coverage.

- Tasks
  - Wire a GitHub Actions job that runs pgvector integration tests when `PG_TEST_DSN` is provided (matrix on Postgres versions optional). Fallback to unit‑only when DSN not set.

- Acceptance
  - CI green with unit tests; optional live job green in staging.

---

## Rollout

1) Staging
   - Enable pgvector on a canary environment.
   - Run Vector Store API flows and embeddings pipeline against Postgres.
   - Validate SLOs: ANN p95 ≤ 150 ms (k=10), hybrid ≤ 250 ms.

2) Migration
   - For tenants/collections selected, run migration helper.
   - Build HNSW, ANALYZE.
   - Toggle reads to pgvector via settings; hold Chroma for rollback window.

3) Production
   - Monitor latency, errors, autovacuum, relation bloat.
   - Expand tenant coverage; decommission Chroma when confident.

Rollback
- Set `RAG.vector_store_type=chromadb` and restart services. Keep Chroma data intact during migration until cutover.

---

## Risks & Mitigations

- Index/tuning drift: HNSW vs IVFFLAT availability varies by pgvector version.
  - Mitigation: Attempt HNSW then fallback to IVFFLAT; expose session `ef_search` control.
- Dimension mismatch between collections/models.
  - Mitigation: Strict dimension checks at write; schedule re‑embed on embedder/version mismatch.
- Large table growth and VACUUM pressure.
  - Mitigation: ANALYZE after bulk loads; consider partitioning at 10M+ rows (see scale_to_millions.md).
- Migration time for big collections.
  - Mitigation: Batched copy with progress; off‑peak scheduling; optional dual‑write window if needed.

---

## Configuration Reference (pgvector)

settings `[RAG]`:
- `vector_store_type=pgvector`
- `pgvector.host`, `pgvector.port`, `pgvector.database`, `pgvector.user`, `pgvector.password`, `pgvector.sslmode`
- Optional `pgvector.dsn` (overrides discrete params)
- Optional `pgvector.hnsw_ef_search` (session; default 64)

JSONB filter examples
- Equality: `{ "kind": "chunk" }`
- `$in`: `{ "media_id": { "$in": ["1","2","3"] } }`
- `$and` composition: `{ "$and": [{"kind":"chunk"},{"hyde_rank": {"$lte": 2}}] }`

Environment (examples)
- `PG_TEST_DSN=postgresql://user:pass@localhost:5432/db`

---

## Acceptance Checklist

- [x] Vector Store API works against pgvector (create, upsert, query, index info)
- [x] Storage worker writes via adapter and passes idempotency + dimension checks
- [x] Soft-delete removes vectors for deleted media
- [x] Migration helper copies collections with matching counts
- [ ] RAG retriever returns results using pgvector
- [ ] Docs updated; WebUI shows backend info
- [ ] CI unit + optional live tests pass

---

## Follow‑ups (post‑v0)

- Add `delete_by_filter` to the adapter interface (pgvector JSONB, Chroma where filter) for efficient deletions.
- Unified embeddings table option with partitioning (tenant/time) and RLS policies.
- Bulk COPY path for very large upserts.
- Grafana panels for pgvector index health and query latency.
