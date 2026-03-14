# SQLite Maintenance Bootstrap Centralization Design

**Date:** 2026-03-13

## Goal

Centralize the remaining duplicated SQLite maintenance and bootstrap PRAGMA setup in the approved non-runtime paths while preserving their existing semantics.

## Scope

This pass covers only:

- `tldw_Server_API/app/core/Jobs/migrations.py`
- `tldw_Server_API/app/core/Audit/audit_shared_migration.py`
- `tldw_Server_API/app/core/AuthNZ/startup_integrity.py`
- `tldw_Server_API/app/core/DB_Management/sqlite_policy.py`

## Non-Goals

- Changing live runtime connection policy
- Touching embedded migration SQL bodies such as raw `BEGIN` statements in legacy migration files
- Refactoring PostgreSQL migration/bootstrap paths
- Broadening helper policy beyond what these three call sites already do

## Recommended Approach

Use the existing shared SQLite helper functions at the call sites with narrow per-module overrides, rather than adding new maintenance-specific helper wrappers.

### Why this approach

- It removes duplicated PRAGMA setup without expanding helper API surface prematurely.
- It preserves each module's current exception handling and operational intent.
- It avoids pulling legacy migration SQL into the same risk envelope.

## Design

### Shared helper usage

Reuse the existing helper functions:

- `configure_sqlite_connection(...)`
- `configure_sqlite_connection_async(...)`

This pass does not require new helper entry points. Callers will explicitly pass the narrow settings they need.

### Jobs migrations

Replace the local SQLite tuning block in `ensure_jobs_tables(...)` with `configure_sqlite_connection(...)` using:

- `use_wal=True`
- `synchronous="NORMAL"`
- `busy_timeout_ms=5000`
- `foreign_keys=False`
- `temp_store=None`

This preserves the current behavior: WAL, `NORMAL`, and timeout are applied on a best-effort basis, while no new connection policy is introduced for foreign keys or temp storage.

### Audit shared migration

Replace the repeated async PRAGMA block for the destination shared DB with `configure_sqlite_connection_async(...)` using:

- `use_wal=True`
- `synchronous="NORMAL"`
- `busy_timeout_ms=5000`
- `foreign_keys=True`
- `temp_store="MEMORY"`

This matches the current migration target setup and keeps the existing best-effort exception guard.

### AuthNZ startup integrity

Replace the direct `PRAGMA busy_timeout` call in `_run_sqlite_pragma_check(...)` with `configure_sqlite_connection(...)` in readonly-check mode using:

- `use_wal=False`
- `synchronous=None`
- `busy_timeout_ms=<derived timeout>`
- `foreign_keys=False`
- `temp_store=None`

The intent is to keep this preflight check minimal and readonly. It should not enable WAL or other runtime-oriented PRAGMAs on the read-only URI connection.

## Error Handling

- `Jobs/migrations.py` stays best-effort for SQLite tuning. The helper call remains inside the existing suppression block so schema bootstrap continues even if a PRAGMA fails.
- `audit_shared_migration.py` stays best-effort for destination DB tuning. The helper call remains inside the existing `_AUDIT_DB_EXCEPTIONS` guard.
- `startup_integrity.py` stays strict. If readonly connection setup fails, that failure should continue flowing through the integrity-check error path rather than being suppressed.

## Testing Strategy

Extend existing suites:

- `tldw_Server_API/tests/Jobs/test_jobs_migrations_sqlite.py`
- `tldw_Server_API/tests/Audit/test_audit_shared_migration.py`
- `tldw_Server_API/tests/AuthNZ/unit/test_startup_integrity.py`

Add focused regression coverage for:

- Jobs migration helper adoption with the narrow kwargs
- Audit shared migration helper adoption with the async kwargs
- AuthNZ startup integrity helper adoption in readonly-check mode

Keep the existing functional assertions in place so helper adoption does not replace behavior verification.

## Verification

After implementation:

- run the focused red/green tests for the three touched suites
- run a targeted pytest sweep covering those suites together
- run Bandit on the touched Python files
