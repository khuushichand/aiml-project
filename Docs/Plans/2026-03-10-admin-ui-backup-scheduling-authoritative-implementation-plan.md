# Authoritative Backup Scheduling Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the admin UI's browser-local backup scheduling with platform-owned, AuthNZ-backed schedules that enqueue Jobs for real backup execution.

**Architecture:** Persist shared backup schedules and per-slot run claims in the AuthNZ control-plane DB, use APScheduler only to detect due runs and enqueue Jobs, and execute scheduled backups through the existing `create_backup_snapshot(...)` service in a dedicated Jobs worker. Keep the admin UI schedule form simple, but make all schedule state and run metadata authoritative from backend APIs.

**Tech Stack:** FastAPI, Pydantic v2, AuthNZ SQLite/PostgreSQL migrations, APScheduler, core Jobs `JobManager`, Loguru, Next.js/React, Vitest, pytest, Bandit.

## Progress

- Task 1: Complete
- Task 2: Complete
- Task 3: Complete
- Task 4: Complete
- Task 5: Complete
- Task 6: Complete
- Task 7: Complete

---

### Task 1: Add AuthNZ schedule persistence and failing repository tests

**Files:**
- Create: `tldw_Server_API/app/core/AuthNZ/repos/backup_schedules_repo.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Test: `tldw_Server_API/tests/Admin/test_backup_schedules_repo.py`
- Test: `tldw_Server_API/tests/AuthNZ/integration/test_authnz_backup_schedules_repo_postgres.py`

**Step 1: Write the failing repository tests**

Cover:
- create schedule row
- enforce one active schedule per `(dataset, target_user_id)`
- allow `authnz` with `target_user_id=None`
- create run claim row with unique `run_slot_key`
- list schedules newest-updated-first

```python
def test_create_schedule_rejects_duplicate_active_target(repo):
    repo.create_schedule(dataset="media", target_user_id=7, ...)
    with pytest.raises(Exception):
        repo.create_schedule(dataset="media", target_user_id=7, ...)
```

**Step 2: Run repository test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_backup_schedules_repo.py -q`

Expected: FAIL because the repo and schema do not exist yet.

**Step 3: Add migrations**

Add `backup_schedules` and `backup_schedule_runs` tables for both SQLite and PostgreSQL.

Schema requirements:
- schedule row stores dataset, target user, frequency, timezone, anchors, retention, pause flag, run summary
- run row stores schedule id, scheduled fire time, run slot key, job id, status, timestamps, error
- unique active schedule per `(dataset, target_user_id)` in the chosen backend-safe form
- unique `run_slot_key`

**Step 4: Add the minimal repository**

Implement methods such as:
- `ensure_schema()`
- `create_schedule(...)`
- `update_schedule(...)`
- `pause_schedule(...)`
- `resume_schedule(...)`
- `delete_schedule(...)`
- `get_schedule(...)`
- `list_schedules(...)`
- `claim_run_slot(...)`
- `mark_run_queued(...)`
- `mark_run_running(...)`
- `mark_run_succeeded(...)`
- `mark_run_failed(...)`

**Step 5: Re-run repository tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_backup_schedules_repo.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ/integration/test_authnz_backup_schedules_repo_postgres.py -q`

Expected: PASS

**Step 6: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/repos/backup_schedules_repo.py \
  tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/tests/Admin/test_backup_schedules_repo.py \
  tldw_Server_API/tests/AuthNZ/integration/test_authnz_backup_schedules_repo_postgres.py
git commit -m "feat(admin-backups): add authoritative schedule persistence"
```

### Task 2: Add schedule schemas, API contract, and failing API tests

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py`
- Test: `tldw_Server_API/tests/Admin/test_backup_schedules_api.py`
- Modify: `tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py`

**Step 1: Write the failing API tests**

Cover:
- create/list/update schedule
- pause/resume/delete
- target user required for per-user datasets
- target user forbidden for `authnz`
- org-scoped admin cannot schedule out-of-scope user
- only platform admins can schedule `authnz`

```python
async def test_create_backup_schedule_requires_target_user_for_media(client):
    response = client.post("/api/v1/admin/backup-schedules", json={
        "dataset": "media",
        "frequency": "daily",
        "time_of_day": "02:00",
        "retention_count": 7,
    })
    assert response.status_code == 400
    assert response.json()["detail"] == "target_user_required"
```

**Step 2: Run the API test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_backup_schedules_api.py -q`

Expected: FAIL because the schemas and routes do not exist yet.

**Step 3: Add schemas**

Add:
- `BackupScheduleItem`
- `BackupScheduleListResponse`
- `BackupScheduleCreateRequest`
- `BackupScheduleUpdateRequest`
- `BackupScheduleMutationResponse`

Include backend-returned display fields:
- `schedule_description`
- `next_run_at`
- `last_run_at`
- `last_status`
- `last_job_id`
- `last_error`

**Step 4: Add admin routes**

Add:
- `GET /admin/backup-schedules`
- `POST /admin/backup-schedules`
- `PATCH /admin/backup-schedules/{schedule_id}`
- `POST /admin/backup-schedules/{schedule_id}/pause`
- `POST /admin/backup-schedules/{schedule_id}/resume`
- `DELETE /admin/backup-schedules/{schedule_id}`

Use the same admin scope enforcement helper already used by manual backup endpoints.

**Step 5: Update OpenAPI contract tests**

Assert the new admin routes exist and reference the new response schemas.

**Step 6: Re-run API tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_backup_schedules_api.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py -q`

Expected: PASS

**Step 7: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py \
  tldw_Server_API/tests/Admin/test_backup_schedules_api.py \
  tldw_Server_API/tests/Admin/test_admin_split_openapi_contract.py
git commit -m "feat(admin-backups): add schedule API contract"
```

### Task 3: Add schedule service logic and authoritative schedule semantics

**Files:**
- Create: `tldw_Server_API/app/services/admin_backup_schedules_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_backup_schedules_service.py`

**Step 1: Write the failing service tests**

Cover:
- derive weekly anchor from create/update date
- derive monthly anchor from create/update date
- monthly fallback uses last day of shorter months
- build schedule description text
- reject duplicate active target

```python
def test_monthly_schedule_falls_back_to_last_day(service, frozen_time):
    schedule = service.create_schedule(... frequency="monthly", created_at="2026-01-31T10:00:00Z")
    assert service.describe_schedule(schedule).startswith("Monthly on day 31")
```

**Step 2: Run the service tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_backup_schedules_service.py -q`

Expected: FAIL because the service does not exist yet.

**Step 3: Implement the service**

Include:
- validation helpers for dataset/target-user rules
- anchor derivation logic
- persisted timezone defaulting
- schedule description generation
- mutation helpers used by the API layer

Keep schedule execution separate; this task only owns schedule configuration and derived semantics.

**Step 4: Re-run service and API tests**

Run:
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_backup_schedules_service.py -q`
- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_backup_schedules_api.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_backup_schedules_service.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py \
  tldw_Server_API/tests/Admin/test_admin_backup_schedules_service.py
git commit -m "feat(admin-backups): add schedule service semantics"
```

### Task 4: Add Jobs domain helpers, scheduler, and slot-claim enqueue path

**Files:**
- Create: `tldw_Server_API/app/core/Storage/backup_schedule_jobs.py`
- Create: `tldw_Server_API/app/services/admin_backup_scheduler.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_backup_scheduler.py`

**Step 1: Write the failing scheduler tests**

Cover:
- due active schedule claims one run slot and enqueues one job
- duplicate scheduler scans do not enqueue twice for same fire slot
- paused schedule is skipped
- deleted schedule is removed from APScheduler registry on rescan

```python
async def test_due_schedule_enqueues_once(monkeypatch, scheduler_service):
    await scheduler_service.scan_once()
    await scheduler_service.scan_once()
    assert create_job_mock.call_count == 1
```

**Step 2: Run the scheduler tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_backup_scheduler.py -q`

Expected: FAIL because the scheduler service does not exist yet.

**Step 3: Add shared Jobs constants**

In `backup_schedule_jobs.py`, define:
- domain
- job type
- queue helper
- payload normalization helpers

**Step 4: Implement the scheduler**

Follow existing patterns from:
- `reading_digest_scheduler.py`
- `connectors_sync_scheduler.py`

Requirements:
- load schedules from the repo
- compute next fire time from stored frequency/timezone/anchor
- claim run slot in DB before enqueue
- enqueue a core Job using `get_job_manager()` or `JobManager`
- update schedule `next_run_at` and run row metadata

**Step 5: Wire startup**

Start the scheduler in `app/main.py` behind an env flag such as `ADMIN_BACKUP_SCHEDULER_ENABLED=true`.

**Step 6: Re-run scheduler tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_backup_scheduler.py -q`

Expected: PASS

**Step 7: Commit**

```bash
git add tldw_Server_API/app/core/Storage/backup_schedule_jobs.py \
  tldw_Server_API/app/services/admin_backup_scheduler.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Admin/test_admin_backup_scheduler.py
git commit -m "feat(admin-backups): enqueue scheduled backup jobs"
```

### Task 5: Add the scheduled backup Jobs handler and worker

**Files:**
- Create: `tldw_Server_API/app/services/admin_backup_jobs_worker.py`
- Modify: `tldw_Server_API/app/core/Storage/backup_schedule_jobs.py`
- Modify: `tldw_Server_API/app/services/admin_data_ops_service.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_backup_jobs.py`

**Step 1: Write the failing worker tests**

Cover:
- worker reloads the schedule row before execution
- paused schedule does not execute a backup artifact
- successful run calls `create_backup_snapshot(...)`
- failed backup updates run row and schedule `last_error`

```python
async def test_scheduled_backup_job_executes_existing_backup_service(job_handler, monkeypatch):
    result = await handle_backup_schedule_job(job_row)
    assert result["status"] == "succeeded"
    create_backup_snapshot_mock.assert_called_once()
```

**Step 2: Run the worker tests to verify they fail**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_backup_jobs.py -q`

Expected: FAIL because the worker handler does not exist yet.

**Step 3: Implement the handler and worker**

Use `WorkerSDK` plus `JobManager`, following existing worker patterns.

Behavior:
- normalize payload
- load schedule and run rows
- mark run `running`
- execute `create_backup_snapshot(...)`
- mark run `succeeded` or `failed`
- update schedule `last_*`

**Step 4: Re-run worker tests**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_backup_jobs.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_backup_jobs_worker.py \
  tldw_Server_API/app/core/Storage/backup_schedule_jobs.py \
  tldw_Server_API/app/services/admin_data_ops_service.py \
  tldw_Server_API/tests/Admin/test_admin_backup_jobs.py
git commit -m "feat(admin-backups): add scheduled backup worker"
```

### Task 6: Replace admin-ui local schedule storage with backend APIs

**Files:**
- Modify: `admin-ui/lib/api-client.ts`
- Modify: `admin-ui/components/data-ops/BackupsSection.tsx`
- Test: `admin-ui/components/data-ops/BackupsSection.test.tsx`

**Step 1: Write the failing frontend tests**

Cover:
- schedule tab loads backend schedules instead of `localStorage`
- target user required for per-user datasets
- target user hidden/disabled for `authnz`
- pause/resume/delete call the backend
- backend failure renders error and no local success banner

```tsx
it('requires a target user for media schedules', async () => {
  render(<BackupsSection refreshSignal={0} />);
  await user.selectOptions(screen.getByLabelText(/dataset/i), 'media');
  await user.click(screen.getByRole('button', { name: /create schedule/i }));
  expect(screen.getByText(/select a target user/i)).toBeInTheDocument();
});
```

**Step 2: Run the frontend test to verify it fails**

Run: `bunx vitest run admin-ui/components/data-ops/BackupsSection.test.tsx`

Expected: FAIL because the component still uses `localStorage`.

**Step 3: Add API client methods**

Add:
- `listBackupSchedules`
- `createBackupSchedule`
- `updateBackupSchedule`
- `pauseBackupSchedule`
- `resumeBackupSchedule`
- `deleteBackupSchedule`

**Step 4: Update the component**

Replace:
- `SCHEDULE_STORAGE_KEY`
- `parseScheduleStorage`
- local persist helpers

With:
- backend-backed fetch and mutation flows
- user picker backed by `api.getUsers(...)`
- schedule description and run metadata rendering from backend

**Step 5: Re-run frontend tests**

Run: `bunx vitest run admin-ui/components/data-ops/BackupsSection.test.tsx`

Expected: PASS

**Step 6: Commit**

```bash
git add admin-ui/lib/api-client.ts \
  admin-ui/components/data-ops/BackupsSection.tsx \
  admin-ui/components/data-ops/BackupsSection.test.tsx
git commit -m "feat(admin-ui): use authoritative backup schedules"
```

### Task 7: Add full verification, audit coverage, and cleanup

**Files:**
- Modify: `tldw_Server_API/tests/Admin/test_data_ops.py`
- Modify: `admin-ui/Release_Checklist.md`
- Test: touched backend/frontend test files from prior tasks

**Step 1: Add one end-to-end-ish backend test**

Extend `test_data_ops.py` or a dedicated integration test to prove:
- schedule persisted
- scheduler claims due slot
- job is queued
- worker creates a real backup artifact visible through `GET /admin/backups`

**Step 2: Run the targeted verification suite**

Run:

```bash
source .venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Admin/test_backup_schedules_repo.py \
  tldw_Server_API/tests/AuthNZ/integration/test_authnz_backup_schedules_repo_postgres.py \
  tldw_Server_API/tests/Admin/test_backup_schedules_api.py \
  tldw_Server_API/tests/Admin/test_admin_backup_schedules_service.py \
  tldw_Server_API/tests/Admin/test_admin_backup_scheduler.py \
  tldw_Server_API/tests/Admin/test_admin_backup_jobs.py \
  tldw_Server_API/tests/Admin/test_data_ops.py -q
```

Run:

```bash
bunx vitest run admin-ui/components/data-ops/BackupsSection.test.tsx
```

Run:

```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/AuthNZ/repos/backup_schedules_repo.py \
  tldw_Server_API/app/services/admin_backup_schedules_service.py \
  tldw_Server_API/app/services/admin_backup_scheduler.py \
  tldw_Server_API/app/services/admin_backup_jobs_worker.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py \
  tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  -f json -o /tmp/bandit_admin_backup_scheduling.json
```

Expected: PASS, with Bandit clean on the touched backend code.

**Step 3: Update release checklist**

Add authoritative backup schedule validation to the admin-ui release checklist.

**Step 4: Commit**

```bash
git add tldw_Server_API/tests/Admin/test_data_ops.py \
  admin-ui/Release_Checklist.md
git commit -m "test(admin-backups): verify authoritative schedule flow"
```
