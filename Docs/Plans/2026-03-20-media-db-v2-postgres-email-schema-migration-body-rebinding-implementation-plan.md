# Implementation Plan: Media DB v2 Postgres Email Schema Migration Body Rebinding

Date: 2026-03-20
Branch: `codex/media-db-v2-stage1-caller-first`

## Stage 1: Add Red Regressions
**Goal**: Lock the intended `v22` ownership, compat-shell, and migration-path invariants before implementation.
**Success Criteria**:
- Canonical ownership regression for `v22` fails red
- Legacy compat-shell delegation regression for `v22` fails red
- Dedicated Postgres `v22` migration-path test is added and exercises the intended path
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v22'`
- `test_media_postgres_migrations.py -k 'v22 or email'`
**Status**: Not Started

## Stage 2: Add Package Helper Module
**Goal**: Introduce a package-owned helper for the `v22` migration body without changing runtime ownership yet.
**Success Criteria**:
- New helper module exists and is exported
- Red regressions remain red until rebinding/delegation is completed
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v22'`
**Status**: Not Started

## Stage 3: Rebind Canonical v22 Method
**Goal**: Move canonical runtime ownership for `_postgres_migrate_to_v22` to the package helper.
**Success Criteria**:
- Canonical ownership regression turns green
- Legacy compat-shell delegation regression remains red until shell conversion
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v22'`
**Status**: Not Started

## Stage 4: Convert Legacy v22 to Compat Shell
**Goal**: Preserve the legacy API surface while routing through the package helper via live-module reference.
**Success Criteria**:
- Legacy compat-shell delegation regression turns green
- No direct legacy inline `v22` execution path remains
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v22'`
**Status**: Not Started

## Stage 5: Add Focused Helper Behavior Test
**Goal**: Lock the package helper’s minimal delegate behavior.
**Success Criteria**:
- Helper behavior test passes
- The helper invokes `_ensure_postgres_email_schema(conn)`
**Tests**:
- `test_media_db_schema_bootstrap.py -k 'v22 or email_schema'`
**Status**: Not Started

## Stage 6: Close-Out Verification
**Goal**: Verify the full `v22` tranche with targeted integration, security, ownership, and diff hygiene checks.
**Success Criteria**:
- Focused Postgres verification bundle passes
- Bandit finds no issues in touched production files
- Ownership count drops by `1`
- `git diff --check` is clean
- Worktree is clean
**Tests**:
- `test_media_postgres_support.py`
- `test_media_postgres_migrations.py`
- `test_media_db_v2_regressions.py`
- `test_media_db_schema_bootstrap.py`
- `python -m bandit -r <touched production files>`
- `python Helper_Scripts/checks/media_db_runtime_ownership_count.py`
- `git diff --check`
**Status**: Not Started
