# Admin UI DSR Authoritative Intake Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace the admin UI's disabled local-only data subject request flow with an authoritative backend-backed preview, intake, and audit workflow that records requests truthfully without claiming export or erasure execution.

**Architecture:** Add a small dedicated DSR persistence layer in AuthNZ, expose preview/create/list endpoints from the existing admin data-ops router, and then rewire the admin UI component to consume only server-backed preview and history data. Keep milestone 1 narrow: record requests with idempotency and audit events, but do not execute export or deletion.

**Tech Stack:** FastAPI, AuthNZ SQLite/PostgreSQL migrations, repository/service pattern under `tldw_Server_API`, Next.js 15, React 19, TypeScript 5, Vitest, Pytest, Bun.

---

## Stage 1: Add Durable DSR Persistence
**Goal:** Create a shared control-plane store for recorded data subject requests that works across AuthNZ backends.
**Success Criteria:** The AuthNZ layer can persist and list DSR records by `client_request_id`, and duplicate create attempts do not create duplicate rows.
**Tests:** `python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py -q`
**Status:** Not Started

### Task 1: Add the DSR table and repository

**Files:**
- Modify: `tldw_Server_API/app/core/AuthNZ/migrations.py`
- Modify: `tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py`
- Create: `tldw_Server_API/app/core/AuthNZ/repos/data_subject_requests_repo.py`
- Test: `tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py`

**Step 1: Write the failing repository test**

Create `tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py` with a case that inserts one request and then replays the same `client_request_id`.

```python
async def test_repo_create_request_is_idempotent(tmp_path):
    repo = DataSubjectRequestsRepo()

    first = await repo.create_or_get_request(
        client_request_id="dsr-1",
        requester_identifier="user@example.com",
        resolved_user_id=7,
        request_type="export",
        status="recorded",
        selected_categories=["media_records"],
        preview_summary=[{"key": "media_records", "count": 3}],
        coverage_metadata={"supported": ["media_records"]},
        requested_by_user_id=1,
    )
    second = await repo.create_or_get_request(
        client_request_id="dsr-1",
        requester_identifier="user@example.com",
        resolved_user_id=7,
        request_type="export",
        status="recorded",
        selected_categories=["media_records"],
        preview_summary=[{"key": "media_records", "count": 3}],
        coverage_metadata={"supported": ["media_records"]},
        requested_by_user_id=1,
    )

    assert first["id"] == second["id"]
```

**Step 2: Run the test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py -q`

Expected: FAIL because the repo and/or table do not exist yet.

**Step 3: Write the minimal persistence layer**

Add an additive AuthNZ migration for `data_subject_requests`, add the matching PostgreSQL ensure statements, and implement a small repo with:

```python
class DataSubjectRequestsRepo:
    async def create_or_get_request(...): ...
    async def list_requests(...): ...
```

Store `selected_categories`, `preview_summary`, and `coverage_metadata` as JSON text.

**Step 4: Run the repo test to verify it passes**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/AuthNZ/migrations.py tldw_Server_API/app/core/AuthNZ/pg_migrations_extra.py tldw_Server_API/app/core/AuthNZ/repos/data_subject_requests_repo.py tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py
git commit -m "feat(admin-dsr): add durable request persistence"
```

## Stage 2: Expose Authoritative Preview, Create, And List APIs
**Goal:** Add admin-scoped DSR preview and intake endpoints that recompute preview server-side, enforce user scope, and emit audit events.
**Success Criteria:** Preview fails closed, create persists only authoritative snapshots, duplicate `client_request_id` calls are idempotent, and list returns paged results filtered by admin scope.
**Tests:** `python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_api.py -q`
**Status:** Not Started

### Task 2: Add the backend API contract and service layer

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/admin_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py`
- Create: `tldw_Server_API/app/services/admin_data_subject_requests_service.py`
- Test: `tldw_Server_API/tests/Admin/test_data_subject_requests_api.py`

**Step 1: Write the failing API tests**

Create `tldw_Server_API/tests/Admin/test_data_subject_requests_api.py` with these cases:

```python
def test_preview_returns_404_for_unknown_requester(...): ...
def test_create_records_request_and_reuses_client_request_id(...): ...
def test_list_returns_newest_first_with_limit_offset(...): ...
def test_preview_enforces_admin_scope(...): ...
```

For the create test, assert that the stored row contains the server-computed preview summary, not client-supplied preview data.

**Step 2: Run the test to verify it fails**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_api.py -q`

Expected: FAIL because the schemas, service, and endpoints do not exist.

**Step 3: Write the minimal backend implementation**

Add schema models for preview/create/list and implement a service with functions similar to:

```python
async def preview_data_subject_request(principal, requester_identifier: str) -> dict[str, Any]: ...
async def create_data_subject_request(principal, payload, request: Request) -> dict[str, Any]: ...
async def list_data_subject_requests(principal, *, limit: int, offset: int, ...) -> dict[str, Any]: ...
```

Requirements:

- resolve requester to a known user
- call `_enforce_admin_user_scope(...)`
- count only authoritative categories supported in milestone 1
- recompute preview inside `create`
- emit admin audit events for preview and create

**Step 4: Run the API tests to verify behavior**

Run: `source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_api.py -q`

Expected: PASS

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/admin_schemas.py tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py tldw_Server_API/app/services/admin_data_subject_requests_service.py tldw_Server_API/tests/Admin/test_data_subject_requests_api.py
git commit -m "feat(admin-dsr): add preview and intake endpoints"
```

## Stage 3: Replace The Admin UI Local-Only DSR Flow
**Goal:** Re-enable the DSR screen using only authoritative backend preview and request-log data.
**Success Criteria:** The admin UI no longer reads or writes DSR history from `localStorage`, no longer fabricates preview data, and records requests with truthful milestone-1 copy.
**Tests:** `bunx vitest run components/data-ops/DataSubjectRequestsSection.test.tsx app/data-ops/__tests__/page.a11y.test.tsx`
**Status:** Not Started

### Task 3: Update the admin UI DSR component and tests

**Files:**
- Modify: `admin-ui/lib/api-client.ts`
- Modify: `admin-ui/components/data-ops/DataSubjectRequestsSection.tsx`
- Modify: `admin-ui/components/data-ops/DataSubjectRequestsSection.test.tsx`
- Test: `admin-ui/app/data-ops/__tests__/page.a11y.test.tsx`

**Step 1: Write the failing frontend tests**

Extend `admin-ui/components/data-ops/DataSubjectRequestsSection.test.tsx` with cases like:

```tsx
it('loads request history from the backend instead of localStorage', async () => {
  apiMock.listDataSubjectRequests.mockResolvedValue({ items: [{ id: 1, requester_identifier: 'user@example.com', request_type: 'export', status: 'recorded', requested_at: '2026-03-10T12:00:00Z' }], total: 1, limit: 50, offset: 0 });
  render(<DataSubjectRequestsSection refreshSignal={0} />);
  expect(await screen.findByText('user@example.com')).toBeInTheDocument();
});

it('does not show success when request creation fails', async () => {
  apiMock.previewDataSubjectRequest.mockResolvedValue(...);
  apiMock.createDataSubjectRequest.mockRejectedValue(new Error('boom'));
  render(<DataSubjectRequestsSection refreshSignal={0} />);
  // submit and assert no recorded row or success copy
});
```

**Step 2: Run the test to verify it fails**

Run: `cd admin-ui && bunx vitest run components/data-ops/DataSubjectRequestsSection.test.tsx`

Expected: FAIL because the component still depends on local storage and fake-success flows.

**Step 3: Write the minimal frontend implementation**

Update the API client with:

```ts
listDataSubjectRequests: (params?: Record<string, string>) =>
  requestJson('/admin/data-subject-requests?...'),
```

Then update `DataSubjectRequestsSection.tsx` to:

- load request history from the backend on mount and after submit
- remove `localStorage` helpers entirely
- remove `buildLocalCategorySummary`
- remove `downloadExportArchive`
- change success copy for `export` and `erasure` to `Request recorded for review`
- keep `access` summary rendering but also refresh the server-backed log

**Step 4: Run the frontend tests to verify behavior**

Run: `cd admin-ui && bunx vitest run components/data-ops/DataSubjectRequestsSection.test.tsx app/data-ops/__tests__/page.a11y.test.tsx`

Expected: PASS

**Step 5: Commit**

```bash
git add admin-ui/lib/api-client.ts admin-ui/components/data-ops/DataSubjectRequestsSection.tsx admin-ui/components/data-ops/DataSubjectRequestsSection.test.tsx admin-ui/app/data-ops/__tests__/page.a11y.test.tsx
git commit -m "feat(admin-ui): use authoritative DSR backend flow"
```

## Stage 4: Verify The End-To-End Milestone Contract
**Goal:** Prove the new backend-backed DSR intake flow works across the touched surfaces and does not introduce new security findings in changed code.
**Success Criteria:** Focused frontend and backend suites pass, the admin data-ops tests stay green, and Bandit is clean for the touched Python scope after filtering expected pytest `B101` assertions.
**Tests:** Focused Vitest and Pytest suites, Bandit, optional targeted build/typecheck if frontend contract changes require it.
**Status:** Not Started

### Task 4: Run the verification gate

**Files:**
- Verify only

**Step 1: Run the focused backend suites**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-dsr-authoritative-intake
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Admin/test_data_subject_requests_repo.py tldw_Server_API/tests/Admin/test_data_subject_requests_api.py tldw_Server_API/tests/Admin/test_data_ops.py -q
```

Expected: PASS

**Step 2: Run the focused frontend suites**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-dsr-authoritative-intake/admin-ui
bunx vitest run components/data-ops/DataSubjectRequestsSection.test.tsx app/data-ops/__tests__/page.a11y.test.tsx
```

Expected: PASS

**Step 3: Run type-aware frontend verification if API shapes changed**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-dsr-authoritative-intake/admin-ui
bun run typecheck
```

Expected: PASS

**Step 4: Run Bandit on touched backend paths**

Run:

```bash
cd /Users/macbook-dev/Documents/GitHub/tldw_server2/.worktrees/admin-ui-dsr-authoritative-intake
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r tldw_Server_API/app/api/v1/endpoints/admin/admin_data_ops.py tldw_Server_API/app/services/admin_data_subject_requests_service.py tldw_Server_API/app/core/AuthNZ/repos/data_subject_requests_repo.py -s B101 -f json -o /tmp/bandit_admin_dsr.json
```

Expected: exit code `0` with no actionable findings.

**Step 5: Commit**

```bash
git add -A
git commit -m "test(admin-dsr): verify authoritative intake milestone"
```
