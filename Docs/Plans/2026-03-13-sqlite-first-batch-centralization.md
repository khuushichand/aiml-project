# SQLite First-Batch Centralization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Centralize the remaining first-batch SQLite runtime PRAGMA setup behind the shared helper while keeping Prompt Studio's WAL policy local.

**Architecture:** Extend `sqlite_policy.py` with an async PRAGMA helper, migrate the remaining duplicated runtime setup in AuthNZ, Media DB, and the shared SQLite backend, and move Prompt Studio's WAL decision to a local hook in `Prompts_DB` so reopened connections follow the same policy. Keep `BEGIN IMMEDIATE` behavior unchanged where it is already correct.

**Tech Stack:** Python, sqlite3, aiosqlite, pytest

---

## Stage 1: Finalize Design And Touch Points
**Goal**: Capture the narrower first-batch centralization scope and the Prompt Studio WAL-hook approach.
**Success Criteria**: Design doc lists the modules, helper changes, and verification plan.
**Tests**: None.
**Status**: Complete

## Stage 2: Red Tests For Async Helper And First-Batch Integrations
**Goal**: Add failing tests that prove the first-batch modules still rely on local PRAGMA setup.
**Success Criteria**: New assertions fail before production code changes.
**Tests**:
- `python -m pytest tldw_Server_API/tests/DB_Management/test_sqlite_policy.py tldw_Server_API/tests/AuthNZ/unit/test_sqlite_transaction_modes.py -v`
- `python -m pytest tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_database_backends.py tldw_Server_API/tests/prompt_studio/test_database.py -k "pragma or wal_mode or sqlite_backend or reopened_connections_keep_ci_delete_mode" -v`
- `python -m pytest tldw_Server_API/tests/prompt_studio/test_database.py::TestDatabaseInitialization::test_reopened_connections_keep_ci_delete_mode -v`
**Status**: Complete

**Result**: Red-green cycle completed. Failures initially showed the missing async helper, AuthNZ runtime PRAGMAs still being hand-rolled, Media/shared-backend code still bypassing the helper, and Prompt Studio reopened connections reverting to WAL under CI instead of preserving DELETE mode.

## Stage 3: Implement Helper And Migrate First-Batch Modules
**Goal**: Add the async helper, adopt it in the remaining modules, and move Prompt Studio WAL selection to a local hook.
**Success Criteria**: First-batch modules no longer duplicate the shared runtime PRAGMA policy, and Prompt Studio reopened connections honor its WAL mode rules.
**Tests**:
- Re-run the Stage 2 commands after each batch.
**Status**: Complete

**Result**: Added `configure_sqlite_connection_async()` to `sqlite_policy.py`, migrated AuthNZ SQLite runtime setup to it, delegated Media DB and shared backend PRAGMA setup to the helper, and moved Prompt Studio's WAL decision to a protected `Prompts_DB` journal-mode hook so reopened connections follow the same local policy.

## Stage 4: Broader Regression Verification
**Goal**: Prove the helper centralization does not break current module behavior.
**Success Criteria**: Existing targeted AuthNZ, Media DB, Prompt Studio, and backend tests pass.
**Tests**:
- `python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_sqlite_transaction_modes.py tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py tldw_Server_API/tests/DB_Management/test_database_backends.py tldw_Server_API/tests/prompt_studio/test_database.py -v`
**Status**: Complete

**Result**: Passed. `71 passed, 7 skipped, 7 warnings in 34.23s`.

## Stage 5: Security Verification And Status Update
**Goal**: Run Bandit on the touched scope and update the plan statuses with actual results.
**Success Criteria**: Bandit output is reviewed and any new findings in changed code are fixed or accurately reported.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/AuthNZ/database.py tldw_Server_API/app/core/DB_Management/Media_DB_v2.py tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py tldw_Server_API/app/core/DB_Management/Prompts_DB.py tldw_Server_API/app/core/DB_Management/backends/sqlite_backend.py tldw_Server_API/app/core/DB_Management/sqlite_policy.py -f json -o /tmp/bandit_sqlite_first_batch_centralization.json`
**Status**: Complete

**Result**: Bandit reported no new findings in the helper or SQLite PRAGMA centralization changes. Remaining findings are pre-existing low-severity `B311` reports in older `PromptStudioDatabase.py` randomness code outside this SQLite work.
