# PostgreSQL Content Mode - Quick Start

Run the content databases (Media, ChaChaNotes, Workflows, etc.) on PostgreSQL instead of SQLite.

## 1) Install dependencies

```bash
pip install "psycopg[binary]"  # PostgreSQL driver
# Optional for pgvector-based vector search in Postgres
pip install pgvector
```

Ensure your PostgreSQL server is reachable and you have a database created (e.g., `tldw_content`).

## 2) Configure environment variables

```bash
export TLDW_CONTENT_DB_BACKEND=postgresql
export TLDW_PG_HOST=localhost
export TLDW_PG_PORT=5432
export TLDW_PG_DATABASE=tldw_content
export TLDW_PG_USER=tldw_user
export TLDW_PG_PASSWORD=super-secret
```

Alternatively, set these in your process manager or container environment.

## 3) Initialize the schema

Start the API once to create and validate the content schema:

```bash
python -m uvicorn tldw_Server_API.app.main:app --reload
```

Logs should include confirmation that the PostgreSQL content backend was validated. If you see connection or schema errors, check your env vars and ensure the user has privileges to create tables and indexes.

## 4) Migrate existing content (optional)

If you already have content indexed in SQLite, migrate it using the built-in migration tool:

```bash
python -m tldw_Server_API.app.core.DB_Management.migration_tools \
  --content-sqlite Databases/user_databases/<user_id>/Media_DB_v2.db \
  --workflows-sqlite Databases/workflows.db \
  --pg-host "$TLDW_PG_HOST" --pg-port "$TLDW_PG_PORT" \
  --pg-database "$TLDW_PG_DATABASE" --pg-user "$TLDW_PG_USER" \
  --pg-password "$TLDW_PG_PASSWORD" --batch-size 500
```

See also: `Deployment/Postgres_Migration_Guide.md`.

## 5) Backups

Use the helper script or pg_dump directly:

```bash
# Helper
python Helper_Scripts/pg_backup_restore.py backup \
  --backup-dir ./tldw_DB_Backups/postgres --label content

# CLI
PGPASSWORD=... pg_dump -h $TLDW_PG_HOST -p $TLDW_PG_PORT -U $TLDW_PG_USER \
  -F c --no-owner --no-privileges -f content_$(date +%Y%m%d_%H%M%S).dump $TLDW_PG_DATABASE
```
