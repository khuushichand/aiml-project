# PostgreSQL Content Migration Guide

This document explains how to migrate existing SQLite content databases to PostgreSQL using the built-in migration tooling (`migration_tools.py`). The script copies Media, analytics, ChaChaNotes, workflows, and related metadata while preserving UUIDs, timestamps, and soft-delete flags so you can switch the backend without re-ingesting content or re-running jobs.

See also: `Docs/Deployment/Postgres_Migration_Guide.md` in the repository for the source version.

## Prerequisites

- Back up all SQLite databases (`Databases/user_databases/<user_id>/Media_DB_v2.db`, `Databases/workflows.db`, `Databases/user_databases/*/ChaChaNotes.db`, `Analytics.db`).
- Install PostgreSQL and ensure the target database is accessible.
- Install `psycopg` (e.g., `pip install "psycopg[binary]"`).
- Configure the server once against PostgreSQL so the schema exists (set `TLDW_CONTENT_DB_BACKEND=postgresql` temporarily and start the API).

## Step 1 - Prepare connection details

```bash
export PGHOST=localhost
export PGPORT=5432
export PGDATABASE=tldw_content
export PGUSER=tldw_user
export PGPASSWORD=super-secret
```

## Step 2 - Run the migration utility

```bash
python -m tldw_Server_API.app.core.DB_Management.migration_tools \
      --content-sqlite Databases/user_databases/<user_id>/Media_DB_v2.db \
      --chacha-sqlite Databases/user_databases/default/ChaChaNotes.db \
      --analytics-sqlite Analytics.db \
      --workflows-sqlite Databases/workflows.db \
      --pg-host "$PGHOST" \
      --pg-port "$PGPORT" \
      --pg-database "$PGDATABASE" \
      --pg-user "$PGUSER" \
      --pg-password "$PGPASSWORD" \
      --batch-size 500
```

## Step 3 - Validate the migration

Compare row counts in SQLite vs Postgres, run dual-backend tests as needed, and check stress suite if applicable.

## Step 4 - Switch the application configuration

Set environment variables (examples):

```bash
export TLDW_CONTENT_DB_BACKEND=postgresql
export TLDW_PG_HOST=$PGHOST
export TLDW_PG_PORT=$PGPORT
export TLDW_PG_DATABASE=$PGDATABASE
export TLDW_PG_USER=$PGUSER
export TLDW_PG_PASSWORD=$PGPASSWORD
```

Restart the stack and confirm logs mention PostgreSQL usage for content and workflows.

## Troubleshooting

- Foreign-key errors - ensure schema exists (start API once before migrating).
- Sequence mismatch - rerun with small batch size or reseed sequences.
- Large datasets - increase `--batch-size` or migrate one DB at a time.
