# Media DB V2 FTS Schema Helper Rebinding Design

## Goal

Rebind the FTS schema helper cluster, `_ensure_fts_structures()`,
`_ensure_sqlite_fts()`, and `_ensure_postgres_fts()`, onto a package-owned
schema helper module so the canonical `MediaDatabase` no longer owns those
methods through `Media_DB_v2`, while preserving the legacy compat shell and
retargeting the package feature wrapper away from legacy-owned methods.

## Scope

In scope:
- `_ensure_fts_structures()`
- `_ensure_sqlite_fts()`
- `_ensure_postgres_fts()`
- `media_db/schema/features/fts.py`
- canonical rebinding in `media_database_impl.py`
- live-module compat shells in `Media_DB_v2.py`
- focused ownership, helper-path, and integration regression coverage

Out of scope:
- `ensure_chunk_fts()` and `maybe_rebuild_chunk_fts_if_empty()`
- FTS maintenance helpers already moved to `runtime/fts_ops.py`
- `_ensure_postgres_rls()`
- claims-specific rebuild helpers
- broader bootstrap coordinators beyond the FTS feature seam

## Current State

The remaining normalized legacy-owned canonical-method count is `193`.

`schema/features/fts.py` currently forwards to legacy-owned DB methods:
- `ensure_sqlite_fts_structures(db, conn)` calls `db._ensure_fts_structures(conn)`
- `ensure_postgres_fts(db, conn)` calls `db._ensure_postgres_fts(conn)`

That keeps package bootstrap code pointed at legacy ownership even after recent
bootstrap-coordinator extraction.

## Target Design

Add one package-owned schema module:
- `tldw_Server_API/app/core/DB_Management/media_db/schema/fts_structures.py`

It should own:
- `ensure_fts_structures(db, conn) -> None`
- `ensure_sqlite_fts(db, conn) -> None`
- `ensure_postgres_fts(db, conn) -> None`

Then:
- update `schema/features/fts.py` to call those package helpers directly
- rebind the canonical `MediaDatabase` methods in `media_database_impl.py`
- keep the legacy methods in `Media_DB_v2.py` as live-module compat shells

## Behavior Invariants

`ensure_fts_structures()` must preserve:
- SQLite dispatch to `ensure_sqlite_fts(...)`
- PostgreSQL dispatch to `ensure_postgres_fts(...)`
- `NotImplementedError` for unsupported backends

`ensure_sqlite_fts()` must preserve:
- `conn.executescript(self._FTS_TABLES_SQL)`
- `conn.executescript(self._CLAIMS_FTS_TRIGGERS_SQL)`
- verification that `media_fts` and `keyword_fts` both exist
- `DatabaseError` on missing required core FTS tables
- `conn.commit()` in the `finally` block

`ensure_postgres_fts()` must preserve:
- `backend.create_fts_table(...)` for `media_fts`, `keyword_fts`, and
  `claims_fts`
- best-effort `unvectorized_chunks_fts` creation
- warning-only behavior for chunk FTS creation failure

## Tests

Add three layers of coverage:

1. Ownership and compat-shell regressions in
   `test_media_db_v2_regressions.py`
   - canonical `_ensure_fts_structures`, `_ensure_sqlite_fts`, and
     `_ensure_postgres_fts` are no longer legacy-owned
   - legacy methods delegate through a live package module reference

2. Helper-path tests in `test_media_db_schema_bootstrap.py`
   - `ensure_fts_structures(...)` dispatches correctly by backend
   - `ensure_sqlite_fts(...)` runs both scripts, verifies required tables,
     commits, and raises on missing core FTS tables
   - `ensure_postgres_fts(...)` calls `create_fts_table(...)` in order and
     tolerates chunk-FTS failure
   - `schema/features/fts.py` routes through the package helpers

3. Existing integration guards
   - `test_ensure_media_schema_keeps_sqlite_schema_intact`
   - `test_claims_schema.py`
   - `test_claims_fts_triggers.py`

## Success Criteria

- canonical `MediaDatabase._ensure_fts_structures` is package-owned
- canonical `MediaDatabase._ensure_sqlite_fts` is package-owned
- canonical `MediaDatabase._ensure_postgres_fts` is package-owned
- `schema/features/fts.py` no longer depends on legacy-owned DB methods
- legacy `Media_DB_v2` methods remain callable compat shells
- focused helper and integration tests pass
- normalized ownership count drops `193 -> 190`
