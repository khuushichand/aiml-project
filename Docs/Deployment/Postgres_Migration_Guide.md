
# PostgreSQL Content Migration Guide

This document explains how to migrate existing SQLite content databases to PostgreSQL using the
built-in migration tooling (`migration_tools.py`). The script copies Media, analytics, and
ChaChaNotes data while preserving UUIDs, timestamps, and soft-delete flags so you can switch the
backend without re-ingesting content.

## Prerequisites

- Back up all SQLite databases (`Databases/Media_DB_v2.db`, `Databases/user_databases/*/ChaChaNotes.db`, `Analytics.db`).
- Install PostgreSQL and ensure the target database is accessible (local host or remote).
- Install the Python dependency `psycopg2-binary` (now listed in `requirements.txt`).
- Configure the server once against PostgreSQL so the schema exists. The easiest option is to set
  `TLDW_CONTENT_DB_BACKEND=postgresql` temporarily and start the API; it will create all tables and
  FTS artefacts, then shut the server down before migrating data.

## Step 1 – Prepare connection details

Collect the PostgreSQL host, port, database, username, and password. These map directly onto the
CLI arguments and `DatabaseConfig` fields inside the migration utility.

```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=tldw_content
export PGUSER=tldw_user
export PGPASSWORD=super-secret
```

## Step 2 – Run the migration utility

Invoke the migration module with paths to your existing SQLite databases. Provide `--content-sqlite`
for the main media database and optionally pass `--chacha-sqlite` and `--analytics-sqlite` if you
want to migrate user notes or analytics data in the same pass.

```bash
python -m tldw_Server_API.app.core.DB_Management.migration_tools       --content-sqlite Databases/Media_DB_v2.db       --chacha-sqlite Databases/user_databases/default/ChaChaNotes.db       --analytics-sqlite Analytics.db       --pg-host "$PGHOST"       --pg-port "$PGPORT"       --pg-database "$PGDATABASE"       --pg-user "$PGUSER"       --pg-password "$PGPASSWORD"       --batch-size 500
```

The script performs the following actions for each supplied database:

1. Reads table definitions from SQLite, respecting foreign-key dependencies.
2. Deletes existing rows in PostgreSQL (in dependency order) so the migration is idempotent.
3. Copies data in batches using the backend abstraction layer.
4. Resyncs sequences so future inserts continue from the correct IDs.

Use `--skip-table <table_name>` to omit auxiliary tables (for example, to skip large log tables).

## Step 3 – Validate the migration

- Compare row counts between SQLite and PostgreSQL:

  ```sql
  -- Run in psql
  SELECT COUNT(*) FROM media;
  SELECT COUNT(*) FROM claims;
  ```

  ```bash
  sqlite3 Databases/Media_DB_v2.db 'SELECT COUNT(*) FROM Media;'
  ```

- Run the new dual-backend unit tests to ensure the application-level routines behave correctly:

  ```bash
  pytest tldw_Server_API/tests/DB_Management/test_media_postgres_support.py              tldw_Server_API/tests/RAG/test_analytics_backend.py              tldw_Server_API/tests/DB_Management/test_migration_tools.py
  ```

  *(These tests use fakes/stubs and do not require a live PostgreSQL instance.)*

## Step 4 – Switch the application configuration

1. Update environment variables or `Config_Files/config.txt`:

   ```bash
   export TLDW_CONTENT_DB_BACKEND=postgresql
   export TLDW_PG_HOST=$PGHOST
   export TLDW_PG_PORT=$PGPORT
   export TLDW_PG_DATABASE=$PGDATABASE
   export TLDW_PG_USER=$PGUSER
   export TLDW_PG_PASSWORD=$PGPASSWORD
   ```

2. Remove or archive the old SQLite files once you are confident the migration succeeded.

3. Restart the API/WebUI stack. On startup the service should log that it is using PostgreSQL for
   Media, ChaChaNotes, and Analytics.

## Troubleshooting

- **Foreign-key errors during copy** – ensure the PostgreSQL schema was created by running the API
  once before migrating. The script expects tables and constraints to exist.
- **Sequence mismatch** – rerun the migration with `--batch-size 1` for the affected database to
  recompute the sequence state, or run the generated `SELECT setval(...)` statements manually.
- **Large datasets** – increase `--batch-size` (default 500) to improve throughput, or run per
  database to isolate issues.

## Next steps

- Update deployment scripts to point at PostgreSQL hosts.
- Configure backups for the new PostgreSQL databases.
- Remove legacy cron jobs or tooling that assumed SQLite file copies.
