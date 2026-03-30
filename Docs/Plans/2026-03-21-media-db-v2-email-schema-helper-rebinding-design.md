# Media DB V2 Email Schema Helper Rebinding Design

## Goal

Rebind `_ensure_sqlite_email_schema()` and `_ensure_postgres_email_schema()`
onto a package-owned schema helper module so the canonical `MediaDatabase` no
longer owns the cross-backend email schema ensure pair through `Media_DB_v2`,
while preserving the legacy compat shell and keeping email-native schema/index
behavior unchanged.

## Scope

In scope:
- `_ensure_sqlite_email_schema()`
- `_ensure_postgres_email_schema()`
- canonical rebinding in `media_database_impl.py`
- live-module compat shells in `Media_DB_v2.py`
- focused ownership and helper-path regressions
- existing SQLite email schema and Postgres v22 migration guards

Out of scope:
- email sync state APIs
- email search behavior
- email-specific migrations beyond reusing the existing v22 guard
- other nearby SQLite/Postgres ensure helpers

## Current State

The remaining normalized legacy-owned canonical-method count is `190`.

The SQLite helper owns:
- detecting whether `email_fts` already exists
- executing `_EMAIL_SCHEMA_SQL`, `_EMAIL_INDICES_SQL`, and `_EMAIL_SQLITE_FTS_SQL`
- rebuild gating so `INSERT INTO email_fts(email_fts) VALUES ('rebuild')` only
  runs when the FTS table was newly created
- warning-only behavior on SQLite errors

The PostgreSQL helper owns:
- converting `_EMAIL_SCHEMA_SQL` and `_EMAIL_INDICES_SQL` through
  `_convert_sqlite_sql_to_postgres_statements(...)`
- executing each converted statement
- warning-only behavior per failing statement

## Target Design

Add one package-owned schema module:
- `tldw_Server_API/app/core/DB_Management/media_db/schema/email_schema_structures.py`

It should own:
- `ensure_sqlite_email_schema(db, conn) -> None`
- `ensure_postgres_email_schema(db, conn) -> None`

Then:
- rebind the canonical `MediaDatabase` methods in `media_database_impl.py`
- keep the legacy methods in `Media_DB_v2.py` as live-module compat shells

## Behavior Invariants

`ensure_sqlite_email_schema()` must preserve:
- `email_fts` existence probe before bootstrap
- executescript order:
  - `_EMAIL_SCHEMA_SQL`
  - `_EMAIL_INDICES_SQL`
  - `_EMAIL_SQLITE_FTS_SQL`
- rebuild only when `email_fts` did not already exist
- warning-only behavior on `sqlite3.Error`

`ensure_postgres_email_schema()` must preserve:
- conversion of schema SQL and index SQL separately
- sequential execution of all converted statements
- warning-only behavior per `BackendDatabaseError`
- no early abort when a single statement fails

## Tests

Add three layers of coverage:

1. Ownership and compat-shell regressions in
   `test_media_db_v2_regressions.py`
   - canonical `_ensure_sqlite_email_schema` is no longer legacy-owned
   - canonical `_ensure_postgres_email_schema` is no longer legacy-owned
   - legacy methods delegate through a live package module reference

2. Helper-path tests in `test_media_db_schema_bootstrap.py`
   - SQLite helper executes scripts in order and only rebuilds when FTS was new
   - PostgreSQL helper executes converted schema/index statements in order and
     tolerates one failing statement

3. Existing integration guards
   - `test_ensure_sqlite_email_schema_rebuilds_only_when_fts_is_created`
   - `test_media_postgres_migration_reaches_v22_and_restores_email_schema`

## Success Criteria

- canonical `MediaDatabase._ensure_sqlite_email_schema` is package-owned
- canonical `MediaDatabase._ensure_postgres_email_schema` is package-owned
- legacy `Media_DB_v2` methods remain callable compat shells
- focused helper and integration tests pass
- normalized ownership count drops `190 -> 188`
