# Media DB V2 Postgres Claims Migration Body Rebinding Design

## Summary

Rebind PostgreSQL migration body methods `v10` and `v17` onto a package-owned
helper module so the canonical `MediaDatabase` no longer owns those methods via
legacy globals, while preserving `Media_DB_v2` as a live-module compatibility
shell.

## Scope

In scope:

- Add a package helper module for `run_postgres_migrate_to_v10(...)` and
  `run_postgres_migrate_to_v17(...)`
- Rebind canonical `MediaDatabase._postgres_migrate_to_v10` and
  `_postgres_migrate_to_v17` in `media_database_impl.py`
- Convert legacy `Media_DB_v2` methods into live-module delegation shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests that prove both claims helper calls happen in
  order
- Reuse the existing PostgreSQL migration-path coverage that already downgrades
  to schema version `9` and verifies claims artifacts are restored by later
  migrations

Out of scope:

- Changing `migrations.py`
- Extracting `_ensure_postgres_claims_tables(...)`
- Extracting `_ensure_postgres_claims_extensions(...)`
- Altering claims schema SQL or claims domain behavior
- Touching `v11` MediaFiles migration behavior

## Why This Slice

`v10` and `v17` are the remaining paired thin delegate migration bodies in the
canonical class. They both call the same two claims ensure helpers:

- `_ensure_postgres_claims_tables(conn)`
- `_ensure_postgres_claims_extensions(conn)`

That makes them a good ownership-reduction slice without widening into the
claims helper bodies themselves.

## Risks

### Duplicate Claims Extension Invocation

`_ensure_postgres_claims_tables(conn)` already calls
`_ensure_postgres_claims_extensions(conn)` internally. The migration body also
calls `_ensure_postgres_claims_extensions(conn)` afterward. The helper must
preserve that exact order and duplicate call pattern, because it is the current
runtime behavior.

### Boundary Versus Behavior

This tranche should move canonical method ownership without changing the claims
helper bodies. The helper module must remain a thin orchestration layer.

### Compat Shell Integrity

`Media_DB_v2._postgres_migrate_to_v10` and `_postgres_migrate_to_v17` must
remain present as compatibility shells and delegate through a live module
reference so monkeypatch-style regression tests still have a stable seam.

## Test Strategy

Add three test layers:

1. Ownership regressions:
   - canonical `MediaDatabase._postgres_migrate_to_v10/_v17` no longer use
     legacy globals
   - legacy `Media_DB_v2` methods delegate through the helper module

2. Focused helper-path tests:
   - `run_postgres_migrate_to_v10(...)` invokes claims tables then claims
     extensions
   - `run_postgres_migrate_to_v17(...)` invokes claims tables then claims
     extensions

3. Broader migration-path guard:
   - reuse the existing `v9 -> v20` PostgreSQL migration repair test that
     verifies `claims_monitoring_events` is restored

## Success Criteria

- Canonical `MediaDatabase._postgres_migrate_to_v10` is package-owned
- Canonical `MediaDatabase._postgres_migrate_to_v17` is package-owned
- Legacy `Media_DB_v2._postgres_migrate_to_v10/_v17` remain live-module compat
  shells
- Focused helper-path tests pass
- Existing PostgreSQL migration/support bundle stays green or skips only for the
  environment-dependent Postgres fixture
- Normalized ownership count drops from `210` to `208`
