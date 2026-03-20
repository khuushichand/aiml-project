# SQLite Maintenance Bootstrap Centralization Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Centralize duplicated SQLite bootstrap PRAGMA setup in Jobs migrations, Audit shared migration, and AuthNZ startup integrity without changing their existing operational semantics.

**Architecture:** Reuse `sqlite_policy.py` at the three approved maintenance/bootstrap call sites only. Keep Jobs and Audit setup best-effort, keep AuthNZ startup integrity strict, and preserve each module's narrow PRAGMA footprint through explicit helper kwargs rather than new wrapper APIs.

**Tech Stack:** Python, sqlite3, aiosqlite, pytest

---

## Stage 1: Finalize Design And Approved Scope
**Goal**: Capture the exact maintenance/bootstrap modules to change and explicitly exclude embedded legacy migration SQL.
**Success Criteria**: Design doc records scope, per-module helper kwargs, error-handling policy, and verification plan.
**Tests**: None.
**Status**: Complete

## Stage 2: Red Tests For Maintenance Bootstrap Helper Adoption
**Goal**: Add failing tests that prove the approved maintenance/bootstrap paths still hand-roll SQLite PRAGMAs instead of using the shared helper contract.
**Success Criteria**: New assertions fail before production code changes.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Jobs/test_jobs_migrations_sqlite.py -v`
- `python -m pytest tldw_Server_API/tests/Audit/test_audit_shared_migration.py -v`
- `python -m pytest tldw_Server_API/tests/AuthNZ/unit/test_startup_integrity.py -v`
**Status**: Complete
**Results**:
- Confirmed intended red failures before production changes in Jobs migrations, Audit shared migration, and AuthNZ startup integrity helper adoption tests.

## Stage 3: Implement Helper Adoption In Approved Maintenance Paths
**Goal**: Replace the duplicated PRAGMA blocks in the three approved modules with shared helper calls while preserving current behavior.
**Success Criteria**: Jobs migrations, Audit shared migration, and AuthNZ startup integrity use `sqlite_policy.py` with the approved narrow kwargs and unchanged exception policy.
**Tests**:
- Re-run the Stage 2 commands after each module update.
**Status**: Complete
**Results**:
- Jobs migrations now uses `configure_sqlite_connection(...)` in best-effort mode with its existing narrow PRAGMA footprint.
- Audit shared migration now uses `configure_sqlite_connection_async(...)` in best-effort mode for the destination shared DB.
- AuthNZ startup integrity now uses `configure_sqlite_connection(...)` in readonly-check mode with WAL disabled and only the intended minimal settings.

## Stage 4: Broader Regression Verification
**Goal**: Prove the maintenance/bootstrap centralization does not change expected behavior in the touched modules.
**Success Criteria**: The three targeted suites pass together after the helper adoption changes.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Jobs/test_jobs_migrations_sqlite.py tldw_Server_API/tests/Audit/test_audit_shared_migration.py tldw_Server_API/tests/AuthNZ/unit/test_startup_integrity.py -v`
**Status**: Complete
**Results**:
- `20 passed, 17 warnings in 6.19s`

## Stage 5: Security Verification And Status Update
**Goal**: Run Bandit on the touched scope and update this plan with actual results.
**Success Criteria**: New findings in changed code are fixed or accurately reported before completion.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/Jobs/migrations.py tldw_Server_API/app/core/Audit/audit_shared_migration.py tldw_Server_API/app/core/AuthNZ/startup_integrity.py tldw_Server_API/app/core/DB_Management/sqlite_policy.py -f json -o /tmp/bandit_sqlite_maintenance_bootstrap_centralization.json`
**Status**: Complete
**Results**:
- Bandit completed successfully with `0` findings in the touched maintenance/bootstrap SQLite modules.
