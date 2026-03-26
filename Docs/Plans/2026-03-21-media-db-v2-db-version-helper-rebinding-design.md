# Media DB V2 DB Version Helper Rebinding Design

## Summary

Rebind the SQLite `_get_db_version(...)` helper onto a package-owned schema
helper so the canonical `MediaDatabase` no longer owns that method through
legacy globals, while preserving `Media_DB_v2` as a live-module compatibility
shell.

## Scope

In scope:

- add one package schema helper module for `_get_db_version(...)`
- rebind canonical `MediaDatabase._get_db_version`
- convert the legacy `Media_DB_v2._get_db_version` method into a live-module
  compat shell
- add direct ownership/delegation regressions
- add focused helper-path tests asserting:
  - version rows still return the stored integer
  - empty `schema_version` still returns `0`
  - missing `schema_version` table still returns `0`
  - other SQLite failures still wrap as `DatabaseError`

Out of scope:

- changing bootstrap orchestration in `sqlite_helpers.py`
- changing `_initialize_schema(...)` or `_apply_schema_v1_sqlite(...)`
- changing PostgreSQL schema-version helpers
- changing schema migration ordering or transaction behavior
- changing any caller-facing bootstrap semantics

## Why This Slice

`_get_db_version(...)` is the smallest remaining bootstrap-adjacent helper that
still sits on the canonical class through legacy globals. It already has a
clear behavior contract and only a narrow package caller surface through the
SQLite bootstrap coordinator, so it is a low-risk singleton ownership
reduction.

## Risks

Low. The main invariants are behavioral:

- missing `schema_version` must still be treated as version `0`
- empty result sets must still return `0`
- non-table SQLite failures must still raise `DatabaseError`
- SQLite bootstrap callers must still work through the instance method seam
- instance-level monkeypatching of `_get_db_version(...)` must remain intact

## Test Strategy

Add:

1. canonical ownership regression for `_get_db_version`
2. legacy compat-shell delegation regression for `_get_db_version`
3. focused helper-path tests for:
   - successful version lookup
   - empty table result
   - missing-table fallback
   - wrapped SQLite error path
4. reuse the SQLite bootstrap package path in
   `tldw_Server_API/app/core/DB_Management/media_db/schema/backends/sqlite_helpers.py`
   as the structural caller to keep the instance seam intact

## Success Criteria

- canonical `_get_db_version(...)` is package-owned
- legacy `Media_DB_v2._get_db_version(...)` remains a live-module compat shell
- focused helper-path tests pass
- existing bootstrap structure remains unchanged
- normalized ownership count drops from `163` to `162`
