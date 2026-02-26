# Reminder and Notifications v1 Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build v1 user reminders/tasks and in-app notifications (inbox + realtime + snooze), including owned-job completion/failure notifications.

**Architecture:** Use APScheduler only to enqueue due reminder runs into the existing Jobs module. Use dedicated reminder/notification persistence in the per-user Collections DB and process delivery via Jobs workers. Provide REST + SSE APIs for task/inbox management and realtime UI updates.

**Tech Stack:** FastAPI, Pydantic v2, APScheduler, Jobs manager/worker SDK, SQLite/Postgres-compatible DB adapters via `Collections_DB`, pytest, Next.js frontend toast/inbox components.

---

## Worktree Prerequisite

- Create and use an isolated worktree before implementation:
- Run: `git worktree add .worktrees/reminder_notifications -b codex/reminder-notifications-v1`
- Expected: new worktree created and checked out on a `codex/*` branch.

### Task 1: Add API Schemas for Tasks and Notifications

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/reminders_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/__init__.py`
- Test: `tldw_Server_API/tests/Notifications/test_reminders_schemas.py`

**Step 1: Write the failing test**

```python
from pydantic import ValidationError
from tldw_Server_API.app.api.v1.schemas.reminders_schemas import ReminderTaskCreateRequest


def test_reminder_task_create_requires_schedule_fields():
    try:
        ReminderTaskCreateRequest(title="Follow up", schedule_kind="one_time")
        assert False, "expected validation error"
    except ValidationError:
        assert True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_reminders_schemas.py::test_reminder_task_create_requires_schedule_fields -v`
Expected: FAIL due to missing schema module/class.

**Step 3: Write minimal implementation**

```python
class ReminderTaskCreateRequest(BaseModel):
    title: str
    body: str | None = None
    schedule_kind: Literal["one_time", "recurring"]
    run_at: str | None = None
    cron: str | None = None
    timezone: str | None = None
```

Add validators enforcing:
- `one_time` => `run_at` required
- `recurring` => `cron` + `timezone` required

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/reminders_schemas.py tldw_Server_API/app/api/v1/schemas/__init__.py tldw_Server_API/tests/Notifications/test_reminders_schemas.py
git commit -m "feat(reminders): add request/response schemas"
```

### Task 2: Add Reminder/Notification Tables and DB Methods

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/Collections_DB.py`
- Test: `tldw_Server_API/tests/Collections/test_reminders_notifications_db.py`

**Step 1: Write the failing test**

```python
def test_create_and_list_reminder_task(collections_db):
    task_id = collections_db.create_reminder_task(user_id="1", title="Ping", schedule_kind="one_time", run_at="2026-03-01T10:00:00+00:00")
    rows = collections_db.list_reminder_tasks(user_id="1")
    assert any(r.id == task_id for r in rows)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Collections/test_reminders_notifications_db.py::test_create_and_list_reminder_task -v`
Expected: FAIL due to missing schema/table/method.

**Step 3: Write minimal implementation**

- Add table DDL/backfill for:
  - `reminder_tasks`
  - `reminder_task_runs`
  - `user_notifications`
  - `notification_preferences`
- Add methods:
  - `create_reminder_task`, `get_reminder_task`, `list_reminder_tasks`, `update_reminder_task`, `delete_reminder_task`
  - `create_reminder_task_run`, `update_reminder_task_run_status`
  - `create_user_notification`, `list_user_notifications`, `mark_user_notifications_read`, `dismiss_user_notification`, `count_unread_user_notifications`
  - `get_notification_preferences`, `update_notification_preferences`

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/Collections_DB.py tldw_Server_API/tests/Collections/test_reminders_notifications_db.py
git commit -m "feat(reminders): add reminder and notification persistence"
```

### Task 3: Build Reminder Domain Service (CRUD + Snooze)

**Files:**
- Create: `tldw_Server_API/app/core/Reminders/reminders_service.py`
- Test: `tldw_Server_API/tests/Notifications/test_reminders_service.py`

**Step 1: Write the failing test**

```python
def test_snooze_creates_one_time_task(reminders_service):
    new_task = reminders_service.snooze_task(task_id="t1", user_id="1", minutes=30)
    assert new_task.schedule_kind == "one_time"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_reminders_service.py::test_snooze_creates_one_time_task -v`
Expected: FAIL due to missing service.

**Step 3: Write minimal implementation**

```python
class RemindersService:
    def snooze_task(self, task_id: str, user_id: str, minutes: int):
        # clone task content and create one-time task at now + minutes
        ...
```

Include ownership checks and sane bounds for `minutes`.

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Reminders/reminders_service.py tldw_Server_API/tests/Notifications/test_reminders_service.py
git commit -m "feat(reminders): add core reminder service with snooze"
```

### Task 4: Add Reminder Scheduler Service (APScheduler -> Jobs)

**Files:**
- Create: `tldw_Server_API/app/services/reminders_scheduler.py`
- Test: `tldw_Server_API/tests/Notifications/test_reminders_scheduler.py`

**Step 1: Write the failing test**

```python
async def test_due_slot_enqueues_job_once(reminders_scheduler, monkeypatch):
    created = []
    monkeypatch.setattr(reminders_scheduler._jobs, "create_job", lambda **k: created.append(k) or {"id": 1})
    await reminders_scheduler._run_task_schedule("task_1", user_id=1)
    assert len(created) == 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_reminders_scheduler.py::test_due_slot_enqueues_job_once -v`
Expected: FAIL due to missing scheduler module.

**Step 3: Write minimal implementation**

- Mirror `reading_digest_scheduler` patterns:
  - start/stop lifecycle
  - user DB rescan
  - per-schedule APS registration
  - run-slot idempotency key: `task:{task_id}:{run_slot}`
- Enqueue Jobs with dedicated domain/job type, owner user id set.

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/reminders_scheduler.py tldw_Server_API/tests/Notifications/test_reminders_scheduler.py
git commit -m "feat(reminders): schedule reminder tasks into Jobs"
```

### Task 5: Add Reminder Jobs Handler and Worker

**Files:**
- Create: `tldw_Server_API/app/core/Reminders/reminder_jobs.py`
- Create: `tldw_Server_API/app/services/reminder_jobs_worker.py`
- Test: `tldw_Server_API/tests/Notifications/test_reminder_jobs_worker.py`

**Step 1: Write the failing test**

```python
async def test_reminder_job_creates_notification(reminder_job_handler, fake_job):
    result = await reminder_job_handler(fake_job)
    assert result["status"] == "succeeded"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_reminder_jobs_worker.py::test_reminder_job_creates_notification -v`
Expected: FAIL due to missing handler.

**Step 3: Write minimal implementation**

- Parse job payload (`task_id`, `user_id`, `scheduled_for`).
- Create `reminder_task_runs` row.
- Create `user_notifications` row (`kind=reminder_due`).
- Mark one-time tasks disabled after success.

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Reminders/reminder_jobs.py tldw_Server_API/app/services/reminder_jobs_worker.py tldw_Server_API/tests/Notifications/test_reminder_jobs_worker.py
git commit -m "feat(reminders): add reminder jobs handler and worker"
```

### Task 6: Add Jobs Event -> In-App Notification Bridge

**Files:**
- Create: `tldw_Server_API/app/services/jobs_notifications_service.py`
- Test: `tldw_Server_API/tests/Notifications/test_jobs_notifications_service.py`

**Step 1: Write the failing test**

```python
async def test_job_completed_event_creates_notification(service, sample_job_event):
    n = await service.process_event(sample_job_event)
    assert n.kind == "job_completed"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_jobs_notifications_service.py::test_job_completed_event_creates_notification -v`
Expected: FAIL due to missing service.

**Step 3: Write minimal implementation**

- Poll/tail `job_events` for `job.completed` and `job.failed`.
- Resolve owning user and enforce prefs.
- Write deduped `user_notifications` rows.
- Persist cursor safely.

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/jobs_notifications_service.py tldw_Server_API/tests/Notifications/test_jobs_notifications_service.py
git commit -m "feat(notifications): bridge job events into user inbox"
```

### Task 7: Add Tasks and Notifications API Endpoints

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/reminders.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/notifications.py`
- Modify: `tldw_Server_API/app/main.py` (router registration)
- Test: `tldw_Server_API/tests/Notifications/test_reminders_api.py`
- Test: `tldw_Server_API/tests/Notifications/test_notifications_api.py`

**Step 1: Write the failing tests**

```python
def test_create_reminder_task(client, auth_headers):
    res = client.post("/api/v1/tasks", json={"title": "Review", "schedule_kind": "one_time", "run_at": "2026-03-01T10:00:00+00:00"}, headers=auth_headers)
    assert res.status_code == 201
```

```python
def test_unread_notification_count(client, auth_headers):
    res = client.get("/api/v1/notifications/unread-count", headers=auth_headers)
    assert res.status_code == 200
    assert "unread_count" in res.json()
```

**Step 2: Run tests to verify they fail**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_reminders_api.py::test_create_reminder_task -v`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_notifications_api.py::test_unread_notification_count -v`

Expected: FAIL due to missing endpoints.

**Step 3: Write minimal implementation**

Implement:
- `/api/v1/tasks` CRUD + `/api/v1/tasks/{id}/snooze`
- `/api/v1/notifications` list/read/dismiss/unread-count/preferences

**Step 4: Run tests to verify they pass**

Run the two pytest commands above.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/reminders.py tldw_Server_API/app/api/v1/endpoints/notifications.py tldw_Server_API/app/main.py tldw_Server_API/tests/Notifications/test_reminders_api.py tldw_Server_API/tests/Notifications/test_notifications_api.py
git commit -m "feat(api): add reminders and notifications endpoints"
```

### Task 8: Add Notifications SSE Stream Endpoint

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/notifications.py`
- Test: `tldw_Server_API/tests/Notifications/test_notifications_sse.py`

**Step 1: Write the failing test**

```python
async def test_notifications_stream_returns_sse_frame(async_client, auth_headers):
    resp = await async_client.get("/api/v1/notifications/stream", headers=auth_headers)
    assert resp.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_notifications_sse.py::test_notifications_stream_returns_sse_frame -v`
Expected: FAIL.

**Step 3: Write minimal implementation**

- Add SSE stream with cursor support and heartbeat.
- Emit on newly created `user_notifications` rows.

**Step 4: Run test to verify it passes**

Run: same pytest command as Step 2.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/notifications.py tldw_Server_API/tests/Notifications/test_notifications_sse.py
git commit -m "feat(notifications): add SSE stream endpoint"
```

### Task 9: Wire Startup/Shutdown Services

**Files:**
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Notifications/test_notifications_service_lifecycle.py`

**Step 1: Write the failing test**

```python
def test_notifications_services_start_when_enabled(monkeypatch):
    monkeypatch.setenv("REMINDERS_SCHEDULER_ENABLED", "true")
    # assert startup wires scheduler and workers
    assert True
```

**Step 2: Run test to verify it fails meaningfully**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications/test_notifications_service_lifecycle.py -v`
Expected: FAIL until lifecycle wiring exists.

**Step 3: Write minimal implementation**

- Start/stop:
  - reminders scheduler
  - reminder jobs worker
  - jobs notifications bridge worker
- Follow existing `reading_digest` and `jobs_webhooks` lifecycle patterns.

**Step 4: Run test to verify it passes**

Run: same pytest command.
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/main.py tldw_Server_API/tests/Notifications/test_notifications_service_lifecycle.py
git commit -m "feat(notifications): wire scheduler and workers into app lifecycle"
```

### Task 10: Frontend Inbox, Badge, Toast, and Snooze Action

**Files:**
- Create: `apps/tldw-frontend/pages/notifications.tsx`
- Create: `apps/tldw-frontend/lib/api/notifications.ts`
- Modify: `apps/tldw-frontend/components/ui/ToastProvider.tsx`
- Modify: `apps/tldw-frontend/components/AppProviders.tsx`
- Test: `apps/tldw-frontend/__tests__/pages/notifications.test.tsx`

**Step 1: Write the failing test**

```tsx
it('renders unread count and marks notification read', async () => {
  render(<NotificationsPage />)
  expect(await screen.findByText(/Unread/i)).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run: `cd apps/tldw-frontend && bunx vitest run __tests__/pages/notifications.test.tsx`
Expected: FAIL due to missing page/API wiring.

**Step 3: Write minimal implementation**

- Add notifications page with inbox list + mark read + dismiss.
- Add SSE/poll listener for realtime new-notification events.
- Show toast with Snooze button; on click call `/api/v1/tasks/{id}/snooze`.

**Step 4: Run test to verify it passes**

Run: same vitest command.
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/pages/notifications.tsx apps/tldw-frontend/lib/api/notifications.ts apps/tldw-frontend/components/ui/ToastProvider.tsx apps/tldw-frontend/components/AppProviders.tsx apps/tldw-frontend/__tests__/pages/notifications.test.tsx
git commit -m "feat(frontend): add notifications inbox, badge, and snooze toast"
```

### Task 11: Verify, Security Scan, and Documentation

**Files:**
- Modify: `Docs/API-related/` (add reminders/notifications API doc)
- Modify: `README.md` (brief feature mention)

**Step 1: Run backend tests for touched scope**

Run:
`source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Notifications tldw_Server_API/tests/Collections/test_reminders_notifications_db.py -v`
Expected: PASS.

**Step 2: Run frontend tests for touched scope**

Run:
`cd apps/tldw-frontend && bunx vitest run __tests__/pages/notifications.test.tsx`
Expected: PASS.

**Step 3: Run Bandit on touched backend paths**

Run:
`source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/reminders.py tldw_Server_API/app/api/v1/endpoints/notifications.py tldw_Server_API/app/core/Reminders tldw_Server_API/app/services/reminders_scheduler.py tldw_Server_API/app/services/reminder_jobs_worker.py tldw_Server_API/app/services/jobs_notifications_service.py -f json -o /tmp/bandit_reminders_notifications.json`
Expected: no new high-severity findings in changed code.

**Step 4: Update docs**

- Add endpoint and payload documentation with examples.
- Document env flags and defaults (`task cap`, scheduler toggles, polling intervals).

**Step 5: Commit**

```bash
git add Docs/API-related README.md
git commit -m "docs: add reminders and notifications API usage"
```

