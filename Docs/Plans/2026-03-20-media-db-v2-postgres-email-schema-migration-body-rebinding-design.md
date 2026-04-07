# Media DB v2 Postgres Email Schema Migration Body Rebinding Design

Date: 2026-03-20
Branch: `codex/media-db-v2-stage1-caller-first`

## Summary

Extract PostgreSQL migration body `v22` from legacy canonical-method ownership while
preserving the `Media_DB_v2` compat shell.

This tranche is a real ownership-reduction slice for exactly one migration body:
`_postgres_migrate_to_v22`.

## Why This Slice

`_postgres_migrate_to_v22` is the next adjacent migration body after the completed
`v16`, `v18`, `v19`, `v20`, and `v21` rebinding work. Unlike `v21`, the `v22`
migration body is a thin delegate:

- `_postgres_migrate_to_v22(self, conn)` only calls `_ensure_postgres_email_schema(conn)`

That makes the migration body itself a good ownership-reduction candidate, while
the broader email-native helper remains intentionally out of scope.

## In Scope

- Add a package-owned helper module for `v22`
- Rebind canonical `MediaDatabase._postgres_migrate_to_v22` in
  `media_database_impl.py`
- Keep `Media_DB_v2._postgres_migrate_to_v22` as a live-module compat shell
- Add direct ownership and delegation regressions
- Add a focused helper behavior test
- Add one dedicated Postgres migration-path test that proves `21 -> 22` restores
  stable email-native artifacts

## Out of Scope

- Any changes to `_ensure_postgres_email_schema(conn)`
- Any changes to `migrations.py`
- Any broader email-native schema refactor
- Any caller migrations

## Design

### Helper Module

Add a package-owned migration-body helper module:

- `media_db/schema/migration_bodies/postgres_email_schema.py`

The helper will expose:

- `run_postgres_migrate_to_v22(db, conn)`

Its behavior should remain minimal and exact:

1. Call `db._ensure_postgres_email_schema(conn)`

No email-native SQL or schema behavior should change in this tranche.

### Canonical Rebinding

Rebind only the canonical class method in `media_database_impl.py`:

- `MediaDatabase._postgres_migrate_to_v22 = run_postgres_migrate_to_v22`

This is what reduces normalized legacy-owned canonical-method count by 1.

### Legacy Compat Shell

Keep `Media_DB_v2._postgres_migrate_to_v22` present, but convert it into a
live-module compat shell using `import_module(...)`, matching the pattern already
used for `v12`, `v13`, `v16`, `v18`, `v19`, `v20`, and `v21`.

That preserves the legacy import and monkeypatch seam without leaving runtime
ownership on the legacy canonical class.

## Tests

### Direct Regressions

Add to `test_media_db_v2_regressions.py`:

- canonical `MediaDatabase._postgres_migrate_to_v22` no longer uses legacy globals
- legacy `Media_DB_v2._postgres_migrate_to_v22` delegates through the package helper

### Focused Helper Behavior

Add a unit test to `test_media_db_schema_bootstrap.py` that proves
`run_postgres_migrate_to_v22(db, conn)` invokes `db._ensure_postgres_email_schema(conn)`.

### Migration-Path Guard

Add one dedicated integration test to `test_media_postgres_migrations.py`:

- downgrade schema version to `21`
- remove a stable email-native table/index signal
- run `db._initialize_schema()`
- assert the signal is restored and schema version reaches current

Use stable artifacts already reflected in existing email-native tests:

- `email_sources`
- `idx_email_messages_tenant_date_id`

The exact downgrade mechanics should be chosen to minimize brittleness while still
proving the `v22` path executed.

## Success Criteria

- `MediaDatabase._postgres_migrate_to_v22` is package-owned
- `Media_DB_v2._postgres_migrate_to_v22` remains a compat shell
- focused helper behavior test passes
- dedicated Postgres `v22` migration-path test passes or skips only when Postgres
  is unavailable in the test environment
- broader Postgres support/migration/regression bundle stays green
- normalized ownership count drops by `1`

Expected ownership delta:

- `218 -> 217`

## Risks

### Over-scoping into email-native schema logic

`_ensure_postgres_email_schema(conn)` is broad and replays many statements. Pulling
that helper body into this tranche would widen the task far beyond one migration body.

### Brittle migration-path assertion

The dedicated `21 -> 22` test should assert only stable email-native artifacts.
Testing too much of the email-native surface would make the tranche noisier than
necessary.

### False-positive migration coverage

If the migration-path test does not remove a real `v22` artifact first, the test
can pass without proving that `v22` restored anything.
