# PostgreSQL Backups

This guide shows how to back up and restore the content databases when running on PostgreSQL. It includes both CLI usage (`pg_dump`/`pg_restore`) and the built-in helpers available in tldw_server.

## TL;DR

- Install PostgreSQL client tools so `pg_dump` and `pg_restore` are available on PATH.
- Create a compressed backup (custom format):
  - `PGPASSWORD=... pg_dump -h <host> -p <port> -U <user> -F c -f content_YYYYMMDD.dump <database>`
- Restore into a database (drop objects first, single transaction):
  - `PGPASSWORD=... pg_restore -h <host> -p <port> -U <user> -d <database> -c -1 content_YYYYMMDD.dump`
- Roles/privileges are not included by default. Dump globals separately:
  - `pg_dumpall --globals-only > globals.sql`

## Prerequisites

- PostgreSQL client tools installed locally or in your admin container.
- Network access to the target PostgreSQL instance.
- User with sufficient privileges to read from (backup) or write to (restore) the database.

## Recommended Flags

- Backups
  - `-F c`: Custom format (compressed, parallelizable with pg_restore).
  - `--no-owner --no-privileges`: Avoid preserving object owners/privileges; makes restores portable across environments.
- Restores
  - `-1`: Single transaction to ensure atomic restore.
  - `-c`: Clean (drop) objects before recreate.

Examples:

```bash
# Backup
export PGPASSWORD="<password>"
pg_dump \
  -h <host> -p 5432 -U <user> \
  -F c --no-owner --no-privileges \
  -f content_$(date +%Y%m%d_%H%M%S).dump \
  <database>

# Restore (to same or new database)
export PGPASSWORD="<password>"
pg_restore \
  -h <host> -p 5432 -U <user> \
  -d <database> \
  -c -1 \
  content_YYYYMMDD_HHMMSS.dump
```

To include owners/privileges (not recommended for managed DBs), omit `--no-owner --no-privileges` during backup and run with an admin role during restore.

## tldw_server Helpers (Python)

The project exposes helpers in `DB_Backups` for programmatic backups and restores. They read connection details from the configured PostgreSQL backend and call `pg_dump` / `pg_restore` under the hood.

```python
from tldw_Server_API.app.core.DB_Management.DB_Manager import get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.DB_Backups import (
    create_postgres_backup,
    restore_postgres_backup,
)

backend = get_content_backend_instance()  # must be PostgreSQL content backend

# Create a backup (compressed custom format) in the target directory
out_path = create_postgres_backup(backend, backup_dir="./tldw_DB_Backups/postgres", label="content")
print("Backup result:", out_path)

# Restore a backup (drops objects first, runs in a single transaction)
status = restore_postgres_backup(backend, dump_file=out_path, drop_first=True)
print("Restore result:", status)
```

Notes:
- Helpers require `pg_dump` (backup) and `pg_restore` (restore) to be on PATH.
- The backup helper writes with `--no-owner --no-privileges` for portability.
- Backup destination: set `TLDW_DB_BACKUP_PATH` to override the default
  `./tldw_DB_Backups/` base directory used by server helpers (SQLite and
  PostgreSQL). Per-DB subdirectories are created under this base.

## Roles and Privileges

Backups usually exclude global objects (roles, tablespaces). If you need to recreate roles on a fresh cluster:

```bash
pg_dumpall --globals-only > globals.sql
# Apply to target cluster (admin permissions required)
psql -h <host> -p 5432 -U <admin> -f globals.sql
```

## Operational Tips

- Retention: keep a rolling window (e.g., 7 daily, 4 weekly, 3 monthly) and test restores periodically.
- Encryption: store dumps on encrypted volumes or use object storage with server-side encryption.
- Verification: after restore, sanity-check schema version tables and row counts; run app smoke tests.
- Performance: for large DBs, consider `pg_dump -j <N>` and `pg_restore -j <N>` to parallelize.
- Containerized DBs: exec into the container that has client tools, or mount them in an admin container.
