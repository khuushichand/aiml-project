# Media DB V2 Postgres Collections Migration Body Rebinding Design

**Status:** Proposed, review-derived, and ready for tranche planning on
2026-03-20.

**Goal:** Reduce canonical legacy ownership by rebinding PostgreSQL migration
body methods `v12` and `v13` onto package-owned helpers while keeping
`Media_DB_v2` as the explicit compat-shell surface and leaving
`_ensure_postgres_collections_tables(conn)` legacy-owned for now.

## Why This Tranche Exists

The previous `v14` and `v15` data-tables tranche proved the compat-shell
delegation pattern, but it was intentionally boundary-only and left the
normalized ownership count flat.

The next safe slice for real ownership reduction is the PostgreSQL
collections/content-items pair:

- `_postgres_migrate_to_v12(conn)`
- `_postgres_migrate_to_v13(conn)`

Both methods are currently thin delegates to one existing helper:

- `_ensure_postgres_collections_tables(conn)`

That makes them good candidates for the next step up in rigor:

- package-owned canonical class methods
- legacy compat shells preserved
- expected normalized ownership count drop of `2`

## Review Corrections Incorporated

### 1. Leave the migration registry alone

[`migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
already builds the PostgreSQL migration map from the active DB object's bound
methods. Rebasing the canonical class methods is enough for runtime ownership
to move; changing the registry would only add churn.

### 2. Separate canonical ownership from compat-shell behavior

This tranche has two distinct invariants:

- canonical `MediaDatabase._postgres_migrate_to_v12/_v13` are no longer
  legacy-owned
- legacy `Media_DB_v2._postgres_migrate_to_v12/_v13` still exist and delegate
  through a live module reference

Both must be tested directly.

### 3. Keep `_ensure_postgres_collections_tables(conn)` out of scope

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
still owns a broad PostgreSQL collections/content-items setup block inside
`_ensure_postgres_collections_tables(conn)`. Pulling that in now would widen
this slice into a larger collections bootstrap migration.

### 4. Keep migration semantics unchanged

Both extracted helpers should stay thin wrappers that call:

- `db._ensure_postgres_collections_tables(conn)`

This tranche changes ownership, not schema behavior.

## In Scope

- package-native helper module for PostgreSQL collections migration bodies
- canonical class rebinding for `_postgres_migrate_to_v12`
- canonical class rebinding for `_postgres_migrate_to_v13`
- live-module compat shells in `Media_DB_v2`
- direct regressions for ownership and compat-shell delegation
- focused Postgres migration/support verification

## Out Of Scope

- moving `_ensure_postgres_collections_tables(conn)`
- changing the migration registry/runner
- reworking the collections/content-items SQL body
- changing `v14+` migration bodies
- changing bootstrap coordinators
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Add one narrow package module for Postgres collections migration bodies

Introduce a package-owned helper module under the schema migration-bodies
package, for example:

- `schema/migration_bodies/postgres_collections.py`

That module should own:

- `run_postgres_migrate_to_v12(db, conn)`
- `run_postgres_migrate_to_v13(db, conn)`

Both remain thin wrappers that call `db._ensure_postgres_collections_tables(conn)`.

### B. Rebind only the canonical class methods

[`media_database_impl.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
should rebind:

- `MediaDatabase._postgres_migrate_to_v12`
- `MediaDatabase._postgres_migrate_to_v13`

to the new package helpers.

This is the change that should reduce the normalized legacy-owned canonical
method count.

### C. Keep `Media_DB_v2` as the compat shell

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
should continue defining:

- `_postgres_migrate_to_v12(conn)`
- `_postgres_migrate_to_v13(conn)`

but those methods should delegate through a live module reference using
`import_module(...)`, matching the established `v14`/`v15` shell pattern.

## Risks

### 1. False ownership win

If only the legacy shell methods change and the canonical class is not rebound,
the count will stay flat. The plan must make the canonical rebinding explicit.

### 2. Broken compat seam

If the legacy shell imports helper functions statically instead of calling
through a live module reference, monkeypatch-based delegation tests will stop
proving the shell contract.

### 3. Accidental widening into collections bootstrap work

Moving `_ensure_postgres_collections_tables(conn)` or its SQL body would turn
this into a much larger domain extraction. That is intentionally deferred.

## Required Tests

- ownership/delegation regressions in
  [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
- PostgreSQL support checks in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
- migration-path verification in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)

Direct regressions should prove:

- canonical `v12` is no longer legacy-owned
- canonical `v13` is no longer legacy-owned
- legacy `v12` delegates to the package helper
- legacy `v13` delegates to the package helper

## Success Criteria

- canonical `MediaDatabase._postgres_migrate_to_v12/_v13` are package-owned
- legacy `Media_DB_v2._postgres_migrate_to_v12/_v13` remain supported compat
  shells
- PostgreSQL migration/support suites stay green
- normalized ownership count drops by `2`

## Recommended Next Tranche

1. Add focused regressions for canonical ownership and legacy-shell delegation.
2. Add the package-native collections migration-body helper module.
3. Rebind canonical `v12` and `v13` in `media_database_impl.py`.
4. Convert legacy `v12` and `v13` to live-module compat shells.
5. Verify with focused Postgres support, migration, regression, Bandit, and
   ownership-count checks.
