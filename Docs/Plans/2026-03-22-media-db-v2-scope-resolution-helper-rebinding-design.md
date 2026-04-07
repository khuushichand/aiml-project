# Media DB V2 Scope Resolution Helper Rebinding Design

## Summary

After the safe-metadata search tranche, the normalized legacy ownership count
is `17`. The cleanest remaining non-bootstrap helper is `_resolve_scope_ids()`.

This method is small, but it sits on an important seam: package-native runtime
helpers already call `self._resolve_scope_ids()` to stamp org/team scope into
sync rows and media inserts. Moving canonical ownership for this helper closes
that remaining legacy dependency without widening into bootstrap, PostgreSQL
schema coordination, or rollback.

## Current Method Shape

`_resolve_scope_ids()` currently owns:

- request-scope lookup through `get_scope()`
- fallback when request scope is unavailable
- defaulting to `self.default_org_id` / `self.default_team_id`
- override behavior when `effective_org_id` / `effective_team_id` are present
- cache writeback into `self._scope_cache`
- tuple return of `(org_id, team_id)`

## Why This Slice Is Safe

This is a bounded internal helper:

- it has no SQL or transaction behavior
- it is already consumed through the instance seam by package-native runtime
  code
- existing request-scope tests already pin the higher-level caller behavior
- it is smaller and lower-risk than the remaining bootstrap/init cluster

That makes it safer than the other remaining surfaces:

- `initialize_db(...)`
- `_initialize_schema*` and PostgreSQL bootstrap helpers
- `rollback_to_version(...)`

## Risks To Pin

### 1. Scope fallback must stay non-fatal

`get_scope()` is wrapped so request-scope lookup failures do not break callers.
The runtime helper must preserve the same fallback-to-default behavior.

### 2. Partial scope overrides must preserve defaults

If request scope only supplies an org or a team, the missing half should still
fall back to the database defaults rather than becoming `None`.

### 3. Cache writeback must remain intact

Callers may rely on `_scope_cache` being updated with the resolved tuple. That
side effect needs direct coverage in the helper tests.

## Recommended Tranche

Move only:

- `_resolve_scope_ids()`

Defer:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_*`
- `_initialize_schema*`
- `_run_postgres_migrations(...)`
- `_get_postgres_migrations(...)`
- `_ensure_postgres_*`
- `_postgres_policy_exists(...)`
- `_ensure_postgres_rls(...)`
- `rollback_to_version(...)`

## Design

Add one package-owned runtime module:

- `tldw_Server_API/app/core/DB_Management/media_db/runtime/scope_resolution_ops.py`

It should expose:

- `_resolve_scope_ids(...)`

Then:

- rebind canonical `MediaDatabase._resolve_scope_ids` in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy method in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into a live-module compat shell

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical `MediaDatabase._resolve_scope_ids(...)` no longer using legacy
  globals
- legacy `Media_DB_v2._resolve_scope_ids(...)` delegating through
  `scope_resolution_ops.py`

### Focused helper coverage

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_scope_resolution_ops.py`

Pin:

- canonical helper rebinding
- default-only fallback behavior
- request-scope override behavior
- partial-scope fallback behavior
- non-fatal `get_scope()` exception fallback
- `_scope_cache` writeback behavior

### Broader caller-facing guards

Reuse existing coverage:

- [test_media_db_request_scope_isolation.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_request_scope_isolation.py)
- [test_media_db_sync_utils.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_sync_utils.py)

## Success Criteria

- canonical ownership for `_resolve_scope_ids(...)` moves off legacy globals
- legacy method remains a live-module compat shell
- helper-path tests pass for fallback, overrides, and cache writeback
- request-scope and sync utility guards stay green
- normalized ownership count drops `17 -> 16`
