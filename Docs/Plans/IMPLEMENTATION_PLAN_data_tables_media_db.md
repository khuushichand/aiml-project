## Stage 1: Define Data Tables Schema
**Goal**: Add Data Tables schema (tables + indexes) to Media_DB_v2 base SQL.
**Success Criteria**: New tables are defined in base schema for fresh SQLite/Postgres databases.
**Tests**: N/A (schema only).
**Status**: Complete

## Stage 2: Wire Schema Ensures/Migrations
**Goal**: Ensure existing SQLite/Postgres Media DBs receive the new tables.
**Success Criteria**: Initialization paths create Data Tables for existing databases without errors.
**Tests**: N/A (schema only).
**Status**: Complete

## Stage 3: Verification Notes
**Goal**: Document manual verification steps for schema presence.
**Success Criteria**: Notes added for checking tables in SQLite/Postgres.
**Tests**: N/A (schema only).
**Status**: Complete

Manual verification:
```bash
# SQLite (replace <user_id> as needed)
sqlite3 Databases/user_databases/<user_id>/Media_DB_v2.db \
  "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'data_table%';"
```

```sql
-- Postgres
SELECT table_name
FROM information_schema.tables
WHERE table_schema = 'public'
  AND table_name LIKE 'data_table%';
```
