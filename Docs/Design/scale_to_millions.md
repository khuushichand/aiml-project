# Scaling tldw_server to Millions of Documents

Status: Draft v0.1 • Owner: Platform • Related: PG-Support-Plan.md

## 1) Executive Summary

Goal: evolve from a 10k-doc SQLite + Chroma deployment to a multi-tenant, millions-of-documents architecture using PostgreSQL for metadata/full-text and pgvector for embeddings, without breaking existing APIs. The system must support: high-throughput ingestion, hybrid retrieval (FTS + vectors + re-rank), multi-user isolation, and predictable performance targets.

Non-goals: switch primary programming model or API surface; introduce external managed services; change WebUI/API semantics.

## 2) Requirements & Targets

- Scale: 5-10M chunks (documents split into chunks) per instance; multiple tenants.
- Latency targets (hot cache, tuned):
  - FTS candidate fetch: p95 ≤ 60 ms (k<=100)
  - Vector ANN (k=10): p95 ≤ 150 ms with prefilters
  - Hybrid end-to-end (k=10, re-rank<=100): p95 ≤ 250 ms
- Ingestion throughput: ≥ 1M chunks/day sustained with background workers.
- Multi-tenancy: strict row isolation by `tenant_id`; optional RLS.
- Fault tolerance: safe retries, idempotent upserts, VACUUM/autovacuum settings.

## 3) Current State (Brief)

- SQLite is used for media/notes DBs; FTS5 powers search; Chroma stores embeddings per user.
- RAG has a pluggable vector store with adapters for Chroma and pgvector (`rag_service/vector_stores/*`).
- Separate work exists for a database backend abstraction (see PG-Support-Plan.md) but it is not yet integrated into Media_DB_v2 and other modules.

## 4) Target Architecture (High-Level)

- Storage:
  - PostgreSQL 16+ as the system of record for metadata and text.
  - Extensions: `pgvector`, `pg_trgm` (for fuzzy search), `uuid-ossp` (optional).
  - Full-text search via `tsvector/tsquery` with GIN indexes.
  - Embeddings in pgvector with HNSW (preferred) or IVFFLAT indexes.
- Multi-tenancy: single database with `tenant_id` column on all core tables; optional RLS.
- Retrieval: hybrid pipeline combining FTS candidates and ANN candidates, then re-ranks (BM25/ts_rank + vector score normalization).
- Ingestion: chunking + batch inserts + background workers; COPY/`executemany` paths; backpressure controls.
- Compatibility: keep SQLite/Chroma as a mode for small/local installs.

## 5) Data Model (PostgreSQL)

Two complementary layers:

1) Text + Metadata (normalized in Postgres)

- `tenants(tenant_id, name, created_at)` - optional helper table.
- `documents(id, tenant_id, external_ref, title, source_uri, author, created_at, updated_at, soft_deleted_at, meta jsonb)`
- `chunks(id, tenant_id, document_id, ordinal, text, meta jsonb, ts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(text,''))) STORED, created_at, updated_at, soft_deleted_at)`

Indexes:
- `btree (tenant_id, document_id, ordinal)`
- Partial indexes excluding soft-deleted rows: `WHERE soft_deleted_at IS NULL`
- `GIN (ts)` on `chunks` for FTS; `pg_trgm` GIN or GIST on text columns (titles) for fuzzy matching if needed.

Partitioning (optional, recommended at 10M+ chunks):
- Hash partition `chunks` by `tenant_id` or time-partition by `created_at` (operational preference). Mirror for related tables.

2) Embeddings (pgvector)

Option A (current adapter default): per-collection tables (`vs_<collection>`) with schema:
- `id text PRIMARY KEY, content text, metadata jsonb, embedding vector(dim)`
- Index: `HNSW` (`vector_l2_ops` or `vector_cosine_ops`).

Option B (recommended for millions of chunks): a unified embeddings table:
- `chunk_embeddings(id uuid/uuidv7, tenant_id, chunk_id, model, embedding vector(dim), meta jsonb, created_at)`
- Composite indexes: `(tenant_id, model)` + HNSW on `embedding` per partition (if partitioned by tenant or by time).

Both options are compatible with the `PGVectorAdapter`. For large deployments, prefer Option B to avoid proliferation of many per-collection tables and to enable global filters and capacity planning.

HNSW DDL example (pgvector >= 0.7):
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE IF NOT EXISTS chunk_embeddings (
  id uuid PRIMARY KEY,
  tenant_id text NOT NULL,
  chunk_id text NOT NULL,
  model text NOT NULL,
  embedding vector(1536) NOT NULL,
  meta jsonb,
  created_at timestamptz DEFAULT now()
);
CREATE INDEX IF NOT EXISTS chunk_embeddings_tenant_model
  ON chunk_embeddings (tenant_id, model);
-- Choose ops per metric: vector_l2_ops, vector_cosine_ops, vector_ip_ops
CREATE INDEX IF NOT EXISTS chunk_embeddings_hnsw
  ON chunk_embeddings USING hnsw (embedding vector_cosine_ops)
  WITH (m=16, ef_construction=200);
```

FTS DDL example:
```sql
CREATE EXTENSION IF NOT EXISTS pg_trgm;
CREATE TABLE IF NOT EXISTS chunks (
  id text PRIMARY KEY,
  tenant_id text NOT NULL,
  document_id text NOT NULL,
  ordinal int NOT NULL,
  text text NOT NULL,
  meta jsonb,
  ts tsvector GENERATED ALWAYS AS (to_tsvector('english', coalesce(text,''))) STORED,
  created_at timestamptz DEFAULT now(),
  updated_at timestamptz DEFAULT now(),
  soft_deleted_at timestamptz
);
CREATE INDEX IF NOT EXISTS chunks_tenant_doc_ord ON chunks(tenant_id, document_id, ordinal);
CREATE INDEX IF NOT EXISTS chunks_ts_idx ON chunks USING gin(ts);
CREATE INDEX IF NOT EXISTS chunks_not_deleted ON chunks(tenant_id) WHERE soft_deleted_at IS NULL;
```

Row-level security (optional):
```sql
ALTER TABLE chunks ENABLE ROW LEVEL SECURITY;
CREATE POLICY tenant_isolation ON chunks
  USING (tenant_id = current_setting('app.tenant_id', true));
```

## 6) Retrieval Strategy (Hybrid)

Pipeline:
1. Prefilter by `tenant_id`, type, tags, time range.
2. Produce candidates via:
   - FTS: `to_tsquery` or `plainto_tsquery` against `chunks.ts` (limit N).
   - Vector: pgvector ANN k-NN (limit M) using `embedding <=> query` (cosine/L2/IP) with HNSW.
3. Merge candidates, normalize scores, re-rank (BM25/ts_rank + vector score); apply diversity/parent passage grouping if configured.
4. Fetch parent documents and return.

Notes:
- Use `SET hnsw.ef_search = 64` (or tune) per connection for latency/recall tradeoffs.
- For IVFFLAT, `SET ivfflat.probes = <n>` per query.
- Always include `tenant_id` in WHERE to reduce candidate space prior to ANN ranking.

## 7) Ingestion & Jobs

- Chunking: leverage the unified chunking module and ingestion pipeline; ensure chunks carry stable `chunk_id` and `tenant_id`.
- Batch writes: use COPY (psycopg `copy_expert`) or `executemany` with batches of 500-2000 rows depending on payload size.
- Background workers: use existing worker/orchestrator modules to process embedding jobs and storage in parallel (bounded concurrency per tenant).
- Backpressure & retries: queue size caps per tenant; exponential backoff; idempotent upserts by `chunk_id`.
- Large files: store raw media outside DB (disk/object store); DB keeps normalized text+metadata only.

## 8) Migration Plan

Phases (align with PG-Support-Plan.md):
1) Enable Postgres runtime config toggles (already present in `core/config.py` for RAG/pgvector). Validate `PGVectorAdapter` end-to-end on a canary tenant.
2) Integrate DB backend abstraction into `Media_DB_v2` and related modules, replacing direct `sqlite3` calls with the factory. Keep SQLite as default.
3) Baseline Postgres schema via Alembic migrations (extensions, tables, indexes, RLS optional). Provide Docker Compose for Postgres+pgvector+pgbouncer.
4) Data mover CLI:
   - Export from SQLite (documents, chunks, metadata).
   - Re-embed or import embeddings (if Chroma export with aligned IDs is available).
   - Verify counts and sample retrieval parity.
5) Dual-write (optional, short window) → cut over reads to Postgres/pgvector → decommission dual writes.

Validation:
- Row counts match (±0 with soft-deletes considered).
- Sampled queries (FTS only, vector only, hybrid) produce equivalent or better top-k.
- p95 latencies within targets after warmup.

## 9) Deployment & Tuning

- Topology: Postgres 16+ with `pgvector` and `pg_trgm`; pgbouncer for pooling; optional read replica for analytics.
- Tuning (starting points; adjust per hardware):
  - `shared_buffers`: ~25% RAM; `effective_cache_size`: 50-75% RAM
  - `work_mem`: 16-64MB; `maintenance_work_mem`: 512MB-2GB for index builds
  - Autovacuum: more aggressive on `chunks` and `chunk_embeddings`
  - Analyze tables after bulk loads; rebuild HNSW offline during low-traffic windows if needed
- Observability: slow query log; `pg_stat_statements`; metrics via exporters; application tracing of retrieval steps.

### PG Pooling & HNSW Tuning (App-Level)

- Config keys under `[RAG]` for `vector_store_type=pgvector`:
  - `pgvector_pool_min_size` (default 1), `pgvector_pool_max_size` (default 5), `pgvector_pool_size` (alias)
  - `pgvector_hnsw_ef_search` (default 64; higher = better recall, higher latency)
- Recommended values:
  - Up to 1M chunks: pool_min=1, pool_max=5-10, ef_search=64-128
  - 1-10M chunks: pool_min=2-4, pool_max=10-20, ef_search=128-256
  - >10M chunks: consider partitioning; pool_max 20-50, ef_search 128-256; add read replicas if needed

## 10) Configuration & Interfaces

- Modes:
  - `DB_ENGINE = sqlite | postgres`
  - `VECTOR_BACKEND = chroma | pgvector`
- RAG pgvector config is already scaffolded in `tldw_Server_API/app/core/config.py` under `[RAG.pgvector]`.
- Vector store: continue using `VectorStoreFactory`; productionize `PGVectorAdapter` with:
  - HNSW index creation (pgvector >= 0.7)
  - Connection pooling (psycopg3 / pgbouncer)
  - JSONB filter strategy for metadata
  - Table naming strategy to avoid explosion (e.g., `vs_t_<tenant>_chunks`)

## 11) Testing & Benchmarks

- Parametrize integration tests to run on both backends (SQLite/Chroma vs Postgres/pgvector).
- Synthetic dataset generator: N docs, M chunks/doc, metadata skew, 768/1536 dims.
- Scenarios: single-tenant, multi-tenant; cold/hot cache; mixed read/write.
- KPIs: ingest throughput, ANN/FTS latency p50/p95/p99, hybrid latency, index build time, storage footprint.
- Targets: see Section 2.

## 12) Risks & Alternatives

- HNSW memory footprint: mitigate via partitioning and careful M/ef settings.
- Index rebuild times: schedule maintenance windows or rolling partitions.
- Query planner regressions: pin planner settings per query when necessary; keep queries simple and parameterized.
- Alternative vector stores: can swap via adapter if Postgres contention appears at 10M+ scale; keep the interface stable.

## 13) Milestones

1) Baseline schema + config switches documented; dev docker-compose for PG + pgvector.
2) Integrate backend abstraction into Media_DB_v2; green tests on both SQLite and Postgres.
3) PG vector store hardened (HNSW indices + pooling + metadata filters).
4) Ingestion pipeline batched + job-driven; COPY path validated.
5) Migration tool + parity checks; canary tenant cutover.
6) Benchmarks published; tuning guide added.

---

Appendix A - Example Queries

- FTS candidates:
```sql
SELECT id, ts_rank(ts, q) AS rank
FROM chunks, to_tsquery('english', $1) q
WHERE tenant_id = $2 AND soft_deleted_at IS NULL AND ts @@ q
ORDER BY rank DESC
LIMIT 100;
```

- Vector ANN candidates (cosine):
```sql
SET LOCAL hnsw.ef_search = 64;
SELECT id, embedding <=> $1 AS distance
FROM chunk_embeddings
WHERE tenant_id = $2 AND model = $3
ORDER BY distance ASC
LIMIT 50;
```

- Merge/re-rank in app layer (preferred for flexibility) or via SQL CTEs if needed.
