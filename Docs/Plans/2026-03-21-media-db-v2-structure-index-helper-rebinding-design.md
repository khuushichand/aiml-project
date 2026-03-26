# Media DB V2 Structure Index Helper Rebinding Design

## Summary

Rebind the DocumentStructureIndex write helper trio onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns
`_write_structure_index_records`, `write_document_structure_index`, or
`delete_document_structure_for_media` through legacy globals, while preserving
`Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `_write_structure_index_records(...)`
  - `write_document_structure_index(...)`
  - `delete_document_structure_for_media(...)`
- Rebind canonical `MediaDatabase` methods for those three helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - old rows are cleared before new structure rows are inserted
  - invalid structure rows are skipped without aborting the write
  - SQLite vs Postgres deleted-flag encoding stays unchanged
  - public write validates `media_id` and runs through the transaction path
  - delete returns the cursor rowcount and no-ops on falsey `media_id`
- Reuse the existing structure-index integration tests as the broader guard

Out of scope:

- Rebinding media navigation read helpers
- Changing repository-level section aggregation logic
- Changing `DocumentStructureIndex` schema or parent-link repair behavior
- Rebinding the trash/share cluster, claims, email sync, or bootstrap/init
  surfaces

## Why This Slice

This is the cleanest bounded write-helper cluster left after the sync-log
slice. The methods are contiguous, have a single clear caller in the media
repository, and already feed the structure-index integration tests under
`tests/RAG_NEW/unit/test_structure_index.py`.

## Risks

Low to medium. The main invariants are:

- canonical methods must stop resolving through `Media_DB_v2`
- legacy `Media_DB_v2` methods must remain present and delegate through a live
  module reference
- `_write_structure_index_records(...)` must keep the clear-then-insert order
  and continue skipping invalid rows instead of failing the whole write
- public wrappers must preserve current validation and transaction behavior

## Test Strategy

Add:

1. canonical ownership regressions for all three methods
2. legacy compat-shell delegation regressions for all three methods
3. focused helper-path tests in
   `tldw_Server_API/tests/DB_Management/test_media_db_structure_index_ops.py`
   for:
   - clear-then-insert order
   - invalid-row skip behavior
   - public write transaction wrapping
   - delete rowcount/no-op behavior
4. reuse the broader guards in:
   - `tldw_Server_API/tests/RAG_NEW/unit/test_structure_index.py`
   - `tldw_Server_API/tests/Media/test_media_navigation.py`

## Success Criteria

- canonical structure-index write helpers are package-owned
- legacy `Media_DB_v2` methods remain live-module compat shells
- focused helper-path tests pass
- structure-index integration tests stay green
- normalized ownership count drops from `148` to `145`
