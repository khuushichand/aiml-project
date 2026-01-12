# Source Hash Index for Media Pre-check

## Context
Media ingestion pre-checks currently deduplicate local files by searching
`DocumentVersions.safe_metadata` with a JSON `LIKE` predicate for
`source_hash`. This is slow on large datasets and cannot use indexes.

## Goal
Add a dedicated `Media.source_hash` column with an index to enable fast
deduplication. Update the pre-check query to prefer the indexed column,
falling back to the legacy `safe_metadata` search for older rows.

## Proposed Changes
- Schema: add `source_hash TEXT` to `Media` plus index
  `idx_media_source_hash` on `Media(source_hash)`.
- Persistence: populate `Media.source_hash` when a `source_hash` is
  available during ingestion.
- Pre-check: when `source_hash` is present and the column exists, query
  by `Media.source_hash`. If the column is missing or a row lacks a value,
  fall back to the legacy `safe_metadata` `LIKE` filter.

## Migration/Compatibility
- Update base schema for new databases.
- Add an ensure/migration step for existing SQLite/Postgres DBs.
- Preserve legacy behavior through fallback until all rows have
  `Media.source_hash`.

## Risks
- Older rows without `source_hash` will still require the legacy
  `safe_metadata` search.
- Extra schema update paths need to remain idempotent.

## Testing
- Unit test: insert media with `source_hash` and verify it persists.
- Optional integration check: pre-check query returns existing row by
  `Media.source_hash`.
