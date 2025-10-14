# Workflows (v0.1)

This document captures the current state of the Workflows module, its APIs, data model, execution engine behavior, security model, and the near‑term roadmap. It supersedes the placeholder links that were here previously. For the initial PRD, see `Workflows-PRD-1.md` at the repository root.

## Status & Scope

- Implemented: Linear workflows with a small, composable step set and a robust runtime (retries, timeouts, pause/resume, cancel, heartbeats, orphan reaping). Streaming run events over WebSocket and HTTP polling. Artifacts persisted and downloadable with guardrails. SQLite default; PostgreSQL supported via shared content backend.
- Non‑goals in v0.1: Branching/parallelism, graph/DAG editor, arbitrary user code execution, distributed workers. These are planned for v0.2+.

## Module Layout

- Engine and registry: `tldw_Server_API/app/core/Workflows/`
  - `engine.py`: workflow runtime, scheduler, control actions
  - `adapters.py`: step implementations (prompt, rag_search, media_ingest, mcp_tool, webhook)
  - `subprocess_utils.py`: child process lifecycle helpers
  - `registry.py`: available step types
- Persistence: `tldw_Server_API/app/core/DB_Management/Workflows_DB.py` (SQLite and PostgreSQL via `DatabaseBackend`)
- API: `tldw_Server_API/app/api/v1/endpoints/workflows.py` and `.../schemas/workflows.py`
- WebUI: `tldw_Server_API/WebUI/tabs/workflows_content.html`
- PRD: `Workflows-PRD-1.md`

## API Surface

Base prefix: `/api/v1/workflows`

- Definitions
  - `POST /` → Create definition (immutable versions)
  - `GET /` → List active definitions (tenant + owner scoped)
  - `GET /{workflow_id}` → Get definition (includes stored snapshot)
  - `POST /{workflow_id}/versions` → Create new version
  - `DELETE /{workflow_id}` → Soft delete
- Runs
  - `POST /{workflow_id}/run?mode=async|sync` → Run saved definition (idempotency supported)
  - `POST /run?mode=async|sync` → Run ad‑hoc definition (configurable rate‑limited)
  - `GET /runs?status=&owner=&workflow_id=&limit=&offset=` → List runs (owner by default; admin may filter by `owner`), returns `runs` and optional `next_offset` for pagination
  - `GET /runs/{run_id}` → Run status and final outputs
  - `GET /runs/{run_id}/events?since=` → Ordered event stream (HTTP polling)
  - `WS /ws?run_id=...&token=...` → Live event stream (JWT required; run owner only)
  - `POST /runs/{run_id}/pause|resume|cancel|retry` → Control actions
- Human in the loop
  - `POST /runs/{run_id}/steps/{step_id}/approve|reject` → Approve/reject with optional edits
- Artifacts
  - `GET /runs/{run_id}/artifacts` → List run artifacts
  - `GET /artifacts/{artifact_id}/download` → Download a single artifact (file:// only)
  - `GET /runs/{run_id}/artifacts/download` → Zip and stream all eligible artifacts
- Options discovery
  - `GET /options/chunkers` → Chunker methods, defaults, and basic param schema
  - `GET /step-types` → List available step types for UI builders

## Definition Schema (v0.1)

Minimal JSON body for `WorkflowDefinitionCreate`:

```
{
  "name": "hello",
  "version": 1,
  "description": "optional",
  "tags": ["demo"],
  "inputs": {},
  "steps": [
    {"id": "s1", "name": "Greet", "type": "prompt", "config": {"template": "Hello {{ inputs.name }}"}}
  ],
  "metadata": {},
  "visibility": "private"
}
```

Server‑enforced limits (config in code):
- Definition size ≤ 256 KB
- ≤ 50 steps per definition
- Step `config` size ≤ 32 KB
- Unknown step types rejected at create/run

## Step Types

Registered under `StepTypeRegistry`:

- `prompt`: Render a prompt template using sandboxed template engine; returns `{ text }`. Supports `simulate_delay_ms` for testing timeouts/retries and optional artifact persistence.
- `rag_search`: Execute RAG search via unified pipeline; returns `{ documents, metadata, timings, citations? }`. Passes through core pipeline options such as reranking, security filters, and generation.
- `media_ingest`: Ingest local files (`file://...`) or optional network sources via yt‑dlp/ffmpeg (egress allowlisted). Supports text extraction, chunking strategies, optional indexing into the Media DB, and artifact persistence of downloaded files.
- `mcp_tool`: Execute MCP tools through the unified server registry. Test‑friendly fallback for `tool_name=echo`.
- `webhook`: Send events to a URL (HMAC signing and SSRF/egress controls) or dispatch to registered webhooks.
- `wait_for_human`: Pause run with status `waiting_human` until `approve`/`reject`.
- `delay`: Pause the workflow for a fixed time (milliseconds). Useful for demos, backoffs or pacing.
- `log`: Log a templated message at the chosen level (`debug|info|warning|error`). Helps with debugging and audit trails.

See `adapters.py` for configuration keys and behavior of each step.

## Engine Behavior

- Modes: `async` (background via in‑process scheduler) and `sync` (server‑side synchronous; UI reattaches by `run_id`).
- Lifecycle: `queued → running → (waiting_human|cancelled|failed|succeeded)`.
- Retries/Timeouts: Per‑step `retry` (exponential backoff + jitter) and `timeout_seconds` enforced. Cooperative cancellation via a cancel flag checked between sleeps/attempts.
- Heartbeats/Leases: Step runs record `locked_by/locked_at/lock_expires_at/heartbeat_at`; orphan reaper marks stale step runs as failed and emits events.
- Subprocess Steps: Launched in new process group; engine records `pid/pgid/workdir/stdout/stderr` and escalates termination on cancel/timeout.
- Events: Strict `event_seq` ordering per run; WebSocket emits a `snapshot` and then ordered events with lightweight heartbeats.

## Persistence

- Default: SQLite (`Databases/workflows.db`) with WAL enabled.
- PostgreSQL: Supported when a content backend is configured; schema migrations applied automatically (see tests under `tests/Workflows/test_workflows_postgres_migrations.py`).
- Tables: `workflows`, `workflow_runs`, `workflow_step_runs`, `workflow_events`, `workflow_artifacts`.
- Idempotency: `idempotency_key` prevents duplicate run creation per `(tenant_id, user_id, workflow)`.

## Security Model

- AuthNZ: All HTTP endpoints use standard API auth; WS requires a JWT and enforces run‑owner equality (subject must match `run.user_id`).
- Tenant Isolation: Read operations enforce tenant boundaries, and HTTP reads now enforce run‑owner or admin (consistent with WS).
- Rate Limits: Ad‑hoc runs and run‑saved endpoints are rate‑limited via `slowapi` if available.
- Egress Controls: Webhook step checks URL via `is_url_allowed` to block private IPs/SSRF; optional HMAC signature header.
- Artifact Downloads: Only `file://` URIs; size and MIME allowlists enforced; basic path containment checks.

### RBAC Claims Exposure

`get_request_user` now enriches the request user with AuthNZ-backed RBAC claims:
- `roles`: names from `user_roles`
- `permissions`: aggregated from role permissions and explicit `user_permissions` overrides
- `is_admin`: true if `admin` role or `is_superuser`

In single-user mode, the fixed user is exposed with admin-like claims for compatibility.

## Configuration

- Concurrency limits: `WORKFLOWS_TENANT_CONCURRENCY` (default 2), `WORKFLOWS_WORKFLOW_CONCURRENCY` (default 1)
- Ad‑hoc runs: `WORKFLOWS_DISABLE_ADHOC=true` to disable
- Artifacts: `WORKFLOWS_ARTIFACT_MAX_DOWNLOAD_BYTES`, `WORKFLOWS_ARTIFACT_ALLOWED_MIME`, `WORKFLOWS_ARTIFACT_BULK_MAX_BYTES`
- Webhooks: `WORKFLOWS_WEBHOOK_SECRET`, `WORKFLOWS_WEBHOOK_TIMEOUT`
- Completion hooks: `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS=true` globally disables completion webhooks.
- DB URI (SQLite): `DATABASE_URL_WORKFLOWS=sqlite:///path/to/workflows.db`
- Webhook global disable: `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS=true` disables completion hooks globally
- Artifact scope validation: `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true|false` (default true). When false, validation failures log a warning but do not block download.
- SQLite connection pool: `WORKFLOWS_SQLITE_POOL_SIZE` (default 0 disables) enables a lightweight pool for hot paths (events).
 
In production, when the content backend is configured for PostgreSQL (recommended), the Workflows DB will default to PostgreSQL automatically via the shared backend wiring. SQLite remains the default for development and tests.

## WebUI

- Basic tab at `tldw_Server_API/WebUI/tabs/workflows_content.html` for definition CRUD, run start (sync/async), run status, event stream, and artifact downloads (server and client‑side zip).

## Testing

- Unit/integration tests for DB and engine across SQLite and PostgreSQL backends: `tldw_Server_API/tests/Workflows/*`
- Stress tests (disabled by default): enable with `TLDW_WORKFLOW_STRESS=1`.
- E2E tests exercise workflows in user flows where relevant.

## Known Gaps (to address)

- Artifact path scope validation uses `commonpath` with a strict/relaxed toggle; consider moving to `Path.is_relative_to` when minimum Python supports it.
- Per-run event counters reduce races; assess using DB-side sequences if needed under extreme concurrency.
- SQLite still uses a lightweight pool; evaluate moving workflows to Postgres by default in production.

## Roadmap (v0.2+)

- Branching/Conditionals/Parallelism: Introduce minimal JSONLogic‑like conditions, `branch`/`join` steps, and foreach/parallel fan‑out with deterministic join semantics.
- Step Library Expansion: STT/TTS adapters, data transformation sandbox, export steps.
- Schedules/Triggers: Time‑based triggers and inbound webhook triggers.
- Budgets/Quotas: Per‑tenant/user budgets with enforcement and reporting.
- GUI Builder: Drag‑and‑drop graph editor in the WebUI backed by the APIs above.

## Quick Start

1. Create a definition:
   `POST /api/v1/workflows` with a minimal body (see schema above)
2. Run it: `POST /api/v1/workflows/{id}/run?mode=async|sync`
3. Watch progress: `GET /api/v1/workflows/runs/{run_id}/events` or `WS /api/v1/workflows/ws?run_id=...`
4. Download outputs: `GET /api/v1/workflows/runs/{run_id}/artifacts` and `.../download`

For deeper goals and rationale, see `Workflows-PRD-1.md`.
