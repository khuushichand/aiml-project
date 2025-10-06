## Stage 0: Baseline & Scaffolding
**Goal**: Establish baseline knowledge for embeddings A/B evaluations and prep scaffolding for implementation work.
**Success Criteria**:
- Document existing evaluations DB adapters, migration framework, and feature flags relevant to embeddings.
- `IMPLEMENTATION_PLAN.md` captures staged roadmap and ownership notes for embeddings A/B testing.
- Placeholder pytest markers/fixtures created under `tests/evaluations/embeddings_abtest` (skipped for now) to unblock later test additions.
**Tests**:
- `python -m pytest -k "embeddings_abtest"` (expects skip markers until stages complete)
**Status**: Complete

#### Stage 0 Findings (initial pass)
- **DB adapter baseline**: `app/core/DB_Management/Evaluations_DB.py` already provisions the `embedding_abtests`, `embedding_abtest_arms`, `embedding_abtest_queries`, and `embedding_abtest_results` tables and exposes CRUD helpers (`create_abtest`, `upsert_abtest_arm`, `insert_abtest_queries`, `insert_abtest_result`, etc.). The adapter executes raw SQLite statements via the shared connection pool; no SQLAlchemy layer exists yet.
- **Schema management**: Evaluations DB relies on opportunistic `CREATE TABLE IF NOT EXISTS` + best-effort `ALTER TABLE` inside `EvaluationsDatabase._init_schema`. There is no alembic-style migration history; schema changes must remain additive and idempotent for SQLite/Postgres parity.
- **Existing services**: `app/core/Evaluations/embeddings_abtest_service.py` implements hashing (`_compute_collection_hash`, `_compute_pipeline_hash`), collection building (Chroma), query execution, and metrics rollups, while `embeddings_abtest_runner.py` wires the background orchestration entry points. Current API routes live in `app/api/v1/endpoints/evaluations_unified.py` and persist directly through the DB adapter.
- **Feature flags / gating**: heavy AB test execution is guarded by `EVALS_HEAVY_ADMIN_ONLY` (defaults to true) in both the API layer and AuthNZ helper; `TESTING` enables synthetic corpus fallback inside the builder. General Evaluations toggles (`EVALS_DEBUG`, rate-limit tiers, circuit breakers) are sourced from `Config_Files/evaluations_config.yaml` via `EvaluationsConfigManager`.
- **Test scaffolding**: added `tests/Evaluations/embeddings_abtest/test_scaffold.py` with a session fixture that skips under the `embeddings_abtest` marker; marker registered in `pyproject.toml` to keep pytest discovery ready.
- **Observations**: despite “stub” comments, the service currently performs end-to-end work; planned milestones should account for existing behaviors to avoid regressions or migrate functionality where overlap exists.

## Stage 1: Persistence & Schemas (M1)
**Goal**: Define storage and API contracts for embeddings A/B tests.
**Success Criteria**:
- DB migrations create `embedding_abtests`, `embedding_abtest_arms`, `embedding_abtest_queries`, `embedding_abtest_results` tables with indexes and FKs.
- SQLAlchemy adapter in `app/core/Evaluations/db_adapter.py` exposes CRUD for tests, arms, queries, and results.
- Pydantic schemas (`EmbeddingsABTestConfig`, `EmbeddingsABTestCreateRequest`, `EmbeddingsABTestResultSummary`) available under evaluations schemas.
- API endpoints `POST /api/v1/evaluations/embeddings/abtest` and `GET /api/v1/evaluations/embeddings/abtest/{test_id}` return stored config and status.
**Tests**:
- Migration smoke tests validating table creation and rollback.
- Unit tests for schema validation and adapter CRUD round-trips.
- API test asserting create/status flow persists request payloads.
**Status**: Not Started

## Stage 2: Collection Build Pipeline (M2)
**Goal**: Build and reuse per-arm embedding collections with deterministic hashing.
**Success Criteria**:
- Hash helpers generate `collection_hash` and `pipeline_hash` deterministically from config payloads.
- Collection builder enqueues `prepare_collections` jobs per arm, chunking media and embedding via existing services.
- Per-arm Chroma namespaces created/reused; build stats persisted with retry handling.
- Arm statuses transition through pending → building → ready/failure with structured logging.
**Tests**:
- Unit tests for hashing determinism and namespace naming.
- Integration test with synthetic embeddings verifying reuse of identical configs.
- Failure path test ensuring retries and error propagation update arm status.
**Status**: Not Started

## Stage 3: Query Runner & Metrics (M3)
**Goal**: Execute vector retrieval queries per arm and compute evaluation metrics.
**Success Criteria**:
- Evaluation runner processes `embedding_abtest_queries` for each arm using per-arm query embeddings.
- Metrics calculator produces Recall@k, MRR, nDCG, and Hit@k per query and aggregates per arm.
- Query latency captured and stored; results persisted into `embedding_abtest_results`.
- API endpoints `POST /api/v1/evaluations/embeddings/abtest/{test_id}/run` and `GET /api/v1/evaluations/embeddings/abtest/{test_id}/results` (paged) exposed.
**Tests**:
- Unit tests for metric calculations including edge cases.
- Integration test running mini corpus with deterministic embeddings validating aggregate metrics.
- API pagination test ensuring result slicing works.
**Status**: Not Started

## Stage 4: Advanced Retrieval & Governance (M4)
**Goal**: Support hybrid retrieval, cleanup policies, and admin controls.
**Success Criteria**:
- Hybrid pipeline path wired into RAG service honoring `hybrid_alpha`, reranker config, and consistent per-arm query embeddings.
- Cleanup policy executor enforces `on_complete` deletion and optional TTL.
- Quotas, rate limits, and provider allowlists enforced for heavy operations.
- Audit logging captures collection creation, query execution, and cleanup actions.
**Tests**:
- Integration test covering hybrid retrieval with mocked reranker.
- Unit tests for cleanup scheduler (TTL expiry) and permission enforcement.
- Load test script or smoke to confirm rate limiter behavior under concurrency (documented).
**Status**: Not Started

## Stage 5: Hardening, Observability & Docs (M5/M6)
**Goal**: Finalize quality gates, observability, exports, and documentation.
**Success Criteria**:
- Prometheus metrics and structured logs emitted for A/B test runs, arm builds, and query latencies.
- Property tests for hashing, metric bounds, and deterministic collection naming.
- Results export utility (CSV/JSON) available; optional statistical significance analysis implemented if time allows.
- Documentation updates covering API usage, developer guide, and evaluation README entries.
**Tests**:
- Property-based tests verifying hashing/metric invariants.
- Integration test for export endpoints producing expected payloads.
- Docs lint/check (if configured) passes; manual checklist executed.
**Status**: Not Started

---

### Notes & Assumptions
- Evaluations DB remains SQLite by default; Postgres paths follow existing adapter patterns.
- Synthetic embedding providers available under `TESTING=true` for deterministic tests.
- Heavy compute endpoints gated behind admin roles and subject to quota settings.
- Reuse of existing chunking and embeddings services prioritized; new abstractions added only if reuse fails.
