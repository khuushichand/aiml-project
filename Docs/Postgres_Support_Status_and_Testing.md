# PostgreSQL Support — Current State and Testing Guide

This document summarizes the current state of PostgreSQL support across the server and provides clear, reproducible steps to validate behavior (locally and in CI-like conditions). It also captures key environment flags (CORS, setup guard) and common troubleshooting notes.

## Current State (as of this change)

- Content Databases (Media + ChaChaNotes)
  - Backend abstraction in place; app can run on SQLite or PostgreSQL via shared backend.
  - Media: schema bootstrap and migrations validated; RAG parity paths verified by tests. FTS is handled via backend helpers (Postgres uses tsvector + triggers). Migration CLI covers media tables and reseeds sequences.
  - ChaChaNotes: backend-aware bootstrap and CRUD/search implemented; PostgreSQL FTS created via backend translator; dual‑backend coverage exists. Remaining edge maintenance utilities are guarded or refactored.

- Prompt Studio
  - PostgreSQL-backed implementation for projects, prompts (versioned), signatures, test cases (CRUD/search/stats), test runs, evaluations, and optimization flows.
  - Dual‑backend API integration tests pass across project/prompt/test‑case/evaluation flows.
  - Sync logging to `sync_log` is optional; missing table no longer causes failures on Postgres.

- Workflows
  - Backend-aware adapter with PostgreSQL schema bootstrap and CRUD for definitions, runs, steps, events, artifacts.
  - Migration CLI can copy workflows from SQLite to PostgreSQL (with type-safe inserts and sequence sync). Dual‑backend smoke tests pass.

- Migrations and Tooling
  - `migration_tools.py` can migrate Content and Workflows SQLite DBs to Postgres, performing boolean coercions and sequence reseeding. Integration tests validate row counts.

- Configuration
  - Content backend selection via `TLDW_CONTENT_DB_BACKEND` (`sqlite` or `postgres`) and `TLDW_CONTENT_PG_*`/`POSTGRES_TEST_*` env vars. See “Backend Selection” below.

- Security & CORS
  - Setup guard defaults to allowing only local, non‑proxied mutating setup requests; set `TLDW_SETUP_ALLOW_REMOTE=1` to temporarily permit remote setup changes.
  - CORS can be disabled wholesale via `DISABLE_CORS=1` (or `[Server] disable_cors=true` in `config.txt`).

## Prerequisites

- Docker (for local Postgres)
- Python 3.10+ environment with project dependencies
- `psycopg2-binary==2.9.9` (installed when running Postgres tests)

## Start a Local Postgres for Tests

1) Launch the container

```bash
docker compose -f tldw_Server_API/Dockerfiles/docker-compose.postgres.yml up -d
docker compose -f tldw_Server_API/Dockerfiles/docker-compose.postgres.yml ps
# Ensure STATUS shows healthy
```

2) Export Postgres test environment variables (zsh/bash)

```bash
export POSTGRES_TEST_HOST=127.0.0.1
export POSTGRES_TEST_PORT=5432
export POSTGRES_TEST_DB=tldw_users
export POSTGRES_TEST_USER=tldw_user
export POSTGRES_TEST_PASSWORD=TestPassword123!
```

3) Install psycopg driver (v3)

```bash
python3 -m pip install "psycopg[binary]~=3.2"
```

## Run the Dual‑Backend Test Matrix

The following suites validate Postgres + SQLite parity for Prompt Studio, RAG, media migrations, migration CLI, and Workflows.

```bash
pytest -q \
  tldw_Server_API/tests/prompt_studio/integration/test_dual_backend_prompt_studio.py \
  tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py \
  tldw_Server_API/tests/prompt_studio/integration/test_import_csv_and_async_eval.py \
  tldw_Server_API/tests/prompt_studio/integration/test_optimizations_dual_backend_heavy.py \
  tldw_Server_API/tests/RAG/test_dual_backend_rag_flow.py \
  tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py \
  tldw_Server_API/tests/DB_Management/test_migration_cli_integration.py \
  tldw_Server_API/tests/Workflows/test_dual_backend_workflows.py
```

Expected outcome (current snapshot): 22 passed, 2 skipped.

Notes:
- Prompt Studio dual-backend suites parameterize the backend; providing the Postgres env vars turns on the Postgres variant.
- Heavy optimization suite (slow): now marked `@pytest.mark.slow` and runs against a single backend per run. Select with:
  - `TLDW_PS_BACKEND=sqlite|postgres` (default `sqlite`)
  - `pytest -m slow tldw_Server_API/tests/prompt_studio/integration/test_optimizations_dual_backend_heavy.py`
- Heavy optimization env tuning:
  - `TLDW_PS_STRESS=1` enables larger datasets/iterations.
  - `TLDW_PS_TC_COUNT` (default 250; stress 1000) controls test case volume.
  - `TLDW_PS_ITERATIONS` (default 5; stress 10) controls iteration count.
  - `TLDW_PS_OPT_COUNT` (default 3; stress 8) controls concurrent optimizations.
- CI/PG control:
  - `TLDW_TEST_POSTGRES_REQUIRED=1` makes tests fail fast if Postgres is unreachable (instead of skip).
- SQLite mode control (Prompt Studio tests):
  - `TLDW_PS_SQLITE_WAL=1` opts into WAL mode for per-test SQLite DBs to mimic prod; default is `DELETE` to reduce file churn in CI.
- Faster, prod-close test startup:
  - The API app respects `TEST_MODE=true` and/or `DISABLE_HEAVY_STARTUP=1` to skip unrelated heavy subsystems (MCP, TTS, chat workers, background loops) during tests. Prompt Studio behavior remains unchanged.
- Job queue leasing:
  - `TLDW_PS_JOB_LEASE_SECONDS` controls the lease window for processing jobs (default `60`). Jobs with expired leases are reclaimed on next acquire.
  - `TLDW_PS_HEARTBEAT_SECONDS` optionally sets the heartbeat interval for renewing leases (default is lease/2 capped at 30s).
- Workflows and migration CLI tests require the Postgres container to be running and reachable via env vars.

## Run the Migration CLI Against Staging Databases

The CLI migrates SQLite content and workflows DBs into PostgreSQL and compares row counts. You can run these integration tests directly:

```bash
pytest -q tldw_Server_API/tests/DB_Management/test_migration_cli_integration.py
```

Manual usage example:

```bash
python -m tldw_Server_API.app.core.DB_Management.migration_tools \
  --content-sqlite Databases/Media_DB_v2.db \
  --workflows-sqlite Databases/workflows.db \
  --pg-host "$POSTGRES_TEST_HOST" \
  --pg-port "$POSTGRES_TEST_PORT" \
  --pg-database "$POSTGRES_TEST_DB" \
  --pg-user "$POSTGRES_TEST_USER" \
  --pg-password "$POSTGRES_TEST_PASSWORD"
```

The migrator truncates target tables, inserts in batches, coerces booleans for Postgres, and reseeds sequences.

## Optional: Workflow Stress Tests

There is an opt‑in stress suite for workflows. Enable with an env gate to avoid long runs by default:

```bash
export TLDW_WORKFLOW_STRESS=1
pytest -q tldw_Server_API/tests/Workflows/test_workflow_stress.py
```

Ensure your Postgres is sized appropriately (consider increasing pool size, CPU/memory).

## Backend Selection in the App

To run the application on PostgreSQL for content databases (Media/ChaCha/Prompt Studio/Workflows):

- Set the backend selection via env or config:
  - `TLDW_CONTENT_DB_BACKEND=postgres`
  - And provide Postgres credentials (env or `config.txt`):
    - `TLDW_CONTENT_PG_HOST`, `TLDW_CONTENT_PG_PORT`, `TLDW_CONTENT_PG_DATABASE`, `TLDW_CONTENT_PG_USER`, `TLDW_CONTENT_PG_PASSWORD`
    - OR use `POSTGRES_TEST_*` while developing locally (the backend loader understands both conventions)
- Start the server:
  - `python -m uvicorn tldw_Server_API.app.main:app --reload`

The app also honors `config.txt` under `[Database]` with keys like `type=postgresql`, `pg_host`, `pg_port`, etc.

## CORS and Setup Guards

- Disable CORS entirely (for same‑origin deployments):
  - `DISABLE_CORS=1` (env) or `[Server] disable_cors=true` in `Config_Files/config.txt`.
- Setup access guard:
  - By default, mutating setup actions require local, non‑proxied requests.
  - Temporarily permit remote setup changes by exporting `TLDW_SETUP_ALLOW_REMOTE=1`.

## macOS: Setting Environment Variables

- Temporary (current shell):
  - `export NAME=value`
- Persistent for zsh:
  - `echo 'export NAME=value' >> ~/.zshrc && source ~/.zshrc`

Common examples:

```bash
export TLDW_CONTENT_DB_BACKEND=postgres
export TLDW_CONTENT_PG_HOST=127.0.0.1
export TLDW_CONTENT_PG_PORT=5432
export TLDW_CONTENT_PG_DATABASE=tldw_users
export TLDW_CONTENT_PG_USER=tldw_user
export TLDW_CONTENT_PG_PASSWORD=TestPassword123!

export DISABLE_CORS=1                        # optional
export TLDW_SETUP_ALLOW_REMOTE=1             # optional (be cautious)

# Prompt Studio test controls
export TLDW_TEST_POSTGRES_REQUIRED=1         # fail fast if PG unreachable
export TLDW_PS_SQLITE_WAL=1                  # opt-in: use WAL for per-test SQLite
export DISABLE_HEAVY_STARTUP=1               # skip MCP/TTS/chat workers in tests
export TLDW_PS_BACKEND=sqlite                # heavy suite backend: sqlite|postgres
```

## Troubleshooting

- FATAL: password authentication failed / no password supplied
  - Ensure Postgres env vars are exported in the shell running pytest and/or the app.

- psycopg parameter errors
  - Ensure parameters are passed as sequences/tuples (not dicts) when using %s placeholders.

- relation "sync_log" does not exist (Prompt Studio)
  - Sync logging is optional; errors are swallowed. Create the `sync_log` table if you need local sync capture; otherwise you can ignore the debug messages.

- Database locked (SQLite tests)
  - Legacy SQLite concurrency tests can be flaky; our code includes backoff/retries for common paths. Prefer Postgres for heavier concurrency scenarios.

## Snapshot of Key Test Entry Points

- Prompt Studio dual‑backend flows:
  - `tldw_Server_API/tests/prompt_studio/integration/test_dual_backend_prompt_studio.py`
  - `tldw_Server_API/tests/prompt_studio/integration/test_projects_prompts_flows.py`
  - `tldw_Server_API/tests/prompt_studio/integration/test_import_csv_and_async_eval.py`

- RAG retrievers parity:
  - `tldw_Server_API/tests/RAG/test_dual_backend_rag_flow.py`

- Migrations:
  - `tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py`
  - `tldw_Server_API/tests/DB_Management/test_migration_cli_integration.py`

- Workflows (dual backend):
  - `tldw_Server_API/tests/Workflows/test_dual_backend_workflows.py`
  - Optional stress: `tldw_Server_API/tests/Workflows/test_workflow_stress.py` (with `TLDW_WORKFLOW_STRESS=1`)

## Suggested Next Steps

- Expand dual‑backend coverage to long‑running Prompt Studio optimization flows and larger data sets.
- Enable a Postgres service in CI for full repository tests (beyond the selected matrix).
- Continue performance tuning and observability for production deployments (pool sizing, slow query logging, metrics).
