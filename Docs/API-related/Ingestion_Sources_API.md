# Ingestion Sources API

Ingestion Sources provides a generic sync/import API for filesystem-backed content. A source can point at a local directory or a staged archive snapshot and sync into either the `media` sink or the `notes` sink.

This API is ingest-only. It defines sources, stages archive refreshes, and enqueues sync jobs. It does not currently ship a dedicated WebUI.

See `Docs/Plans/2026-03-08-ingestion-source-sync-design.md` for the original design and tradeoffs.

## Endpoints

- `POST /api/v1/ingestion-sources` - create a source
- `GET /api/v1/ingestion-sources` - list sources
- `GET /api/v1/ingestion-sources/{source_id}` - get a source
- `PATCH /api/v1/ingestion-sources/{source_id}` - update mutable source settings
- `POST /api/v1/ingestion-sources/{source_id}/sync` - enqueue a manual sync
- `POST /api/v1/ingestion-sources/{source_id}/archive` - upload a new archive snapshot and enqueue sync
- `GET /api/v1/ingestion-sources/{source_id}/items` - inspect tracked source items
- `POST /api/v1/ingestion-sources/{source_id}/items/{item_id}/reattach` - reattach a detached notes item

## Core object: IngestionSource

Key fields:
- `id`, `user_id`
- `source_type`: `local_directory` or `archive_snapshot`
- `sink_type`: `media` or `notes`
- `policy`: `canonical` or `import_only`
- `enabled`
- `schedule_enabled`, `schedule_config`
- `config`
- `active_job_id`
- `last_successful_snapshot_id`
- `last_sync_started_at`, `last_sync_completed_at`, `last_sync_status`, `last_error`
- `last_successful_sync_summary`: summary of the last successful run, including counters like `processed`, `degraded_items`, `sink_failed_items`, `ingestion_failed_items`, `detached_conflicts`
- `created_at`, `updated_at`

## Source types

### `local_directory`

`config` requires:

```json
{
  "path": "/absolute/path/under/an/allowed/root"
}
```

Notes:
- Paths must resolve under `INGESTION_SOURCE_ALLOWED_ROOTS`.
- V1 supports manual sync and optional scheduled rescans.
- Local directory sources are intended for self-hosted/admin-controlled deployments where workers can access the configured path.

### `archive_snapshot`

`config` is currently empty on create:

```json
{}
```

Refreshes are driven by `POST /api/v1/ingestion-sources/{source_id}/archive`.

Supported archive upload formats:
- `.zip`
- `.tar`
- `.tar.gz`, `.tgz`
- `.tar.bz2`, `.tbz2`
- `.tar.xz`, `.txz`

Safety rules:
- path traversal members are rejected
- symlinks are rejected
- encrypted ZIPs are rejected

## Sink types

### `media`

Use for broader document ingestion. Mixed sources can include Markdown, text, HTML, JSON, XML, DOCX, RTF, PDF, and EPUB. Changed items update the existing bound media/document record when possible.

### `notes`

Use for text-first note sync. Notes are latest-state sync in v1 and do not preserve full historical note bodies by themselves.

If a sync-managed note is edited locally and diverges, the item becomes `conflict_detached` instead of being overwritten on the next sync.

## Create

`POST /api/v1/ingestion-sources`

Example request for a local-directory notes source:

```json
{
  "source_type": "local_directory",
  "sink_type": "notes",
  "policy": "canonical",
  "enabled": true,
  "schedule_enabled": false,
  "schedule": {},
  "config": {
    "path": "/srv/tldw/notes"
  }
}
```

Example response:

```json
{
  "id": 12,
  "user_id": 1,
  "source_type": "local_directory",
  "sink_type": "notes",
  "policy": "canonical",
  "enabled": true,
  "schedule_enabled": false,
  "schedule_config": {},
  "config": {
    "path": "/srv/tldw/notes"
  },
  "active_job_id": null,
  "last_successful_snapshot_id": null,
  "last_sync_started_at": null,
  "last_sync_completed_at": null,
  "last_sync_status": null,
  "last_error": null,
  "last_successful_sync_summary": {},
  "created_at": "2026-03-08 12:00:00",
  "updated_at": "2026-03-08 12:00:00"
}
```

## List

`GET /api/v1/ingestion-sources`

Returns all sources owned by the authenticated user.

Example response:

```json
[
  {
    "id": 12,
    "user_id": 1,
    "source_type": "archive_snapshot",
    "sink_type": "media",
    "policy": "canonical",
    "enabled": true,
    "schedule_enabled": false,
    "schedule_config": {},
    "config": {},
    "active_job_id": null,
    "last_successful_snapshot_id": 44,
    "last_sync_started_at": "2026-03-08 12:05:00",
    "last_sync_completed_at": "2026-03-08 12:05:03",
    "last_sync_status": "success",
    "last_error": null,
    "last_successful_sync_summary": {
      "processed": 8,
      "created": 2,
      "changed": 1,
      "deleted": 0,
      "unchanged": 5,
      "degraded_items": 1,
      "sink_failed_items": 1,
      "ingestion_failed_items": 0,
      "detached_conflicts": 0,
      "current_item_count": 8
    }
  }
]
```

## Get

`GET /api/v1/ingestion-sources/{source_id}`

Returns the same object shape as list, including `last_successful_sync_summary`.

## Update

`PATCH /api/v1/ingestion-sources/{source_id}`

Mutable fields:
- `policy`
- `enabled`
- `schedule_enabled`
- `schedule`

Example request:

```json
{
  "policy": "import_only",
  "schedule_enabled": true,
  "schedule": {
    "cron": "0 * * * *",
    "timezone": "UTC"
  }
}
```

Important constraints:
- `source_type`, `sink_type`, and source identity are immutable after the first successful sync.
- Attempts to change immutable fields after first success return `409`.

## Manual sync

`POST /api/v1/ingestion-sources/{source_id}/sync`

Response:

```json
{
  "status": "queued",
  "source_id": 12,
  "job_id": 301
}
```

This only enqueues work. Sync execution runs through the Jobs worker path.

## Archive refresh

`POST /api/v1/ingestion-sources/{source_id}/archive`

Multipart form field:
- `archive`: ZIP or tar-family upload

Response:

```json
{
  "status": "queued",
  "source_id": 12,
  "job_id": 302,
  "snapshot_status": "staged"
}
```

Notes:
- archive upload is only valid for `archive_snapshot` sources
- the uploaded archive is persisted as a source artifact
- a failed candidate refresh does not replace the prior successful snapshot

## Items

`GET /api/v1/ingestion-sources/{source_id}/items`

Returns tracked items for the source.

Example response:

```json
[
  {
    "id": 77,
    "source_id": 12,
    "normalized_relative_path": "alpha.md",
    "content_hash": "b1946ac92492d2347c6235b4d2611184",
    "sync_status": "sync_managed",
    "binding": {
      "note_id": "note-123",
      "sync_status": "sync_managed",
      "current_version": 4
    },
    "present_in_source": true
  }
]
```

Common `sync_status` values:
- `sync_managed`
- `active`
- `conflict_detached`
- `degraded_ingestion_error`
- `degraded_sink_error`
- `archived`

## Reattach

`POST /api/v1/ingestion-sources/{source_id}/items/{item_id}/reattach`

This is only supported for `notes` sinks and only when the item is currently `conflict_detached`.

It restores the binding to `sync_managed` and clears the tracked content hash so the next sync reapplies upstream content.

## Failure model

Sync runs are source-scoped, but failures are isolated per item where possible:
- extraction/parsing failure marks an item `degraded_ingestion_error`
- sink apply failure marks an item `degraded_sink_error`
- notes divergence marks an item `conflict_detached`

Successful items in the same run still apply, and the last successful snapshot summary records the degraded counters.

## Current limitations

- No dedicated WebUI yet.
- Archive refresh is snapshot-based; archive item rename continuity is still `delete + create`.
- Notes sync is latest-state sync, not full note-history preservation.
- The public API currently exposes source and item state, but not a dedicated job-status endpoint for ingestion sources beyond the shared Jobs system.
