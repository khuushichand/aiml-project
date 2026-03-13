# Admin UI Maintenance Rotation Authoritative Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the simulated maintenance key-rotation workflow with an authoritative, Jobs-backed admin run model that uses shared backend status/history and real scoped dry-run/execute requests.

**Architecture:** Add AuthNZ-backed `maintenance_rotation_runs` persistence and admin endpoints for create/list/detail, then enqueue a Jobs worker that performs the real `JobManager.rotate_encryption_keys(...)` call using server-side configured key sources. Update `MaintenanceSection.tsx` to submit real scoped requests, poll authoritative run state, and remove all `localStorage`/timer simulation logic.

**Tech Stack:** FastAPI, Pydantic, AuthNZ SQLite/Postgres repos, Jobs manager/worker SDK patterns, Next.js/React, Vitest, pytest, Bandit.

---

### Task 1: Add the rotation-run persistence model

**Status:** Complete

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/core/AuthNZ/repos/maintenance_rotation_runs_repo.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/tests/Admin/test_maintenance_rotation_runs_repo.py`

**Step 1: Write the failing repo tests**

Add tests for:
- create a run with mode/scope/confirmation metadata
- list recent runs newest-first
- update run status, job id, affected count, and error message
- enforce one active execute run at a time

**Step 2: Run repo tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_maintenance_rotation_runs_repo.py -q
```

Expected: FAIL because the repo/table do not exist yet.

**Step 3: Add minimal migration and repo implementation**

Implement:
- additive SQLite migration for `maintenance_rotation_runs`
- matching Postgres ensure helper
- repo methods:
  - `create_run(...)`
  - `list_runs(...)`
  - `get_run(...)`
  - `mark_running(...)`
  - `mark_complete(...)`
  - `mark_failed(...)`
  - `has_active_execute_run(...)`

Do not store raw key material.

**Step 4: Run repo tests to verify they pass**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/maintenance_rotation_runs_repo.py \
  tldw_Server_API/tests/Admin/test_maintenance_rotation_runs_repo.py
git commit -m "feat(maintenance): add rotation run persistence"
```

### Task 2: Add service-layer validation and run creation

**Status:** Complete

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/services/admin_maintenance_rotation_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_service.py`

**Step 1: Write the failing service tests**

Cover:
- create dry-run run with validated scope
- reject execute without `confirmed=True`
- reject when server-side key source is unavailable
- reject when another execute run is active
- compute and persist `scope_summary` and `key_source`

**Step 2: Run tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_service.py -q
```

Expected: FAIL because service and schemas do not exist yet.

**Step 3: Implement the minimal service**

Add:
- Pydantic request/response models for create/list/detail
- service helpers for:
  - key-source availability validation
  - scope-summary construction
  - active execute exclusion
  - create/list/detail orchestration

Use server-side key-source selection only.

**Step 4: Run tests to verify they pass**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_maintenance_rotation_service.py \
  tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_service.py
git commit -m "feat(maintenance): add rotation service validation"
```

### Task 3: Add admin endpoints for create/list/detail

**Status:** Complete

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/tests/Admin/test_maintenance_rotation_api.py`

**Step 1: Write the failing API tests**

Cover:
- `POST /api/v1/admin/maintenance/rotation-runs` dry-run create
- execute create requires confirmation
- list/detail endpoints return authoritative run rows
- domain scope enforcement is preserved

**Step 2: Run tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_maintenance_rotation_api.py -q
```

Expected: FAIL because the endpoints are missing.

**Step 3: Implement the endpoints**

Wire:
- create/list/detail routes under the admin maintenance surface
- service calls
- admin audit emission on create
- clear HTTP error mapping for:
  - missing confirmation
  - missing key source
  - active execute conflict
  - invalid scope

**Step 4: Run tests to verify they pass**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py \
  tldw_Server_API/tests/Admin/test_maintenance_rotation_api.py
git commit -m "feat(maintenance): add rotation run admin endpoints"
```

### Task 4: Add Jobs-backed execution worker

**Status:** Complete

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/services/admin_maintenance_rotation_jobs_worker.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/app/main.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_jobs.py`

**Step 1: Write the failing worker tests**

Cover:
- dry-run run transitions `queued -> running -> complete`
- execute run transitions `queued -> running -> complete`
- failed rotation records `status=failed` and `error_message`
- worker calls `JobManager.rotate_encryption_keys(...)` with the persisted scope and resolved server-side key source

**Step 2: Run tests to verify they fail**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_jobs.py -q
```

Expected: FAIL because the worker and enqueue path do not exist yet.

**Step 3: Implement minimal worker + enqueue flow**

Use the admin backup jobs worker pattern as the reference.

Add:
- worker handler that loads a run by id
- server-side key-source resolution
- status updates before/after execution
- startup wiring in `main.py`

**Step 4: Run tests to verify they pass**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_maintenance_rotation_jobs_worker.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_jobs.py
git commit -m "feat(maintenance): add jobs-backed rotation worker"
```

### Task 5: Replace the admin-ui simulated workflow

**Status:** Complete

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/admin-ui/components/data-ops/MaintenanceSection.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/admin-ui/lib/api-client.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/admin-ui/types/index.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/admin-ui/components/data-ops/MaintenanceSection.test.tsx`

**Step 1: Write the failing frontend tests**

Cover:
- submits real scoped dry-run/execute request body
- no `localStorage` load/save for rotation state/history
- no fake fallback run when backend create fails
- renders backend run history/detail
- polls while status is `queued` or `running`

**Step 2: Run tests to verify they fail**

Run:
```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/admin-ui
bunx vitest run components/data-ops/MaintenanceSection.test.tsx
```

Expected: FAIL because the component still uses local state/timers.

**Step 3: Implement the minimal UI replacement**

Remove:
- `localStorage` state/history
- progress timer simulation
- fabricated fallback run behavior

Add:
- form fields for mode/domain/queue/job type/fields/limit
- confirmation step
- create/list/detail API calls
- polling tied to backend status

**Step 4: Run tests to verify they pass**

Run the same vitest command.

**Step 5: Commit**

```bash
git add admin-ui/components/data-ops/MaintenanceSection.tsx \
  admin-ui/lib/api-client.ts \
  admin-ui/types/index.ts \
  admin-ui/components/data-ops/MaintenanceSection.test.tsx
git commit -m "feat(admin-ui): use authoritative maintenance rotation runs"
```

### Task 6: Add verification and cleanup coverage

**Status:** Complete

**Files:**
- Modify as needed based on verification
- Test: existing touched tests

**Step 1: Run the backend slice**

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Admin/test_maintenance_rotation_runs_repo.py \
  tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_service.py \
  tldw_Server_API/tests/Admin/test_maintenance_rotation_api.py \
  tldw_Server_API/tests/Admin/test_admin_maintenance_rotation_jobs.py -q
```

Expected: PASS

**Step 2: Run the frontend slice**

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-maintenance-rotation-authoritative/admin-ui
bunx vitest run components/data-ops/MaintenanceSection.test.tsx
bun run typecheck
bunx eslint components/data-ops/MaintenanceSection.tsx components/data-ops/MaintenanceSection.test.tsx lib/api-client.ts types/index.ts
```

Expected: PASS

**Step 3: Run Bandit on touched backend files**

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/AuthNZ/repos/maintenance_rotation_runs_repo.py \
  tldw_Server_API/app/services/admin_maintenance_rotation_service.py \
  tldw_Server_API/app/services/admin_maintenance_rotation_jobs_worker.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py \
  -f json -o /tmp/bandit_maintenance_rotation_authoritative.json
```

Expected: no new findings

**Step 4: Commit any final verification fixes**

```bash
git add <touched files>
git commit -m "test(maintenance): finalize authoritative rotation verification"
```
