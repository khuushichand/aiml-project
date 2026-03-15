# SQLite Infrastructure Runtime Centralization Design

**Date:** 2026-03-13

## Goal

Finish centralizing SQLite runtime connection policy for the remaining infrastructure and service modules that still hand-roll PRAGMA setup.

## Scope

This pass covers runtime connection bootstrap in:

- `tldw_Server_API/app/core/Audit/unified_audit_service.py`
- `tldw_Server_API/app/core/Jobs/manager.py`
- `tldw_Server_API/app/core/Sandbox/store.py`
- `tldw_Server_API/app/core/DB_Management/Kanban_DB.py`
- `tldw_Server_API/app/core/DB_Management/ACP_Sessions_DB.py`
- `tldw_Server_API/app/core/DB_Management/ACP_Audit_DB.py`
- `tldw_Server_API/app/core/DB_Management/ChatWorkflows_DB.py`
- `tldw_Server_API/app/core/Evaluations/connection_pool.py`
- `tldw_Server_API/app/core/DB_Management/sqlite_policy.py`

## Non-Goals

- Reworking PostgreSQL code paths
- Changing migration or schema-rebuild semantics
- Replacing module-specific tuning that is intentionally different
- Touching DDL-only transaction blocks such as Topic Monitoring schema migrations

## Recommended Approach

Use the shared SQLite policy helper for live connection bootstrap only, then preserve module-specific extras with small local statements after the helper call.

### Why this approach

- It removes the last broad pockets of duplicated runtime PRAGMA policy.
- It avoids folding migration behavior into the runtime helper.
- It keeps intentional differences local and obvious, instead of expanding the helper into a feature-specific abstraction.

## Design

### Shared helper contract

Reuse the existing helper functions:

- `configure_sqlite_connection(...)`
- `configure_sqlite_connection_async(...)`
- `begin_immediate_if_needed(...)`

Do not add module-name branching to the helper. Callers should pass their local policy values explicitly.

### Audit service

Replace the duplicated async PRAGMA blocks in:

- `_init_database()`
- `_ensure_db_pool()`
- the test-mode fallback flush path

with `configure_sqlite_connection_async(...)`.

Keep the following local:

- `row_factory = aiosqlite.Row`
- `PRAGMA auto_vacuum=INCREMENTAL`
- `PRAGMA query_only=ON` on read-only handles

The read-only helper path should still apply the standard runtime PRAGMAs before setting `query_only`.

### Jobs manager

Replace the SQLite runtime PRAGMA block in `_connect()` with the shared sync helper. Preserve the current timeout and keep PostgreSQL paths untouched.

### Sandbox store

Replace the SQLite runtime PRAGMA block in `_conn()` with the shared sync helper. Keep existing `BEGIN IMMEDIATE` write paths unchanged. Do not touch the PostgreSQL control-plane store implementation.

### Kanban DB

Replace `_configure_connection()` internals with the shared sync helper using:

- `busy_timeout_ms=30000`
- `cache_size=-64000`
- `use_wal=False` for in-memory connections

Row factory setup remains local.

### ACP and Chat Workflows

Replace connection bootstrap PRAGMAs in:

- `ACPSessionsDB._get_conn()`
- `ACPAuditDB._get_conn()`
- `ChatWorkflowsDatabase.__init__()`

with the shared sync helper. Keep existing `BEGIN IMMEDIATE` transaction handling local.

### Evaluations connection pool

Replace `PooledConnection._configure_connection()` with the shared sync helper, then keep:

- `PRAGMA mmap_size=268435456`

as a local post-helper statement.

## Testing Strategy

Add red/green coverage for:

- Audit async runtime connections using the standard PRAGMA set
- Jobs, Sandbox, Kanban, ACP, Chat Workflows, and Evaluations runtime connections using the expected helper-driven PRAGMA values
- Existing transaction-mode assertions continuing to use `BEGIN IMMEDIATE`
- Module-specific overrides remaining intact, especially Kanban timeout/cache and Evaluations `mmap_size`

Prefer extending existing regression files before creating new ones. Add new focused tests only where async/runtime behavior does not fit cleanly into the existing SQLite policy integration suite.

## Verification

After implementation:

- run the focused red/green tests first
- run a targeted pytest sweep covering Audit, Jobs, Sandbox, Kanban, ACP, Chat Workflows, Evaluations, and SQLite policy integrations
- run Bandit on the touched Python files
