# Reading List Digest + Progress (Design)

## Summary
Stage 4 adds two post-MVP capabilities for Reading List:
1) scheduled reading digests rendered via Outputs templates and stored as output artifacts, and
2) local-only reading progress tracking in the WebUI.

This document outlines the intended architecture and UX for both features.

## Goals
- Persist reading progress per item on the client only (no server storage).
- Restore reading position when reopening a saved article.
- Surface progress clearly in the reader UI.
- Allow users to configure digest schedules and render outputs using existing templates.
- Store digest artifacts via the Outputs system with retention metadata.

## Non-Goals
- Sync reading progress across devices or users.
- Expose reading progress in the API or export payloads.
- Provide “smart” recommendations beyond basic filtering for the first iteration.

## Reading Progress (local-only)
### Storage
- Use `createLocalRegistryBucket` with a prefix like `registry:reading-progress:`.
- Keyed by reading item id.
- Value schema:
  - `percent` (0–100 float)
  - `scrollTop` (px)
  - `scrollHeight` (px)
  - `clientHeight` (px)
- `updatedAt` recorded by the bucket metadata.

### Behavior
- Capture progress on scroll (debounced writes).
- On open, restore scroll position:
  - Prefer stored `scrollTop` when content height is unchanged.
  - Fall back to `percent` to compute scroll position if height changed.
- Only track when the content tab is active.

### UI
- Display a small progress bar + percent in the item detail header.
- Keep progress local; do not show in exports or API responses.

## Reading Digest Scheduling (planned)
### Data Model
- New table (per-user): `reading_digest_schedules`
  - `id` (uuid)
  - `tenant_id`, `user_id`
  - `name`
  - `cron`, `timezone`
  - `enabled`, `require_online`
  - `filters_json` (status/tags/favorite/date range/limit)
  - `template_name` or `template_id`, `format`
  - `last_run_at`, `next_run_at`, `last_status`
  - `created_at`, `updated_at`

### Scheduler
- APScheduler-based service (`reading_digest_scheduler.py`).
- On cron fire, enqueue a Jobs entry (domain `reading`, job_type `reading_digest`).
- Store schedule run status and next fire time after enqueue.

### Job Processing
- Worker `reading_digest_jobs_worker.py` consumes Jobs queue.
- Loads schedule, queries Reading List via `ReadingService.list_items`.
- Builds template context with `outputs_service.build_items_context_from_content_items`.
- Renders template (or fallback default markdown) and writes output file.
- Creates an output artifact with type `reading_digest` and metadata (schedule_id, filters, item_ids, template info).

### API
- CRUD endpoints under `/api/v1/reading/digests/schedules`.
- List generated outputs for reading digests (by type) under `/api/v1/reading/digests/outputs`.

### Tests
- Schedule create/get/list/update/delete.
- Job execution inserts output artifact and file.
- Template selection and fallback rendering.

## Security & Privacy
- Progress stays in client storage only.
- Digest outputs respect per-user outputs path validation.

## Rollout
- Phase 1: local-only progress (UI + storage).
- Phase 2: digest schedules + Jobs worker + outputs artifacts.
