# Implementation Plan: Media DB v2 Postgres Structure/Visual Index Migration Body Rebinding

Date: 2026-03-20
Branch: `codex/media-db-v2-stage1-caller-first`

## Stage 1: Add Red Regressions
**Goal**: Lock the intended `v21` ownership, compat-shell, and migration-path invariants before implementation.
**Success Criteria**:
- Canonical ownership regression for `v21` fails red
- Legacy compat-shell delegation regression for `v21` fails red
- Dedicated Postgres `v21` migration-path test fails red
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v21'`
- `test_media_postgres_migrations.py -k 'v21 or structure or visual'`
**Status**: Not Started

## Stage 2: Add Package Helper Module
**Goal**: Introduce a package-owned helper for the `v21` migration body without changing runtime ownership yet.
**Success Criteria**:
- New helper module exists and is exported
- Red regressions remain red until rebinding/delegation is completed
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v21'`
**Status**: Not Started

## Stage 3: Rebind Canonical v21 Method
**Goal**: Move canonical runtime ownership for `_postgres_migrate_to_v21` to the package helper.
**Success Criteria**:
- Canonical ownership regression turns green
- Legacy compat-shell delegation regression remains red until shell conversion
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v21'`
**Status**: Not Started

## Stage 4: Convert Legacy v21 to Compat Shell
**Goal**: Preserve the legacy API surface while routing through the package helper via live-module reference.
**Success Criteria**:
- Legacy compat-shell delegation regression turns green
- No direct legacy inline `v21` execution path remains
**Tests**:
- `test_media_db_v2_regressions.py -k 'postgres_migrate_to_v21'`
**Status**: Not Started

## Stage 5: Add Focused Helper Behavior Test
**Goal**: Lock the package helper’s table-detection and index-creation behavior.
**Success Criteria**:
- Helper behavior test passes
- The helper emits the expected structure and visual index SQL
**Tests**:
- `test_media_db_schema_bootstrap.py -k 'v21 or structure_visual'`
**Status**: Not Started

## Stage 6: Close-Out Verification
**Goal**: Verify the full `v21` tranche with targeted integration, security, ownership, and diff hygiene checks.
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
