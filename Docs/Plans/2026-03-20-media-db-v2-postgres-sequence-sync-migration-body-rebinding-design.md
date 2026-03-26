# Media DB V2 Postgres Sequence-Sync Migration Body Rebinding Design

**Status:** Proposed, review-derived, and ready for tranche planning on
2026-03-20.

**Goal:** Reduce canonical legacy ownership by rebinding PostgreSQL migration
body method `v18` onto a package-owned helper while keeping `Media_DB_v2` as
the explicit compat-shell surface and leaving
`_sync_postgres_sequences(conn)` legacy-owned.

## Why This Tranche Exists

The completed `v16` source-hash tranche confirmed the narrow ownership-reduction
pattern for thin PostgreSQL migration bodies:

- add a package helper
- rebind the canonical `MediaDatabase` method
- preserve the legacy `Media_DB_v2` method as a live-module compat shell
- add one focused helper behavior test when the broader migration suite does not
  isolate the body sufficiently

The next safest adjacent candidate is:

- `_postgres_migrate_to_v18(conn)`

It is currently a one-line delegate in
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
that calls:

- `_sync_postgres_sequences(conn)`

Unlike `v19`, `v20`, `v21`, or `v22`, it does not widen into FTS/RLS, TTS
history, inline index SQL, or email schema setup.

## Review Corrections Incorporated

### 1. Add one direct `v18` helper behavior check

[`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
already covers the broader sequence-sync migration path, but it does not
isolate `v18` as tightly as the `v16` tranche isolated its helper path. This
tranche therefore includes one small focused helper behavior test proving the
package helper calls `db._sync_postgres_sequences(conn)`.

### 2. Keep `_sync_postgres_sequences(conn)` out of scope

The helper body at
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
is a larger SQL-backed method and should remain untouched here. This tranche
moves only the migration-body ownership.

### 3. Leave the registry and runner alone

[`migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
already binds migration methods from the active DB object. Rebasing canonical
`v18` is enough; changing the registry would only add churn.

## In Scope

- package-native helper module for PostgreSQL sequence-sync migration body `v18`
- canonical class rebinding for `_postgres_migrate_to_v18`
- live-module compat shell for legacy `_postgres_migrate_to_v18`
- direct ownership/delegation regressions for `v18`
- one focused sequence-sync helper behavior check
- focused Postgres verification and ownership recount

## Out Of Scope

- moving `_sync_postgres_sequences(conn)`
- changing the migration registry/runner
- changing sequence-sync SQL or backend behavior
- touching `v19+` migration bodies
- changing bootstrap coordinators
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Add one narrow package module for the `v18` migration body

Introduce a package-owned helper module under the schema migration-bodies
package, for example:

- `schema/migration_bodies/postgres_sequence_sync.py`

That module should own:

- `run_postgres_migrate_to_v18(db, conn)`

It should stay a thin wrapper around:

- `db._sync_postgres_sequences(conn)`

### B. Rebind only the canonical class method

[`media_database_impl.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
should rebind:

- `MediaDatabase._postgres_migrate_to_v18`

to the new package helper. This is the ownership-reduction step for the
canonical class.

### C. Keep `Media_DB_v2` as the compat shell

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
should continue defining `_postgres_migrate_to_v18(conn)`, but that method
should delegate through a live module reference using `import_module(...)`,
matching the established `v12`-`v16` compat-shell pattern.

## Risks

### 1. False confidence from broad suites

The broader Postgres migration suite covers sequence-sync behavior, but without
one focused helper test this tranche would still prove seam movement more
clearly than helper intent.

### 2. Accidental widening into sequence-sync implementation work

Pulling `_sync_postgres_sequences(conn)` into this slice would widen the change
from one migration body into shared SQL and backend behavior.

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

- canonical `v18` is no longer legacy-owned
- legacy `v18` delegates to the package helper

## Success Criteria

- canonical `MediaDatabase._postgres_migrate_to_v18` is package-owned
- legacy `Media_DB_v2._postgres_migrate_to_v18` remains a supported compat shell
- the focused sequence-sync helper behavior check passes
- PostgreSQL migration/support suites stay green
- normalized ownership count drops by `1`

## Recommended Next Tranche

1. Add focused regressions for canonical ownership and legacy-shell delegation.
2. Add the package-native sequence-sync migration-body helper module.
3. Rebind canonical `v18` in `media_database_impl.py`.
4. Convert legacy `v18` to a live-module compat shell.
5. Add one focused helper behavior test.
6. Verify with focused Postgres support, migration, regression, Bandit, and
   ownership-count checks.
