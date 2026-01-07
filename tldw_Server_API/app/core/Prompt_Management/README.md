# Prompt_Management

Prompt authoring, organization, evaluation, and optimization. This module includes a classic Prompts API and the Prompt Studio suite (projects, prompts, test cases, optimizations, status, and WebSocket broadcasting).

## 1. Descriptive of Current Feature Set

- Prompts API (classic)
  - Search prompts (FTS where available), list/export, keywords CRUD (normalized), soft delete.
  - Export prompts as CSV or Markdown; ephemeral prompt collections for quick grouping.
- Prompt Studio
  - Projects: CRUD, archive/unarchive, stats; multi-entity workspace per user/team.
  - Prompts: CRUD, versioning within projects, execute (dry-run) with project context.
  - Test cases: CRUD and batch runs; golden set support; generation helpers.
  - Optimizations: Request/track optimization jobs (MCTS and friends), monitor metrics.
  - Status: Lightweight status/health and metrics updates.
  - Realtime: WebSocket event broadcasting on project/prompt/test updates.
- Governance & safety
  - RBAC-style access checks for read/write actions; per-route rate limits.
  - Dual backend support for Prompt Studio DB (SQLite/PostgreSQL), with advisory lock metrics in PG mode.

Related Endpoints (file:line)
- Mounted routes: tldw_Server_API/app/main.py:2953 (Prompts), 2957–2963 (Prompt Studio routers)
- Prompts API (prefix `/api/v1/prompts`)
  - Health: tldw_Server_API/app/api/v1/endpoints/prompts.py:58
  - Sync log: tldw_Server_API/app/api/v1/endpoints/prompts.py:118
  - Search: tldw_Server_API/app/api/v1/endpoints/prompts.py:144
  - Keywords: create 183, list 236, delete 257
  - Export: GET 284 (CSV/Markdown base64)
  - Collections (ephemeral): create 709, get 733
- Prompt Studio (prefix `/api/v1/prompt-studio/...`)
  - Projects: tldw_Server_API/app/api/v1/endpoints/prompt_studio_projects.py:51 (CRUD + list)
  - Prompts: tldw_Server_API/app/api/v1/endpoints/prompt_studio_prompts.py:46 (CRUD, list, execute, versions)
  - Test cases: tldw_Server_API/app/api/v1/endpoints/prompt_studio_test_cases.py:45 (CRUD, batch)
  - Optimizations: tldw_Server_API/app/api/v1/endpoints/prompt_studio_optimization.py:58 (job submission/queries)
  - Evaluations: tldw_Server_API/app/api/v1/endpoints/prompt_studio_evaluations.py:37 (evaluation runs)
  - Status: tldw_Server_API/app/api/v1/endpoints/prompt_studio_status.py:20 (queue + metrics)
  - WebSocket: tldw_Server_API/app/api/v1/endpoints/prompt_studio_websocket.py:24 (`/api/v1/prompt-studio/ws`)

Related Schemas
- Prompts API: tldw_Server_API/app/api/v1/schemas/prompt_schemas.py:1
- Prompt Studio base/project/prompt/test/optimization:
  - tldw_Server_API/app/api/v1/schemas/prompt_studio_base.py:1
  - tldw_Server_API/app/api/v1/schemas/prompt_studio_project.py:1
  - tldw_Server_API/app/api/v1/schemas/prompt_studio_schemas.py:1
  - tldw_Server_API/app/api/v1/schemas/prompt_studio_test.py:1
  - tldw_Server_API/app/api/v1/schemas/prompt_studio_optimization.py:1

## 2. Technical Details of Features

- Architecture & data flow
  - Prompts API uses `PromptsDatabase` via `get_prompts_db_for_user` and interop helpers (`Prompts_Interop.py`).
  - Prompt Studio uses `PromptStudioDatabase` for projects/prompts/test cases; endpoints enforce access control and rate limits.
  - Real-time updates via `prompt_studio_websocket` router and `EventBroadcaster` with per-connection context.
- Storage & schema
  - Prompts: tables for prompts, keywords, sync_log; soft-delete and version fields where applicable.
  - Prompt Studio DB: extends prompts DB with project, prompt versions, test cases, job queue; FTS support; sync and audit fields.
  - Backends: SQLite and PostgreSQL supported for Prompt Studio (advisory locks/metrics in PG).
- Key classes/modules
  - Prompts interop: tldw_Server_API/app/core/Prompt_Management/Prompts_Interop.py:1 (export/search/keywords utilities, singleton DB init)
  - Prompt Studio DB: tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py:1 (dual-backend, helpers, row adapters)
  - Prompt engineering utilities: tldw_Server_API/app/core/Prompt_Management/Prompt_Engineering.py:1 (meta-prompt generator)
  - Prompt Studio runtime:
    - Event broadcaster: tldw_Server_API/app/core/Prompt_Management/prompt_studio/event_broadcaster.py:2
    - Metrics/monitoring: tldw_Server_API/app/core/Prompt_Management/prompt_studio/monitoring.py:1
    - MCTS optimizer: tldw_Server_API/app/core/Prompt_Management/prompt_studio/mcts_optimizer.py:1
- Security, RBAC, and rate limits
  - Prompts API typically guarded by token (`verify_token`) and per-user DB scoping.
  - Prompt Studio: `get_prompt_studio_user`, `require_project_access`, `require_project_write_access`, and `check_rate_limit` dependencies enforce access and quotas (see endpoint files at references above).
- Exports
  - CSV or Markdown via `db_export_prompts_formatted` (stream-safe for large outputs; base64 file content for HTTP responses).
- Configuration
  - `USER_DB_BASE_DIR` (from `tldw_Server_API.app.core.config`): per-user DB root directory; defaults to `Databases/user_databases/` under the project root. Override via environment variable or `Config_Files/config.txt` as needed.
  - Prompt Studio backend can be selected in tests via `TLDW_PS_BACKEND` (see tests README).
  - Routers are gated by route policy in `main.py` (e.g., `prompt-studio` routes must be enabled).
- Error handling
  - DB-layer exceptions (`InputError`, `ConflictError`, `DatabaseError`) mapped to HTTP 400/409/500 consistently; 404 on missing resources.

## 3. Developer‑Related/Relevant Information for Contributors

- Folder structure
  - `Prompt_Management/Prompts_Interop.py` — Interop helpers and singleton DB wiring.
  - `Prompt_Management/Prompt_Engineering.py` — Meta-prompt generation utilities.
  - `Prompt_Management/prompt_studio/` — Runtime (jobs, metrics, broadcaster, optimizer) and docs.
  - `api/v1/endpoints/prompts.py` — Classic prompts REST API.
  - `api/v1/endpoints/prompt_studio_*.py` — Prompt Studio routers (projects, prompts, tests, optimization, evals, status, ws).
- Patterns & tips
  - Always obtain DB instances via API deps (`get_prompts_db_for_user`, `get_prompt_studio_db`); don’t instantiate DB classes directly in endpoints.
  - Enforce access with `require_project_access`/`require_project_write_access` and rate limit sensitive operations with `check_rate_limit`.
  - Keep pagination (`page`, `per_page`) and soft-delete semantics consistent across list/search endpoints.
  - Prefer streaming/encoded responses for large exports; avoid loading entire files into memory server-side.
- Tests
  - Prompts API integration: tldw_Server_API/tests/Prompt_Management_NEW/integration/test_prompts_api.py:30
  - Prompt Studio E2E: tldw_Server_API/tests/e2e/test_prompt_studio_e2e.py:23 (projects + websocket)
  - Prompt Studio API + PG advisory lock metrics: tldw_Server_API/tests/prompt_studio/integration/*
  - Lint: tldw_Server_API/tests/lint/test_no_dict_usage.py (guards dict usage in endpoints)
- Quick examples (curl)
  - Prompts search: `curl -X POST \
    'http://127.0.0.1:8000/api/v1/prompts/search?search_query=hello' \
    -H 'Authorization: Bearer <token>'`
  - Create Prompt Studio project: `curl -X POST \
    http://127.0.0.1:8000/api/v1/prompt-studio/projects \
    -H 'Content-Type: application/json' -d '{"name":"Demo","status":"active"}'`
- Pitfalls & gotchas
  - Prompt Studio write operations require proper user context and permissions; expect 403/401 if deps aren’t satisfied.
  - In PG mode, lock contention can surface; metrics (e.g., `prompt_studio.pg_advisory.*`) help diagnose.
  - Large exports may produce big payloads; use CSV for compactness and chunked downloading when possible.
