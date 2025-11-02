# Database Backends: Query Placeholders and FTS Guidelines

This project supports both SQLite and PostgreSQL for content storage through a shared backend abstraction. This note summarizes best practices for SQL placeholders and Full-Text Search (FTS) across backends.

## Placeholders and Parameterization

- Always use parameterized queries. Never interpolate user input into SQL strings.
- For positional parameters in code, write queries using SQLite’s `?` placeholders. The PostgreSQL backend automatically converts `?` → `%s` using a safe tokenizer that ignores quoted text.
- For named parameters with dictionaries, use the native placeholder style for your backend:
  - PostgreSQL: `%(name)s`
  - SQLite: `:name` or `?` with tuple/sequence
- Prefer the shared helpers when you need to pre-compute statements:
  - `prepare_backend_statement(backend_type, sql, params)`
  - `prepare_backend_many_statement(backend_type, sql, params_list)`
- The PostgreSQL adapter internally invokes the shared preparation path for both `execute(...)` and `execute_many(...)`. Direct calls to `DatabaseBackend.execute` are safe.

## FTS Implementation Guidance

- SQLite uses FTS5 virtual tables (`media_fts`, `keyword_fts`, `claims_fts`) with `bm25()` for ranking.
  - Create/update with `INSERT OR REPLACE` into the FTS virtual tables.
  - Rank with: `ORDER BY bm25(media_fts) ASC` (lower is more relevant).
- PostgreSQL uses `tsvector` columns with GIN indexes and `to_tsquery`/`ts_rank`.
  - Do not use `INSERT OR REPLACE` on Postgres.
  - Update the `tsvector` via `UPDATE ... SET ...` expressions and rely on normal tables + indexes.
  - Rank with: `ORDER BY ts_rank(tsvector_col, to_tsquery(...)) DESC`.
- Cross-backend query translation
  - Use `FTSQueryTranslator` to translate between FTS5 and `to_tsquery` syntax where needed.
  - Be aware that FTS5 scores are typically negative (bm25), while Postgres scores are positive (ts_rank).

## Safety and Performance Tips

- Avoid excessively long FTS queries. The `MediaDatabase.search_media_db` method clamps query length via `FTS_QUERY_MAX_CHARS` (default 1000). Override with the env var if needed.
- Validate fields used in `ORDER BY` and dynamic filters to prevent SQL injection. Use safe identifier escaping helpers when building dynamic identifiers.
- Prefer batching (`execute_many`) for large inserts/updates.

## Backups

- SQLite: use the built-in backup APIs (see `DB_Backups.create_backup`) and sidecar WAL/SHM copying.
- PostgreSQL: use `pg_dump` via the helper in `DB_Backups.create_postgres_backup(...)`. Requires `pg_dump` to be installed and on PATH. The helper sources connection details from the configured backend.
