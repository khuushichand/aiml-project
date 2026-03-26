# Media DB V2 Sync Utility Helper Rebinding Design

## Summary

Rebind the shared sync/version utility cluster onto package-owned runtime
helpers so the canonical `MediaDatabase` no longer owns `_generate_uuid`,
`_get_current_utc_timestamp_str`, `_get_next_version`, or `_log_sync_event`
through legacy globals, while preserving `Media_DB_v2` as a live-module
compatibility shell.

## Scope

In scope:

- Add one package runtime helper module for:
  - `_generate_uuid(...)`
  - `_get_current_utc_timestamp_str(...)`
  - `_get_next_version(...)`
  - `_log_sync_event(...)`
- Rebind canonical `MediaDatabase` methods for those four helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - UUID generation still yields version-4 UUID strings
  - UTC timestamp strings still use millisecond precision with a trailing `Z`
  - version lookup still enforces safe identifiers, filters out deleted rows,
    and rejects non-integer versions
  - sync-log writes still prune `vector_embedding`, normalize datetimes, and
    preserve the SQLite/Postgres write split

Out of scope:

- Changing `_get_db_version(...)`
- Changing `_normalize_data_table_row_json(...)`
- Changing transaction semantics or connection lifecycle
- Changing caller behavior that instance-monkeypatches these methods
- Changing sync-log schema, replication logic, or downstream readers

## Why This Slice

This is the smallest remaining shared runtime helper cluster with broad reuse
across sync-aware mutations and media CRUD flows. Unlike broader schema or
domain helpers, these methods are narrowly scoped and already have natural
behavior seams that can be pinned with direct unit tests.

## Risks

Low to medium. The main invariants are behavioral, not architectural:

- `_get_current_utc_timestamp_str(...)` must keep the current UTC millisecond
  ISO-8601 format ending in `Z`
- `_generate_uuid(...)` must keep returning string UUID4 values
- `_get_next_version(...)` must preserve safe identifier validation, the
  `deleted = 0` filter, integer-only version semantics, and `DatabaseError`
  wrapping for database failures
- `_log_sync_event(...)` must preserve missing-input no-op behavior, payload
  pruning, datetime normalization, and the backend-specific SQLite/Postgres
  execution path
- instance-level monkeypatching must remain intact because existing callers and
  tests patch these methods directly on the database object

## Test Strategy

Add:

1. canonical ownership regressions for all four methods
2. legacy compat-shell delegation regressions for all four methods
3. focused helper-path tests for:
   - UUID4 output
   - timestamp string format
   - version lookup success, deleted-row filtering, unsafe-identifier
     rejection, and non-integer-version rejection
   - sync-log SQLite payload pruning / datetime normalization
   - sync-log Postgres routing through `_execute_with_connection(...)`
4. reuse existing caller-facing tests in:
   - `tldw_Server_API/tests/DB_Management/test_media_postgres_support.py`
   - `tldw_Server_API/tests/DB_Management/test_media_prompts_sqlite.py`
   - `tldw_Server_API/tests/DB_Management/test_media_db_api_imports.py`

## Success Criteria

- canonical helper methods are package-owned
- legacy `Media_DB_v2` helper methods remain live-module compat shells
- focused helper-path tests pass
- existing caller-facing compatibility tests stay green
- normalized ownership count drops from `179` to `175`
