# Workflows v0.1/v0.2 - PRD Mapping to Code

This document maps the high-level PRD (Workflows-PRD-1.md) to concrete files, modules, and endpoints implemented in this repository. It highlights what is in place now, what is intentionally stubbed for v0.1, and what remains TODO.

## Scope Implemented (current)

- Engine + scheduler:
  - Linear engine with per-step timeouts, retries, pause/resume, cooperative cancel, leases/heartbeats, orphan reaper: `tldw_Server_API/app/core/Workflows/engine.py`
  - In-process fair scheduler with per-tenant and per-workflow concurrency limits.
- Step registry and adapters:
  - Registry: `tldw_Server_API/app/core/Workflows/registry.py`
  - Adapters: `prompt`, `rag_search`, `media_ingest` (local + HTTP), `mcp_tool`, `webhook`, `wait_for_human`: `tldw_Server_API/app/core/Workflows/adapters.py`
- Database adapter (SQLite): `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`
  - Definitions, runs (with optional tokens/cost fields), step runs (with pid/pgid/workdir/stdout/stderr), events, artifacts.
- API endpoints (CRUD + run lifecycle + events + artifacts): `tldw_Server_API/app/api/v1/endpoints/workflows.py`
- Pydantic schemas: `tldw_Server_API/app/api/v1/schemas/workflows.py`
- Router mounted in app: `app/main.py`
- Options discovery (chunkers for builder UIs): `GET /api/v1/workflows/options/chunkers`

## PRD → Code Mapping

- Workflow definition: JSON schema with steps and templated inputs
  - `schemas/workflows.py: WorkflowDefinitionCreate` (id/name/type/config/timeout/retry)
  - Stored verbatim in DB (`Workflows_DB.py` → `workflows.definition_json`)

- Execution modes `mode=async|sync`
  - `endpoints/workflows.py`: `POST /workflows/{id}/run?mode=async|sync` and `POST /workflows/run?...`
  - Both modes execute server-side; the WebUI re-attaches to the run for guided sessions.

- Run/status/events/artifacts APIs
  - `GET /workflows/runs/{run_id}` (tenant-isolated)
  - `GET /workflows/runs/{run_id}/events?since=...` (tenant-isolated, strict event_seq)
  - `WS /workflows/ws?run_id=...` (JWT + run-level auth)
  - `GET /workflows/runs/{run_id}/artifacts` (tenant-isolated)

- Pause/resume/cancel + retry
  - `POST /workflows/runs/{run_id}/{pause|resume|cancel}`
  - `POST /workflows/runs/{run_id}/retry`

- Storage
  - Dedicated SQLite DB: `Databases/workflows.db` via `Workflows_DB.py` (WAL enabled). Honors `DATABASE_URL_WORKFLOWS` for `sqlite://` URIs.

- Options discovery
  - RAG: reuse existing `GET /api/v1/rag/capabilities`
  - Chunkers: `GET /api/v1/chunking/capabilities` (this change)

## Security & AuthNZ

- HTTP endpoints use `get_request_user` (single-user API key and multi-user JWT modes).
- Tenant isolation enforced for list/get definition, get run, events, and artifacts.
- WS auth: JWT verification and run-level authorization enforced (subject must match `run.user_id`).
- Egress protections: `is_url_allowed` for webhooks and HTTP ingest (allowlist + private IP block). Webhooks support HMAC signing.

## Observability

- Telemetry hooks (OpenTelemetry) under `core/Metrics` are integrated where available; engine appends normalized events and sets run status/duration.
- Step events include `step_started|step_completed|step_failed|step_timeout|step_cancelled|step_log_tail`; run events include `run_started|run_completed|run_failed|run_cancelled|waiting_human`.
- Token/cost metrics stored on runs opportunistically when present in step outputs.

## What Is Stubbed/Deferred (per PRD)

- Postgres backend for `DATABASE_URL_WORKFLOWS` (currently supports `sqlite://` paths).
- WebUI CSRF/CSP and minimal screens to surface definitions/runs/approvals.
- Full artifact production from steps (DB + endpoint exist; step adapters selectively attach metadata/events, not persisted artifact rows yet).
- Budgets/quotas; triggers; branch/parallel (v0.2+ roadmap).

## Data Model (implemented)

- `workflows`: definition storage with versioning, soft delete.
- `workflow_runs`: lifecycle and snapshot fields, plus optional `tokens_input|tokens_output|cost_usd`.
- `workflow_events`: append-only event log with `event_seq` and `created_at`.
- `workflow_step_runs`: includes `attempt`, leases/heartbeat, and subprocess fields (`pid|pgid|workdir|stdout|stderr`).
- `workflow_artifacts`: artifact metadata per run/step (v0.2 surface).

## Notes / Deviations

- RAG sources naming should align with `media_db`, `notes`, `characters`, `chats` per unified pipeline.
- Chunker discovery for workflow builders is exposed at `GET /api/v1/workflows/options/chunkers` (not ingestion-specific).
- `DATABASE_URL_WORKFLOWS` currently supports only `sqlite://` URIs for custom paths.

## Next Iteration Checklist

1) Persist artifacts for relevant steps and expose streaming download where applicable.
2) Standardize token/cost capture across providers; emit metrics counters/histograms.
3) Optional: Postgres support for `DATABASE_URL_WORKFLOWS` with migrations.
4) WebUI: definitions editor, runs timeline, approvals panel with CSRF; SSE alternative to WS where needed.
5) Branch/parallel (v0.2+) and triggers/schedules.
