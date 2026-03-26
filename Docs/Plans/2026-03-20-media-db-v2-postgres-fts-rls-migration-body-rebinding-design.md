# Media DB V2 Postgres FTS-RLS Migration Body Rebinding Design

**Status:** Proposed, review-derived, and ready for tranche planning on
2026-03-20.

**Goal:** Reduce canonical legacy ownership by rebinding PostgreSQL migration
body method `v19` onto a package-owned helper while keeping `Media_DB_v2` as
the explicit compat-shell surface and leaving both
`_ensure_postgres_fts(conn)` and `_ensure_postgres_rls(conn)` legacy-owned.

## Why This Tranche Exists

The completed `v16`, `v18`, and `v20` tranches confirmed the narrow
ownership-reduction pattern for thin PostgreSQL migration bodies:

- add a package helper
- rebind the canonical `MediaDatabase` method
- preserve the legacy `Media_DB_v2` method as a live-module compat shell
- add one focused helper behavior test when the broader migration suite does not
  isolate the body sufficiently

The next remaining migration-body candidate is:

- `_postgres_migrate_to_v19(conn)`

It differs from the last three tranches because it is a paired-helper body:

- `_ensure_postgres_fts(conn)`
- `_ensure_postgres_rls(conn)`

So this tranche is still narrow, but it must explicitly treat `v19` as a
two-helper migration body rather than a single-delegate migration body.

## Review Corrections Incorporated

### 1. Treat `v19` as a paired-helper body

This slice should not pretend `v19` is as narrow as `v20`. It owns one
migration-body method but delegates into both FTS and RLS ensures, so the
helper module and focused behavior test must cover both calls.

### 2. Keep `_ensure_postgres_fts(conn)` and `_ensure_postgres_rls(conn)` out of scope

Both helpers remain legacy-owned in
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py).
This tranche moves only the migration-body ownership, not the underlying FTS or
RLS implementation.

### 3. Leave the registry and runner alone

[`migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
already binds migration methods from the active DB object. Rebasing canonical
`v19` is enough; changing the registry would only add churn.

## In Scope

- package-native helper module for PostgreSQL FTS/RLS migration body `v19`
- canonical class rebinding for `_postgres_migrate_to_v19`
- live-module compat shell for legacy `_postgres_migrate_to_v19`
- direct ownership/delegation regressions for `v19`
- one focused helper behavior check asserting both FTS and RLS delegation
- focused Postgres verification and ownership recount

## Out Of Scope

- moving `_ensure_postgres_fts(conn)`
- moving `_ensure_postgres_rls(conn)`
- changing FTS or RLS SQL / backend behavior
- changing the migration registry/runner
- touching `v21` or `v22`
- changing bootstrap coordinators
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Add one package module for the paired `v19` migration body

Introduce a package-owned helper module under the schema migration-bodies
package, for example:

- `schema/migration_bodies/postgres_fts_rls.py`

That module should own:

- `run_postgres_migrate_to_v19(db, conn)`

It should stay a thin wrapper around:

- `db._ensure_postgres_fts(conn)`
- `db._ensure_postgres_rls(conn)`

### B. Rebind only the canonical class method

[`media_database_impl.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
should rebind:

- `MediaDatabase._postgres_migrate_to_v19`

to the new package helper. This is the ownership-reduction step for the
canonical class.

### C. Keep `Media_DB_v2` as the compat shell

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
should continue defining `_postgres_migrate_to_v19(conn)`, but that method
should delegate through a live module reference using `import_module(...)`,
matching the established compat-shell pattern from the earlier migration-body
tranches.

## Risks

### 1. Understating the blast radius

`v19` touches both FTS and RLS, so the focused helper behavior test must assert
both calls. Treating this like a one-helper body would leave the tranche
under-specified.

### 2. Accidental widening into FTS or RLS implementation work

Pulling either `_ensure_postgres_fts(conn)` or `_ensure_postgres_rls(conn)` into
this slice would widen the change from one migration body into substantive
schema/policy behavior.

### 3. Flat ownership count

If only the legacy shell changes and the canonical class is not rebound, the
count will stay flat. The plan must keep the canonical rebinding explicit.

## Required Tests

- ownership/delegation regressions in
  [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
- focused helper behavior test in
  [`test_media_db_schema_bootstrap.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
  or another narrowly scoped DB-management test file
- migration-path verification in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
- PostgreSQL support checks in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)

Direct regressions should prove:

- canonical `v19` is no longer legacy-owned
- legacy `v19` delegates to the package helper

The focused helper behavior test should prove:

- `run_postgres_migrate_to_v19(db, conn)` invokes both
  `_ensure_postgres_fts(conn)` and `_ensure_postgres_rls(conn)` in order

## Success Criteria

- canonical `MediaDatabase._postgres_migrate_to_v19` is package-owned
- legacy `Media_DB_v2._postgres_migrate_to_v19` remains a supported compat shell
- the focused FTS/RLS helper behavior check passes
- PostgreSQL migration/support suites stay green
- normalized ownership count drops by `1`

## Recommended Next Tranche

1. Add focused regressions for canonical ownership and legacy-shell delegation.
2. Add the package-native FTS/RLS migration-body helper module.
3. Rebind canonical `v19` in `media_database_impl.py`.
4. Convert legacy `v19` to a live-module compat shell.
5. Add one focused helper behavior test covering both FTS and RLS delegation.
6. Verify with focused Postgres support, migration, regression, Bandit, and
   ownership-count checks.
