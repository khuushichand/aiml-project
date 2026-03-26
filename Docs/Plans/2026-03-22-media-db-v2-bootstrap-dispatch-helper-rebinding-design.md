# Media DB V2 Bootstrap Dispatch Helper Rebinding Design

## Summary

After the scope-resolution tranche, the normalized legacy ownership count is
`16`. The best remaining bounded slice is the thin bootstrap/migration dispatch
layer:

- `_initialize_schema(...)`
- `_initialize_schema_sqlite(...)`
- `_initialize_schema_postgres(...)`
- `_run_postgres_migrations(...)`
- `_get_postgres_migrations(...)`

These methods already route straight into package-owned schema helpers, so this
is a high-leverage ownership reduction without widening into constructor,
schema-v1, RLS, or rollback behavior.

## Current Method Shape

These five methods currently own almost no behavior:

- `_initialize_schema(...)` calls `ensure_media_schema(self)`
- `_initialize_schema_sqlite(...)` calls `bootstrap_sqlite_schema(self)`
- `_initialize_schema_postgres(...)` calls `bootstrap_postgres_schema(self)`
- `_run_postgres_migrations(...)` calls
  `run_postgres_migrations(self, conn, current_version, target_version)`
- `_get_postgres_migrations(...)` returns `get_postgres_migrations(self)`

The real logic already lives in package modules:

- `media_db/schema/bootstrap.py`
- `media_db/schema/backends/sqlite_helpers.py`
- `media_db/schema/backends/postgres_helpers.py`
- `media_db/schema/migrations.py`

## Why This Slice Is Safe

This tranche is dispatcher-only:

- no new schema logic is introduced
- no SQL bodies move
- the package helper implementations are already covered
- it reduces ownership by `5` without touching `initialize_db(...)`,
  `__init__(...)`, schema-v1 setup, Postgres RLS helpers, or rollback

That makes it safer than the remaining bootstrap-heavy methods:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `_ensure_postgres_rls(...)`
- `_postgres_policy_exists(...)`
- `rollback_to_version(...)`

## Risks To Pin

### 1. Canonical methods must resolve from package helper modules

Because these methods are already thin dispatchers, the actual risk is leaving
canonical ownership on `Media_DB_v2` rather than on the package helpers.

### 2. Legacy methods must stay live-module compat shells

The legacy class still needs working entrypoints for monkeypatching and import
compatibility, so each method should delegate via `import_module(...)` to the
same package helper it used before.

### 3. Existing helper tests must follow the canonical seam, not the legacy module

At least one current bootstrap test patches `Media_DB_v2.ensure_media_schema`.
After rebinding, canonical coverage should patch the package helper module
instead, or it will falsely report a regression.

## Recommended Tranche

Move only:

- `_initialize_schema(...)`
- `_initialize_schema_sqlite(...)`
- `_initialize_schema_postgres(...)`
- `_run_postgres_migrations(...)`
- `_get_postgres_migrations(...)`

Defer:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `_ensure_postgres_claims_tables(...)`
- `_ensure_postgres_collections_tables(...)`
- `_ensure_postgres_claims_extensions(...)`
- `_postgres_policy_exists(...)`
- `_ensure_postgres_rls(...)`
- `rollback_to_version(...)`

## Design

Do not add a new wrapper module.

Instead:

- rebind canonical methods directly in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
  to the existing package helpers
- convert the legacy methods in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into live-module compat shells that import and call those same helpers

Target package helpers:

- `media_db.schema.bootstrap.ensure_media_schema`
- `media_db.schema.backends.sqlite_helpers.bootstrap_sqlite_schema`
- `media_db.schema.backends.postgres_helpers.bootstrap_postgres_schema`
- `media_db.schema.migrations.run_postgres_migrations`
- `media_db.schema.migrations.get_postgres_migrations`

## Test Strategy

### Direct regressions

Add ownership/delegation regressions in
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
for:

- canonical methods no longer using legacy globals
- legacy methods delegating through their package helpers

### Focused helper-path coverage

Update
[test_media_db_schema_bootstrap.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
to pin the canonical seam through package helper modules for:

- `_initialize_schema(...)`
- `_initialize_schema_sqlite(...)`
- `_initialize_schema_postgres(...)`
- `_run_postgres_migrations(...)`
- `_get_postgres_migrations(...)`

### Broader caller-facing guards

Reuse:

- [test_media_postgres_support.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
- constructor/initialization guards already present in
  [test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)

## Success Criteria

- canonical ownership for the five dispatcher methods moves off legacy globals
- legacy methods remain live-module compat shells
- bootstrap helper tests stay green after moving to the canonical package seam
- Postgres support guards stay green
- normalized ownership count drops `16 -> 11`
