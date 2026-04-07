# Media DB V2 Postgres MediaFiles Migration Body Rebinding Design

## Summary

Rebind PostgreSQL migration body method `v11` onto a package-owned helper module
so the canonical `MediaDatabase` no longer owns that method through legacy
globals, while preserving `Media_DB_v2` as a live-module compatibility shell
and keeping the MediaFiles migration error-handling semantics unchanged.

## Scope

In scope:

- Add a package helper module for `run_postgres_migrate_to_v11(...)`
- Rebind canonical `MediaDatabase._postgres_migrate_to_v11` in
  `media_database_impl.py`
- Convert legacy `Media_DB_v2._postgres_migrate_to_v11` into a live-module
  compat shell
- Add direct ownership/delegation regressions
- Add focused helper-path tests for statement forwarding and error handling
- Add one dedicated `v10 -> v11` PostgreSQL repair test for MediaFiles table
  restoration

Out of scope:

- Changing `migrations.py`
- Rebinding `_convert_sqlite_sql_to_postgres_statements(...)`
- Altering `_MEDIA_FILES_TABLE_SQL`
- Changing MediaFiles repository behavior

## Why This Slice

`v11` is the last adjacent PostgreSQL migration body still owned by the legacy
module. After it, the remaining legacy-owned canonical methods are helper
bodies and broader domain surfaces rather than the linear migration-body run.

## Risks

### Per-Statement Error Handling

The current body catches `BackendDatabaseError` for each individual converted
statement and logs a warning before continuing. The helper must preserve that
behavior exactly.

### Outer Defensive Exception Swallowing

The outer `except _MEDIA_NONCRITICAL_EXCEPTIONS` path logs a warning and does
not re-raise. The helper must preserve that noncritical behavior.

### Converter Ownership Boundary

The helper should continue calling
`db._convert_sqlite_sql_to_postgres_statements(db._MEDIA_FILES_TABLE_SQL)`.
This tranche must not pull the conversion helper into scope.

## Test Strategy

Add three test layers:

1. Ownership regressions:
   - canonical `MediaDatabase._postgres_migrate_to_v11` no longer uses legacy
     globals
   - legacy `Media_DB_v2._postgres_migrate_to_v11` delegates through a live
     helper module reference

2. Focused helper-path tests:
   - converted statements are executed in order
   - per-statement `BackendDatabaseError` is swallowed and later statements
     still run
   - outer noncritical conversion failure is swallowed cleanly

3. Migration-path guard:
   - dedicated `v10 -> v11` PostgreSQL repair test that removes the `MediaFiles`
     table, downgrades schema version to `10`, reruns `_initialize_schema()`,
     and asserts `MediaFiles` is restored

## Success Criteria

- Canonical `MediaDatabase._postgres_migrate_to_v11` is package-owned
- Legacy `Media_DB_v2._postgres_migrate_to_v11` remains a live-module compat
  shell
- Focused helper-path tests pass
- Dedicated `v10 -> v11` migration-path test passes or skips cleanly when the
  Postgres fixture is unavailable
- Normalized ownership count drops from `208` to `207`
