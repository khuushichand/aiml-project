# Workflows (v0.1)

This document captures the current state of the Workflows module, its APIs, data model, execution engine behavior, security model, and the near‑term roadmap. It supersedes the placeholder links that were here previously. For the consolidated PRD, see `Docs/Design/Workflows_PRD.md` (the historical draft remains at `Workflows-PRD-1.md`).

## Status & Scope

- Implemented: Linear workflows with a small, composable step set and a robust runtime (retries, timeouts, pause/resume, cancel, heartbeats, orphan reaping). Streaming run events over WebSocket and HTTP polling. Artifacts persisted and downloadable with guardrails. SQLite default; PostgreSQL supported via shared content backend.
- Non‑goals in v0.1: Full graph editor and distributed workers. Minimal branching (branch/map) has been added to enable early DAG-like flows; richer parallelism is planned for v0.2+.

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
  - `GET /runs/{run_id}/artifacts/manifest?verify=` → Per-run artifact manifest; optional checksum verification
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
- `branch`: Evaluate a boolean condition and optionally jump to a target step id (`true_next` / `false_next`).
- `map`: Fan‑out over a list and apply a nested step with optional concurrency; returns a list of `results`.

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
- Tables: `workflows`, `workflow_runs`, `workflow_step_runs`, `workflow_events`, `workflow_artifacts` (+ optional `workflow_event_counters`, `workflow_webhook_dlq`).
- Idempotency: `idempotency_key` prevents duplicate run creation per `(tenant_id, user_id, workflow)`.
- Indices/constraints and types:
  - Per‑run event ordering: composite index and unique constraint on `(run_id, event_seq)` in `workflow_events`.
  - Cascading deletes: `workflow_events`, `workflow_step_runs`, and `workflow_artifacts` reference `workflow_runs(run_id)` with `ON DELETE CASCADE` (PostgreSQL). New SQLite DBs use the same FK with `PRAGMA foreign_keys=ON`.
  - Partial indexes on statuses: `status='running'` and `status='queued'` for faster active/queue queries (PostgreSQL and modern SQLite).
  - JSON payloads: PostgreSQL stores `workflow_events.payload_json` as `JSONB` with a GIN index; SQLite stores JSON as `TEXT`.
- Pooling & contention:
  - PostgreSQL uses `psycopg_pool` when available (min/max size, timeouts, max lifetime/idle) with `dict_row` rows; falls back to a minimal pool if not installed.
  - SQLite applies `PRAGMA busy_timeout=5000`, `wal_autocheckpoint=1000`; hot write paths include exponential backoff on `database is locked`.

## Security Model

- AuthNZ: All HTTP endpoints use standard API auth; WS requires a JWT and enforces run‑owner equality (subject must match `run.user_id`).
- Tenant Isolation: Read operations enforce tenant boundaries, and HTTP reads now enforce run‑owner or admin (consistent with WS).
- Rate Limits: Ad‑hoc runs and run‑saved endpoints are rate‑limited via `slowapi` if available.
  - Tests/CI can bypass limits by setting `WORKFLOWS_DISABLE_RATE_LIMITS=true` (auto-detected under pytest).
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
- Webhook egress policy: Per‑tenant allow/deny lists are enforced for completion webhooks and webhook steps.
  - Global: `WORKFLOWS_WEBHOOK_ALLOWLIST`, `WORKFLOWS_WEBHOOK_DENYLIST`
  - Tenant overrides: `WORKFLOWS_WEBHOOK_ALLOWLIST_<TENANT>`, `WORKFLOWS_WEBHOOK_DENYLIST_<TENANT>` (tenant upper‑cased, `-` → `_`)
  - Private IP blocking follows `WORKFLOWS_EGRESS_BLOCK_PRIVATE` (defaults true).
- DB URI (SQLite): `DATABASE_URL_WORKFLOWS=sqlite:///path/to/workflows.db`
- Webhook global disable: `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS=true` disables completion hooks globally
- Artifact scope validation: `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true|false` (default true). When false, validation failures log a warning but do not block download.
- Artifact validation modes (per-run override):
  - Each run can opt into `validation_mode = 'non-block'` to allow artifact downloads even when scope validation fails. This is a per-run override intended for trusted/internal workflows.
  - Resolution order: per-run setting is evaluated first; if not set (or not `non-block`), the server falls back to `WORKFLOWS_ARTIFACT_VALIDATE_STRICT` (default true).
  - Example behavior:
    - `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=false` → downloads proceed with a warning when path scope validation fails.
    - `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true` and run’s `validation_mode='non-block'` → downloads proceed for that run despite strict env setting.
  - Scope check uses `commonpath` between the resolved artifact path and recorded `workdir` (when available). Only `file://` artifacts are downloadable via the API.
- Artifact integrity: When `checksum_sha256` is recorded for an artifact, downloads verify the checksum. On mismatch, responses use `409 Conflict` in strict mode; non‑strict modes warn and continue.
- Artifact manifest: `GET /runs/{run_id}/artifacts/manifest?verify=true` computes checksums and returns `integrity_summary`.
- Artifact retention and GC:
  - Worker: `WORKFLOWS_ARTIFACT_GC_ENABLED=true` to enable.
  - Settings: `WORKFLOWS_ARTIFACT_RETENTION_DAYS` (default 30), `WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC` (default 3600).
  - Behavior: Deletes DB rows for artifacts older than retention. For `file://` URIs, also deletes files from disk.
- SQLite connection pool: `WORKFLOWS_SQLITE_POOL_SIZE` (default 0 disables) enables a lightweight pool for hot paths (events).

### Security & Governance

- Egress policy (centralized):
  - Profile: `WORKFLOWS_EGRESS_PROFILE=strict|permissive|custom` (default `strict` in `prod`, `permissive` otherwise based on `ENVIRONMENT`/`APP_ENV`).
  - Allowed schemes: `http, https` (fixed).
  - Allowed ports: `WORKFLOWS_EGRESS_ALLOWED_PORTS` (comma‑separated; default `80,443`).
  - Allowlist (host/domain): `WORKFLOWS_EGRESS_ALLOWLIST` (comma‑separated; supports subdomains via `example.com`).
  - Block private/reserved IPs: `WORKFLOWS_EGRESS_BLOCK_PRIVATE=true|false` (default true). DNS is resolved and all target IPs must be public.
  - Webhook‑specific allow/deny (global and per‑tenant) remain available as documented above; they use the centralized evaluator.

- Audit logging (Unified Audit Service):
  - Workflows endpoints log key events: admin owner overrides, permission denials (tenant mismatch, not owner), and run creation (saved/adhoc). Logs include a request ID when provided (`X-Request-ID`), IP, user agent, endpoint and method where available.
  - Query audit logs via `GET /api/v1/admin/audit-log`.

- PII/Secrets:
  - Log redaction for `log` step: `WORKFLOWS_REDACT_LOGS=true|false` (default true) applies PII redaction to messages before emitting to logs.
  - Field‑level encryption for artifact metadata: enable with `WORKFLOWS_ARTIFACT_ENCRYPTION=true` and provide `WORKFLOWS_ARTIFACT_ENC_KEY` (base64 16/24/32 bytes for AES‑GCM). Encrypted metadata is transparently decrypted on read when the key is present; otherwise a placeholder is returned.
  - Scoped secrets injection: run requests accept `secrets` (map of strings). These are injected into the execution context as `context.secrets` and never persisted. Secrets are cleared from memory when the run reaches a terminal state.

- Quotas and rate limits:
  - Endpoint rate‑limits (slowapi) remain as before and are disabled in tests.
  - Per‑user quotas at run start (saved and ad‑hoc):
    - Burst: `WORKFLOWS_QUOTA_BURST_PER_MIN` (default 60/min).
    - Daily: `WORKFLOWS_QUOTA_DAILY_PER_USER` (default 1000/day).
    - On exceed: returns `429 Too Many Requests` with headers `X-RateLimit-Limit`, `X-RateLimit-Remaining`, and `X-RateLimit-Reset`.
    - Disable (e.g., tests): `WORKFLOWS_DISABLE_QUOTAS=true`.

### Observability

- Metrics (Prometheus-compatible):
  - Counters: `workflows_runs_started{tenant,mode}`, `workflows_runs_completed{tenant}`, `workflows_runs_failed{tenant}`.
  - Histograms: `workflows_run_duration_ms{tenant}`, `workflows_step_duration_ms{type}`.
  - Step counters: `workflows_steps_started{type}`, `workflows_steps_succeeded{type}`, `workflows_steps_failed{type}`.
  - Webhooks: `workflows_webhook_deliveries_total{status,host}` with status in `delivered|failed|blocked`.
  - Engine gauges: `workflows_engine_queue_depth`.
  - Scrape: `/metrics` (root) or `/api/v1/metrics` (JSON).

- Tracing (OpenTelemetry):
  - Spans: `workflows.run` (per run), nested `workflows.step` (per step), and `workflows.webhook` (completion hook delivery).
  - W3C trace context injected into outbound webhook headers (`traceparent`, optional `baggage`).

- Health & Readiness:
  - Liveness: `GET /healthz` returns `{status, queue_depth, time}`.
  - Readiness: `GET /readyz` returns `{ready, engine, db, time}` with DB connectivity and backend schema version (when using PostgreSQL) checked against the expected version.
 
In production, when the content backend is configured for PostgreSQL (recommended), the Workflows DB will default to PostgreSQL automatically via the shared backend wiring. SQLite remains the default for development and tests.

## Validation Modes

- Global strict validation for artifact download scope:
  - Env: `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true|false` (default: true)
  - Behavior: when true, file:// downloads must be under the recorded workdir and have an allowed MIME; otherwise 400.
  - When false, scope mismatches are logged as warnings and the download proceeds.
- Per-run override:
  - Run metadata may include `validation_mode: 'block'|'non-block'` (default: `block`).
  - Non-block allows artifact download even when global strict is enabled.

## Control: Cancel / Pause / Resume

- `POST /runs/{run_id}/cancel` sets a cancel flag and attempts to terminate any recorded subprocesses; the running step cooperatively checks `is_cancelled()`.
- `POST /runs/{run_id}/pause` transitions the run to `paused` and emits a `run_paused` event; `resume` returns the run to `running`.
- Steps receive periodic heartbeats (`heartbeat_at`) and may be locked for a short TTL to prevent concurrent work.

## Webhooks: Lifecycle and Delivery

- Completion webhooks can be configured on definitions (`on_completion_webhook: {url, include_outputs}`) and are dispatched on terminal states.
- Global disable: `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS=true` short-circuits dispatch.
- SSRF/egress policy:
  - Central evaluator enforces allowed schemes/ports, host allowlist, and private IP blocking.
  - Per-tenant allow/deny via `WORKFLOWS_WEBHOOK_ALLOWLIST(_<TENANT>)`, `WORKFLOWS_WEBHOOK_DENYLIST(_<TENANT>)`.
- Signing and tracing:
  - HMAC header when `WORKFLOWS_WEBHOOK_SECRET` is set: `X-Workflows-Signature` and `X-Hub-Signature-256`.
  - W3C `traceparent` is injected when tracing is enabled.
- Delivery outcomes are recorded as `webhook_delivery` run events with `status=delivered|failed|blocked` and masked host.
- Dead-letter queue (DLQ): failures enqueue into `workflow_webhook_dlq` for background retries with exponential backoff and jitter.

## Retention Policy (Artifacts)

- Optional background GC removes file:// artifacts and DB rows older than `WORKFLOWS_ARTIFACT_RETENTION_DAYS` (default 30).
- Enable worker via `WORKFLOWS_ARTIFACT_GC_ENABLED=true`; interval controlled by `WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC`.

## Configuration Reference

- Backend selection
  - Uses shared content backend (see `Config_Files/config.txt` → `[Database] type=sqlite|postgres`); Workflows will default to Postgres when the content backend is Postgres.
  - SQLite DB path (fallback): `Databases/workflows.db` (config key `workflows_path`).

- Rate limits and quotas (disabled in tests automatically)
  - Endpoint rate limits (slowapi): disabled with `WORKFLOWS_DISABLE_RATE_LIMITS=true`.
  - Quotas at run start: `WORKFLOWS_QUOTA_BURST_PER_MIN` (60), `WORKFLOWS_QUOTA_DAILY_PER_USER` (1000), disable with `WORKFLOWS_DISABLE_QUOTAS=true`.

- Engine concurrency
  - `WORKFLOWS_TENANT_CONCURRENCY` (default 2), `WORKFLOWS_WORKFLOW_CONCURRENCY` (default 1).

- Egress policy
  - Profile: `WORKFLOWS_EGRESS_PROFILE=strict|permissive|custom` (defaults to `strict` in prod, `permissive` elsewhere).
  - Allowed ports: `WORKFLOWS_EGRESS_ALLOWED_PORTS` (default `80,443`).
  - Host allowlist: `WORKFLOWS_EGRESS_ALLOWLIST` (comma-separated, supports subdomains).
  - Private IP blocking: `WORKFLOWS_EGRESS_BLOCK_PRIVATE=true|false` (default true).
  - Webhook allow/deny: `WORKFLOWS_WEBHOOK_ALLOWLIST(_<TENANT>)`, `WORKFLOWS_WEBHOOK_DENYLIST(_<TENANT>)`.

- Webhooks
  - Global disable: `WORKFLOWS_DISABLE_COMPLETION_WEBHOOKS=true|false` (default false).
  - Signing secret: `WORKFLOWS_WEBHOOK_SECRET`.
  - DLQ worker: `WORKFLOWS_WEBHOOK_DLQ_ENABLED`, `WORKFLOWS_WEBHOOK_DLQ_INTERVAL_SEC`, `WORKFLOWS_WEBHOOK_DLQ_BATCH`, `WORKFLOWS_WEBHOOK_DLQ_TIMEOUT_SEC`, `WORKFLOWS_WEBHOOK_DLQ_BASE_SEC`, `WORKFLOWS_WEBHOOK_DLQ_MAX_BACKOFF_SEC`, `WORKFLOWS_WEBHOOK_DLQ_MAX_ATTEMPTS`.

- Artifacts
  - Validation strictness: `WORKFLOWS_ARTIFACT_VALIDATE_STRICT=true|false` (default true).
  - Metadata encryption: `WORKFLOWS_ARTIFACT_ENCRYPTION=true|false` (+ `WORKFLOWS_ARTIFACT_ENC_KEY`).
  - Retention worker: `WORKFLOWS_ARTIFACT_GC_ENABLED`, `WORKFLOWS_ARTIFACT_RETENTION_DAYS`, `WORKFLOWS_ARTIFACT_GC_INTERVAL_SEC`.

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

- Branching/Conditionals/Parallelism: Expand minimal `branch/map` to full JSONLogic‑like conditions and parallel fan‑out with deterministic fan‑in/merge semantics.
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

### Example: Branch → Map → Log

A small pipeline that branches based on an input flag. If `inputs.enabled` is true, it maps over an `items` array and logs each item; otherwise it logs an error and exits.

```
{
  "name": "branch-map-log",
  "version": 1,
  "inputs": {"enabled": true, "items": ["alpha", "beta", "gamma"]},
  "steps": [
    {"id": "s_branch", "type": "branch", "config": {
      "condition": "{{ inputs.enabled }}",
      "true_next": "s_map",
      "false_next": "s_err"
    }},

    {"id": "s_map", "type": "map", "config": {
      "items": "{{ inputs.items }}",
      "concurrency": 2,
      "step": {"type": "log", "config": {"message": "Item {{ item }}", "level": "info"}}
    }, "on_success": "s_done", "on_failure": "s_err"},

    {"id": "s_err", "type": "log", "config": {"message": "Disabled or an error occurred", "level": "warning"}},
    {"id": "s_done", "type": "log", "config": {"message": "All done", "level": "info"}}
  ]
}
```

Notes:
- `branch` sets `__next__` internally when a target is provided; engine jumps by deterministic IDs.
- `map` runs the nested step for each element with limited concurrency and returns `{ results, count }` in `last` for downstream steps.
- `on_failure` on `s_map` routes to `s_err` if the map step cannot complete.
