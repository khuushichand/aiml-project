# Media DB V2 SQLite-To-Postgres Conversion Helper Rebinding Design

## Summary

Rebind `_convert_sqlite_sql_to_postgres_statements` and
`_transform_sqlite_statement_to_postgres` onto a package-owned schema helper so
the canonical `MediaDatabase` no longer owns those conversion helpers through
legacy globals, while preserving `Media_DB_v2` as a live-module compatibility
shell.

## Scope

In scope:

- Add a package schema helper module for:
  - `_convert_sqlite_sql_to_postgres_statements(...)`
  - `_transform_sqlite_statement_to_postgres(...)`
- Rebind canonical `MediaDatabase` methods for those two helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests for:
  - filtering SQLite-only lines and collecting semicolon-terminated statements
  - delegating statement conversion through the package-owned transform helper
  - one direct token-level transform example

Out of scope:

- Changing `run_postgres_migrate_to_v11(...)`
- Changing `prepare_backend_statement(...)` or query-utils transforms
- Changing the MediaFiles migration control flow

## Why This Slice

This is the next narrow helper cluster after the backend-preparation trio. The
pair is self-contained, already has indirect coverage via the MediaFiles
migration tests, and it reduces ownership without widening into claims, email,
or bootstrap coordinators.

## Risks

Low to moderate. The main invariants are:

- comment/blank/PRAGMA/FTS/trigger lines still get filtered
- statements are still buffered until `;`
- `_convert_sqlite_sql_to_postgres_statements(...)` still delegates each
  statement through `_transform_sqlite_statement_to_postgres(...)`
- `_transform_sqlite_statement_to_postgres(...)` keeps existing token rewrites

## Test Strategy

Add:

1. canonical ownership regressions for both methods
2. legacy compat-shell delegation regressions for both methods
3. focused helper-path tests covering line filtering, delegation, and one
   concrete rewrite
4. reuse the existing MediaFiles migration tests as the broader guard

## Success Criteria

- canonical conversion helper methods are package-owned
- legacy `Media_DB_v2` conversion helper methods remain live-module compat
  shells
- focused helper-path tests pass
- existing MediaFiles migration tests stay green
- normalized ownership count drops from `202` to `200`
