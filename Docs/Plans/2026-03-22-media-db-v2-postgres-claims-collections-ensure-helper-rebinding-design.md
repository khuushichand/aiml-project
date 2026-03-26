# Media DB V2 Postgres Claims/Collections Ensure Helper Rebinding Design

## Summary

After the Postgres RLS tranche, the normalized legacy ownership count is `9`.
The cleanest remaining non-constructor, non-rollback slice is the Postgres
claims/collections ensure-helper cluster:

- `_ensure_postgres_claims_tables(...)`
- `_ensure_postgres_collections_tables(...)`
- `_ensure_postgres_claims_extensions(...)`

These methods are still legacy-owned, but they already sit behind package-owned
bootstrap and migration coordinators. Moving them into one package-owned schema
helper reduces ownership without widening into constructor/bootstrap entry
points, SQLite backend setup, schema-v1 application, or rollback.

## Current Method Shape

`_ensure_postgres_claims_tables(...)` currently owns:

- translation of `_CLAIMS_TABLE_SQL` through `_convert_sqlite_sql_to_postgres_statements(...)`
- create-table-first execution ordering
- the mandatory call into `_ensure_postgres_claims_extensions(...)` before
  running non-create statements
- warning-and-continue handling for DDL/index failures

`_ensure_postgres_collections_tables(...)` currently owns:

- direct PostgreSQL DDL for `output_templates`, `reading_highlights`,
  `collection_tags`, `content_items`, and `content_item_tags`
- index creation for those tables
- one outer warning boundary around the collection/content-item ensure flow

`_ensure_postgres_claims_extensions(...)` currently owns:

- late `claims` column adds and NULL backfills
- review-log, review-metrics, review-rules, monitoring, analytics-export,
  notifications, cluster, and cluster-link/member ensure DDL
- index creation for the late claims tables
- warning-and-continue handling for backend failures

## Why This Slice Is Safe

This is still a bounded Postgres-only schema ensure surface:

- no constructor or `initialize_db(...)` compatibility behavior
- no SQLite backend setup
- no schema-v1 full-script execution
- no rollback/version restore coordination
- existing bootstrap and migration callers already exercise the helper order

That makes it safer than the remaining legacy-owned surfaces:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `rollback_to_version(...)`

## Risks To Pin

### 1. Claims-table ordering must stay intact

`_ensure_postgres_claims_tables(...)` must still:

1. run translated `CREATE TABLE` statements first
2. invoke `_ensure_postgres_claims_extensions(...)`
3. only then run the remaining non-create statements

If that order changes, later index/statement execution can race missing columns.

### 2. Collections ensure must preserve its one-shot warning boundary

`_ensure_postgres_collections_tables(...)` is intentionally tolerant. A backend
failure should warn and stop the helper rather than raising.

### 3. Claims extensions must keep the late-schema artifacts that active callers use

The extracted claims runtime surfaces now depend on the extension tables and
indexes being present. The helper tests should pin representative artifacts from:

- review columns on `claims`
- review log
- review metrics
- monitoring events
- claim clusters and cluster membership

## Recommended Tranche

Move only:

- `_ensure_postgres_claims_tables(...)`
- `_ensure_postgres_collections_tables(...)`
- `_ensure_postgres_claims_extensions(...)`

Defer:

- `__init__(...)`
- `initialize_db(...)`
- `_ensure_sqlite_backend(...)`
- `_apply_schema_v1_sqlite(...)`
- `_apply_schema_v1_postgres(...)`
- `rollback_to_version(...)`

## Design

Add one package-owned schema helper module:

- `tldw_Server_API/app/core/DB_Management/media_db/schema/postgres_claims_collection_structures.py`

It should expose:

- `ensure_postgres_claims_tables(...)`
- `ensure_postgres_collections_tables(...)`
- `ensure_postgres_claims_extensions(...)`

Then:

- rebind the canonical `MediaDatabase` methods in
  [media_database_impl.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/media_db/media_database_impl.py)
- convert the legacy methods in
  [Media_DB_v2.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/app/core/DB_Management/Media_DB_v2.py)
  into live-module compat shells

No caller modules should change. The existing package-owned bootstrap and
migration helpers should continue calling the DB methods exactly as they do now.

## Test Strategy

### Direct regressions

Extend
[test_media_db_v2_regressions.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_v2_regressions.py)
with ownership/delegation coverage for all three methods:

- canonical methods no longer use legacy globals
- legacy methods delegate through the new schema helper module

### Focused helper coverage

Add:

- `tldw_Server_API/tests/DB_Management/test_media_db_postgres_claims_collection_structures.py`

Pin:

- canonical helper rebinding
- claims-table create-table-first ordering with extension call before the
  non-create statement pass
- collections-table DDL coverage for representative tables/indexes
- claims-extensions coverage for late columns, backfills, key tables, and key
  indexes

### Broader caller-facing guards

Reuse:

- [test_media_db_schema_bootstrap.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_media_db_schema_bootstrap.py)
- [test_claims_schema.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_schema.py)
- [test_claims_fts_triggers.py](/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/media-db-v2-phase1-refactor/tldw_Server_API/tests/DB_Management/test_claims_fts_triggers.py)

## Success Criteria

- canonical ownership for the three Postgres ensure helpers moves off legacy
  globals
- legacy methods remain live-module compat shells
- helper-path tests pass for claims-table ordering and representative
  collections/claims-extension DDL coverage
- bootstrap and claims schema guards stay green
- normalized ownership count drops `9 -> 6`
