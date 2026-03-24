# Media DB V2 Postgres TTS-History Migration Body Rebinding Design

**Status:** Proposed, review-derived, and ready for tranche planning on
2026-03-20.

**Goal:** Reduce canonical legacy ownership by rebinding PostgreSQL migration
body method `v20` onto a package-owned helper while keeping `Media_DB_v2` as
the explicit compat-shell surface and leaving
`_ensure_postgres_tts_history(conn)` legacy-owned.

## Why This Tranche Exists

The completed `v16` and `v18` tranches confirmed the narrow ownership-reduction
pattern for thin PostgreSQL migration bodies:

- add a package helper
- rebind the canonical `MediaDatabase` method
- preserve the legacy `Media_DB_v2` method as a live-module compat shell
- add one focused helper behavior test when the broader migration suite does not
  isolate the body sufficiently

The next safest adjacent candidate is:

- `_postgres_migrate_to_v20(conn)`

It is currently a one-line delegate in
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
that calls:

- `_ensure_postgres_tts_history(conn)`

Unlike `v19`, it does not widen into both FTS and RLS behavior in the same
slice.

## Review Corrections Incorporated

### 1. Add one direct `v20` helper behavior check

[`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
already reaches schema `v20`, but it does not isolate the `v20` helper path as
tightly as these narrow migration-body tranches need. This tranche therefore
includes one focused helper behavior test proving the package helper calls
`db._ensure_postgres_tts_history(conn)`.

### 2. Keep `_ensure_postgres_tts_history(conn)` out of scope

The helper body at
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
is shared bootstrap/schema behavior and should remain untouched here. This
tranche moves only the migration-body ownership.

### 3. Leave the registry and runner alone

[`migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
already binds migration methods from the active DB object. Rebasing canonical
`v20` is enough; changing the registry would only add churn.

## In Scope

- package-native helper module for PostgreSQL TTS-history migration body `v20`
- canonical class rebinding for `_postgres_migrate_to_v20`
- live-module compat shell for legacy `_postgres_migrate_to_v20`
- direct ownership/delegation regressions for `v20`
- one focused TTS-history helper behavior check
- focused Postgres verification and ownership recount

## Out Of Scope

- moving `_ensure_postgres_tts_history(conn)`
- changing the migration registry/runner
- changing TTS-history schema SQL or backend behavior
- touching `v19`, `v21`, or `v22` migration bodies
- changing bootstrap coordinators
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Add one narrow package module for the `v20` migration body

Introduce a package-owned helper module under the schema migration-bodies
package, for example:

- `schema/migration_bodies/postgres_tts_history.py`

That module should own:

- `run_postgres_migrate_to_v20(db, conn)`

It should stay a thin wrapper around:

- `db._ensure_postgres_tts_history(conn)`

### B. Rebind only the canonical class method

[`media_database_impl.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
should rebind:

- `MediaDatabase._postgres_migrate_to_v20`

to the new package helper. This is the ownership-reduction step for the
canonical class.

### C. Keep `Media_DB_v2` as the compat shell

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
should continue defining `_postgres_migrate_to_v20(conn)`, but that method
should delegate through a live module reference using `import_module(...)`,
matching the established `v12`-`v18` compat-shell pattern.

## Risks

### 1. False confidence from broad suites

The broader Postgres migration suite reaches `v20`, but without one focused
helper test this tranche would still prove seam movement more clearly than
helper intent.

### 2. Accidental widening into TTS-history implementation work

Pulling `_ensure_postgres_tts_history(conn)` into this slice would widen the
change from one migration body into shared schema/bootstrap behavior.

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

- canonical `v20` is no longer legacy-owned
- legacy `v20` delegates to the package helper

## Success Criteria

- canonical `MediaDatabase._postgres_migrate_to_v20` is package-owned
- legacy `Media_DB_v2._postgres_migrate_to_v20` remains a supported compat shell
- the focused TTS-history helper behavior check passes
- PostgreSQL migration/support suites stay green
- normalized ownership count drops by `1`

## Recommended Next Tranche

1. Add focused regressions for canonical ownership and legacy-shell delegation.
2. Add the package-native TTS-history migration-body helper module.
3. Rebind canonical `v20` in `media_database_impl.py`.
4. Convert legacy `v20` to a live-module compat shell.
5. Add one focused helper behavior test.
6. Verify with focused Postgres support, migration, regression, Bandit, and
   ownership-count checks.
