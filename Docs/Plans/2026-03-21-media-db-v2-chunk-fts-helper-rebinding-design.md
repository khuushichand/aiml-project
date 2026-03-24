# Media DB V2 Chunk FTS Helper Rebinding Design

## Goal

Rebind the SQLite chunk-FTS helper pair, `ensure_chunk_fts()` and
`maybe_rebuild_chunk_fts_if_empty()`, onto a package-owned runtime module so
the canonical `MediaDatabase` no longer owns those methods through
`Media_DB_v2`, while preserving the legacy compat shell and keeping chunk FTS
bootstrap behavior unchanged.

## Scope

In scope:
- `ensure_chunk_fts()`
- `maybe_rebuild_chunk_fts_if_empty()`
- canonical rebinding in `media_database_impl.py`
- live-module compat shells in `Media_DB_v2.py`
- focused ownership, helper-path, and integration regression coverage

Out of scope:
- `_ensure_fts_structures()`
- `_ensure_sqlite_fts()`
- `_ensure_postgres_fts()`
- claims FTS rebuild helpers
- chunk retrieval SQL or retriever behavior beyond existing guards

## Current State

The remaining normalized legacy-owned canonical-method count is `195`. The
chunk-FTS pair is a small SQLite-only cluster in `Media_DB_v2.py` with a
bounded caller surface in the RAG retriever and existing integration coverage
in `test_chunk_fts_integration.py`.

## Target Design

Add one package-owned runtime module,
`tldw_Server_API/app/core/DB_Management/media_db/runtime/chunk_fts_ops.py`,
containing:
- `ensure_chunk_fts(self) -> None`
- `maybe_rebuild_chunk_fts_if_empty(self) -> None`

Then:
- rebind the canonical `MediaDatabase` methods in `media_database_impl.py`
- keep `Media_DB_v2` methods present as live-module compat shells using
  `import_module(...)`

## Behavior Invariants

`ensure_chunk_fts()` must preserve:
- SQLite-only no-op for non-SQLite backends
- existence check against `sqlite_master`
- `CREATE VIRTUAL TABLE IF NOT EXISTS unvectorized_chunks_fts`
- rebuild insert only when the table did not previously exist
- noncritical exception swallowing with debug logging

`maybe_rebuild_chunk_fts_if_empty()` must preserve:
- SQLite-only no-op for non-SQLite backends
- empty-count check against `unvectorized_chunks_fts`
- create-on-missing fallback by calling `ensure_chunk_fts()`
- rebuild insert only when the current count is zero
- noncritical exception swallowing with debug logging

## Tests

Add three layers of coverage:

1. Ownership and compat-shell regressions in
   `test_media_db_v2_regressions.py`
   - canonical methods no longer resolve globals from `Media_DB_v2`
   - legacy methods delegate through a live runtime module reference

2. Helper-path tests in `test_media_db_schema_bootstrap.py`
   - `ensure_chunk_fts()` creates the virtual table and rebuilds only when the
     table is new
   - `maybe_rebuild_chunk_fts_if_empty()` creates the table on missing, then
     rebuilds when empty
   - `maybe_rebuild_chunk_fts_if_empty()` does not rebuild when count is
     already nonzero

3. Existing integration guard in `test_chunk_fts_integration.py`
   - chunk retrieval still works after the helper move

## Success Criteria

- canonical `MediaDatabase.ensure_chunk_fts` is package-owned
- canonical `MediaDatabase.maybe_rebuild_chunk_fts_if_empty` is package-owned
- legacy `Media_DB_v2` methods remain callable compat shells
- focused helper and integration tests pass
- normalized ownership count drops `195 -> 193`
