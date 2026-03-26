# Implementation Plan: Media DB v2 Postgres Early Schema Migration Body Rebinding

Date: 2026-03-21
Branch: `codex/media-db-v2-stage1-caller-first`

## Stage 1: Add Red Regressions
**Goal**: Lock the intended ownership and compat-shell invariants for `v5` through `v8`.
**Success Criteria**:
- canonical ownership regressions for `v5` through `v8` fail red
- legacy compat-shell delegation regressions for `v5` through `v8` are present
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v5 or postgres_migrate_to_v6 or postgres_migrate_to_v7 or postgres_migrate_to_v8'`
**Status**: Complete

## Stage 2: Add Package Helper Module
**Goal**: Introduce a package-owned helper module for `v5` through `v8` without changing runtime ownership yet.
**Success Criteria**:
- new helper module exists and is exported
- red ownership regressions remain red until rebinding is completed
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v5 or postgres_migrate_to_v6 or postgres_migrate_to_v7 or postgres_migrate_to_v8'`
**Status**: Complete

## Stage 3: Rebind Canonical Methods
**Goal**: Move canonical runtime ownership for `v5` through `v8` to the package helper.
**Success Criteria**:
- canonical ownership regressions turn green
- legacy compat-shell regressions remain green
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v5 or postgres_migrate_to_v6 or postgres_migrate_to_v7 or postgres_migrate_to_v8'`
**Status**: Complete

## Stage 4: Add Focused Helper Behavior Tests
**Goal**: Lock the helper module’s SQL-emission behavior for `v5` through `v8`.
**Success Criteria**:
- helper-path tests pass for all four entrypoints
**Tests**:
- `test_media_db_schema_bootstrap.py -k 'run_postgres_migrate_to_v5 or run_postgres_migrate_to_v6 or run_postgres_migrate_to_v7 or run_postgres_migrate_to_v8'`
**Status**: Complete

## Stage 5: Close-Out Verification
**Goal**: Verify the full `v5` through `v8` tranche with targeted behavior, security, ownership, and diff hygiene checks.
**Success Criteria**:
- focused Postgres verification bundle passes
- Bandit finds no issues in touched production files
- ownership count drops by `4`
- `git diff --check` is clean
- worktree is clean
**Tests**:
- `test_media_postgres_support.py`
- `test_media_postgres_migrations.py`
- `test_media_db_v2_regressions.py`
- `test_media_db_schema_bootstrap.py`
- `python -m bandit -r <touched production files>`
- `python Helper_Scripts/checks/media_db_runtime_ownership_count.py`
- `git diff --check`
**Status**: Complete
