# Scheduler Metadata Migration Notes

The scheduler now requires every task submission to include metadata with a non-empty `user_id`. This metadata is persisted across all backends and is used to enforce ownership checks (for example, cancelling tasks).

## SQLite schema update

Existing SQLite deployments need to add the new `metadata` column to the `tasks` table before restarting the scheduler:

```sql
ALTER TABLE tasks ADD COLUMN metadata TEXT NOT NULL DEFAULT '{}';
```

The application will automatically populate the column for new installs, but legacy databases must run the migration once. After the column exists the scheduler will backfill metadata with the JSON value `{}` when older rows are read.

## Client changes

All task submissions (single and batch) must now send a metadata dictionary that includes a `user_id`. Calls without metadata (or with an empty `user_id`) return `400` errors. When migrating API clients, ensure that:

- `metadata["user_id"]` is set to the authenticated principal
- optional additional metadata should be JSON-serialisable

Cancelling a task now enforces that only the owning `user_id` (or an admin) may do so. Update any scripts that previously relied on metadata being optional.
