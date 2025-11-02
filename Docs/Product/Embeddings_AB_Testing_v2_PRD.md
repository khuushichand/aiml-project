# Embeddings A/B Testing v2 - Product Requirements Document

## Overview
- **Objective**: Deliver fully managed embeddings A/B testing with reusable collections, queued execution, governance controls, and comprehensive observability to compare embedding configurations at scale.
- **Primary Outcome**: Allow admins and evaluation engineers to design, run, inspect, and export embedding experiments confidently, with automated cleanup and metrics.

## Scope (v2)
1. Formalize persistence (SQLAlchemy adapter or documented alternative) with migrations and tests; restore implementation roadmap documentation.
2. Enable collection builders to reuse existing corpora via deterministic hashing, run in background queues, and support failure retries.
3. Execute query runners (vector or hybrid with optional reranker) while recording per-query metrics, exposing paginated result APIs, and providing significance analysis.
4. Enforce cleanup policies, quotas, rate limits, and audit logging for creation, runs, exports, and deletions.
5. Emit Prometheus metrics and structured logs; ship export tooling and update documentation.

## Out of Scope
- Rewriting existing RAG pipelines or chunkers beyond what reuse requires.
- UI work outside the existing evaluations console (if any).
- Advanced statistical tooling beyond the current sign test (document stretch goals separately if needed).

## Personas & Use Cases
- **Evaluation Engineer**: Configures A/B runs, monitors progress, inspects aggregates, and exports results for stakeholders.
- **Admin / Platform Ops**: Tracks resource usage, enforces quotas, and audits evaluation activity.
- **Data Scientist**: Compares hybrid versus vector retrieval pipelines, evaluates statistical significance, and iterates on configurations.
- **Support Engineer**: Validates customer-requested experiments, ensures cleanup, and diagnoses run issues.

## Functional Requirements
1. **Planning & Tracking**
   - Reintroduce `IMPLEMENTATION_PLAN.md` with milestone status updates.
   - Add a CI guard that fails when the plan is missing or stale (e.g., last updated milestone exceeds configured window).

2. **Persistence Layer**
   - Adopt a SQLAlchemy-backed adapter (or document why the existing approach remains) with migration coverage for SQLite/Postgres.
   - Ensure tables for tests, arms, queries, and results have foreign keys and indexes for lookup patterns.
   - Provide CRUD unit tests validating create/update/delete flows across backends.

3. **Collection Pipeline**
   - Respect `reuse_existing` flag by hashing corpus + config and skipping rebuild when collections exist.
   - Push collection builds into a background queue with retry/backoff handling and observable status transitions (`pending → building → ready/failed`).
   - Store stats metadata (chunk counts, embedding dimensions, provider/model revisions) for each arm.

4. **Query Runner & Metrics**
   - Support vector-only and hybrid retrieval (with optional reranker) per arm.
   - Record per-query metrics (Recall@k, MRR, nDCG, Hit@k, latency percentiles) and persist results.
   - Expose paginated result APIs (default 50, max 500) with summary aggregates and significance calculations.

5. **Governance & Cleanup**
   - Implement cleanup policies: immediate deletion when `on_complete` is set and TTL sweeper for residual collections.
   - Enforce quotas, provider allowlists, and rate limits at both API and worker levels.
   - Emit structured audit logs for create, run, delete, and export actions.

6. **Observability & Exports**
   - Emit Prometheus metrics covering collection builds, job durations, queue depth, and success/failure counts.
   - Produce structured logs for key lifecycle events and errors.
   - Provide JSON/CSV exports with stable schema definitions and update developer/user documentation with usage guides.

## Non-Functional Requirements
- Background jobs must support retries with exponential backoff and expose their state through metrics/logging.
- Queue workers should scale horizontally; job status must persist and remain queryable after restarts.
- API responses must be paginated (default 50, max 500) and include total counts for clients.
- Test coverage must address hashing determinism, collection reuse, cleanup behavior, API contracts, and export payload integrity.

## Milestones & Timeline
1. **M1 - Persistence & Documentation (1 week)**
   Finalize adapter/migrations, re-establish implementation plan doc, and add CRUD tests.

2. **M2 - Collection Pipeline (1.5 weeks)**
   Implement reuse logic, background job execution, status transitions, and failure handling tests.

3. **M3 - Query Runner & Metrics (1 week)**
   Solidify retrieval flows, persist metrics, and add pagination/aggregation tests.

4. **M4 - Governance & Cleanup (1 week)**
   Enforce quotas, implement cleanup scheduler, record audit logs, and validate enforcement paths.

5. **M5 - Observability & Exports (1 week)**
   Ship Prometheus metrics, structured logging, export endpoints with tests, and documentation updates including property/integration tests.

## Dependencies
- Background task infrastructure (reuse existing evaluation runner or introduce queue service).
- Access to embedding providers and API keys for test corpora.
- Redis or equivalent datastore for job tracking and TTL enforcement.
- Prometheus/Grafana stack for metrics ingestion and visualization.

## Risks & Mitigations
- **Long-running jobs**: Use queue with max concurrency limits and cancellation hooks; surface progress metrics.
- **Resource overuse**: Enforce quotas and rate limits in API and worker tiers; alert on threshold breaches.
- **Data drift**: Hash configs and track provider/model revisions to detect mismatches before reuse.
- **Test flakiness**: Employ synthetic embeddings and deterministic corpora in CI to guarantee repeatable results.
