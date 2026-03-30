# Media DB V2 Postgres Data-Tables Ensure Helper Rebinding Design

## Summary

Rebind `_ensure_postgres_data_tables`, `_ensure_postgres_columns`, and
`_ensure_postgres_data_tables_columns` onto package-owned schema helpers so the
canonical `MediaDatabase` no longer owns this PostgreSQL data-tables ensure
cluster through legacy globals, while preserving `Media_DB_v2` as a live-module
compatibility shell.

## Scope

In scope:

- Add a package schema helper module for:
  - `_ensure_postgres_data_tables(...)`
  - `_ensure_postgres_columns(...)`
  - `_ensure_postgres_data_tables_columns(...)`
- Rebind canonical `MediaDatabase` methods for those three helpers
- Convert legacy `Media_DB_v2` methods into live-module compat shells
- Add direct ownership/delegation regressions
- Add focused helper-path tests asserting:
  - `CREATE TABLE` statements run before the late-column ensure
  - late-column ensure runs before non-table statements
  - `_ensure_postgres_columns(...)` only adds missing columns
  - `_ensure_postgres_data_tables_columns(...)` performs the expected
    column/backfill/index sequence

Out of scope:

- Changing `_DATA_TABLES_SQL`
- Changing `run_postgres_migrate_to_v14(...)` or `run_postgres_migrate_to_v15(...)`
- Changing Data Tables CRUD behavior
- Changing claims, collections, TTS history, or source-hash PostgreSQL ensure helpers

## Why This Slice

This is the next clean helper cluster after the SQLite post-core and claims
extension slices. `_ensure_postgres_columns(...)` is only used by
`_ensure_postgres_data_tables_columns(...)`, and both sit directly underneath
`_ensure_postgres_data_tables(...)`. Rebasing all three together keeps the
call chain intact and avoids splitting a generic helper away from its only
current caller.

## Risks

Low to medium. The main invariants are ordering and preserving graceful
best-effort behavior:

- `CREATE TABLE` statements must still run before late-column repair
- late-column repair must still run before index/other statements
- missing-column introspection must stay warning-only on backend errors
- `client_id` / `last_modified` backfill and `idx_data_tables_workspace_tag`
  creation must remain unchanged

## Test Strategy

Add:

1. canonical ownership regressions for all three methods
2. legacy compat-shell delegation regressions for all three methods
3. focused helper-path tests for:
   - `_ensure_postgres_data_tables(...)` statement ordering
   - `_ensure_postgres_columns(...)` missing-column repair behavior
   - `_ensure_postgres_data_tables_columns(...)` late-column and index flow
4. reuse existing `test_media_postgres_migrations.py` `workspace_tag` repair
   coverage as the broader migration-path guard

## Success Criteria

- canonical helper methods are package-owned
- legacy `Media_DB_v2` helper methods remain live-module compat shells
- focused helper-path tests pass
- existing PostgreSQL data-tables migration coverage stays green
- normalized ownership count drops from `184` to `181`
