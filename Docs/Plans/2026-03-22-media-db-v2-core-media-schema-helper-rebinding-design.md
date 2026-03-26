# Media DB V2 Core Media Schema Helper Rebinding Design

**Date:** 2026-03-22
**Status:** Proposed
**Target Area:** `tldw_Server_API/app/core/DB_Management/Media_DB_v2.py`
**Target Ownership Count:** `6 -> 4`

## Objective

Move the remaining schema-v1 core apply pair off the legacy `Media_DB_v2`
module:

- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`

The goal is to make the package-owned bootstrap path fully own the core schema
apply seam, instead of routing through package modules that still delegate back
into legacy-owned method bodies.

## Why This Slice

After the Postgres claims/collections ensure tranche, the remaining legacy-owned
surface is:

- `__init__(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `_ensure_sqlite_backend(...)`
- `initialize_db(...)`
- `rollback_to_version(...)`

`rollback_to_version(...)` is an active mutation coordinator with API and DB
manager call paths, so it should remain isolated in its own tranche.

`__init__(...)` and `initialize_db(...)` are constructor/compat wrappers with a
large caller surface. `_ensure_sqlite_backend(...)` is effectively a no-op and
does not unlock another owned package seam by itself.

The schema-v1 core apply pair is the clean bounded slice because:

1. Both methods are already conceptually routed through
   `media_db/schema/features/core_media.py`.
2. The current package seam still resolves to legacy-owned method bodies.
3. Rebinding this pair removes a real bootstrap dependency without mixing in
   constructor, API compatibility, or rollback semantics.

## Current State

`media_db/schema/features/core_media.py` currently exposes:

- `apply_sqlite_core_media_schema(db, conn)`
- `apply_postgres_core_media_schema(db, conn)`

But both helpers simply call:

- `db._apply_schema_v1_sqlite(conn)`
- `db._apply_schema_v1_postgres(conn)`

That means package-native bootstrap still depends on legacy ownership for the
actual schema-v1 apply logic.

## Proposed Design

Expand `media_db/schema/features/core_media.py` so it owns the real schema-v1
apply logic:

- move the full SQLite schema-v1 apply body into
  `apply_sqlite_core_media_schema(db, conn)`
- move the full PostgreSQL schema-v1 apply body into
  `apply_postgres_core_media_schema(db, conn)`

Then:

1. Rebind canonical `MediaDatabase._apply_schema_v1_sqlite` and
   `MediaDatabase._apply_schema_v1_postgres` in
   `media_db/media_database_impl.py`
2. Convert the legacy methods in `Media_DB_v2.py` into live-module compat
   shells that delegate through `import_module(...)`

This keeps the active package seam unchanged while removing the remaining
legacy ownership for the schema-v1 apply logic.

## Invariants To Preserve

### SQLite

`_apply_schema_v1_sqlite(...)` must preserve:

1. execution of the full schema script including schema-version seed/update
2. post-script `self._ensure_sqlite_email_schema(conn)`
3. Media-table validation against the expected column set
4. explicit schema-version verification against `_CURRENT_SCHEMA_VERSION`
5. FTS creation through `_ensure_fts_structures(conn)` inside the existing
   warning-only boundary
6. conversion of SQLite/Schema errors into `DatabaseError`

### PostgreSQL

`_apply_schema_v1_postgres(...)` must preserve:

1. SQLite-to-Postgres statement conversion for `_TABLES_SQL_V1`,
   `_CLAIMS_TABLE_SQL`, `_MEDIA_FILES_TABLE_SQL`, `_TTS_HISTORY_TABLE_SQL`,
   and `_DATA_TABLES_SQL`
2. ordering:
   - `CREATE TABLE` statements first
   - non-table initializers second
   - must-table validation third
   - index statements fourth
3. fresh-DB `self._ensure_postgres_email_schema(conn)` call
4. final `schema_version` normalization to `_CURRENT_SCHEMA_VERSION`

## Explicit Deferrals

Out of scope for this tranche:

- `__init__(...)`
- `_ensure_sqlite_backend(...)`
- `initialize_db(...)`
- `rollback_to_version(...)`

## Test Strategy

### New focused tests

Add a dedicated helper-path file, likely:

- `tldw_Server_API/tests/DB_Management/test_media_db_core_media_schema_ops.py`

Pin:

1. canonical helper rebinding to `schema/features/core_media.py`
2. SQLite path:
   - email ensure runs after schema script
   - Media validation failure raises
   - FTS failure is warning-only
3. PostgreSQL path:
   - create-table-first ordering
   - must-table validation
   - email ensure and schema-version normalization

### Ownership/delegation regressions

Extend:

- `tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py`

Pin:

1. canonical methods no longer resolve globals from `Media_DB_v2`
2. legacy compat-shell methods delegate via live-module import

### Broader guards

Use existing bootstrap callers in:

- `tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py`
- `tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py`

## Risks

### Risk 1: SQLite validation drift

The SQLite body contains the strictest local validation in the remaining
bootstrap surface. Missing any expected Media column or changing the warning
boundary around FTS creation would be a real behavior regression.

Mitigation:

- direct helper tests for validation and FTS warning behavior

### Risk 2: Postgres ordering drift

The Postgres body depends on statement ordering before must-table checks and
follow-up ensures.

Mitigation:

- direct ordered-call helper test using backend stubs

### Risk 3: Widening into constructor/bootstrap wrappers

It would be easy to drag `initialize_db(...)` or `__init__(...)` into this
slice. That would mix schema application with object-lifecycle behavior.

Mitigation:

- keep the tranche strictly to the schema-v1 apply pair

## Success Criteria

1. Canonical ownership for `_apply_schema_v1_sqlite(...)` and
   `_apply_schema_v1_postgres(...)` moves to `schema/features/core_media.py`
2. Legacy methods become compat shells only
3. Focused helper tests and ownership regressions pass
4. Bootstrap guard tests stay green
5. Normalized ownership count drops from `6` to `4`
