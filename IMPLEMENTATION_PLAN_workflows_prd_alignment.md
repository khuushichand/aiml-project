## Stage 1: PRD Alignment
**Goal**: Make Product PRD consistent with Published PRD scope (v0.1), including branch/map scope and chunking contract.
**Success Criteria**: Docs no longer claim linear-only v0.1; chunker contract reflects core_chunking only; on_timeout/assignment notes align with current intent.
**Tests**: N/A (doc-only)
**Status**: Complete

## Stage 2: DB Migration for Step Runs
**Goal**: Add `tenant_id` and `assigned_to` to `workflow_step_runs` with schema + migration/backfill updates.
**Success Criteria**: Schema version bumps; columns exist in SQLite and Postgres; step runs written with tenant/assignee.
**Tests**: `tldw_Server_API/tests/Workflows/test_workflows_postgres_migrations.py`
**Status**: Complete

## Stage 3: Human Step Enforcement + Timeout Routing
**Goal**: Require `assigned_to_user_id` for wait steps and route `on_timeout` automatically.
**Success Criteria**: API rejects missing assignment; approvals enforce assignee; timeouts route to configured step or fail run.
**Tests**: `tldw_Server_API/tests/Workflows/test_engine_scheduler.py`, `tldw_Server_API/tests/Workflows/test_engine_step_types.py`
**Status**: Complete

## Stage 4: Validation + Tests
**Goal**: Implement strict RAG config validation and chunking contract checks; update/add tests.
**Success Criteria**: Unknown RAG fields rejected; bounds enforced; chunking name/version validated; tests updated.
**Tests**: `tldw_Server_API/tests/Workflows/test_workflows_api.py`, `tldw_Server_API/tests/Workflows/test_stage3_chunkers_rag.py`
**Status**: Complete
