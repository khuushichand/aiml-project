# Media DB V2 Constructor Resolution Rebinding Design

**Status:** Proposed, review-corrected, and ready for planning on 2026-03-20.

**Goal:** Rebind the backend-resolution portion of `MediaDatabase` construction without bundling schema/bootstrap ownership, so the canonical class stops resolving constructor backend selection through `Media_DB_v2.py` while preserving current init behavior.

## Why This Tranche Exists

The low-risk infrastructure work is no longer in the simple helper phase.

After the execution-helper tranche, the normalized ownership count is `226`, but
the remaining legacy-owned surface is not one cohesive "infra" block. It splits
into:

- constructor/backend-resolution behavior
- schema/bootstrap coordinators
- FTS/bootstrap helpers
- domain-heavy PostgreSQL migration helpers
- remaining user/domain methods

The first of those is still attractive because it is:

- a bounded behavior cluster
- high leverage for future init/bootstrap extraction
- still independent from most domain write/query logic

But it is only safe if it stays narrowly focused on backend resolution and the
constructor branches that directly depend on it.

## Review Corrections Incorporated

### 1. Do not bundle `__init__` and schema/bootstrap as one infra move

[`__init__`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py) immediately:

- validates and resolves the DB path
- calls `_resolve_backend`
- sets backend type/default scope state
- creates the in-memory persistent SQLite connection
- calls `_initialize_schema`

That means "constructor/bootstrap" is not one safe slice. The backend-selection
branch and the schema-initialization branch must be split.

This tranche only touches:

- `_resolve_backend`
- the minimal `__init__` wiring needed to keep it coherent
- constructor-path regressions that prove behavior is unchanged

It does **not** move `_initialize_schema`, `_initialize_schema_sqlite`,
`_initialize_schema_postgres`, or the schema-application helpers.

### 2. Treat `_resolve_backend` as the center of the tranche

[`_resolve_backend`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
contains several behavior-sensitive branches:

- explicit backend parameter wins
- env-forced Postgres mode
- config-driven Postgres mode
- pytest/test-mode fallback back to SQLite for explicit file paths
- SQLite fallback for explicit `db_path`
- final resolver fallback via configured content backend

Those branches are the real ownership target here. The constructor should move
only far enough to delegate backend selection to a package-native runtime
module.

### 3. Keep schema and migration coordinators out of scope

The constructor immediately calls `_initialize_schema`, but that method fans
into:

- `_initialize_schema_sqlite`
- `_initialize_schema_postgres`
- `_apply_schema_v1_sqlite`
- `_ensure_fts_structures`
- `_ensure_sqlite_email_schema`
- PostgreSQL migration dispatch

Those are already mixed with claims, data tables, email, visibility, TTS,
collections, FTS, and RLS setup.

That is not a low-risk infra tranche. It is several later tranches.

### 4. Keep Postgres migration ownership domain-split, not infra-bundled

[`_get_postgres_migrations`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
looks infra-oriented, but it dispatches into domain-heavy migration methods for:

- claims
- collections
- data tables
- FTS
- RLS
- email-native schema

This tranche does not move migration ownership.

### 5. Preserve runtime validation invariants

The runtime factory in
[factory.py](./../../tldw_Server_API/app/core/DB_Management/media_db/runtime/factory.py)
still depends on:

- `_CURRENT_SCHEMA_VERSION`
- `create_media_database(...)`
- `_postgres_policy_exists`

So constructor extraction must not accidentally widen into schema/policy
validation or change the canonical class identity and contract.

## In Scope

- Add a package-native runtime module for backend resolution, for example:
  `tldw_Server_API/app/core/DB_Management/media_db/runtime/backend_resolution.py`
- Rebind canonical `MediaDatabase._resolve_backend` to that runtime module
- Rebind only the constructor logic that directly depends on the extracted
  backend-resolution behavior if needed
- Add constructor-path regressions for:
  - explicit backend precedence
  - env-forced Postgres resolution
  - config-driven Postgres resolution
  - pytest-mode SQLite suppression when explicit file path is used
  - `:memory:` persistent SQLite connection creation
  - init cleanup on `_initialize_schema` failure

## Out Of Scope

- `_initialize_schema`
- `_initialize_schema_sqlite`
- `_initialize_schema_postgres`
- `_apply_schema_v1_sqlite`
- `_get_db_version`
- `_get_postgres_migrations`
- `_postgres_migrate_to_v*`
- `_ensure_fts_structures`
- `_ensure_sqlite_fts`
- `_ensure_sqlite_email_schema`
- `_ensure_postgres_fts`
- `_ensure_postgres_rls`
- `_ensure_postgres_claims_tables`
- `_ensure_postgres_data_tables`
- `_ensure_postgres_email_schema`
- `_ensure_sqlite_backend`
- any caller migration work

## Architecture

### A. Extract backend resolution into a package-native runtime module

Create a runtime module that owns the exact current semantics of
`_resolve_backend`:

- accept explicit backend untouched
- load config only when needed
- honor `CONTENT_DB_MODE` / `TLDW_CONTENT_DB_BACKEND`
- preserve test-mode SQLite suppression when explicit file paths are used
- preserve SQLite fallback for explicit `db_path`
- preserve configured content-backend fallback

This module should stay method-shaped and receive `self`, just like the earlier
runtime helper modules.

### B. Keep `__init__` as a compat-owned coordinator in this tranche

Do **not** move the whole constructor yet.

Instead:

- keep path validation, directory creation, and schema-init orchestration where
  they are
- rebind only `_resolve_backend`
- add regressions around the constructor branches that exercise the rebound
  method

If later review shows that one tiny constructor helper must move together with
`_resolve_backend`, keep that change minimal and strictly constructor-local.

### C. Preserve current initialization cleanup semantics

When `_initialize_schema()` fails, `__init__` currently:

- logs a fatal initialization error
- calls `close_connection()`
- raises `DatabaseError`

This tranche must preserve that behavior even though schema ownership itself is
not moving.

### D. Preserve in-memory SQLite constructor behavior

The constructor currently creates a persistent SQLite connection for `:memory:`
DBs and runs `_apply_sqlite_connection_pragmas()` against it.

That branch is constructor-sensitive and must remain covered by regressions in
this tranche even though the pragma helper itself already moved earlier.

## Testing Strategy

### 1. Ownership regression

Add a narrow ownership regression in
`tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`
asserting that canonical `MediaDatabase._resolve_backend` resolves through the
new runtime module after rebinding.

### 2. Constructor-path regressions

Add or extend focused tests proving:

- explicit backend parameter bypasses config/env lookup
- env-forced Postgres path uses configured Postgres backend when available
- pytest/test mode with explicit file db path suppresses forced Postgres and
  stays SQLite
- `:memory:` DB still creates the persistent SQLite connection and applies the
  existing pragma helper seam
- constructor failure still calls `close_connection()` before re-raising

These should live in the existing DB-management regression files, not a new
integration suite.

### 3. Runtime factory safety checks

Re-run the factory/runtime validation tests after the tranche to confirm:

- schema-version lookup is unchanged
- startup validation behavior is unchanged
- Postgres content-backend validation still works with the canonical class

## Expected Outcome

After this tranche:

- canonical backend-resolution ownership moves out of `Media_DB_v2.py`
- constructor behavior is regression-locked before any schema/bootstrap move
- the next tranche can review schema coordinator extraction from a safer base

This is the correct next infra slice. Anything broader than `_resolve_backend`
plus constructor-path regressions widens immediately into mixed bootstrap and
domain migration behavior.
