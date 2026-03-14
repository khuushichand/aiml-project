# SQLite Legacy Modules Design

**Date:** 2026-03-13

## Goal

Standardize SQLite runtime behavior across legacy and user-feature database modules by centralizing repeated connection PRAGMA setup and outer write transaction behavior, without broad backend rewrites or migration-path changes.

## Scope

This design covers request-facing/runtime SQLite modules that still duplicate connection setup or use plain `BEGIN` for outer write transactions:

- `tldw_Server_API/app/core/DB_Management/Voice_Registry_DB.py`
- `tldw_Server_API/app/core/DB_Management/TopicMonitoring_DB.py`
- `tldw_Server_API/app/core/DB_Management/Guardian_DB.py`
- `tldw_Server_API/app/core/DB_Management/Prompts_DB.py`
- `tldw_Server_API/app/core/DB_Management/Workflows_DB.py`
- `tldw_Server_API/app/core/DB_Management/Personalization_DB.py`
- `tldw_Server_API/app/core/DB_Management/ResearchSessionsDB.py`
- `tldw_Server_API/app/core/DB_Management/Meetings_DB.py`
- `tldw_Server_API/app/core/DB_Management/Orchestration_DB.py`
- `tldw_Server_API/app/core/DB_Management/Circuit_Breaker_Registry_DB.py`
- `tldw_Server_API/app/core/Scheduler/backends/sqlite_backend.py`
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` (runtime connection bootstrap and outer transaction manager only)

## Non-Goals

- Replacing legacy modules with the shared backend abstraction
- Changing migration, schema rebuild, or backup code paths
- Touching explicit maintenance flows that intentionally disable foreign keys
- Large refactors to unrelated SQL or schema code

## Recommended Approach

Use a small shared helper module rather than isolated per-file fixes or a large backend migration.

### Why this approach

- It removes duplicated SQLite setup logic that has already drifted across modules.
- It keeps the changes mechanical and low-risk for older modules.
- It standardizes policy without forcing architectural rewrites.

## Helper Contract

Add `tldw_Server_API/app/core/DB_Management/sqlite_policy.py` with two focused functions:

### `configure_sqlite_connection(...)`

Apply standard connection PRAGMAs with configurable overrides:

- `use_wal=True`
- `synchronous="NORMAL"`
- `foreign_keys=True`
- `busy_timeout_ms=5000`
- `temp_store="MEMORY"`
- `cache_size=None`
- `enable_on_memory=False`

Behavior:

- Set `journal_mode=WAL` for file-backed DBs when `use_wal=True`
- Skip WAL on in-memory DBs unless `enable_on_memory=True`
- Apply `synchronous`, `foreign_keys`, `busy_timeout`, `temp_store`, and optional `cache_size`
- Avoid any module-name-specific branching

### `begin_immediate_if_needed(conn) -> bool`

Behavior:

- If `conn.in_transaction` is false, execute `BEGIN IMMEDIATE` and return `True`
- If already in a transaction, do nothing and return `False`

This keeps legacy commit/rollback flows intact while standardizing outer write lock acquisition.

## Module Migration Plan

### Direct helper adoption

For modules with local `_connect()` or similar connection factories, replace repeated PRAGMA blocks with `configure_sqlite_connection()`:

- `Voice_Registry_DB.py`
- `TopicMonitoring_DB.py`
- `Guardian_DB.py`
- `Prompts_DB.py`
- `Workflows_DB.py`
- `Personalization_DB.py`
- `ResearchSessionsDB.py`
- `Meetings_DB.py`
- `Orchestration_DB.py`
- `Circuit_Breaker_Registry_DB.py`
- `Scheduler/backends/sqlite_backend.py` for any remaining duplicated transaction setup path

### Transaction behavior updates

Convert outer write transactions from plain `BEGIN` to `BEGIN IMMEDIATE`, preferably through `begin_immediate_if_needed()` where the surrounding code already manages commit/rollback:

- `Voice_Registry_DB.py`
- `TopicMonitoring_DB.py`
- `Guardian_DB.py`
- `Prompts_DB.py`
- `Scheduler/backends/sqlite_backend.py`
- `ChaChaNotes_DB.py`

### ChaChaNotes constraints

Keep this module narrow:

- Move its default runtime connection bootstrap to the helper
- Change its outer transaction manager to `BEGIN IMMEDIATE`
- Leave migration/DDL and explicit `foreign_keys=OFF` flows untouched

## Testing Strategy

### Helper-level tests

Add focused tests for:

- file-backed connections receive the standard PRAGMA set
- in-memory connections skip WAL by default
- optional `cache_size` is applied only when provided
- `begin_immediate_if_needed()` starts only the outer transaction

### Module-level regression tests

Add or extend targeted tests only for the behavior being changed:

- outer write transactions use `BEGIN IMMEDIATE`
- migrated modules use the helper-driven PRAGMA set
- scheduler’s remaining transaction path is immediate
- ChaChaNotes runtime path uses helper/default transaction behavior without altering maintenance exceptions

## Verification

After implementation:

- run targeted pytest for the helper and touched DB modules
- run Bandit on the touched Python files
- avoid completion claims without fresh command output

## Risks And Mitigations

### Risk: helper overreach

Mitigation:

- keep the helper procedural and small
- do not fold migration/backups into it

### Risk: behavior drift in legacy modules

Mitigation:

- change only connection PRAGMAs and outer transaction starts
- preserve local commit/rollback flow and special-case maintenance blocks

### Risk: in-memory test breakage from WAL assumptions

Mitigation:

- WAL defaults off for in-memory connections unless explicitly enabled

