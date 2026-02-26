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
- **Task scheduler service** (new): APScheduler service that registers enabled schedules and enqueues Jobs.
- **Reminder jobs worker** (new): consumes reminder jobs, writes reminder notifications.
- **Jobs-event notification bridge** (new): tails `job_events` and emits in-app notifications for `job.completed`/`job.failed` for owned jobs.

### 4.2 Reused primitives

- Core `Jobs` module (leases/retries/idempotency/events/admin tooling).
- Existing scheduler patterns from `reading_digest_scheduler` and `workflows_scheduler`.
- Existing SSE conventions (jobs events stream/admin events stream).
- Existing per-user DB patterns used by `Collections` / `Guardian` / `Claims`.

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
- `status` (`queued|running|succeeded|failed|skipped`)
- `error`
- `created_at`, `started_at`, `completed_at`
- unique idempotency key per run slot

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
- `created_at`, `read_at`, `dismissed_at`

### 5.4 `notification_preferences`

- `user_id` (PK)
- `reminder_enabled` (default true)
- `job_completed_enabled` (default true)
- `job_failed_enabled` (default true)
- `updated_at`

## 6. API Surface (v1)

### 6.1 Tasks API

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `PATCH /api/v1/tasks/{id}`
- `DELETE /api/v1/tasks/{id}`
- `POST /api/v1/tasks/{id}/snooze`

### 6.2 Notifications API

- `GET /api/v1/notifications`
- `GET /api/v1/notifications/unread-count`
- `POST /api/v1/notifications/mark-read`
- `POST /api/v1/notifications/{id}/dismiss`
- `GET /api/v1/notifications/preferences`
- `PATCH /api/v1/notifications/preferences`
- `GET /api/v1/notifications/stream` (SSE)

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
4. SSE emits updates.

### 7.3 Snooze flow (toast action)

1. Client sends snooze request.
2. Server creates derived one-time reminder preserving optional link metadata.
3. Scheduler handles it as normal reminder task.

## 8. Error Handling and Guardrails

- Idempotency keys:
  - task run enqueue: `task:{task_id}:{scheduled_for_iso}`
  - notification dedupe: e.g. `job:{job_id}:{event_type}`
- Validate cron/timezone with `422` responses on invalid input.
- Scheduler settings: `max_instances=1`, coalescing enabled, bounded misfire grace.
- Active task cap in v1 (default `10`, configurable env).
- All notification state is persisted first; realtime stream is additive.
- Strict per-user ownership scope across all endpoints.

## 9. Important Hardening Item

To support “notify for all owned jobs”, event rows must reliably carry owner attribution for completion/failure paths. Existing code already writes these events but some pathways may need explicit owner propagation hardening.

## 10. Testing Strategy

### Unit tests

- Schedule validation and normalization.
- Next-run computation (including timezone and DST boundaries).
- Dedup/idempotency behavior.
- Snooze creates correctly-derived one-time reminder.

### Integration tests

- Task CRUD + pause/resume + snooze.
- Notifications list/unread/mark-read/dismiss.
- Preferences impact on job-completion notifications.
- AuthNZ owner scoping (single-user + multi-user).

### Worker/service tests

- Due reminder enqueued exactly once per slot.
- Worker writes run + notification records.
- Job-events bridge writes expected notifications and dedupes.

### Frontend/E2E

- Badge increments on new notification.
- Toast appears on realtime event.
- Snooze from toast schedules and later delivers reminder.

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

