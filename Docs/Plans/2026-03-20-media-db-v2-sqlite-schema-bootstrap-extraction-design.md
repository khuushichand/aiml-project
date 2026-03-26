# Media DB V2 SQLite Schema Bootstrap Extraction Design

**Status:** Proposed, review-corrected, and ready for tranche planning on 2026-03-20.

**Goal:** Extract the real SQLite schema bootstrap coordinator out of legacy
`Media_DB_v2` ownership without mixing in PostgreSQL bootstrap or domain-heavy
migration ownership.

## Why This Tranche Exists

The last review confirmed that the next safe slice is narrower than "schema
bootstrap."

Two important facts are now true:

1. `_initialize_schema()` is already effectively package-owned because
   [`Media_DB_v2._initialize_schema`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
   delegates straight into
   [`ensure_media_schema`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/bootstrap.py).
2. The real remaining legacy ownership sits behind the backend-specific bridge
   methods:
   - [`initialize_sqlite_schema`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py)
   - [`initialize_postgres_schema`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/backends/postgres.py)

That means the next meaningful bootstrap move is not top-level dispatch. It is
the SQLite backend bridge and the coordinator logic it still forwards into.

## Review Corrections Incorporated

### 1. Do not target `_initialize_schema` directly

`_initialize_schema()` already just forwards to `ensure_media_schema(self)`.
Moving it would produce very little real ownership reduction.

This tranche leaves:

- `ensure_media_schema(...)`
- `MediaDatabase._initialize_schema(...)`

as they are, and instead targets the SQLite backend bootstrap bridge beneath
them.

### 2. Do not combine SQLite and Postgres bootstrap in one tranche

The SQLite coordinator is already large, but still structurally local to one
backend.

The Postgres coordinator is much wider because it fans into:

- migration dispatch
- FTS setup
- RLS setup
- claims/data-tables/email schema paths

That is a different tranche. SQLite-only extraction is the safe next step.

### 3. Do not move `_apply_schema_v1_sqlite` wholesale yet

[`_apply_schema_v1_sqlite`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
still mixes:

- core media schema DDL
- claims/media files/TTS/data tables
- collection/content-item bootstrap
- email schema ensure
- validation and version check
- FTS follow-up

The coordinator must be decomposed first. This tranche extracts helper groups
and the SQLite backend bridge, not the entire monolith in one jump.

### 4. Fix the duplicated SQLite post-core ensure block before rebinding

[`_initialize_schema_sqlite`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
duplicates the "upgraded DB must still have newer structures" block in multiple
branches:

- collections/content items
- visibility/source hash
- claims extensions
- email schema
- FTS follow-up

That duplicated block should become package-native helpers first, so the
backend bridge can call one canonical package-owned coordinator.

## In Scope

- SQLite backend bootstrap only
- package-native extraction of the duplicated SQLite post-core ensure block
- package-native SQLite schema coordinator invoked by
  `schema/backends/sqlite.py`
- ownership tests showing the SQLite backend bridge no longer forwards into
  legacy `_initialize_schema_sqlite()`

## Out Of Scope

- PostgreSQL bootstrap extraction
- `_initialize_schema()` dispatcher changes
- `_initialize_schema_postgres()`
- `_get_postgres_migrations()`
- any `_postgres_migrate_to_v*`
- Postgres FTS, RLS, claims, data-tables, or email schema extraction
- caller migration work

## Target Architecture

### A. Keep the dispatcher, replace the SQLite backend implementation

Keep:

- `ensure_media_schema(db)`
- `initialize_sqlite_schema(db)` as the backend dispatch surface

Change:

- `initialize_sqlite_schema(db)` should stop calling legacy
  `db._initialize_schema_sqlite()`
- it should instead call a package-native SQLite coordinator

This preserves the already-established package bootstrap boundary.

### B. Extract SQLite post-core ensure helpers

Introduce small package-native helpers for the currently duplicated upgrade
follow-up block:

- collections/content items ensure
- visibility/source hash ensure
- claims extensions ensure
- email schema ensure
- FTS ensure/follow-up

These helpers should be called by one package-native SQLite coordinator, not
duplicated across fresh/upgraded branches.

### C. Keep legacy core-schema application as a temporary leaf

The coordinator may still temporarily call legacy-owned primitives such as:

- `_get_db_version`
- `_apply_schema_v1_sqlite`
- migration tooling integration

That is acceptable in this tranche.

The ownership goal here is the SQLite bootstrap coordinator and its duplicated
follow-up block, not every leaf it currently depends on.

## Suggested Package Shape

- `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite.py`
  - remains the backend entrypoint
- new or expanded package-native helper area, for example:
  - `media_db/schema/sqlite_upgrade_ensures.py`
  - or `media_db/schema/backends/sqlite_helpers.py`

The exact file split matters less than keeping:

- backend bridge small
- duplicated ensures centralized
- migration and core-schema logic out of scope for now

## Testing Strategy

### 1. Existing dispatcher tests

Reuse and extend
[test_media_db_schema_bootstrap.py](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
to prove:

- `ensure_media_schema()` still dispatches correctly
- SQLite backend bootstrap now uses the package-native coordinator

### 2. SQLite integration safety

Reuse existing SQLite schema/bootstrap and email-stage tests:

- [test_media_db_schema_bootstrap.py](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
- [test_email_native_stage1.py](./../../tldw_Server_API/tests/DB_Management/test_email_native_stage1.py)

Add only the smallest missing regression to prove the duplicated ensure block
still runs on:

- already-up-to-date DBs
- freshly initialized DBs
- upgraded DBs

### 3. Ownership regression

Add a regression showing the SQLite backend bridge no longer calls the legacy
private method directly.

This should target the package bootstrap layer, not `MediaDatabase.__dict__`,
because the coordinator is already behind the schema package boundary.

## Expected Outcome

After this tranche:

- the package bootstrap dispatcher remains stable
- SQLite bootstrap coordination is package-owned
- duplicated post-core ensure logic is centralized
- PostgreSQL bootstrap and migration ownership remain untouched and explicitly
  deferred

That creates a safer base for later extraction of the remaining SQLite leaf
helpers and, separately, the future Postgres bootstrap tranche.
