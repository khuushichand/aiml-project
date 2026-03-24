# Media DB V2 SQLite Post-Core Schema Helper Rebinding Design

## Goal

Rebind the small SQLite post-core schema ensure helpers off `Media_DB_v2` so the
canonical `MediaDatabase` no longer owns:
- `_ensure_sqlite_visibility_columns()`
- `_ensure_sqlite_source_hash_column()`
- `_ensure_sqlite_data_tables()`

This slice should preserve the legacy compat shell and keep the helper behavior
unchanged.

## Scope

In scope:
- `_ensure_sqlite_visibility_columns()`
- `_ensure_sqlite_source_hash_column()`
- `_ensure_sqlite_data_tables()`
- canonical rebinding in `media_database_impl.py`
- live-module compat shells in `Media_DB_v2.py`
- focused ownership/delegation regressions
- focused helper-path tests
- existing SQLite post-core bootstrap ordering guard

Out of scope:
- `_ensure_sqlite_claims_extensions()`
- any PostgreSQL ensure helpers
- higher-level bootstrap coordinators
- claims/data-table domain CRUD behavior

## Current State

The remaining normalized legacy-owned canonical-method count is `188`.

These three helpers are still defined on the canonical class through
`Media_DB_v2` even though they are narrow schema helpers:
- visibility helper introspects `Media`, adds missing visibility/owner columns,
  and creates the two related indexes when absent
- source-hash helper introspects `Media`, adds `source_hash`, and creates the
  related index when absent
- data-tables helper just executes `_DATA_TABLES_SQL` with warning-only SQLite
  error handling

## Target Design

Add one package-owned schema module:
- `tldw_Server_API/app/core/DB_Management/media_db/schema/sqlite_post_core_structures.py`

It should own:
- `ensure_sqlite_visibility_columns(db, conn) -> None`
- `ensure_sqlite_source_hash_column(db, conn) -> None`
- `ensure_sqlite_data_tables(db, conn) -> None`

Then:
- rebind the canonical methods in `media_database_impl.py`
- keep the legacy methods in `Media_DB_v2.py` as live-module compat shells

## Behavior Invariants

`ensure_sqlite_visibility_columns()` must preserve:
- `PRAGMA table_info(Media)` introspection first
- `PRAGMA index_list(Media)` fallback to empty set on SQLite failure
- exact missing-artifact gating for:
  - `visibility`
  - `owner_user_id`
  - `idx_media_visibility`
  - `idx_media_owner_user_id`
- no-op when nothing is missing
- warning-only behavior on introspection or executescript failures

`ensure_sqlite_source_hash_column()` must preserve:
- `PRAGMA table_info(Media)` introspection first
- `PRAGMA index_list(Media)` fallback to empty set on SQLite failure
- exact missing-artifact gating for:
  - `source_hash`
  - `idx_media_source_hash`
- no-op when nothing is missing
- warning-only behavior on introspection or executescript failures

`ensure_sqlite_data_tables()` must preserve:
- executes `_DATA_TABLES_SQL`
- warning-only behavior on `sqlite3.Error`

## Tests

Add three layers of coverage:

1. Ownership and compat-shell regressions in
   `test_media_db_v2_regressions.py`
   - canonical methods are no longer legacy-owned
   - legacy methods delegate through a live package module reference

2. Helper-path tests in `test_media_db_schema_bootstrap.py`
   - visibility helper emits the expected SQLite statements when artifacts are
     missing and no-ops when they already exist
   - source-hash helper emits the expected SQLite statements when artifacts are
     missing and no-ops when they already exist
   - data-tables helper runs `_DATA_TABLES_SQL` and tolerates SQLite errors

3. Existing bootstrap ordering guard
   - `test_ensure_sqlite_post_core_structures_runs_followup_ensures`

## Success Criteria

- canonical visibility/source-hash/data-tables helpers are package-owned
- legacy `Media_DB_v2` methods remain callable compat shells
- focused helper tests pass
- existing SQLite post-core ordering guard stays green
- normalized ownership count drops `188 -> 185`
