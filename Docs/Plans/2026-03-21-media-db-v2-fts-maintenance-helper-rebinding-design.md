# Media DB V2 FTS Maintenance Helper Rebinding Design

## Summary

Rebind the FTS maintenance cluster onto a package-owned runtime helper module so
the canonical `MediaDatabase` no longer owns `_update_fts_media`,
`_delete_fts_media`, `_update_fts_keyword`, `_delete_fts_keyword`, and
`sync_refresh_fts_for_entity` through legacy globals, while preserving
`Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add a package runtime helper module for:
  - `_update_fts_media(...)`
  - `_delete_fts_media(...)`
  - `_update_fts_keyword(...)`
  - `_delete_fts_keyword(...)`
  - `sync_refresh_fts_for_entity(...)`
- Rebind canonical `MediaDatabase` methods for those five helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for:
  - SQLite media FTS synonym expansion / fallback behavior
  - PostgreSQL media FTS update/delete SQL routing
  - PostgreSQL keyword FTS update/delete SQL routing
  - sync refresh dispatch for `Media` and `Keywords`

Out of scope:

- Changing `ensure_chunk_fts(...)` or `maybe_rebuild_chunk_fts_if_empty(...)`
- Changing `_ensure_fts_structures(...)`, `_ensure_sqlite_fts(...)`, or
  `_ensure_postgres_fts(...)`
- Changing `rebuild_claims_fts(...)`
- Changing the search/query layer that consumes FTS indexes

## Why This Slice

This is the cleanest remaining cross-backend helper cluster with real runtime
value. The methods already form one cohesive responsibility boundary: maintain
the FTS state for `Media` and `Keywords` rows and refresh that state during sync
application. The existing tests already cover the SQL contract and the sync
rollback seam, so this tranche can reduce ownership meaningfully without
widening into bootstrap or search behavior.

## Risks

Medium-low. The main invariants are:

- PostgreSQL still updates and clears `media_fts_tsv` and `keyword_fts_tsv`
  through `_execute_with_connection(...)`
- SQLite synonym expansion logic for media FTS remains unchanged
- `sync_refresh_fts_for_entity(...)` still refreshes or deletes the correct FTS
  rows for `Media` and `Keywords`
- instance-level monkeypatch points still work for sync processing and API-layer
  callers

The main failure mode would be accidentally moving bootstrap or chunk-FTS
behavior into the same module. This tranche should stay strictly on the
maintenance/update path.

## Test Strategy

Add:

1. canonical ownership regressions for all five methods
2. legacy compat-shell delegation regressions for all five methods
3. focused helper-path tests asserting:
   - SQLite `_update_fts_media(...)` preserves synonym expansion and graceful
     fallback behavior
   - PostgreSQL media FTS update/delete SQL routing
   - PostgreSQL keyword FTS update/delete SQL routing
   - sync refresh delegates to the expected helper methods for create/update/delete
   - sync refresh no-ops on update when payload omits the relevant fields
4. reuse existing:
   - `test_media_postgres_support.py`
   - `test_sync_server.py`
   - `test_media_db_api_imports.py`
   as broader guards

## Success Criteria

- canonical FTS maintenance helpers are package-owned
- legacy `Media_DB_v2` methods remain live-module compat shells
- focused helper tests pass
- existing PostgreSQL FTS, API-layer compat, and sync rollback tests stay green
- normalized ownership count drops from `200` to `195`
