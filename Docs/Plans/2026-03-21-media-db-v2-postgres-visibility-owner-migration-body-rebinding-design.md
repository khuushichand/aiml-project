# Media DB V2 Postgres Visibility/Owner Migration Body Rebinding Design

**Status:** Proposed, review-corrected, and ready for tranche planning on
2026-03-21.

**Goal:** Reduce canonical legacy ownership by rebinding PostgreSQL migration
body method `v9` onto a package-owned helper while keeping `Media_DB_v2` as the
explicit compat-shell surface and leaving the broader visibility/share runtime
behavior untouched.

## Why This Tranche Exists

After completing the `v5` through `v8` early-schema tranche, the next remaining
adjacent PostgreSQL migration body is:

- `_postgres_migrate_to_v9(conn)`

It is the narrowest remaining migration body before the wider claims and
MediaFiles domain work in `v10` and `v11`, but it is still more complex than
the thin single-delegate slices like `v16`, `v18`, or `v20`.

`v9` is a multi-step body that currently:

- adds `visibility`
- adds the `chk_media_visibility` constraint
- adds `owner_user_id`
- backfills `owner_user_id` from numeric `client_id`
- creates `idx_media_visibility`
- creates `idx_media_owner_user_id`

That makes `v9` the right next slice, but only if it is designed as one
ordered multi-statement helper body rather than framed like a one-line delegate.

## Review Corrections Incorporated

### 1. Treat `v9` as a multi-step helper body

This is not another thin-wrapper tranche. The package helper must preserve the
ordered statement sequence inside the migration body, especially around the
constraint and backfill logic.

### 2. Add exact SQL-order helper coverage

A helper-path test must assert the emitted SQL order, not just that some
statements were executed. That is the only reliable way to catch regressions
where indexes or backfill run before their prerequisite columns exist.

### 3. Add a dedicated `v8 -> v9` migration-path repair test

The broader PostgreSQL migration suite does not currently isolate `v9`. This
tranche therefore requires one dedicated migration-path test that downgrades to
schema version `8`, removes `visibility`, `owner_user_id`, and
`idx_media_visibility`, reruns `_initialize_schema()`, and asserts restoration.

### 4. Keep the migration registry untouched

[`migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
already binds migration methods from the active DB object. Rebasing canonical
`v9` is enough; changing the registry would only add churn.

## In Scope

- package-native helper module for PostgreSQL migration body `v9`
- canonical class rebinding for `_postgres_migrate_to_v9`
- live-module compat shell for legacy `_postgres_migrate_to_v9`
- direct ownership and delegation regressions for `v9`
- one exact-order helper behavior test for the full SQL sequence
- one dedicated `v8 -> v9` PostgreSQL repair test
- focused verification and ownership recount

## Out Of Scope

- `v10`, `v11`, or `v17`
- changing the migration registry/runner
- changing share/visibility endpoint behavior
- changing `_CURRENT_SCHEMA_VERSION`
- broader bootstrap extraction
- refactoring `_ensure_postgres_rls` or later policy logic

## Target Architecture

### A. Add one narrow package module for the `v9` migration body

Introduce a package-owned helper module under the schema migration-bodies
package, for example:

- `schema/migration_bodies/postgres_visibility_owner.py`

That module should own:

- `run_postgres_migrate_to_v9(db, conn)`

It should preserve the current body semantics exactly, including:

- lower-case identifier usage through `backend.escape_identifier`
- the `DO $$ ... $$` constraint block
- the numeric `client_id` backfill `UPDATE`
- both index statements

### B. Rebind only the canonical class method

[`media_database_impl.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
should rebind:

- `MediaDatabase._postgres_migrate_to_v9`

to the new package helper. This is the ownership-reduction step for the
canonical class.

### C. Keep `Media_DB_v2` as the compat shell

[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
should continue defining `_postgres_migrate_to_v9(conn)`, but that method
should delegate through a live module reference using `import_module(...)`,
matching the established compat-shell pattern.

## Risks

### 1. Incorrect SQL ordering

If the helper-path test only checks partial output, the tranche can regress the
constraint/backfill/index order without detection.

### 2. Silent widening into share-policy work

This tranche moves only the migration body. It should not evolve into later RLS
or runtime visibility behavior.

### 3. False confidence from broad migration coverage

Without a dedicated `v8 -> v9` repair test, this slice would prove seam
movement more clearly than migration-body behavior.

## Required Tests

- ownership/delegation regressions in
  [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
- exact-order helper behavior test in
  [`test_media_db_schema_bootstrap.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
- dedicated `v8 -> v9` repair test in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
- focused PostgreSQL support checks in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)

Direct regressions should prove:

- canonical `v9` is no longer legacy-owned
- legacy `v9` delegates to the package helper

## Success Criteria

- canonical `MediaDatabase._postgres_migrate_to_v9` is package-owned
- legacy `Media_DB_v2._postgres_migrate_to_v9` remains a supported compat shell
- the helper-path test proves the exact SQL order for `v9`
- the dedicated `v8 -> v9` migration-path test passes or skips cleanly when the
  local Postgres backend is unavailable
- normalized ownership count drops by `1`

Expected ownership delta:

- `211 -> 210`

## Recommended Next Tranche

1. Add direct regressions for canonical ownership and legacy-shell delegation.
2. Add the package-native visibility/owner migration-body helper module.
3. Rebind canonical `v9` in `media_database_impl.py`.
4. Convert legacy `v9` to a live-module compat shell.
5. Add one exact-order helper behavior test for the full SQL sequence.
6. Add one dedicated `v8 -> v9` PostgreSQL repair test.
7. Verify with focused regression, bootstrap, support, migration, Bandit, and
   ownership-count checks.
