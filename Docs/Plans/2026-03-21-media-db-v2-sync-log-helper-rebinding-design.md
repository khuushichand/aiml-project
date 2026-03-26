# Media DB V2 Sync Log Helper Rebinding Design

## Summary

Rebind the sync-log access and maintenance cluster onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns
`get_sync_log_entries`, `delete_sync_log_entries`, or
`delete_sync_log_entries_before` through legacy globals, while preserving
`Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `get_sync_log_entries(...)`
  - `delete_sync_log_entries(...)`
  - `delete_sync_log_entries_before(...)`
- Rebind canonical `MediaDatabase` methods for those three helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - sync-log payload JSON is decoded when valid
  - malformed payload JSON degrades to `None`
  - `limit` handling preserves query/parameter order
  - delete helpers preserve empty-list and validation behavior
  - delete helpers use the expected transaction/execution path
- Reuse the existing Media DB sync-log behavior tests as the broader
  behavioral guard

Out of scope:

- Rebinding the broader trash/share/media-visibility cluster
- Rebinding structure-index write helpers
- Changing sync-log schema, row shape, or ordering semantics
- Changing `_log_sync_event(...)`, bootstrap/init helpers, or any claims/email
  domain behavior

## Why This Slice

This is the smallest remaining bounded runtime cluster with meaningful
coverage. The three methods are contiguous, already have direct behavior tests
in `test_sqlite_db.py`, and there is a close sync-log implementation in
`Prompts_DB.py` that confirms the intended query/decode/delete pattern without
requiring a wider bootstrap or domain refactor.

## Risks

Low. The main invariants are:

- canonical methods must stop resolving through `Media_DB_v2`
- legacy `Media_DB_v2` methods must remain present and delegate through a live
  module reference
- `get_sync_log_entries(...)` must preserve change-id ordering, optional
  `LIMIT`, and payload JSON decode/fallback behavior
- delete helpers must preserve validation, empty-input handling, and
  transaction-backed rowcount behavior

## Test Strategy

Add:

1. canonical ownership regressions for all three methods
2. legacy compat-shell delegation regressions for all three methods
3. focused helper-path tests in
   `tldw_Server_API/tests/DB_Management/test_media_db_sync_log_ops.py` for:
   - payload decode and malformed-payload fallback
   - limit and param ordering
   - delete placeholder/transaction behavior
   - delete-before threshold validation
4. reuse the broader guards in:
   - `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`

## Success Criteria

- canonical sync-log helpers are package-owned
- legacy `Media_DB_v2` methods remain live-module compat shells
- focused helper-path tests pass
- existing sync-log behavior tests stay green
- normalized ownership count drops from `151` to `148`
