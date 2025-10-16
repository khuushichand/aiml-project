# PGVector-do-1 — Enable pgvector as an embeddings datastore

Status: Draft v0.1 • Owner: Platform • Related: Docs/Design/scale_to_millions.md, docker-compose.pg.yml

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

### Phase 0 — Infra & Config (1 day)
Goal: Stand up pgvector locally; verify adapter path via Vector Store API.

- Tasks
  - Bring up Postgres + pgvector: `docker-compose -f docker-compose.pg.yml up -d`.
  - Configure settings: `RAG.vector_store_type=pgvector`, `RAG.pgvector.{dsn|host,port,database,user,password,sslmode}`.
  - Verify OpenAI‑compatible Vector Store API (create store, upsert, search, index_info).

- Acceptance
  - `POST /api/v1/vector_stores` succeeds (pg tables created; HNSW or IVFFLAT index present).
  - `POST /api/v1/vector_stores/{id}/vectors` and `/query` work end‑to‑end.

### Phase 1 — Unify Storage Writes via Adapter (0.5–1 day)
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

### Phase 2 — Soft‑Delete Propagation (0.5 day)
Goal: Ensure deletions propagate to pgvector.

- Changes
  - When media is soft‑deleted (detected in worker), delete vectors via adapter:
    - MVP: list ids by filter (`metadata.media_id = X`) and call `delete_vectors(ids)`.
    - Optional: add `delete_by_filter(filter)` helper on adapters for efficiency (pgvector uses JSONB `@>`).

- Acceptance
  - Unit: soft‑delete path issues delete calls for matching vectors.
  - Manual: verify table row count drops after soft‑delete event.

### Phase 3 — Migration Tooling (1 day)
Goal: Copy existing Chroma collections to pgvector.

- Deliverable: helper script `Helper_Scripts/chroma_to_pgvector_migrate.py` that:
  - Reads from a Chroma collection (via `ChromaDBManager`) page‑wise.
  - Writes to pgvector via `PGVectorAdapter.upsert_vectors` with dimension checks.
  - Optionally re‑builds HNSW/ANALYZE.

- Acceptance
  - Dry‑run and sample migration for a test collection.
  - Row counts match for a known collection.

### Phase 4 — Retrieval Validation (0.5 day)
Goal: Confirm RAG retriever works with pgvector adapter.

- Tasks
  - Configure RAG to use pgvector in settings.
  - Add a small integration test that performs `multi_search` across collections with metadata prefilter.

- Acceptance
  - Retrievers return expected hits; metadata prefilters work (JSONB `@>`).

### Phase 5 — Observability & Tuning (0.5 day)
Goal: Operational knobs and visibility.

- Tasks
  - Expose/confirm `set_hnsw_ef_search` admin call is no‑op for Chroma and active for pgvector.
  - Add a note to Deployment Guide for `ANALYZE`, autovacuum, and HNSW/IVFFLAT tradeoffs.

- Acceptance
  - `/vector_stores/admin/hnsw_ef_search` returns the configured session value on pgvector.

### Phase 6 — Docs & WebUI polish (0.5 day)
Goal: Smooth operator experience.

- Tasks
  - Update Env docs with `RAG.vector_store_type`, `RAG.pgvector.*` and HNSW knobs.
  - Add a small hint in WebUI Vector Stores tab indicating backend is pgvector (from index_info).

- Acceptance
  - Docs compile and link; WebUI shows backend in index info.

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

Environment (examples)
- `PG_TEST_DSN=postgresql://user:pass@localhost:5432/db`

---

## Acceptance Checklist

- [ ] Vector Store API works against pgvector (create, upsert, query, index info)
- [ ] Storage worker writes via adapter and passes idempotency + dimension checks
- [ ] Soft‑delete removes vectors for deleted media
- [ ] Migration helper copies collections with matching counts
- [ ] RAG retriever returns results using pgvector
- [ ] Docs updated; WebUI shows backend info
- [ ] CI unit + optional live tests pass

---

## Follow‑ups (post‑v0)

- Add `delete_by_filter` to the adapter interface (pgvector JSONB, Chroma where filter) for efficient deletions.
- Unified embeddings table option with partitioning (tenant/time) and RLS policies.
- Bulk COPY path for very large upserts.
- Grafana panels for pgvector index health and query latency.
