# Admin UI BYOK Validation And Retention Preview Authoritative Hardening Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the BYOK dashboard's placeholder validation flow with authoritative Jobs-backed validation runs, and replace retention-policy local impact estimates with a backend dry-run preview bound to destructive saves.

**Architecture:** Add AuthNZ-backed BYOK validation-run persistence, admin endpoints, and a Jobs worker for shared validation status/history. Add a backend retention preview endpoint that returns authoritative counts plus a signed preview token, then require that token on the existing retention update path. Update the admin UI to use those real backend flows and remove placeholder/estimated fallbacks.

**Tech Stack:** FastAPI, Pydantic, AuthNZ SQLite/Postgres repos, Jobs manager/worker patterns, Next.js/React, Vitest, pytest, Bandit.

---

### Task 1: Add BYOK validation-run persistence

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/core/AuthNZ/repos/byok_validation_runs_repo.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/tests/Admin/test_byok_validation_runs_repo.py`

**Step 1: Write the failing repo tests**

Add tests for:
- creating a validation run with scope, requester, and status metadata
- listing runs newest-first
- updating a run to `running`, `complete`, and `failed`
- enforcing one active run at a time

**Step 2: Run test to verify it fails**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_byok_validation_runs_repo.py -q
```

Expected: FAIL because the repo/table do not exist yet.

**Step 3: Write minimal implementation**

Implement:
- additive SQLite migration for `byok_validation_runs`
- matching Postgres ensure helper
- repo methods:
  - `create_run(...)`
  - `list_runs(...)`
  - `get_run(...)`
  - `mark_running(...)`
  - `mark_complete(...)`
  - `mark_failed(...)`
  - `has_active_run(...)`

Persist aggregate counts only. Do not persist secrets or detailed provider error payloads.

**Step 4: Run test to verify it passes**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py \
  tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py \
  tldw_Server_API/app/core/AuthNZ/repos/byok_validation_runs_repo.py \
  tldw_Server_API/tests/Admin/test_byok_validation_runs_repo.py
git commit -m "feat(byok): add validation run persistence"
```

### Task 2: Add BYOK validation service and schemas

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/services/admin_byok_validation_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/api/v1/schemas/user_keys.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/tests/Admin/test_admin_byok_validation_service.py`

**Step 1: Write the failing service tests**

Cover:
- create validation run with org/provider filters
- reject create when BYOK is disabled
- reject create when another validation run is active
- compute and persist a `scope_summary`
- redact persisted error summaries

**Step 2: Run test to verify it fails**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_byok_validation_service.py -q
```

Expected: FAIL because service and schemas do not exist yet.

**Step 3: Write minimal implementation**

Add:
- request/response models for BYOK validation-run create/list/detail
- service helpers for:
  - scope validation
  - active-run exclusion
  - bounded provider-summary error formatting
  - list/detail orchestration

Use existing BYOK repos and scope-enforcement patterns already used by `admin_byok_service.py`.

**Step 4: Run test to verify it passes**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_byok_validation_service.py \
  tldw_Server_API/app/api/v1/schemas/user_keys.py \
  tldw_Server_API/tests/Admin/test_admin_byok_validation_service.py
git commit -m "feat(byok): add validation service"
```

### Task 3: Add BYOK validation admin endpoints

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/api/v1/endpoints/admin/admin_byok.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/tests/Admin/test_admin_byok_validation_api.py`

**Step 1: Write the failing API tests**

Cover:
- `POST /api/v1/admin/byok/validation-runs`
- `GET /api/v1/admin/byok/validation-runs`
- `GET /api/v1/admin/byok/validation-runs/{id}`
- active-run conflict returns `409`
- org scope enforcement is preserved

**Step 2: Run test to verify it fails**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_byok_validation_api.py -q
```

Expected: FAIL because the routes are missing.

**Step 3: Write minimal implementation**

Wire:
- create/list/detail endpoints into `admin_byok.py`
- service calls
- clear error mapping for disabled BYOK, conflict, and invalid scope

**Step 4: Run test to verify it passes**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_byok.py \
  tldw_Server_API/tests/Admin/test_admin_byok_validation_api.py
git commit -m "feat(byok): add validation admin endpoints"
```

### Task 4: Add Jobs-backed BYOK validation worker

**Files:**
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/services/admin_byok_validation_jobs_worker.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/main.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/tests/Admin/test_admin_byok_validation_jobs.py`

**Step 1: Write the failing worker tests**

Cover:
- queued run becomes running then complete
- failed provider validation marks run failed with redacted summary
- worker records aggregate counts only
- provider validation uses bounded concurrency

**Step 2: Run test to verify it fails**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_byok_validation_jobs.py -q
```

Expected: FAIL because the worker and enqueue path do not exist yet.

**Step 3: Write minimal implementation**

Use the admin maintenance-rotation and backup worker patterns as references.

Add:
- worker handler that loads a run by id
- validation scan over the targeted keys
- bounded per-provider concurrency
- status transitions and aggregate summary recording

**Step 4: Run test to verify it passes**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_byok_validation_jobs_worker.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Admin/test_admin_byok_validation_jobs.py
git commit -m "feat(byok): add jobs-backed validation worker"
```

### Task 5: Add authoritative retention preview backend contract

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/services/admin_data_ops_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/tldw_Server_API/tests/Admin/test_retention_policy_preview_api.py`

**Step 1: Write the failing backend tests**

Cover:
- preview returns authoritative counts and a `preview_signature`
- unknown policy returns `404`
- invalid range returns `400`
- update rejects missing or invalid preview signature
- update accepts a valid signature for the exact previewed values

**Step 2: Run test to verify it fails**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_retention_policy_preview_api.py -q
```

Expected: FAIL because preview endpoint/signature handling do not exist yet.

**Step 3: Write minimal implementation**

Add:
- preview response schema
- `POST /admin/retention-policies/{policy_key}/preview`
- backend count calculation for audit logs, job records, and backup files
- signed `preview_signature` generation and verification
- update endpoint requirement for a valid signature

Use the existing retention validation path so preview and update share the same range and policy rules.

**Step 4: Run test to verify it passes**

Run the same pytest command.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_data_ops_service.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py \
  tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  tldw_Server_API/tests/Admin/test_retention_policy_preview_api.py
git commit -m "feat(retention): add authoritative preview contract"
```

### Task 6: Replace the BYOK page placeholder validation flow

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/app/byok/page.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/lib/api-client.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/types/index.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/app/byok/__tests__/page.test.tsx`

**Step 1: Write the failing frontend tests**

Cover:
- `Run validation sweep` creates a backend run and polls until terminal
- validation history renders from backend data
- placeholder validation copy is removed
- no fake success state appears when create fails

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui
bunx vitest run app/byok/__tests__/page.test.tsx
```

Expected: FAIL because the page still hides validation sweep and renders placeholder-only copy.

**Step 3: Write minimal implementation**

Add:
- create/list/detail client methods for BYOK validation runs
- page state for active run polling and recent run history
- truthful telemetry/history labels based on backend data

Do not add client-side synthetic histories.

**Step 4: Run test to verify it passes**

Run the same vitest command.

**Step 5: Commit**

```bash
git add admin-ui/app/byok/page.tsx \
  admin-ui/lib/api-client.ts \
  admin-ui/types/index.ts \
  admin-ui/app/byok/__tests__/page.test.tsx
git commit -m "feat(admin-ui): add authoritative byok validation flow"
```

### Task 7: Replace retention local-estimate fallback

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/components/data-ops/RetentionPoliciesSection.tsx`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/lib/api-client.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui/components/data-ops/RetentionPoliciesSection.test.tsx`

**Step 1: Write the failing frontend tests**

Cover:
- preview success requires backend response and stores the returned signature
- preview failure shows error and does not render an estimated preview row
- save request includes the returned `preview_signature`
- changing the days input invalidates the existing preview/signature

**Step 2: Run test to verify it fails**

Run:
```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui
bunx vitest run components/data-ops/RetentionPoliciesSection.test.tsx
```

Expected: FAIL because the component still falls back to a local estimate and the update call does not send a signature.

**Step 3: Write minimal implementation**

Remove:
- local estimate fallback
- “estimated locally” messaging

Add:
- preview-signature handling
- save request payload with `preview_signature`
- strict preview-required gating tied to the current input value

**Step 4: Run test to verify it passes**

Run the same vitest command.

**Step 5: Commit**

```bash
git add admin-ui/components/data-ops/RetentionPoliciesSection.tsx \
  admin-ui/lib/api-client.ts \
  admin-ui/components/data-ops/RetentionPoliciesSection.test.tsx
git commit -m "feat(admin-ui): require authoritative retention preview"
```

### Task 8: Run verification and request review

**Files:**
- Modify if needed: touched files only

**Step 1: Run backend verification**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest \
  tldw_Server_API/tests/Admin/test_byok_validation_runs_repo.py \
  tldw_Server_API/tests/Admin/test_admin_byok_validation_service.py \
  tldw_Server_API/tests/Admin/test_admin_byok_validation_api.py \
  tldw_Server_API/tests/Admin/test_admin_byok_validation_jobs.py \
  tldw_Server_API/tests/Admin/test_retention_policy_preview_api.py -q
```

Expected: all pass.

**Step 2: Run frontend verification**

Run:
```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-byok-retention-authoritative/admin-ui
bunx vitest run app/byok/__tests__/page.test.tsx components/data-ops/RetentionPoliciesSection.test.tsx
bun run typecheck
bunx eslint app/byok/page.tsx components/data-ops/RetentionPoliciesSection.tsx lib/api-client.ts
```

Expected: all pass.

**Step 3: Run security verification**

Run:
```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/core/AuthNZ/repos/byok_validation_runs_repo.py \
  tldw_Server_API/app/services/admin_byok_validation_service.py \
  tldw_Server_API/app/services/admin_byok_validation_jobs_worker.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_byok.py \
  tldw_Server_API/app/services/admin_data_ops_service.py \
  tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py \
  tldw_Server_API/app/api/v1/schemas/admin_schemas.py \
  -f json -o /tmp/bandit_admin_ui_byok_retention_authoritative.json
```

Expected: no new findings in touched code.

**Step 4: Request code review**

Use the `requesting-code-review` skill against the completed branch before opening or merging a PR.

**Step 5: Commit any final review-driven fixes**

```bash
git add <touched files>
git commit -m "fix(admin-ui): address byok and retention review feedback"
```
