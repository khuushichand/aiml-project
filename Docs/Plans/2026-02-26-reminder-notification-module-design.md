# Reminder System and Notification Module Design

**Date:** 2026-02-26
**Status:** Approved (brainstorming)
**Scope:** v1 design for reminders/tasks + in-app notifications in `tldw_server`

## 1. Problem and Goals

`tldw_server` needs a defined system that lets users:

1. Receive notifications about system events and reminders.
2. Create reminders/follow-ups to continue work on specific items.
3. Be notified when background jobs/tasks complete or fail.

Target UX is functionally aligned with ChatGPT Tasks-style behavior: one-time and recurring schedules, offline execution, and a user-manageable task/reminder list.

## 2. Product Decisions Captured

The following decisions were finalized during brainstorming:

- Delivery channels in v1: **in-app only**.
- Reminder attachment model: **freeform content + optional link/entity reference**.
- Job completion notification policy in v1: **all owned jobs by default**.
- Reminder scheduling support in v1: **one-time + recurring + timezone**.
- In-app UX in v1: **inbox + realtime updates + snooze from toast**.

## 3. Approaches Considered

### A. Jobs-centric execution (recommended)
Use APScheduler only for due-time triggering, enqueue task executions into the existing Jobs module, and persist notifications into an inbox table.

- Pros: aligns with repository decision guide (user-visible work => Jobs), retries/idempotency/ops visibility are already solved.
- Cons: more components than direct scheduler write-path.

### B. Direct scheduler to DB notifications
APScheduler directly writes due notifications.

- Pros: fewer moving parts initially.
- Cons: weaker consistency with Jobs operational model and reduced reliability controls.

### C. Extend existing claims/self-monitoring notification paths
Reuse domain-specific tables/services for generic reminders.

- Pros: quick bootstrap.
- Cons: domain coupling and long-term maintenance overhead.

**Recommendation:** Approach A.

## 4. Proposed Architecture

### 4.1 Components

- **Tasks module** (new): manages user reminder/task definitions.
- **Notifications module** (new): manages inbox entries, unread/read state, preferences, and realtime stream.
- **Task scheduler service** (new): APScheduler service that registers enabled schedules and enqueues Jobs; runs only on the active lease holder in multi-instance deployments.
- **Reminder jobs worker** (new): consumes reminder jobs, writes reminder notifications.
- **Jobs-event notification bridge** (new): tails `job_events` and emits in-app notifications for `job.completed`/`job.failed` for owned jobs; uses a persisted cursor with lease ownership.

### 4.2 Reused primitives

- Core `Jobs` module (leases/retries/idempotency/events/admin tooling).
- Existing scheduler patterns from `reading_digest_scheduler` and `workflows_scheduler`.
- Existing SSE conventions (jobs events stream/admin events stream).
- Existing per-user DB patterns used by `Collections` / `Guardian` / `Claims`.

### 4.3 Auth and Access Model

- All routes are authenticated and owner-scoped by default.
- Task/inbox read routes require read-level task/notification scopes.
- Task mutating routes (create/update/delete) require write/control task scope.
- Notification preference updates require notification settings write scope.
- Admin-only visibility beyond owner scope is out of v1 scope.

### 4.4 Multi-instance Ownership Semantics (v1)

- Scheduler and bridge processes may start on all app instances, but only one active lease holder performs enqueue/tail loops at a time.
- Lease acquisition/renewal reuses existing Jobs lease patterns (heartbeat + expiry), with automatic takeover after expiry.
- Bridge cursor is committed only after its batch notification writes commit; a takeover resumes from the last committed cursor.
- Processing model is at-least-once with deterministic dedupe keys (`run_slot_key`, `dedupe_key`) so failover/retry does not surface duplicate inbox entries.

## 5. Data Model (v1)

Persist in per-user DB (new tables in a module local to reminders/notifications).

### 5.1 `reminder_tasks`

- `id` (text/uuid PK)
- `user_id`, `tenant_id`
- `title`, `body`
- optional link fields: `link_type`, `link_id`, `link_url`
- schedule fields:
  - `schedule_kind` (`one_time` | `recurring`)
  - `run_at` (one-time)
  - `cron` (recurring)
  - `timezone`
- execution/status fields:
  - `enabled`
  - `last_run_at`, `next_run_at`, `last_status`
- `created_at`, `updated_at`

### 5.2 `reminder_task_runs`

- `id` (PK)
- `task_id`, `user_id`
- `scheduled_for`
- `job_id`
- `run_slot_utc` (normalized UTC ISO timestamp used for idempotency)
- `run_slot_key` (stable derived key from `task_id + run_slot_utc`)
- `status` (`queued|running|succeeded|failed|skipped`)
- `error`
- `created_at`, `started_at`, `completed_at`
- unique index on `(task_id, run_slot_key)` for per-slot exactly-once semantics

### 5.3 `user_notifications`

- `id` (PK)
- `user_id`
- `kind` (`reminder_due|reminder_failed|job_completed|job_failed`)
- `title`, `message`, `severity`
- source references:
  - `source_task_id`, `source_task_run_id`, `source_job_id`
  - `source_domain`, `source_job_type`
- optional link fields: `link_type`, `link_id`, `link_url`
- `dedupe_key` (unique per user)
- retention fields: `retention_until`, `archived_at`
- `created_at`, `read_at`, `dismissed_at`

### 5.4 `notification_preferences`

- `user_id` (PK)
- `reminder_enabled` (default true)
- `job_completed_enabled` (default true)
- `job_failed_enabled` (default true)
- `updated_at`

### 5.5 `notification_bridge_state`

- `consumer_name` (PK; e.g. `jobs_event_notifications_v1`)
- `last_event_id` (high-watermark cursor)
- `lease_owner_id`
- `lease_expires_at`
- `updated_at`

## 6. API Surface (v1)

### 6.1 Tasks API

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `PATCH /api/v1/tasks/{id}`
- `DELETE /api/v1/tasks/{id}`

### 6.2 Notifications API

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/mark-read`
- `POST /api/v1/notifications/{id}/dismiss`
- `POST /api/v1/notifications/{id}/snooze`
- `GET /api/v1/notifications/preferences`
- `PATCH /api/v1/notifications/preferences`
- `GET /api/v1/notifications/stream` (SSE)

### 6.3 Auth Contract (v1)

- `GET /api/v1/tasks*` requires task read scope.
- `POST/PATCH/DELETE /api/v1/tasks*` requires task control scope.
- `GET /api/v1/notifications*` requires notification read scope.
- `POST/PATCH /api/v1/notifications*` requires notification control scope.
- Endpoint-level rate limits follow existing RBAC rate-limit dependency patterns.

### 6.4 SSE Contract (v1)

- `GET /api/v1/notifications/stream` accepts reconnect cursor via `Last-Event-ID` header (preferred) or `after` query parameter.
- Stream event payload includes stable `event_id`, `notification_id`, `kind`, and `created_at`.
- Server replays missed events for `event_id > cursor` up to a bounded replay window (default `500` events).
- If cursor is stale/outside replay window, server emits `reset_required`; client must refetch via `GET /api/v1/notifications` and resume streaming from fresh cursor.

## 7. Runtime Flows

### 7.1 Reminder due flow

1. Scheduler computes due slot.
2. Scheduler enqueues Jobs entry (domain e.g. `notifications`, job_type `reminder_due`) with idempotency key.
3. Worker executes reminder, writes `reminder_task_runs` and `user_notifications`.
4. SSE emits new notification event; UI updates badge and shows toast.

### 7.2 Job completion/failure flow

1. Bridge worker polls/tails `job_events` for `job.completed` + `job.failed`.
2. Resolves owner and applies preference toggles.
3. Writes deduped `user_notifications` rows.
4. Commits bridge cursor only after writes succeed.
5. SSE emits updates.

### 7.3 Snooze flow (toast action)

1. Client sends snooze request via notification id (`/notifications/{id}/snooze`).
2. Server resolves source notification and creates derived one-time reminder preserving optional link metadata.
3. Scheduler handles it as normal reminder task.

### 7.4 Notification Retention and Prune flow

1. Inbox rows are created with concrete defaults:
   - `reminder_due` / `reminder_failed`: keep for `90` days.
   - `job_completed`: keep for `30` days.
   - `job_failed`: keep for `60` days.
2. Read/dismissed notifications become prune-eligible `30` days after `read_at`/`dismissed_at` (even if base retention is longer).
3. Prune worker archives expired rows first (`archived_at` set), then hard-deletes archived rows after `7` days.
4. Prune is idempotent and scoped per user DB; metrics are emitted for archived/deleted counts.

## 8. Error Handling and Guardrails

- Idempotency keys:
  - task run enqueue: `task:{task_id}:{run_slot_utc}`
  - notification dedupe: e.g. `job:{job_id}:{event_type}`
- Run slot normalization:
  - all recurrence slots are normalized to UTC (`run_slot_utc`) before enqueue.
  - ambiguous/non-existent local DST timestamps are resolved at schedule evaluation time, then persisted as UTC.
- Validate cron/timezone with `422` responses on invalid input.
- Scheduler settings: `max_instances=1` per lease holder, coalescing enabled, bounded misfire grace.
- Active task cap in v1 (default `10`, configurable env), where active means `enabled=true` and `next_run_at IS NOT NULL`.
- One-time tasks auto-disable after terminal success and no longer count toward cap.
- Cap exceedance returns `409` with a typed error code (for deterministic UI handling).
- All notification state is persisted first; realtime stream is additive.
- Strict per-user ownership scope across all endpoints.
- Realtime flood controls:
  - per-user burst cap for SSE/toasts.
  - optional coalesced summary notification for high event volume.
- Link safety:
  - validate `link_url` scheme/host policy before persistence or rendering.
- Retention:
  - notifications are pruned/archived by policy to prevent unbounded table growth.

## 9. Important Hardening Item

To support “notify for all owned jobs”, event rows must reliably carry owner attribution for completion/failure paths.

Release gate for v1:

- no `job.completed`/`job.failed` notification is emitted unless owner resolution succeeds.
- all completion/failure emission paths are covered by tests asserting owner fields are present/derivable.
- unresolved-owner events are counted and logged for operator visibility.

## 10. Testing Strategy

### Unit tests

- Schedule validation and normalization.
- Next-run computation (including timezone and DST boundaries).
- Dedup/idempotency behavior.
- Snooze creates correctly-derived one-time reminder.

### Integration tests

- Task CRUD + pause/resume.
- Notifications list/unread/mark-read/dismiss.
- Notification snooze creates derived one-time reminder with preserved links.
- Preferences impact on job-completion notifications.
- AuthNZ owner scoping (single-user + multi-user).
- Route-level permission/scope enforcement for all new endpoints.

### Worker/service tests

- Due reminder enqueued exactly once per slot.
- Worker writes run + notification records.
- Job-events bridge writes expected notifications and dedupes.
- Job-events bridge skips events lacking owner attribution (and records metrics).
- Bridge cursor commits only after successful batch write; failover resumes from last committed cursor.
- Lease failover permits single active scheduler/bridge owner at a time.
- Notification prune worker enforces retention policy safely.

### Frontend/E2E

- Badge increments on new notification.
- Toast appears on realtime event.
- Snooze from toast (`/notifications/{id}/snooze`) schedules and later delivers reminder.
- High-volume event bursts are coalesced/throttled correctly.

### Security/quality

- Bandit on touched backend scope before completion.
- Regression checks for existing Jobs events consumers.

## 11. Rollout Plan

### Phase 1 (v1)

- Tasks CRUD + scheduling + reminder worker.
- In-app inbox API + unread/read/dismiss + preferences.
- Realtime notification stream.
- Toast + badge + snooze UX.
- Job completion/failure notification bridge (owned jobs default enabled).
- Notification retention/prune worker and related metrics.

### Phase 2

- Rich inbox filtering/search.
- Per-domain/job-type subscription preferences.
- Quiet-hours/digest behavior.

### Phase 3

- Optional external channels (email/webhook).
- Advanced recurrence templates.
- Notification analytics and ops dashboards.

## 12. Non-goals for v1

- Multi-channel external delivery (email/webhooks).
- Complex escalation/routing rules.
- Cross-domain unification with claims/self-monitoring notification tables.
