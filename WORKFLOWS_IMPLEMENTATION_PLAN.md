## Stage 1: Engine Hardening
**Goal**: Make linear execution robust with per-step retries/backoff, universal timeouts, cooperative cancel with subprocess group termination, and minimal leases/heartbeats for safe resume.
**Success Criteria**:
- Step-level `retry` honored with exponential backoff + jitter; `attempt` increments persisted to `workflow_step_runs`.
- Per-step `timeout_seconds` applied across all adapters (prompt, rag_search, mcp_tool, webhook, media_ingest). Timeouts emit `step_timeout` and mark step failed.
- `cancel` escalates to process-group termination for subprocess-backed work (see `subprocess_utils`), emits `step_cancelled` with `forced_kill` flag.
- Heartbeat fields recorded on step rows; on startup, engine reaps orphan running steps and marks them failed with `status_reason=orphan_reaped`.
- Durable event ordering maintained (`event_seq` strictly increasing); run transitions end in `succeeded|failed|cancelled|waiting_human` only.
**Tests**:
- Unit: backoff calculation; `terminate_process` escalation; timeout triggers; orphan reaper logic.
- Integration: cancel during `media_ingest` (TEST_MODE) → run becomes `cancelled`, `step_cancelled` event present; retry increments `attempt` and eventually fails or succeeds; timeout forces step failure.
**Status**: Not Started

## Stage 2: API & DB Completeness
**Goal**: Complete CRUD/versioning, idempotency, and failure-resume semantics aligned to PRD.
**Success Criteria**:
- `POST /api/v1/workflows/{workflow_id}/versions` creates immutable new version (unique `(tenant_id,name,version)`), returns metadata.
- `DELETE /api/v1/workflows/{workflow_id}` soft-deletes definition; default list excludes inactive.
- `POST /api/v1/workflows/runs/{run_id}/retry` resumes from last failed step using same inputs and definition snapshot; emits `run_resumed` with `after` field.
- Idempotency: identical `(tenant_id,user_id,idempotency_key)` returns existing run (DB uniqueness or lookup); documented behavior.
- `workflow_step_runs` extended/used to persist `attempt`, `locked_by`, `locked_at`, `lock_expires_at`, `heartbeat_at`.
**Tests**:
- Unit: DB methods for versions, soft delete, idempotency lookup.
- Integration: create v1 and v2; list reflects latest first; soft-deleted hidden; retry continues from failed step and completes; idempotent run returns same `run_id`.
**Status**: Not Started

## Stage 3: RAG & Media Ingest Integration
**Goal**: Expand adapters to cover PRD options, surface chunker registry, and persist chunking/indexing metadata.
**Success Criteria**:
- `rag_search` supports PRD flags: reranking (`flashrank|cross_encoder|hybrid`), `enable_citations`, `enable_table_processing`, caching toggles; returns `documents`, `timings`, `citations` when enabled.
- `media_ingest` enforces `safety.allowed_domains`, `limits.*`, and returns outputs with `chunker_name`/`chunker_version` when chunking used; `rag_indexed` reflects indexing attempt.
- Options discovery: `GET /api/v1/workflows/options/chunkers` returns names, versions, and parameter schemas from the existing Chunking module.
- Hierarchical chunking descriptors included as specified when applicable.
**Tests**:
- Unit: validate chunker/capabilities payload shape; mapping of rag flags to unified pipeline kwargs.
- Integration: workflow with rag reranking+citations returns expected keys; chunker discovery endpoint responds and is used by definitions validation path (basic).
**Status**: Not Started

## Stage 4: Security & Observability
**Goal**: Strengthen egress/SSRF protections, add telemetry/metrics, and finalize WS/run-level authorization behaviors.
**Success Criteria**:
- Secure HTTP client with egress allowlist and RFC1918/link-local IP blocking (applied to webhook/tool adapters by default); HMAC signing via existing webhook manager verified.
- OpenTelemetry spans for run→step→provider; Prometheus counters/histograms for runs, step durations, cancellations, failures.
- WS already requires JWT and run ownership; document and add structured errors for auth failure.
**Tests**:
- Unit: IP/domain validation; metrics labels sanity; span nesting smoke.
- Integration: webhook in TEST_MODE bypass; unauthorized WS connect rejected; authorized streams events.
**Status**: Not Started

## Stage 5: WebUI Minimal
**Goal**: Provide basic definitions CRUD, runs list/detail with live event timeline, and human-approval panel with CSRF.
**Success Criteria**:
- Definitions list/detail with JSON editor and schema validation; create/run from UI.
- Run detail shows step timeline, logs, final inputs/outputs/error; live updates via WS with reconnect using `since=event_seq`.
- Human-in-the-loop approve/reject UI posts to API; CSRF tokens and CSP applied.
**Tests**:
- E2E (Playwright): create definition, run, observe timeline, approve `wait_for_human` step to completion.
- Security: CSRF token required on POST in UI flows.
**Status**: Not Started

---

### Notes & Assumptions
- Default DB: `Databases/workflows.db` (SQLite with WAL); Postgres via future `DATABASE_URL_WORKFLOWS`.
- Ad-hoc runs may be disabled via `WORKFLOWS_DISABLE_ADHOC`; tests set `TEST_MODE=1` to avoid network/egress.
- Out-of-scope for v0.1 per PRD: branching/parallelism, schedules/triggers, full artifacts, advanced budgets/quotas.

