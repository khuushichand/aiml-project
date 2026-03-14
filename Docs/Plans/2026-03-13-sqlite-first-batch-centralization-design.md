# SQLite First-Batch Centralization Design

**Date:** 2026-03-13

## Goal

Finish centralizing SQLite runtime setup for the earlier server-facing modules that were updated for transaction mode already but still hand-roll connection PRAGMAs.

## Scope

This pass covers:

- `tldw_Server_API/app/core/AuthNZ/database.py`
- `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
- `tldw_Server_API/app/core/DB_Management/PromptStudioDatabase.py`
- `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- `tldw_Server_API/app/core/DB_Management/backends/sqlite_backend.py`
- `tldw_Server_API/app/core/DB_Management/sqlite_policy.py`

## Non-Goals

- Reworking non-SQLite backend logic
- Changing schema or migration semantics
- Broad refactors outside runtime connection bootstrap
- Moving Prompt Studio's CI/test WAL decision into the shared helper

## Recommended Approach

Use the shared SQLite policy helper for the remaining duplicated PRAGMA setup, and extend it with an async variant for `aiosqlite` callers.

### Why this approach

- It removes the last major pockets of duplicated SQLite runtime policy.
- It keeps Prompt Studio's environment-based WAL decision local while still standardizing the rest of the connection policy.
- It avoids coupling async and sync callers to ad hoc local PRAGMA blocks.

## Design

### Shared helper updates

Add an async companion to the existing sync helper in `sqlite_policy.py`:

- `configure_sqlite_connection_async(...)`

Behavior should match the sync helper for:

- `journal_mode`
- `synchronous`
- `foreign_keys`
- `busy_timeout`
- `temp_store`
- optional `cache_size`

The helper should continue to skip WAL for in-memory connections by default.

### AuthNZ

Replace the SQLite PRAGMA blocks in:

- `_create_sqlite_schema()`
- `transaction()`
- `acquire()`

with the async helper. Keep `BEGIN IMMEDIATE` local.

### Media DB

Replace `_apply_sqlite_connection_pragmas()` with a thin call into the shared helper using backend-config-driven `wal_mode` and `foreign_keys` values.

### Shared SQLite backend

Replace duplicated connection PRAGMA code in:

- `SQLiteConnectionPool._create_connection()`
- `SQLiteBackend.connect()`

with the shared helper, preserving current config behavior and existing timeout/cache values.

### Prompt Studio and Prompts DB

Keep Prompt Studio's WAL decision local by moving the WAL choice behind a small protected hook in `Prompts_DB`, for example:

- `PromptsDatabase._should_enable_sqlite_wal() -> bool`

Default behavior remains `True` for Prompts DB. `PromptStudioDatabase` overrides the hook to call `_should_enable_prompt_studio_sqlite_wal()`. The shared helper still applies the remaining PRAGMAs with `use_wal=False` so the journal-mode decision stays outside the helper.

This removes the fragile post-init override in `PromptStudioDatabase` and makes reopened connections respect the same Prompt Studio WAL policy.

## Testing Strategy

Add focused red/green assertions for:

- async helper PRAGMA behavior
- AuthNZ SQLite `transaction()` and `acquire()` PRAGMA setup
- Media DB runtime PRAGMA setup through the helper
- shared backend connection PRAGMA setup
- Prompt Studio runtime connections honoring local WAL policy while still using the standard PRAGMA set

Reuse existing regression files where possible instead of creating a new large suite.

## Verification

After implementation:

- run the focused red/green tests first
- run targeted existing suites for AuthNZ, Media DB, Prompt Studio, and backend abstractions
- run Bandit on the touched Python files

