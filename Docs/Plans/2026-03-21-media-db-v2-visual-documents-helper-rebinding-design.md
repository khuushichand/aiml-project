# Media DB V2 Visual Documents Helper Rebinding Design

## Summary

Rebind the VisualDocuments helper trio onto package-owned runtime helpers so
the canonical `MediaDatabase` no longer owns `insert_visual_document`,
`list_visual_documents_for_media`, or
`soft_delete_visual_documents_for_media` through legacy globals, while
preserving `Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `insert_visual_document(...)`
  - `list_visual_documents_for_media(...)`
  - `soft_delete_visual_documents_for_media(...)`
- Rebind canonical `MediaDatabase` methods for those three helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - insert delegates to `_execute_with_connection(...)` and `_log_sync_event(...)`
  - list delegates to `_fetchall_with_connection(...)` with the expected SQL
    parameters
  - soft delete handles both soft-delete iteration and hard-delete dispatch
- Reuse the existing VisualDocuments behavior tests and visual-ingestion
  integration guard

Out of scope:

- Rebinding MediaFiles helpers
- Changing VisualDocuments SQL or sync-log payload structure
- Rebinding schema/bootstrap helpers
- Rebinding broader media ingestion or visual RAG flow

## Why This Slice

This is the adjacent remaining storage helper cluster after the MediaFiles
slice. The methods are self-contained, already exercised directly in tests,
and do not widen into claims, email, or schema coordination.

## Risks

Low to medium. The key invariants are:

- canonical methods must stop resolving through `Media_DB_v2`
- legacy methods must remain present and delegate through a live module
  reference
- insert must preserve UUID generation, sync-log payload shape, and write
  routing
- list must preserve the deleted-row filter and ordering
- soft delete must preserve both the row-by-row soft-delete path and the
  hard-delete logging path

## Test Strategy

Add:

1. canonical ownership regressions for all three methods
2. legacy compat-shell delegation regressions for all three methods
3. focused helper-path tests in `test_media_db_visual_documents.py` for:
   - insert wrapper behavior
   - list wrapper SQL/parameter behavior
   - soft-delete soft and hard paths
4. reuse existing broader guards in:
   - `tldw_Server_API/tests/DB_Management/test_media_db_visual_documents.py`
   - `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_visual_ingestion.py`

## Success Criteria

- canonical VisualDocuments helper methods are package-owned
- legacy `Media_DB_v2` methods remain live-module compat shells
- focused helper-path tests pass
- existing VisualDocuments and visual-ingestion tests stay green
- normalized ownership count drops from `166` to `163`
