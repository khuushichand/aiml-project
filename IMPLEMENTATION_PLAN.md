## Stage 1: Privilege Maps – Introspection Backbone
**Goal**: Capture real FastAPI route metadata (paths, methods, dependencies, rate-limit tags) to replace scope-derived placeholders.
**Success Criteria**:
- Introspection module produces deterministic registry exercised in unit tests.
- CI validation fails when routes lack catalog identifiers or dependency metadata.
- `PrivilegeMapService` consumes introspection data in a feature branch with tests passing locally.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Privileges/test_privilege_service_sqlite.py`
- New unit tests for the introspection helper module.
**Status**: Not Started

## Stage 2: Privilege Maps – Aggregation & Filtering
**Goal**: Integrate introspection output into privilege summaries/details with enriched metadata and verified filters.
**Success Criteria**:
- Detail items include HTTP method, dependency list, rate-limit class, and source module.
- Summary/group-by endpoints produce counts derived from actual routes.
- Filters for resource, role, and dependency anchor behave per PRD.
**Tests**:
- Existing privilege endpoint tests updated for new fields.
- Additional tests covering role/resource filters and pagination.
**Status**: Not Started

## Stage 3: Privilege Maps – Caching & Trends
**Goal**: Introduce cache layer with invalidation hooks and implement trend calculations for org/team views.
**Success Criteria**:
- Cached responses served within configured TTL; cache invalidates on RBAC/config updates.
- Trend payloads return non-empty deltas aligned with stored history.
- Metrics emitted for cache hit rate and trend generation.
**Tests**:
- Integration test simulating role change invalidation.
- Unit tests for trend calculations with synthetic history.
**Status**: Not Started

## Stage 4: Privilege Maps – Snapshot Fidelity & Async Jobs
**Goal**: Persist snapshot detail matrices, support asynchronous generation, and enforce retention/downsampling policies.
**Success Criteria**:
- New snapshot detail table stores paginated matrices retrievable via API.
- Async snapshot requests enqueue background jobs with observable status updates.
- Retention worker downsamples and purges data per environment settings.
**Tests**:
- Snapshot API integration tests covering async path and pagination.
- Retention job unit test validating TTL behaviour.
**Status**: Not Started

## Stage 5: Privilege Maps – WebUI & Exports
**Goal**: Deliver Next.js pages for admin/org/team/user views with CSV/JSON exports and inline recommended actions.
**Success Criteria**:
- WebUI routes render virtualized tables with filters matching backend APIs.
- Export actions produce files consistent with API schemas.
- Documentation updated for UI usage and refresh controls.
**Tests**:
- Frontend component/unit tests for privilege pages.
- Playwright (or equivalent) smoke covering export workflow.
**Status**: Not Started

## Stage 6: Embeddings A/B – Persistence & Documentation
**Goal**: Finalize database adapter strategy, migrations, and planning artifacts for embeddings A/B testing.
**Success Criteria**:
- SQLAlchemy adapter (or justified alternative) manages embedding tables with migrations for SQLite/Postgres.
- `IMPLEMENTATION_PLAN.md` kept current and referenced in CI guard.
- CRUD unit tests cover create/update/delete across backends.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Evaluations` (expanded suite).
- Migration smoke tests for both SQLite and Postgres.
**Status**: Not Started

## Stage 7: Embeddings A/B – Collection Pipeline
**Goal**: Reuse collections via deterministic hashing and execute builds through background queues with retry handling.
**Success Criteria**:
- `reuse_existing` flag prevents redundant builds when hashes match.
- Background workers manage status transitions (pending → building → ready/failed) with audit logs.
- Per-arm metadata stores chunk counts, embedding dimensions, and model revisions.
**Tests**:
- Integration tests simulating queue retries and reuse scenarios.
- Unit tests for hashing helpers and status transitions.
**Status**: Not Started

## Stage 8: Embeddings A/B – Query Runner & Metrics
**Goal**: Run vector/hybrid retrieval per arm, compute metrics, and serve paginated results with significance analysis.
**Success Criteria**:
- Metric aggregation includes Recall@k, MRR, nDCG, Hit@k, latency percentiles.
- Result APIs paginate (default 50, max 500) and return totals with aggregates.
- Significance analysis accessible via API and validated against fixtures.
**Tests**:
- Integration test with synthetic corpus validating metrics and pagination.
- Unit tests for significance calculation edge cases.
**Status**: Not Started

## Stage 9: Embeddings A/B – Governance & Cleanup
**Goal**: Enforce quotas, rate limits, provider allowlists, and cleanup policies (on-complete + TTL).
**Success Criteria**:
- Cleanup scheduler deletes collections per policy and logs actions.
- Quota breaches prevent new runs and emit alerts.
- Audit log entries created for create/run/delete/export operations.
**Tests**:
- Unit tests for cleanup scheduler and quota enforcement.
- Integration test verifying audit logging outputs.
**Status**: Not Started

## Stage 10: Embeddings A/B – Observability & Exports
**Goal**: Emit Prometheus metrics, structured logs, and provide export tooling with documentation updates.
**Success Criteria**:
- Metrics published for queue depth, job durations, build successes/failures.
- Structured logs aggregated for lifecycle events and errors.
- JSON/CSV exports follow documented schema and pass validation tests.
**Tests**:
- Metrics emission smoke tests.
- Export endpoint tests validating payload structure and content.
**Status**: Not Started
