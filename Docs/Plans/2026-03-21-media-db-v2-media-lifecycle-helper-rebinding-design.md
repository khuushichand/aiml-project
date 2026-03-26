# Media DB V2 Media Lifecycle Helper Rebinding Design

## Summary

Rebind the bounded media lifecycle helper cluster onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns
`soft_delete_media`, `share_media`, `unshare_media`,
`get_media_visibility`, `mark_as_trash`, or `restore_from_trash` through
legacy globals, while preserving `Media_DB_v2` as a live-module compatibility
shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `soft_delete_media(...)`
  - `share_media(...)`
  - `unshare_media(...)`
  - `get_media_visibility(...)`
  - `mark_as_trash(...)`
  - `restore_from_trash(...)`
- Rebind canonical `MediaDatabase` methods for those six helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions for the six methods
- Add focused helper-path tests asserting:
  - `soft_delete_media(cascade=True)` still unlinks keywords, soft-deletes
    child rows, logs sync updates, and calls `_delete_fts_media(...)` through
    the instance seam
  - `share_media(...)` still validates visibility inputs and writes the
    expected visibility/org/team fields
  - `unshare_media(...)` still routes through the share path to restore
    `personal` visibility
  - `get_media_visibility(...)` still returns the current visibility payload
    or `None`
  - `mark_as_trash(...)` and `restore_from_trash(...)` still preserve their
    transaction/update/sync behavior
- Reuse the existing lifecycle and caller-facing tests as broader guards

Out of scope:

- Rebinding `rollback_to_version(...)`
- Rebinding `search_media_db(...)` or `search_by_safe_metadata(...)`
- Rebinding `add_media_with_keywords(...)`
- Changing rollback/version-history semantics
- Changing search or FTS ranking behavior
- Rebinding data tables, claims, email sync, or bootstrap/init surfaces

## Why This Slice

This is the cleanest remaining bounded runtime cluster that still gives a real
ownership drop. The methods already have meaningful coverage across Media DB
SQLite tests, email visibility/deleted behavior tests, DB-manager wrappers,
and real archive/sync callers. Unlike `rollback_to_version(...)`, this slice
does not require moving version-history or search-refresh behavior.

## Risks

Medium. The main invariants are:

- canonical methods must stop resolving through `Media_DB_v2`
- legacy `Media_DB_v2` methods must remain present and delegate through a live
  module reference
- `soft_delete_media(...)` must preserve:
  - keyword unlinking
  - child soft deletes
  - sync-log emission
  - FTS removal
  - post-commit vector invalidation
- `mark_as_trash(...)` and `restore_from_trash(...)` must preserve sync/update
  behavior without touching FTS
- `share_media(...)` and `unshare_media(...)` must keep current validation and
  scope-field behavior

## Test Strategy

Add:

1. canonical ownership regressions for all six lifecycle methods
2. legacy compat-shell delegation regressions for all six methods
3. focused helper-path tests in
   `tldw_Server_API/tests/DB_Management/test_media_db_media_lifecycle_ops.py`
   for:
   - soft-delete cascade behavior and FTS seam usage
   - share/unshare visibility transitions and validation
   - get-visibility payload behavior
   - trash/restore transaction and sync behavior
4. reuse the broader guards in:
   - `tldw_Server_API/tests/MediaDB2/test_sqlite_db.py`
   - `tldw_Server_API/tests/DB_Management/test_email_native_stage1.py`
   - `tldw_Server_API/tests/DB_Management/test_db_manager_wrappers.py`
   - `tldw_Server_API/tests/External_Sources/test_sync_coordinator.py`

## Success Criteria

- canonical lifecycle helpers are package-owned
- legacy `Media_DB_v2` methods remain live-module compat shells
- focused helper-path tests pass
- lifecycle caller-facing tests stay green
- normalized ownership count drops from `145` to `139`
