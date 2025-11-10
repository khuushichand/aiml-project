# PGVector Hybrid Retrieval - Product Requirements Document

## 1. Background
- The current `PGVectorAdapter` (`tldw_Server_API/app/core/RAG/rag_service/vector_stores/pgvector_adapter.py`) implements the `VectorStoreAdapter` interface and is wired in through the factory (`vector_stores/factory.py`) whenever Postgres is selected in the RAG configuration (`Docs/RAG` guidance, `VectorStoreConfig.store_type = PGVECTOR`).
- Each logical collection is materialized as a dedicated table (`vs_{sanitized_name}`) with `id TEXT PRIMARY KEY`, `content TEXT`, `metadata JSONB`, and `embedding vector(dim)`. Optional HNSW or IVFFLAT indexes are created on the embedding column when the database supports them.
- The adapter provides async-friendly execution helpers backed by psycopg v3 pools (fallback to psycopg2), metadata-aware filtering (`_build_where_from_filter` supporting equality, `$and`, `$or`, `$in`, numeric comparisons), bulk upserts, deletions, stats reporting, multi-collection search, and Prometheus metrics for latency and row counts.
- Retrieval today is purely ANN-based: `search` and `multi_search` accept a `query_vector` and optional metadata filter, returning results ordered by vector distance converted into a heuristic similarity score. `database_retrievers.MediaDBRetriever` (and siblings) only forward vectors to the adapter and never supply raw query text. No text-only or hybrid logic exists, and the schema does not include `tsvector` columns or full-text indexes.
- Postgres already supports built-in full-text search primitives (`tsvector`, `ts_rank_cd`) that complement embeddings for keyword-heavy or short-form queries.
- The Azure sample [`rag-postgres-openai-python`](https://github.com/Azure-Samples/rag-postgres-openai-python) demonstrates a hybrid strategy: fetch top-k results from vector search and FTS separately, merge with reciprocal-rank fusion, and reuse ad-hoc filters across both branches.
- Teams ingest mixed content (transcripts, notes, structured snippets). Solely relying on embeddings leads to misses when recall hinges on exact terms (e.g., names, acronyms). Hybrid retrieval improves precision and recall without external infrastructure.

## 2. Objectives & Success Criteria
- Deliver first-class hybrid retrieval within the existing PGVector adapter: vector + FTS scoring with configurable weighting.
- Preserve backward compatibility: existing vector-only flows continue working when FTS is disabled or unavailable.
- Provide schema migrations or auto-DDL to maintain `tsvector` columns and GIN indexes per collection.
- Support metadata-aware filtering for both vector and text branches.
- Emit existing Prometheus metrics (latency, counts) for hybrid paths and expose new counters for FTS participation.
- Offer toggleable configuration (per collection or global) surfaced through `VectorStoreConfig`.
- Achieve measurable recall improvement in regression tests (>15% increase on keyword-heavy benchmark corpus).

## 3. Personas & Use Cases
- **Research Assistant User**: issues natural language queries mixed with literal keywords (“show the COBOL compliance memo about SOC2”). Needs recall across embeddings and exact keywords.
- **ML Ops Engineer**: manages RAG deployments, wants tunable hybrid weights and observability for database performance.
- **Contributor**: extends retrieval strategies (e.g., BM25) and reuses new hooks, tests, and configuration patterns.
- **Enterprise Admin**: requires confidence that new features do not break existing pipelines and can be toggled per tenant or deployment.

## 4. Scope
### In Scope
- Table schema augmentation: add `tsvector` column (generated or explicit) plus GIN index during `create_collection`.
- Upsert path updates to maintain text search vectors (`to_tsvector` on `content` and optional metadata fields).
- Hybrid search SQL: combine ANN results (using `<=>`/`<->`) with FTS ranking (e.g., `ts_rank_cd`) using reciprocal-rank fusion.
- Configurable weighting constant (`k`) and FTS language, exposed via `VectorStoreConfig` and environment/config overrides.
- RAG pipeline wiring: update `database_retrievers` (and any other callers) to pass query text alongside embeddings, while guarding other vector backends that may remain vector-only.
- New adapter API (or extended `search`) that accepts both `query_vector` and `query_text`, defaults to current behavior when either is missing.
- Telemetry: extend Prometheus counters/histograms to distinguish vector-only vs hybrid vs FTS-only code paths.
- Automated regression tests (unit + integration) validating schema creation, upsert regeneration, hybrid scoring, and filter propagation.
- Documentation updates (this PRD, Dev docs, RAG README) plus sample configuration snippet.

### Out of Scope
- Advanced reranking (cross-encoder) within Postgres; remains separate pipeline stage.
- Non-English stemming dictionaries beyond configurable `regconfig` string.
- Historical migration tooling for legacy collections; focus on auto-migration at query time with best-effort backfill.
- UI changes in `tldw-frontend`; API surfaces stay backend-only for this phase.

## 5. Proposed Solution Overview
1. **Schema Enhancements**
   - Adjust `create_collection` to add `tsv tsvector GENERATED ALWAYS AS (...) STORED`.
   - Build GIN index on `tsv`, fall back gracefully if database build lacks permissions.
   - Provide best-effort `ALTER TABLE` path when existing collections detected without `tsv`.

2. **Upsert Pipeline**
   - During `upsert_vectors`, compute `to_tsvector` on `content` or store plain text allowing generated column to populate.
   - Permit configurable inclusion of selected metadata keys (e.g., title, tags) into FTS vector.

3. **Search Execution**
   - New adapter method `search_hybrid` (or extend `search`) orchestrates:
     - Vector subquery: top-N ids via ANN.
     - FTS subquery: top-N ids using `plainto_tsquery` or `websearch_to_tsquery`.
     - Merge using reciprocal-rank fusion (`1 / (k + rank)`), configurable `k`, returning combined score.
   - Existing metadata filter builder reused to inject predicates into both subqueries.
   - Expose parameter(s) to request vector-only or text-only results explicitly.
   - Update retriever layer so `MediaDBRetriever` (and other `BaseRetriever` implementations that rely on the adapter) forward the original query string and handle responses when a backend indicates hybrid mode.

4. **Configuration & API Surface**
   - Extend `VectorStoreConfig` with:
     - `enable_hybrid` (bool), `fts_regconfig`, `hybrid_rrf_k`, `hybrid_vector_limit`, `hybrid_text_limit`.
   - Update factory and adapter initialization to pick up config (from config.txt, env overrides).
   - Maintain backward compatibility with the existing fields (`store_type`, `connection_params`, `embedding_dim`, `distance_metric`, `collection_prefix`, `user_id`) so other adapters remain unaffected.

5. **Observability & Tuning**
   - Add metrics labels or new counters: e.g., `pgvector_queries_total{mode="hybrid"}`.
   - Log once per collection when hybrid fallback occurs due to missing `tsvector`.
   - Provide tracing hooks (structured logs) quoting subquery durations.

## 6. Detailed Requirements
### 6.1 Functional
- `create_collection` ensures `tsvector` column and GIN index exist; idempotent.
- `upsert_vectors` updates both `embedding` and `tsvector` content in a single transaction.
- `search` accepts `query_text: Optional[str]`, `query_vector: Optional[List[float]]` and determines execution mode automatically:
  - Both provided → hybrid SQL.
  - Vector only → current ANN path.
  - Text only → pure FTS query.
- Metadata filters produce consistent results across modes (no duplicate filter logic).
- Results include similarity score normalized to [0,1] for hybrid; provide raw distance/score fields in metadata for downstream debugging.

### 6.2 Non-Functional
- **Performance**: Hybrid query should remain <150 ms p95 on collections ≤100k rows when Postgres has adequate indexes (`k=60`, top=10). Provide configuration to tune subquery limits.
- **Resilience**: If FTS column missing, log warning and fall back to vector-only without throwing.
- **Compatibility**: Works with psycopg v3 pool and psycopg2 fallback; avoid SQLAlchemy dependency in adapter.
- **Security**: Use parameterized queries; sanitize user text before injecting into SQL.
- **Config Validation**: Add schema/typing checks to reject invalid hybrid options at load time.

### 6.3 Telemetry
- Extend `_H_QUERY_LAT`, `_C_ROWS_UPSERTED`, `_C_ROWS_DELETED` with `mode` label or add new metrics.
- Emit structured log per query including `mode`, `vector_rows`, `fts_rows`, `combined_rows`, and final `top_k`.

## 7. Milestones & Deliverables
1. **M0 - Design Finalization (Week 0)**
   - Approve PRD.
   - Define sample collection for regression tests (mix of keyword/semantic docs).

2. **M1 - Schema & Upsert (Week 1)**
   - Implement ALTER/CREATE logic for `tsvector` and indexes.
   - Update upsert path; add unit tests covering generated columns and metadata inclusion.

3. **M2 - Hybrid Query Engine (Week 2)**
   - Implement hybrid SQL execution.
   - Add configuration toggles and validation.
   - Extend Prometheus metrics.

4. **M3 - Integration & QA (Week 3)**
   - Write integration tests using ephemeral Postgres (pytest + docker fixture or Local cluster).
   - Benchmark sample workloads; document tuning recommendations.
   - Update RAG docs and config examples.

5. **M4 - Release Prep (Week 4)**
   - Feature flag default off; run internal soak.
   - Prepare migration guide for existing deployments.
   - Merge behind config guard; communicate in changelog.

## 8. Dependencies & Risks
- Requires Postgres ≥14 with `pgvector` extension and GIN indexes; older deployments may lack permissions or extension support.
- Generated columns may fail if roles lack `ALTER TABLE` privilege; need fallback logging and manual migration instructions.
- Hybrid queries increase load on Postgres; need monitoring to avoid query planner regressions.
- Lack of tsconfig coverage for non-English languages; may deliver degraded FTS scoring globally.
- Integration tests require containerized Postgres; ensure CI can launch ephemeral database or mark tests accordingly.
- Existing automated coverage uses SQLite-backed fixtures; no Postgres-specific CI currently exercises `PGVectorAdapter`, so additional plumbing is required to stand up test databases during the pipeline.

## 9. Open Questions
- Should hybrid be enabled per collection or globally? (Proposal: config supports both; default per adapter.)
- Which metadata fields should contribute to `tsvector` by default? (Content + title? tags?)
- Do we expose API-level parameter to override query mode per request?
- Should we offer adjustable weights beyond reciprocal rank fusion, e.g., linear combination using normalized scores?
- Is there appetite to expose FTS snippets/highlights in RAG responses?

## 10. Acceptance Criteria
- PR merged enabling hybrid retrieval behind config flag.
- Tests: unit (schema/upsert), integration (hybrid results), benchmark script with documented recall uplift.
- Documentation updated (`Docs/RAG`, adapter README, config examples).
- Metrics confirmed in Prometheus/Grafana dashboards, with hybrid queries visible.
- Rollout checklist completed (feature flag defaults, migration instructions, changelog entry).

## 11. Appendix
- Reference implementation: Azure sample `postgres_searcher.py` (hybrid reciprocal-rank fusion with filters).
- Existing filtering utility `_build_where_from_filter` to be reused for FTS where clause injection.
- Consider `websearch_to_tsquery` as optional upgrade for more natural query parsing.
