# Media DB V2 Postgres RLS Helper Rebinding Design

## Summary

After the bootstrap-dispatch tranche, the normalized legacy ownership count is
`11`. The cleanest remaining non-constructor, non-rollback slice is the
PostgreSQL RLS pair:

- `_postgres_policy_exists(...)`
- `_ensure_postgres_rls(...)`

These methods are still legacy-owned, but they are already used through package
bootstrap and runtime-factory seams. Moving them into a package-owned schema
helper reduces ownership without pulling in schema-v1 setup, SQLite bootstrap,
or rollback coordination.

## Current Method Shape

`_postgres_policy_exists(...)` currently owns:

- `pg_policies` probe SQL
- `result.rows` truthiness handling
- warning-and-false fallback on `BackendDatabaseError`

`_ensure_postgres_rls(...)` currently owns:

- visibility-aware predicate construction for `media`
- sync-log scope predicate construction
- old media policy cleanup
- `ENABLE/FORCE ROW LEVEL SECURITY` on `media` and `sync_log`
- media policy drop/recreate behavior
- sync-log policy create-if-missing behavior
- warning-and-continue behavior for backend failures

## Why This Slice Is Safe

This is a bounded Postgres-only helper cluster:

- no constructor or connection-lifecycle logic
- no schema-version/bootstrap dispatch logic
- no rollback/version restore coordination
- existing tests already touch the policy probe seam and the migration/bootstrap
  caller paths

That makes it safer than the remaining legacy-owned surfaces:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `_ensure_postgres_claims_tables(...)`
- `_ensure_postgres_collections_tables(...)`
- `_ensure_postgres_claims_extensions(...)`
- `rollback_to_version(...)`

## Risks To Pin

### 1. Policy probe failures must remain non-fatal

`_postgres_policy_exists(...)` intentionally returns `False` when inspection
fails. The runtime validation path depends on that behavior.

### 2. Media policy recreation must remain unconditional

The new `media_visibility_access` policy is dropped and recreated every run to
ensure predicate updates apply. That is different from the sync-log policies,
which are only created when missing.

### 3. Old media policy cleanup must stay conditional

The legacy `media_scope_*` policies should only be dropped when the probe says
they exist. This prevents unnecessary backend noise and keeps the helper
idempotent.

## Recommended Tranche

Move only:

- `_postgres_policy_exists(...)`
- `_ensure_postgres_rls(...)`

Defer:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `_ensure_postgres_claims_tables(...)`
- `_ensure_postgres_collections_tables(...)`
- `_ensure_postgres_claims_extensions(...)`
- `rollback_to_version(...)`

## Design

Add one package-owned schema helper module:

- `tldw_Server_API/app/core/DB_Management/media_db/schema/features/postgres_rls.py`

It should expose:

- `_postgres_policy_exists(...)`
- `_ensure_postgres_rls(...)`

Then:

- rebind canonical `MediaDatabase` methods in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy methods in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into live-module compat shells

No caller modules should change. `schema/features/policies.py` should continue
to call `db._ensure_postgres_rls(conn)`; canonical rebinding will satisfy that
contract.

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical methods no longer using legacy globals
- legacy methods delegating through the new schema helper module

### Focused helper coverage

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_postgres_rls_ops.py`

Pin:

- canonical helper rebinding
- successful policy probe behavior
- false-on-probe-error behavior
- conditional old-policy drops
- unconditional media policy recreate
- sync-log create-if-missing behavior

### Broader caller-facing guards

Reuse:

- [test_media_db_runtime_factory.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_runtime_factory.py)
- [test_media_db_schema_bootstrap.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)

## Success Criteria

- canonical ownership for the RLS pair moves off legacy globals
- legacy methods remain live-module compat shells
- helper-path tests pass for probe fallback and policy creation/drop behavior
- runtime-factory/bootstrap caller guards stay green
- normalized ownership count drops `11 -> 9`
