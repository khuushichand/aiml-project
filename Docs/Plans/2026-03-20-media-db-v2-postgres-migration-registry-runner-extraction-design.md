# Media DB V2 Postgres Migration Registry And Runner Extraction Design

**Status:** Proposed, review-corrected, and ready for tranche planning on 2026-03-20.

**Goal:** Extract PostgreSQL migration registry and runner ownership out of
legacy `Media_DB_v2` without moving the individual `_postgres_migrate_to_v*()`
body methods yet.

## Why This Tranche Exists

The PostgreSQL bootstrap bridge is now package-owned, but the migration layer is
still effectively legacy-owned through two methods in
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py):

- `_get_postgres_migrations()`
- `_run_postgres_migrations()`

The current package helper in
[`schema/migrations.py`](./../../tldw_Server_API/app/core/DB_Management/media_db/schema/migrations.py)
is only a pass-through back into those legacy methods. That means the package
boundary exists in name only; the real registry assembly and sequential runner
logic are still hosted by `Media_DB_v2`.

At the same time, the individual migration bodies remain broad domain seams:

- claims
- data tables
- collections/content items
- source hash
- FTS and RLS
- TTS history
- email schema

So the safe next step is not migration-body extraction. It is **migration
registry and runner extraction**.

## Review Corrections Incorporated

### 1. Keep the legacy migration body methods in place

The current direct compatibility surface includes:

- `MediaDatabase._get_postgres_migrations(...)`
- `MediaDatabase._postgres_migrate_to_v6(...)`
- other `MediaDatabase._postgres_migrate_to_v*()` helpers

Tests in
[`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
bind to those entrypoints directly. This tranche keeps all individual migration
methods where they are and changes only the registry assembly and sequential
runner logic.

### 2. Preserve the legacy method surface as delegating shells

Even after extraction, `Media_DB_v2` should still define:

- `_get_postgres_migrations()`
- `_run_postgres_migrations(...)`

Those methods should delegate to package-native helpers so existing tests and
compat imports keep working.

### 3. Do not widen into domain migration decomposition

The `v10` through `v22` methods fan into domain-heavy helpers across claims,
data tables, FTS/RLS, email, and TTS. This tranche explicitly defers that work.
The registry should still map to bound legacy instance methods.

### 4. Preserve migration runner semantics exactly

The extracted runner must preserve:

- sorted sequential application
- schema-version updates after each applied migration
- policy ensure via `ensure_postgres_policies(db, conn)`
- incomplete-path error raising through `SchemaError`

This is an ownership move, not a behavioral rewrite.

## In Scope

- package-native migration registry assembly
- package-native sequential migration runner
- delegating legacy `_get_postgres_migrations()` shell
- delegating legacy `_run_postgres_migrations()` shell
- ownership regressions for registry/runner extraction
- focused verification of existing migration behavior

## Out Of Scope

- moving any `_postgres_migrate_to_v*()` method bodies
- claims/data-tables/email/FTS/TTS migration decomposition
- changing `_initialize_schema_postgres()` coordinator behavior
- startup/runtime factory behavior changes unrelated to migration runner
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Make `schema/migrations.py` the real migration owner

`schema/migrations.py` should stop being a thin pass-through and instead own:

- `build_postgres_migration_map(db)`
- `run_postgres_migrations(db, conn, current_version, target_version)`

The migration map should still contain bound legacy methods like
`db._postgres_migrate_to_v6`.

### B. Keep `Media_DB_v2` as the compat shell

`Media_DB_v2._get_postgres_migrations()` should delegate to the package helper
and return the same shape as today.

`Media_DB_v2._run_postgres_migrations()` should delegate to the package helper
and preserve the same error and policy semantics.

### C. Leave migration bodies as legacy leaves

The runner should call whatever bound methods the registry provides. That keeps
the package-native ownership narrow while leaving the domain-heavy migration
bodies untouched for later, domain-specific tranches.

## Risks

### 1. Direct test binding to legacy methods

Tests already assert on `_get_postgres_migrations()` and specific migration body
methods. Replacing those entrypoints would widen churn and break compatibility.
The extraction must leave them present.

### 2. Hidden runner behavior drift

The runner currently guarantees schema-version updates after each step and a
policy ensure after the loop. If the package helper changes that ordering, real
migration behavior can drift without changing import paths.

### 3. False sense of completion

This tranche does not move the migration bodies. It only moves the registry and
runner ownership. The design should say that explicitly so later domain work is
not skipped by mistake.

## Required Tests

- support/compat tests in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
- integration migration tests in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
- bootstrap/migration boundary coverage in
  [`test_media_db_schema_bootstrap.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
- focused ownership regressions in
  [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)

## Recommended Next Tranche

1. Add ownership regressions for package-owned migration registry and runner.
2. Replace the pass-through helper in `schema/migrations.py` with the real
   registry and runner implementation.
3. Delegate `Media_DB_v2._get_postgres_migrations()` and
   `Media_DB_v2._run_postgres_migrations()` to that package helper.
4. Verify with focused Postgres support, migration, bootstrap, and ownership
   tests.
