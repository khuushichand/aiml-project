# Media DB v2 Postgres Early Schema Migration Body Rebinding Design

Date: 2026-03-21
Branch: `codex/media-db-v2-stage1-caller-first`

## Summary

Extract the remaining early PostgreSQL migration bodies `v5` through `v8` from
legacy canonical-method ownership while preserving the `Media_DB_v2` compat shell.

This tranche is a real ownership-reduction slice for exactly four migration bodies:

- `_postgres_migrate_to_v5`
- `_postgres_migrate_to_v6`
- `_postgres_migrate_to_v7`
- `_postgres_migrate_to_v8`

## Why This Slice

After rebinding `v12` through `v22` and then converting `v14`/`v15` into real
ownership reduction, the remaining Postgres migration bodies split into three
groups:

- `v5` through `v8`: narrow early schema primitives
- `v9`: wider constraint/backfill/index work
- `v10` / `v11`: claims and MediaFiles domain work

`v5` through `v8` are the cleanest next ownership-reduction cluster because they
remain relatively self-contained and avoid claims, email-native, MediaFiles, and
other wider domain helpers.

## In Scope

- Add a package-owned helper module for `v5` through `v8`
- Rebind canonical `MediaDatabase._postgres_migrate_to_v5/_v6/_v7/_v8` in
  `media_database_impl.py`
- Keep `Media_DB_v2` methods as live-module compat shells
- Add direct ownership and delegation regressions
- Add focused helper behavior tests for the package helper entrypoints
- Reuse existing Postgres migration/support tests for behavior verification

## Out of Scope

- `v9`
- `v10` / `v11`
- `_get_postgres_migrations()` or `_run_postgres_migrations()`
- Any broader bootstrap extraction
- Any changes to helper bodies outside these four migration methods

## Design

### Helper Module

Add a package-owned migration-body helper module:

- `media_db/schema/migration_bodies/postgres_early_schema.py`

The helper module will expose:

- `run_postgres_migrate_to_v5(db, conn)`
- `run_postgres_migrate_to_v6(db, conn)`
- `run_postgres_migrate_to_v7(db, conn)`
- `run_postgres_migrate_to_v8(db, conn)`

Its behavior should mirror the existing legacy methods exactly:

- `v5`: add `safe_metadata` to `documentversions`
- `v6`: create `documentversionidentifiers` plus indexes
- `v7`: create `documentstructureindex` plus indexes
- `v8`: add `org_id` / `team_id` to `media` and `sync_log`

No SQL, identifier, or branching behavior should change in this tranche.

### Canonical Rebinding

Rebind only the canonical class methods in `media_database_impl.py`:

- `MediaDatabase._postgres_migrate_to_v5 = run_postgres_migrate_to_v5`
- `MediaDatabase._postgres_migrate_to_v6 = run_postgres_migrate_to_v6`
- `MediaDatabase._postgres_migrate_to_v7 = run_postgres_migrate_to_v7`
- `MediaDatabase._postgres_migrate_to_v8 = run_postgres_migrate_to_v8`

This is what reduces normalized legacy-owned canonical-method count by 4.

### Legacy Compat Shells

Keep `Media_DB_v2._postgres_migrate_to_v5/_v6/_v7/_v8` present, but convert them
into live-module compat shells using `import_module(...)`, matching the pattern
already used for the later migration bodies.

## Tests

### Direct Regressions

Add or revise tests in `test_media_db_v2_regressions.py` so that each of:

- `v5`
- `v6`
- `v7`
- `v8`

asserts:

1. canonical method no longer uses legacy globals
2. legacy method delegates through the package helper

### Focused Helper Behavior

Add focused helper-path tests in `test_media_db_schema_bootstrap.py` or an
equivalent DB-management test file:

- `v5` adds `safe_metadata`
- `v6` issues identifier-table creation plus expected index statements
- `v7` issues structure-index table creation plus expected index statements
- `v8` issues scope-column additions for both `media` and `sync_log`

These should be backend-stub tests, not integration tests.

### Migration-Path Guard

Reuse the existing migration-path coverage already present:

- `test_media_postgres_migration_adds_safe_metadata`
- `test_postgres_migrate_to_v6_creates_identifier_table`

If `v7` or `v8` need tighter behavior guarantees after the red phase, add
small focused tests rather than a broad new integration bundle.

## Success Criteria

- canonical `v5` through `v8` methods are package-owned
- legacy `Media_DB_v2` methods remain compat shells
- focused helper behavior tests pass
- existing Postgres migration/support tests stay green
- normalized ownership count drops by `4`

Expected ownership delta:

- `215 -> 211`

## Risks

### Over-clustering

`v5` through `v8` are a coherent early-schema tranche, but `v9` is already
meaningfully wider. Do not silently pull `v9` into this slice.

### SQL drift

These helpers should preserve the current SQL exactly. Cleanup of SQL formatting
or identifier conventions belongs in a later hardening pass.

### Partial coverage

`v6` has direct support coverage already, while `v7` and `v8` lean more on
focused helper tests. If additional red signals appear, add the smallest
possible behavior check rather than widening the tranche.
