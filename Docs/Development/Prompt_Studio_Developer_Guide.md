# Prompt Studio Developer Guide

This guide is for maintainers and contributors working on the Prompt Studio module. It covers architecture, data flow, database models, job orchestration, and development standards.

## Module Overview

Prompt Studio provides a structured lifecycle for prompts:
- Projects: workspace container for prompts + test corpora
- Prompts: versioned prompt definitions (system + user + examples + module configs)
- Test Cases: input/output corpus for evaluations and optimizations
- Evaluations: run a prompt against test cases, capture metrics
- Optimizations: iterate to improve prompts using strategies
- Realtime: WebSocket/SSE updates for jobs and status

Code roots:
- Endpoints: `tldw_Server_API/app/api/v1/endpoints/prompt_studio_*.py`
- Schemas: `tldw_Server_API/app/api/v1/schemas/prompt_studio_*.py`
- Core: `tldw_Server_API/app/core/Prompt_Management/prompt_studio/*`
- DB: `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`

## Data Model (SQLite by default)

Core tables (simplified; see migrations/DDL in `PromptStudioDatabase`):
- `prompt_studio_projects`
- `prompt_studio_prompts` (immutable versions; `parent_version_id` for lineage)
- `prompt_studio_test_cases`
- `prompt_studio_evaluations`, `prompt_studio_test_runs`
- `prompt_studio_optimizations`
- `prompt_studio_job_queue`

Common columns: `id`, `uuid`, timestamps, soft-delete flags, `client_id` for audit trail.

### DDL Snippets

Prompts table (versioned):

```
CREATE TABLE prompt_studio_prompts (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid TEXT UNIQUE NOT NULL,
  project_id INTEGER NOT NULL,
  signature_id INTEGER,
  version_number INTEGER NOT NULL DEFAULT 1,
  name TEXT NOT NULL,
  system_prompt TEXT,
  user_prompt TEXT,
  few_shot_examples JSON,
  modules_config JSON,
  parent_version_id INTEGER,
  change_description TEXT,
  client_id TEXT NOT NULL,
  deleted INTEGER DEFAULT 0,
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

Optimizations table (config JSON):

```
CREATE TABLE prompt_studio_optimizations (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uuid TEXT UNIQUE NOT NULL,
  project_id INTEGER NOT NULL,
  name TEXT,
  initial_prompt_id INTEGER,
  optimized_prompt_id INTEGER,
  optimizer_type TEXT NOT NULL,
  optimization_config JSON,
  initial_metrics JSON,
  final_metrics JSON,
  improvement_percentage REAL,
  iterations_completed INTEGER,
  max_iterations INTEGER,
  status TEXT DEFAULT 'pending',
  created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Main Flows

- Create/Update Prompt: New versions are appended to `prompt_studio_prompts`. Revert creates another version.
- Evaluations: Create record, optionally run background job; record metrics and test runs.
- Optimizations: Create record, enqueue job; workers iterate versions/parameters; persist progress + metrics.
- Realtime: Job events broadcast via event broadcaster; clients subscribe to project/job channels.

## Job Orchestration

- Queue: `prompt_studio_job_queue` stores jobs with `job_type`, `entity_id`, `payload`, `priority`.
- Manager: `JobManager` enqueues, cancels, tracks status.
- Background execution: FastAPI BackgroundTasks for light async; workers can be added for scalability.

## Security & Rate Limiting

- Access control: `require_project_access` for reads, `require_project_write_access` for writes.
- Rate limits: Applied to generation and optimization endpoints; see `prompt_studio_deps.check_rate_limit`.
- Validation: `SecurityConfig` enforces limits (max prompt length, test cases, concurrency).

## Testing Strategy

- Unit: Schemas and core managers (evaluation, optimization, IO)
- Integration: Endpoint tests using TestClient; prefer in-memory SQLite for speed
- Property-based: For generators and optimizers where appropriate
- Determinism: Avoid external LLM calls in tests; mock or simulate metrics

## Development Standards

- Versioning: Prompts are immutable; every update creates a new row. Do not mutate older versions.
- Idempotency: Bulk/import/export should be resilient; guard unique constraints.
- Error handling: Bubble to HTTP with context; avoid leaking stack traces in responses.
- Observability: Log meaningful events (`loguru`), add counters/timers if possible.
- OpenAPI: Add `openapi_extra` examples for new endpoints; keep tag = `Prompt Studio`.
- Docs: Update `Docs/API-related/Prompt_Studio_API.md` for new features.

## Common Tasks

- Add a new endpoint
  1) Add route + request/response schemas
  2) Enforce access dependencies (`require_project_access/_write_access`)
  3) Add validation (lengths, limits via `SecurityConfig`)
  4) Add OpenAPI examples via `openapi_extra`
  5) Update docs and tests

- Add a new optimization strategy
  1) Implement in `optimization_engine` with a clear interface
  2) Whitelist in `GET /optimizations/strategies`
  3) Add tests (unit + integration)
  4) Document parameters in this guide and API docs

## Pitfalls & Notes

- Background tasks: When using TestClient, prefer FastAPI BackgroundTasks (Starlette will await).
- DB locks: Use retries on `sqlite3.OperationalError: database is locked` in write-heavy paths.
- Schema drift: Keep endpoint code and Pydantic schemas in sync; prefer fixing schema mismatch fast.
- Large payloads: Avoid giant prompt/test case bodies in responses; paginate results.

## Future Enhancements

- Worker pool for evaluations/optimizations
- Strategy plugins (entry points) and dynamic loading
- Richer metrics and dashboards (Prometheus + Grafana)
- Project-level templates for module configurations

## Contact

- See repository issues and discussions for active workstreams.
- Maintain the OpenAPI docs alongside code changes.
