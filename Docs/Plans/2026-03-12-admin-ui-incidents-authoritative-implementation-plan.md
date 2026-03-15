# Admin UI Incidents Authoritative Workflow Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace browser-local incident assignment and post-mortem state with authoritative backend-backed incident workflow fields.

**Architecture:** Extend the existing incident record in `system_ops.json`, update the current admin incident schemas and `PATCH` route to own workflow persistence plus timeline append atomically, then simplify the admin-ui incidents page to treat backend incident data as the only durable source of truth.

**Tech Stack:** FastAPI, Pydantic, JSON file-backed admin system ops service, Next.js, React, Vitest, pytest

---

### Task 1: Add backend incident workflow schema coverage

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/tests/Admin/test_incidents_service.py`

**Step 1: Write the failing backend schema/service tests**

Add tests that assert incident records expose:
- `assigned_to_user_id`
- `assigned_to_label`
- `root_cause`
- `impact`
- `action_items`

Also add tests for default values on pre-existing incidents with no workflow fields.

**Step 2: Run the focused pytest slice to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_service.py -q
```

Expected:
- FAIL because the incident payload does not yet include authoritative workflow fields

**Step 3: Implement minimal schema changes**

Extend the relevant Pydantic models in `admin_schemas.py`:
- add a structured incident action-item model
- add workflow fields to `IncidentItem`
- add nullable/optional workflow fields to `IncidentUpdateRequest`

Define explicit partial-update semantics in comments/docstrings:
- omitted means unchanged
- `null` means clear

Add schema-level notes that implementation must preserve omitted-vs-null distinction using `model_fields_set` or `model_dump(exclude_unset=True)` in the endpoint/service path.

**Step 4: Re-run the focused pytest slice**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_service.py -q
```

Expected:
- PASS for the new schema/default-field tests or fail only on the next unimplemented service behavior

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/admin_schemas.py tldw_Server_API/tests/Admin/test_incidents_service.py
git commit -m "test(admin-incidents): cover workflow schema fields"
```

### Task 2: Make backend incident persistence authoritative

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/app/services/admin_system_ops_service.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/tests/Admin/test_incidents_service.py`

**Step 1: Write the failing backend service tests**

Add tests covering:
- assignment persistence using `assigned_to_user_id`
- clearing assignment with `null`
- omitted workflow fields remain unchanged
- post-mortem persistence for `root_cause`, `impact`, and `action_items`
- blank action items normalized away
- timeline entry appended only when structured workflow update succeeds

**Step 2: Run the focused pytest slice to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_service.py -q
```

Expected:
- FAIL because the service still only handles title/status/severity/summary/tags/timeline

**Step 3: Implement minimal service changes**

In `admin_system_ops_service.py`:
- normalize legacy incident records with default workflow fields
- extend `create_incident(...)` defaults
- extend `update_incident(...)` to:
  - detect which request fields were actually supplied by the caller
  - support partial updates for workflow fields
  - clear fields when explicit `None` is provided
  - validate/cap action items
  - append `update_message` under the same store lock after state mutation

Keep the store update atomic inside the existing locked store context.

**Step 4: Re-run the focused pytest slice**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_service.py -q
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/services/admin_system_ops_service.py tldw_Server_API/tests/Admin/test_incidents_service.py
git commit -m "feat(admin-incidents): persist authoritative workflow state"
```

### Task 3: Resolve assignee labels on the backend route

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Create: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/tldw_Server_API/tests/Admin/test_incidents_api.py`

**Step 1: Write the failing endpoint tests**

Add API tests that assert:
- `PATCH /admin/incidents/{id}` with `assigned_to_user_id` persists the user id and backend-resolved label
- assignee must resolve to an admin-capable user
- invalid assignee ids fail closed
- `null` clears assignment
- omitted workflow fields remain unchanged through the API layer

**Step 2: Run the focused pytest slice to verify failure**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_api.py -q
```

Expected:
- FAIL because the route does not yet resolve or persist authoritative assignee metadata

**Step 3: Implement minimal endpoint logic**

In `admin_ops.py`:
- load/resolve the requested user when `assigned_to_user_id` is present
- enforce the v1 assignable-user rule for admin-capable users only
- pass backend-resolved assignee metadata into `svc_update_incident(...)`
- reject invalid assignee ids with a stable 400/404-style API error

Do not trust a client-provided label.

**Step 4: Re-run the focused pytest slice**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_api.py -q
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py tldw_Server_API/tests/Admin/test_incidents_api.py
git commit -m "feat(admin-incidents): resolve authoritative assignee labels"
```

### Task 4: Replace admin-ui local incident workflow persistence

**Files:**
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/admin-ui/app/incidents/page.tsx`
- Modify or delete: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/admin-ui/lib/incident-workflow.ts`
- Modify: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/admin-ui/types/incidents.ts`
- Test: `/Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-incidents-authoritative/admin-ui/app/incidents/__tests__/page.test.tsx`

**Step 1: Write the failing frontend tests**

Add/update tests to assert:
- assignment updates call `api.updateIncident(...)`, not `addIncidentEvent(...)` alone
- page reads assignee/root-cause/impact/action-items from `IncidentItem`
- workflow fields survive reload from backend incident payload
- no `localStorage` incident workflow persistence remains
- current assignee rendering prefers `assigned_to_label` from the incident payload even when the assignee is not present in the currently loaded dropdown options

**Step 2: Run the focused vitest slice to verify failure**

Run:

```bash
bunx vitest run admin-ui/app/incidents/__tests__/page.test.tsx
```

Expected:
- FAIL because the page still reads/writes workflow data via `localStorage`

**Step 3: Implement minimal frontend changes**

In `page.tsx`:
- remove `readIncidentWorkflowMap()` / `writeIncidentWorkflowMap()` durable usage
- initialize form state from incident payloads
- use `api.updateIncident(...)` for assignment and post-mortem saves
- keep unsaved edits only in memory
- render the current assignee from backend incident fields, not only from the loaded dropdown option list

In `types/incidents.ts`:
- extend `IncidentItem` with authoritative workflow fields

Delete or simplify `incident-workflow.ts` so it no longer persists browser storage.

**Step 4: Re-run the focused vitest slice**

Run:

```bash
bunx vitest run admin-ui/app/incidents/__tests__/page.test.tsx
```

Expected:
- PASS

**Step 5: Commit**

```bash
git add admin-ui/app/incidents/page.tsx admin-ui/lib/incident-workflow.ts admin-ui/types/incidents.ts admin-ui/app/incidents/__tests__/page.test.tsx
git commit -m "feat(admin-ui): use authoritative incident workflow state"
```

### Task 5: Verify end-to-end targeted coverage

**Files:**
- Modify only if verification exposes a defect

**Step 1: Run backend incident verification**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_incidents_service.py tldw_Server_API/tests/Admin/test_incidents_api.py -q
```

Expected:
- PASS

**Step 2: Run frontend incident verification**

Run:

```bash
bunx vitest run admin-ui/app/incidents/__tests__/page.test.tsx
```

Expected:
- PASS

**Step 3: Run targeted lint/type checking**

Run:

```bash
cd admin-ui && bunx eslint app/incidents/page.tsx lib/incident-workflow.ts types/incidents.ts app/incidents/__tests__/page.test.tsx
cd admin-ui && bun run typecheck
```

Expected:
- PASS

**Step 4: Run Bandit on touched backend files**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/services/admin_system_ops_service.py tldw_Server_API/app/api/v1/endpoints/admin/admin_ops.py tldw_Server_API/app/api/v1/schemas/admin_schemas.py -f json -o /tmp/bandit_admin_incidents_authoritative.json
```

Expected:
- no new findings

**Step 5: Commit any final verification-driven fixes**

```bash
git add <touched files>
git commit -m "test(admin-incidents): verify authoritative workflow integration"
```

### Task 6: Request code review and prepare branch handoff

**Files:**
- No code changes unless review finds defects

**Step 1: Summarize the change set**

Prepare a concise summary of:
- backend incident schema/store changes
- frontend incidents workflow changes
- verification commands and results

**Step 2: Request review**

Use the local review workflow on the completed branch before proposing merge.

**Step 3: Keep worktree clean**

Run:

```bash
git status --short
```

Expected:
- clean worktree, or only clearly intentional untracked artifacts

**Step 4: Commit review-driven fixes if needed**

```bash
git add <touched files>
git commit -m "fix(admin-incidents): address review feedback"
```
