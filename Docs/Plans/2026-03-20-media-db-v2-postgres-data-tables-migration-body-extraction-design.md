# Media DB V2 Postgres Data Tables Migration Body Extraction Design

**Status:** Proposed, review-derived, and ready for tranche planning on
2026-03-20.

**Goal:** Move the PostgreSQL data-tables migration bodies for `v14` and `v15`
behind package-native helpers while keeping `Media_DB_v2` as the explicit
compat-shell entrypoint and leaving the underlying
`_ensure_postgres_data_tables(conn)` helper legacy-owned for now.

## Why This Tranche Exists

The migration registry and sequential runner are now package-owned, but the
individual migration body methods are still legacy-owned in
[`Media_DB_v2.py`](./../../tldw_Server_API/app/core/DB_Management/Media_DB_v2.py).

The safest first migration-body slice is the PostgreSQL data-tables pair:

- `_postgres_migrate_to_v14(conn)`
- `_postgres_migrate_to_v15(conn)`

Those two methods are the cleanest nearby candidates because they are already
thin delegates to one existing helper:

- `_ensure_postgres_data_tables(conn)`

They also already have meaningful migration-path coverage in
[`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py),
which downgrades schema state and asserts that the `workspace_tag` repair path
is restored through the `v10` to `v20` span.

That makes data tables the right place to prove the migration-body delegation
pattern before touching broader domains like claims, email, TTS history, or
FTS/RLS.

## Review Corrections Incorporated

### 1. Keep the legacy ensure helper in place

This tranche does **not** move `_ensure_postgres_data_tables(conn)` yet. That
helper still carries the real schema behavior. The current move is only about
body-method ownership for:

- `_postgres_migrate_to_v14(conn)`
- `_postgres_migrate_to_v15(conn)`

### 2. Keep the legacy body methods present as compat shells

Even after extraction, `Media_DB_v2` should still define:

- `_postgres_migrate_to_v14(conn)`
- `_postgres_migrate_to_v15(conn)`

Those methods should delegate to package-native helpers so compatibility and
existing bound-method registry behavior remain stable.

This also means the success condition for this tranche is boundary cleanup, not
necessarily a drop in the normalized legacy-owned canonical-method count. The
registry still binds to the legacy shell methods, so count reduction is
optional, not guaranteed, for this slice.

### 3. Do not widen into adjacent migration bodies

This tranche explicitly leaves alone:

- collections/content-items (`v12`, `v13`)
- source-hash (`v16`)
- claims (`v17`)
- sequence sync (`v18`)
- FTS/RLS (`v19`)
- TTS history (`v20`)
- visual/structure indexes (`v21`)
- email (`v22`)

`v21` is especially out of scope because it contains inline SQL rather than a
simple delegate and is a worse first body-extraction target.

### 4. Preserve migration semantics exactly

The extracted package helpers must keep the current behavior exactly:

- `v14` ensures base data-tables schema exists
- `v15` ensures later columns and additions exist
- both still route through `_ensure_postgres_data_tables(conn)`

This is an ownership move, not a schema rewrite.

## In Scope

- package-native body helpers for PostgreSQL `v14` and `v15`
- delegating legacy `_postgres_migrate_to_v14(conn)` shell
- delegating legacy `_postgres_migrate_to_v15(conn)` shell
- focused ownership/delegation regressions for those two methods
- focused verification of data-tables migration behavior

## Out Of Scope

- moving `_ensure_postgres_data_tables(conn)`
- changing the migration registry/runner again
- claims/email/TTS/FTS/RLS/collections migration extraction
- changing bootstrap coordinators
- changing `_CURRENT_SCHEMA_VERSION`

## Target Architecture

### A. Add one narrow package module for Postgres data-tables migration bodies

Introduce a package-native helper module under the schema package, for example:

- `schema/migration_bodies/postgres_data_tables.py`

That module should own:

- `run_postgres_migrate_to_v14(db, conn)`
- `run_postgres_migrate_to_v15(db, conn)`

Both helpers should remain thin wrappers that call
`db._ensure_postgres_data_tables(conn)`.

### B. Keep `Media_DB_v2` as the compat shell

`Media_DB_v2._postgres_migrate_to_v14(conn)` should delegate to the package
helper.

`Media_DB_v2._postgres_migrate_to_v15(conn)` should delegate to the package
helper.

The methods should remain present on the class so the migration registry still
returns bound methods of the DB instance.

The delegation should call through a live module reference, not through a
statically imported function name. That preserves a patch seam for direct
delegation regressions.

### C. Leave the registry and helper layering stable

The current package-owned registry and runner should continue to map versions to
bound legacy methods. Those legacy methods now become thin shells for `v14` and
`v15`, while later body extractions can follow the same pattern.

## Risks

### 1. Wrong invariant in tests

Because the legacy methods remain as compat shells, raw `__globals__` ownership
is not the right assertion for this tranche. The tests should verify delegation,
not that the methods physically live in a new module.

### 2. Over-extraction into `_ensure_postgres_data_tables`

Moving `_ensure_postgres_data_tables(conn)` now would widen the tranche
unnecessarily. The whole point of this slice is to prove the body-shell pattern
first.

### 3. Misleading progress signal

This tranche moves only two body methods behind compat shells. It is
intentionally small and may leave the ownership count unchanged. The design
should make that explicit so the next slices still treat the remaining domains
as separate work.

## Required Tests

- support tests in
  [`test_media_postgres_support.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_support.py)
- migration-path verification in
  [`test_media_postgres_migrations.py`](./../../tldw_Server_API/tests/DB_Management/test_media_postgres_migrations.py)
- focused body/delegation regressions in
  [`test_media_db_v2_regressions.py`](./../../tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)

The direct regressions should prove:

- `_postgres_migrate_to_v14(conn)` delegates to the package helper
- `_postgres_migrate_to_v15(conn)` delegates to the package helper

The broader migration-path test should remain the guard that downgraded schema
state still restores `workspace_tag`.

## Recommended Next Tranche

1. Add focused delegation regressions for `_postgres_migrate_to_v14` and
   `_postgres_migrate_to_v15`.
2. Add a package-native helper module for the two data-tables migration bodies.
3. Delegate the legacy `Media_DB_v2` methods to that helper.
4. Verify with focused Postgres support, migration, and regression tests.
