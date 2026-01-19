PostgreSQL FTS Synonyms (Index-Time Expansion)

Overview
- This project can index synonyms into the PostgreSQL FTS vector (tsvector) using a lightweight table-based dictionary and an expansion function.
- When enabled, Media FTS computation wraps title/content via synonyms_expand(...) before to_tsvector, appending mapped synonyms to improve recall without query-time expansion.

Enable
- Set environment variable `PG_FTS_ENABLE_SYNONYMS=true` to turn on index-time synonyms for Media.
- On first use, the backend creates the following objects (idempotent):
  - `fts_synonyms(term TEXT PRIMARY KEY, synonyms TEXT[])`
  - `synonyms_expand(input TEXT) RETURNS TEXT` (immutable PL/pgSQL)

Managing Synonyms
- Insert rows into `fts_synonyms` to define mappings. Example:

```sql
INSERT INTO fts_synonyms(term, synonyms)
VALUES
  ('cuda', ARRAY['compute unified device architecture','nvidia cuda']),
  ('llm', ARRAY['large language model']);
```

How It Works
- During Media FTS updates (title/content), when `PG_FTS_ENABLE_SYNONYMS=true`:
  - The code computes:
    - `setweight(to_tsvector('english', synonyms_expand(coalesce(title,''))), 'A')`
    - `|| setweight(to_tsvector('english', synonyms_expand(coalesce(content,''))), 'C')`
- This preserves field weights (A for title, C for content) while embedding synonyms.

Notes
- The function is intentionally simple and language-agnostic. For large synonym sets, consider batching or limiting updates.
- This feature is independent of SQLite FTS synonym expansion, which uses index-time content augmentation during insert/update.
- If you already maintain a server-level text search configuration/dictionary, you can disable this (`PG_FTS_ENABLE_SYNONYMS=false`) and keep your DBA-managed approach.
- The server looks for JSON files under `Config_Files/Synonyms/`. You can override the root via `TLDW_CONFIG_PATH` (path to `config.txt`) or `TLDW_CONFIG_DIR` (directory containing `config.txt`).

Troubleshooting
- Ensure the DB user has permission to create functions and tables in the `public` schema.
- If migrations run in restricted environments, pre-create the table/function using your deployment tooling.
