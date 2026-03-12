# Authoritative Backup Scheduling Design

Date: 2026-03-10
Branch: `codex/admin-ui-backup-scheduling-authoritative`

## 1. Problem

The admin backup screen currently exposes a `Schedule` tab, but that schedule state lives only in browser `localStorage`. It is not shared across admins, not durable across devices, and not connected to any authoritative backend execution path. That is acceptable for a prototype but not for live customer operations.

The existing manual backup path is already real:

- `GET /api/v1/admin/backups`
- `POST /api/v1/admin/backups`
- `POST /api/v1/admin/backups/{backup_id}/restore`

The next production-readiness step is to replace the local-only schedule surface with a backend-backed schedule model that is truthful, shared, auditable, and actually executes.

## 2. Goals

- Add authoritative, platform-level shared backup schedules.
- Persist schedule configuration in the AuthNZ control-plane database.
- Use APScheduler only to detect due schedules.
- Use core Jobs for actual backup execution and run visibility.
- Reuse the existing `create_backup_snapshot(...)` service so manual and scheduled backups produce the same artifacts and retention behavior.
- Replace the admin UI schedule tab’s `localStorage` behavior with backend CRUD.
- Keep the visible schedule model simple: `daily | weekly | monthly`, time of day, retention count.

## 3. Non-Goals

- No cron or RRULE support in v1.
- No “backup all users” or fleet-wide multi-user sweep schedule in v1.
- No automatic cancellation of already queued/running jobs when a schedule is paused or deleted.
- No change to the existing manual backup and restore APIs beyond shared service reuse.
- No attempt to make backup scheduling per-admin or per-browser; this is platform policy.

## 4. Chosen Approach

Use platform-owned schedule records plus APScheduler enqueue plus Jobs-backed execution.

Why:

- This is admin-visible operational work, which matches the repository guidance to prefer Jobs.
- Jobs give durable status, retries, queue visibility, and a worker model already used elsewhere in the repo.
- APScheduler remains responsible only for “when is this schedule due,” not “do the backup now.”
- The existing manual backup service already knows how to resolve dataset DB paths, create artifacts, and prune backups.

## 5. Schedule Ownership And Scope

Schedules are platform-level shared records, visible to all authorized admins.

Rules:

- `authnz` schedules are platform-level and may only be created or modified by platform admins.
- Per-user datasets (`media`, `chacha`, `prompts`, `evaluations`, `audit`) require an explicit `target_user_id`.
- Creating or mutating a per-user schedule requires the same target-user scope checks already used by the manual backup endpoints.
- Schedules are not “owned” by the admin who created them; they are shared operational policy.

## 6. V1 Constraints To Keep Behavior Truthful

### 6.1 One active schedule per backup directory

The existing retention logic prunes at the dataset/user backup directory level, not per schedule. That means two schedules targeting the same `(dataset, target_user_id)` would compete and whichever ran last would effectively control retention.

V1 rule:

- Allow at most one active schedule per `(dataset, target_user_id)`.
- For `authnz`, allow at most one active schedule for `dataset='authnz'`.

This keeps retention semantics understandable and avoids schedule collisions.

### 6.2 Persist timezone on the schedule row

The UI keeps a simple time-of-day model. To avoid silent drift when server config changes later, each schedule stores its own timezone snapshot.

V1 rule:

- New schedules default to the platform scheduler timezone, likely `UTC`.
- Existing schedules keep their stored timezone even if the platform default changes.

### 6.3 Explicit weekly/monthly anchor rules

The current UI exposes `weekly` and `monthly` without asking for weekday or day-of-month. V1 keeps the simple UI, but the backend makes the semantics explicit:

- `daily`: run every day at `time_of_day` in the stored timezone
- `weekly`: anchor to the weekday at create time, or at the time frequency is changed to `weekly`
- `monthly`: anchor to the day-of-month at create time, or at the time frequency is changed to `monthly`
- If a month does not contain the anchored day, run on the last day of that month

The UI will display the derived schedule description returned by the backend, such as:

- `Weekly on Tuesday at 02:00 UTC`
- `Monthly on day 31 at 02:00 UTC (last day fallback)`

## 7. Persistence Model

Use the AuthNZ control-plane DB for both SQLite and PostgreSQL backends.

### 7.1 `backup_schedules`

Core fields:

- `id`
- `dataset`
- `target_user_id` nullable
- `frequency` (`daily | weekly | monthly`)
- `time_of_day` (`HH:MM`)
- `timezone`
- `anchor_day_of_week` nullable
- `anchor_day_of_month` nullable
- `retention_count`
- `is_paused`
- `created_by_user_id`
- `updated_by_user_id`
- `created_at`
- `updated_at`
- `next_run_at`
- `last_run_at`
- `last_status`
- `last_job_id`
- `last_error`

Recommended constraints:

- `dataset` limited to supported backup datasets
- `target_user_id` required for all datasets except `authnz`
- unique active schedule per `(dataset, target_user_id)`
- `retention_count >= 1`

### 7.2 `backup_schedule_runs`

This second table exists for two reasons:

1. HA-safe claim/dedup of scheduler fire slots
2. durable schedule-run history

Core fields:

- `id`
- `schedule_id`
- `scheduled_for`
- `run_slot_key`
- `status` (`queued | running | succeeded | failed`)
- `job_id`
- `error`
- `enqueued_at`
- `started_at`
- `completed_at`

Constraint:

- unique `run_slot_key`, where the key is derived from `(schedule_id, scheduled_for)`

The schedule row keeps only the latest summary (`last_*`). The runs table preserves per-fire-slot history and provides the scheduler claim primitive.

## 8. API Surface

Keep existing manual backup APIs as-is.

Add authoritative schedule endpoints under the existing admin data-ops router:

- `GET /api/v1/admin/backup-schedules`
- `POST /api/v1/admin/backup-schedules`
- `PATCH /api/v1/admin/backup-schedules/{schedule_id}`
- `POST /api/v1/admin/backup-schedules/{schedule_id}/pause`
- `POST /api/v1/admin/backup-schedules/{schedule_id}/resume`
- `DELETE /api/v1/admin/backup-schedules/{schedule_id}`

Response fields should include display-ready data:

- `schedule_description`
- `next_run_at`
- `last_run_at`
- `last_status`
- `last_job_id`
- `last_error`

Create/update validation rules:

- reject unknown datasets
- require `target_user_id` for per-user datasets
- reject `target_user_id` for `authnz`
- enforce admin scope for per-user schedules
- restrict `authnz` schedule mutation to platform admins
- reject duplicate active schedules for the same `(dataset, target_user_id)`

## 9. Scheduler Design

Create a dedicated backup scheduler service, modeled after existing scheduler services like:

- `tldw_Server_API/app/services/reading_digest_scheduler.py`
- `tldw_Server_API/app/services/connectors_sync_scheduler.py`

Responsibilities:

- load active schedules from the control-plane DB
- register/update/remove APScheduler jobs
- compute the next due fire time using the stored frequency, anchors, time, and timezone
- claim a run slot in `backup_schedule_runs`
- enqueue a Jobs record for the claimed slot
- update `next_run_at` on the schedule row

Important behavior:

- APScheduler must not create backup artifacts directly.
- APScheduler must be safe in multi-instance deployments.
- Before enqueue, the scheduler claims the specific fire slot in `backup_schedule_runs`; if another instance already claimed it, do nothing.

## 10. Jobs Execution Design

Add a dedicated Jobs domain for scheduled backups.

Recommended shared constants:

- `BACKUP_SCHEDULE_DOMAIN = "admin_backups"`
- `BACKUP_SCHEDULE_JOB_TYPE = "scheduled_backup"`
- queue default such as `"admin-backups"`

The Jobs payload should be intentionally small:

- `schedule_id`
- `scheduled_for`
- optional `run_id`

The worker must reload the authoritative schedule row before executing. It must not trust a stale payload for dataset, user, or retention policy.

Worker flow:

1. Load the schedule row
2. If the schedule no longer exists, exit safely
3. If the schedule is paused, mark the run as skipped/failed with a clear reason and exit
4. Resolve the authoritative dataset and target user
5. Call `create_backup_snapshot(...)`
6. Update `backup_schedule_runs`
7. Update `backup_schedules.last_*`

Pause/delete semantics:

- Pause/delete stops future enqueues
- Already queued/running jobs are not canceled automatically in v1

## 11. Frontend Design

Replace the `Schedule` tab’s local-only state in `admin-ui/components/data-ops/BackupsSection.tsx`.

### 11.1 Keep

- existing `Backups` tab
- manual create backup flow
- manual restore flow
- existing basic schedule form shape where possible

### 11.2 Add

- backend-backed list/create/update/pause/resume/delete schedule actions
- a required `Target user` control for per-user datasets
- read-only schedule description returned from backend
- run metadata columns:
  - next run
  - last run
  - last status
  - last error (if any)

### 11.3 Remove

- `localStorage` schedule persistence
- “applied locally” success semantics
- browser-local schedule truth model

The UI may continue to keep the form simple, while the backend derives and returns anchor semantics.

## 12. Failure Semantics

- Schedule create/update/delete/pause/resume fail closed. No success UI if the backend mutation fails.
- Scheduler enqueue failure updates run metadata and logs, but does not silently mark the schedule successful.
- Backup job success is the only source of truth for successful scheduled execution.
- Missing dataset DBs, invalid user scope, or backup service failures surface as failed runs, not as synthetic “0 work needed” outcomes.

## 13. Auditability

Emit admin audit events for:

- schedule create
- schedule update
- schedule pause
- schedule resume
- schedule delete
- scheduled run enqueue

Suggested resource types:

- `backup_schedule`
- `backup_schedule_run`

Suggested metadata:

- dataset
- target_user_id
- frequency
- timezone
- retention_count
- scheduled_for
- job_id
- outcome status

## 14. Testing Strategy

### Backend

- repo tests for schedule CRUD in SQLite and PostgreSQL
- repo tests for unique active schedule enforcement
- repo tests for run-slot claim dedup
- API tests for create/list/update/pause/resume/delete
- API tests for scope enforcement
- API tests for `authnz` platform-admin restriction
- scheduler tests proving exactly one job enqueue per fire slot
- worker tests proving scheduled jobs call the existing backup service and update run metadata

### Frontend

- `BackupsSection` tests replace `localStorage` schedule expectations with API-backed behavior
- tests for required `target user` on per-user datasets
- tests for `authnz` hiding/disabling target-user selection
- tests for derived weekly/monthly display copy
- tests for failure banners and disabled states

### Integration

- end-to-end backend test: persisted schedule -> due slot claim -> queued job -> backup artifact visible through existing backups list

## 15. Rollout Notes

This design intentionally keeps v1 small:

- no cron parser
- no all-users orchestration
- no automatic queued-job cancellation
- no separate retention model per schedule

The goal is to make the current admin schedule surface authoritative and production-safe without expanding the problem into a full backup orchestration platform.
