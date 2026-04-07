# Media DB V2 Postgres Schema-Version Helper Rebinding Design

## Summary

Rebind `_update_schema_version_postgres` onto a package-owned helper so the
canonical `MediaDatabase` no longer owns that PostgreSQL helper through legacy
globals, while preserving `Media_DB_v2` as a live-module compatibility shell.

## Scope

In scope:

- Add a package helper module for `update_schema_version_postgres(...)`
- Rebind canonical `MediaDatabase._update_schema_version_postgres`
- Convert legacy `Media_DB_v2._update_schema_version_postgres` into a live-module
  compat shell
- Add direct ownership/delegation regressions
- Add one focused helper-path test for SQL and params

Out of scope:

- Changing migration registry/runner behavior
- Changing `_sync_postgres_sequences`
- Changing schema bootstrap flow

## Why This Slice

This is the narrowest remaining Postgres-specific helper. It owns one SQL
statement and has no fan-out into claims, email, or data-table domains.

## Risks

Very low. The main invariant is preserving the exact SQL and params tuple:

- `UPDATE schema_version SET version = %s`
- params `(version,)`

## Test Strategy

Add:

1. canonical ownership regression
2. legacy compat-shell delegation regression
3. helper-path test asserting exact SQL, params, and connection forwarding

## Success Criteria

- canonical `_update_schema_version_postgres` is package-owned
- legacy `Media_DB_v2._update_schema_version_postgres` remains a live-module
  compat shell
- helper-path test passes
- normalized ownership count drops from `207` to `206`
