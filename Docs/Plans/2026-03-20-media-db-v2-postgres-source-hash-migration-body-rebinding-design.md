# Media DB V2 Postgres Source-Hash Migration Body Rebinding Design

**Status:** Proposed, review-derived, and ready for tranche planning on
2026-03-20.

**Goal:** Reduce canonical legacy ownership by rebinding PostgreSQL migration
body method `v16` onto a package-owned helper while keeping `Media_DB_v2` as
the explicit compat-shell surface and leaving
`_ensure_postgres_source_hash_column(conn)` legacy-owned.

## Why This Tranche Exists

The completed `v12`/`v13` collections tranche proved the ownership-reduction
pattern for thin PostgreSQL migration bodies:

- add a package helper
- rebind the canonical `MediaDatabase` method
- preserve the legacy `Media_DB_v2` method as a live-module compat shell

The next safest adjacent candidate is:

- `_postgres_migrate_to_v16(conn)`

It is currently a one-line delegate in
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
that calls:

- `_ensure_postgres_source_hash_column(conn)`

Unlike `v17`, `v18`, `v19`, `v20`, or `v21`, it does not fan into claims,
sequence sync, FTS/RLS, TTS history, or inline index SQL.

## Review Corrections Incorporated

### 1. Add one direct `v16` behavior check

The broad PostgreSQL support and migration suites do not currently isolate the
`v16` source-hash path. This tranche therefore needs one small focused behavior
test in addition to the ownership/delegation regressions, so the slice proves
more than just the seam movement.

### 2. Keep `_ensure_postgres_source_hash_column(conn)` out of scope

The helper body at
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
already has schema-bootstrap coverage and should remain untouched here. This
tranche moves only the migration-body ownership.

### 3. Leave the registry and runner alone

[`migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
already binds migration methods from the active DB object. Rebasing canonical
`v16` is enough; changing the registry would only add churn.

## In Scope

- package-native helper module for PostgreSQL source-hash migration body `v16`
- canonical class rebinding for `_postgres_migrate_to_v16`
- live-module compat shell for legacy `_postgres_migrate_to_v16`
- direct ownership/delegation regressions for `v16`
- one focused source-hash behavior check
- focused Postgres verification and ownership recount

## Out Of Scope

- moving `_ensure_postgres_source_hash_column(conn)`
- changing the migration registry/runner
- changing source-hash schema SQL
- touching `v17+` migration bodies
- changing bootstrap coordinators
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Add one narrow package module for the `v16` migration body

Introduce a package-owned helper module under the schema migration-bodies
package, for example:

- `schema/migration_bodies/postgres_source_hash.py`

That module should own:

- `run_postgres_migrate_to_v16(db, conn)`

It should stay a thin wrapper around:

- `db._ensure_postgres_source_hash_column(conn)`

### B. Rebind only the canonical class method

[`media_database_impl.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
should rebind:

- `MediaDatabase._postgres_migrate_to_v16`

to the new package helper. This is the ownership-reduction step for the
canonical class.

### C. Keep `Media_DB_v2` as the compat shell

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
should continue defining `_postgres_migrate_to_v16(conn)`, but that method
should delegate through a live module reference using `import_module(...)`,
matching the established `v12`-`v15` compat-shell pattern.

## Risks

### 1. False confidence from broad suites

The broader Postgres migration/support suites are useful guards, but they do
not currently isolate `v16`. Without one focused behavior test, the tranche
would mostly prove ownership movement rather than source-hash migration intent.

### 2. Accidental widening into source-hash bootstrap work

Pulling `_ensure_postgres_source_hash_column(conn)` into this slice would widen
the change from one migration body into shared bootstrap behavior.

### 3. Flat ownership count

If only the legacy shell changes and the canonical class is not rebound, the
count will stay flat. The plan must keep the canonical rebinding explicit.

## Required Tests

- ownership/delegation regressions in
  [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
- focused source-hash behavior test in either:
  - [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py), or
  - [`test_media_db_schema_bootstrap.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
- PostgreSQL support checks in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
- migration-path verification in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)

Direct regressions should prove:

- canonical `v16` is no longer legacy-owned
- legacy `v16` delegates to the package helper

## Success Criteria

- canonical `MediaDatabase._postgres_migrate_to_v16` is package-owned
- legacy `Media_DB_v2._postgres_migrate_to_v16` remains a supported compat shell
- the source-hash behavior check passes
- PostgreSQL migration/support suites stay green
- normalized ownership count drops by `1`

## Recommended Next Tranche

1. Add focused regressions for canonical ownership and legacy-shell delegation.
2. Add the package-native source-hash migration-body helper module.
3. Rebind canonical `v16` in `media_database_impl.py`.
4. Convert legacy `v16` to a live-module compat shell.
5. Verify with focused Postgres support, migration, regression, Bandit, and
   ownership-count checks.
