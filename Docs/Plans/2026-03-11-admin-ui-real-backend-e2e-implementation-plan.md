# Admin UI Real-Backend E2E Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a real-backend Playwright lane for `admin-ui` that boots isolated FastAPI instances, seeds deterministic admin fixtures, and verifies DSR, backup scheduling, monitoring authority, and debug RBAC across both JWT and single-user auth modes.

**Architecture:** Extend the existing `admin-ui` Playwright harness with two new real-backend projects, add explicit test-support backend endpoints under `/api/v1/test-support/admin-e2e/*`, and keep the browser flows real while moving fixture creation/reset into env-gated backend helpers. Use one real JWT login smoke, one real single-user login smoke, and seeded session bootstrap for the rest of the JWT feature tests.

**Tech Stack:** Playwright, Next.js (`admin-ui`), FastAPI, AuthNZ SQLite/Postgres test paths, Bun, Pytest, Vitest, GitHub Actions.

## Progress

- [x] Task 1: Add Real-Backend Playwright Projects And Backend Lifecycle Helpers
- [x] Task 2: Add Env-Gated Backend Test-Support Router For Reset, Seed, And Session Bootstrap
- [x] Task 3: Make Login And Session Bootstrap Real In Both Auth Modes
- [x] Task 4: Add DSR Real-Backend E2E Coverage
- [ ] Task 5: Add Backup Scheduling Real-Backend E2E Coverage
- [ ] Task 6: Add Monitoring Authority And Debug RBAC Real-Backend E2E Coverage
- [ ] Task 7: Wire The Real-Backend Lane Into CI And Project Scripts

---

### Task 1: Add Real-Backend Playwright Projects And Backend Lifecycle Helpers

**Files:**
- Modify: `admin-ui/playwright.config.ts`
- Modify: `admin-ui/package.json`
- Create: `admin-ui/tests/e2e/real-backend/helpers/backend-lifecycle.ts`
- Create: `admin-ui/tests/e2e/real-backend/helpers/project-env.ts`
- Create: `admin-ui/tests/e2e/real-backend/helpers/fixtures.ts`
- Test: `admin-ui/tests/e2e/real-backend/login-multi-user.spec.ts` (new)
- Test: `admin-ui/tests/e2e/real-backend/login-single-user.spec.ts` (new)

**Step 1: Write the failing tests**

Create minimal real-backend login smoke specs:

```ts
import { test, expect } from "./helpers/fixtures"

test("multi-user admin login reaches dashboard", async ({ loginPage }) => {
  await loginPage.gotoJwtLogin()
  await loginPage.loginWithPassword("admin", "AdminPass123!")
  await expect(loginPage.page).toHaveURL(/\/(?:$|\?)/)
})
```

```ts
import { test, expect } from "./helpers/fixtures"

test("single-user API-key login reaches debug redirect target", async ({ loginPage }) => {
  await loginPage.gotoSingleUserLogin("/debug")
  await loginPage.loginWithApiKey("single-user-admin-key")
  await expect(loginPage.page).toHaveURL(/\/debug/)
})
```

**Step 2: Run tests to verify they fail**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/login-multi-user.spec.ts --project=chromium-real-jwt --reporter=line`
- `cd admin-ui && bunx playwright test tests/e2e/real-backend/login-single-user.spec.ts --project=chromium-real-single-user --reporter=line`

Expected:

- FAIL because the projects, helpers, and backend lifecycle wiring do not exist yet.

**Step 3: Implement the minimal harness**

Add to `admin-ui/playwright.config.ts`:

```ts
projects: [
  { name: "chromium", use: { ...devices["Desktop Chrome"] } },
  { name: "chromium-real-jwt", use: { ...devices["Desktop Chrome"] } },
  { name: "chromium-real-single-user", use: { ...devices["Desktop Chrome"] } },
]
```

Add `admin-ui` scripts:

```json
{
  "test:real-backend": "playwright test tests/e2e/real-backend"
}
```

Add lifecycle helpers that:

- start backend instances via `python tldw_Server_API/scripts/server_lifecycle.py start`
- use distinct labels/ports for JWT vs single-user
- stop both instances in teardown

**Step 4: Re-run the focused tests**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/login-multi-user.spec.ts --project=chromium-real-jwt --reporter=line`
- `cd admin-ui && bunx playwright test tests/e2e/real-backend/login-single-user.spec.ts --project=chromium-real-single-user --reporter=line`

Expected:

- Still FAIL, but now on missing backend test-support/session bootstrap behavior rather than missing Playwright project wiring.

**Step 5: Commit**

```bash
git add admin-ui/playwright.config.ts admin-ui/package.json \
  admin-ui/tests/e2e/real-backend/helpers/backend-lifecycle.ts \
  admin-ui/tests/e2e/real-backend/helpers/project-env.ts \
  admin-ui/tests/e2e/real-backend/helpers/fixtures.ts \
  admin-ui/tests/e2e/real-backend/login-multi-user.spec.ts \
  admin-ui/tests/e2e/real-backend/login-single-user.spec.ts
git commit -m "test(admin-ui): add real-backend playwright project scaffolding"
```

### Task 2: Add Env-Gated Backend Test-Support Router For Reset, Seed, And Session Bootstrap

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/test_support/admin_e2e.py`
- Create: `tldw_Server_API/app/api/v1/schemas/test_support_schemas.py`
- Create: `tldw_Server_API/app/services/admin_e2e_support_service.py`
- Modify: `tldw_Server_API/app/main.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py` (new)

**Step 1: Write the failing backend tests**

```python
def test_admin_e2e_routes_are_unavailable_without_flag(client):
    response = client.post("/api/v1/test-support/admin-e2e/reset")
    assert response.status_code == 404


def test_admin_e2e_seed_returns_stable_fixture_ids(e2e_client):
    response = e2e_client.post(
        "/api/v1/test-support/admin-e2e/seed",
        json={"scenario": "dsr_jwt_admin"}
    )
    payload = response.json()
    assert payload["users"]["admin"]["id"]
    assert payload["fixtures"]["alerts"][0]["alert_id"]


def test_admin_e2e_bootstrap_jwt_session_returns_cookie_payload(e2e_client):
    seed = e2e_client.post("/api/v1/test-support/admin-e2e/seed", json={"scenario": "jwt_admin"}).json()
    response = e2e_client.post(
        "/api/v1/test-support/admin-e2e/bootstrap-jwt-session",
        json={"principal_key": seed["users"]["admin"]["key"]}
    )
    assert response.status_code == 200
    assert response.json()["cookies"][0]["name"] == "access_token"
```

**Step 2: Run tests to verify failure**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py -q`

Expected:

- FAIL because the test-support router and schemas do not exist.

**Step 3: Implement the router and env gate**

Add an env-gated router under `/api/v1/test-support/admin-e2e` with endpoints:

- `POST /reset`
- `POST /seed`
- `POST /bootstrap-jwt-session`
- `POST /run-due-backup-schedules`

In `tldw_Server_API/app/main.py`, include it only when:

```python
if os.getenv("ENABLE_ADMIN_E2E_TEST_MODE", "").strip().lower() == "true":
    include_router_idempotent(
        app,
        admin_e2e_router,
        prefix=f"{API_V1_PREFIX}/test-support/admin-e2e",
        tags=["test-support"],
    )
```

**Step 4: Re-run the backend tests**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py -q`

Expected:

- PASS for route availability, seed stability, and JWT session bootstrap contract.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/test_support/admin_e2e.py \
  tldw_Server_API/app/api/v1/schemas/test_support_schemas.py \
  tldw_Server_API/app/services/admin_e2e_support_service.py \
  tldw_Server_API/app/main.py \
  tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py
git commit -m "test(api): add admin e2e test-support router"
```

### Task 3: Make Login And Session Bootstrap Real In Both Auth Modes

**Files:**
- Create: `admin-ui/tests/e2e/real-backend/helpers/login-page.ts`
- Create: `admin-ui/tests/e2e/real-backend/helpers/session.ts`
- Modify: `admin-ui/tests/e2e/real-backend/helpers/fixtures.ts`
- Test: `admin-ui/tests/e2e/real-backend/login-multi-user.spec.ts`
- Test: `admin-ui/tests/e2e/real-backend/login-single-user.spec.ts`

**Step 1: Strengthen the failing login specs**

Add exact browser assertions:

```ts
await expect(page.getByRole("heading", { name: /admin dashboard|dashboard/i })).toBeVisible()
```

```ts
await expect(page.getByRole("heading", { name: /debug/i })).toBeVisible()
```

Add one JWT denial smoke:

```ts
test("plain user cannot open admin routes", async ({ seededSession, page }) => {
  await seededSession.as("non_admin")
  await page.goto("/users")
  await expect(page).toHaveURL(/\/login|\/403|\/$/)
})
```

**Step 2: Run tests to verify failure**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/login-*.spec.ts --project=chromium-real-jwt --project=chromium-real-single-user --reporter=line`

Expected:

- FAIL because the session helper and real backend login flow are not fully wired yet.

**Step 3: Implement login/session helpers**

Add a `LoginPage` object with methods like:

```ts
await page.goto(`/login?redirectTo=${encodeURIComponent(target)}`)
await page.getByRole("textbox", { name: /username/i }).fill(username)
await page.getByRole("textbox", { name: /password/i }).fill(password)
await page.getByRole("button", { name: /sign in|log in/i }).click()
```

Add a seeded JWT session helper that:

- calls `/api/v1/test-support/admin-e2e/bootstrap-jwt-session`
- writes the returned cookies into the browser context

Keep single-user login as a real browser flow through `admin-ui/app/login/page.tsx`.

**Step 4: Re-run the login slice**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/login-*.spec.ts --project=chromium-real-jwt --project=chromium-real-single-user --reporter=line`

Expected:

- PASS for:
  - JWT real login smoke
  - JWT denial smoke
  - single-user real API-key login smoke

**Step 5: Commit**

```bash
git add admin-ui/tests/e2e/real-backend/helpers/login-page.ts \
  admin-ui/tests/e2e/real-backend/helpers/session.ts \
  admin-ui/tests/e2e/real-backend/helpers/fixtures.ts \
  admin-ui/tests/e2e/real-backend/login-multi-user.spec.ts \
  admin-ui/tests/e2e/real-backend/login-single-user.spec.ts
git commit -m "test(admin-ui): add real-backend login and session helpers"
```

### Task 4: Add DSR Real-Backend E2E Coverage

**Files:**
- Create: `admin-ui/tests/e2e/real-backend/helpers/page-objects/data-subject-requests-page.ts`
- Create: `admin-ui/tests/e2e/real-backend/data-subject-requests.spec.ts`
- Modify: `tldw_Server_API/app/services/admin_e2e_support_service.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py`

**Step 1: Write the failing DSR browser tests**

```ts
test("records a DSR request and survives reload", async ({ seededSession, dsrPage }) => {
  await seededSession.as("org_admin")
  await dsrPage.goto()
  await dsrPage.previewRequester("managed@example.com", "access")
  await dsrPage.submit()
  await dsrPage.reload()
  await dsrPage.expectRecordedRow("managed@example.com", "recorded")
})
```

```ts
test("out-of-scope requester fails closed", async ({ seededSession, dsrPage }) => {
  await seededSession.as("org_admin")
  await dsrPage.goto()
  await dsrPage.previewRequester("outside-scope@example.com", "access")
  await dsrPage.expectError()
  await dsrPage.reload()
  await dsrPage.expectNoRecordedRow("outside-scope@example.com")
})
```

**Step 2: Run tests to verify failure**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/data-subject-requests.spec.ts --project=chromium-real-jwt --reporter=line`

Expected:

- FAIL because the seed contract does not yet provide the DSR scenario and helper data.

**Step 3: Extend seed support and add the page object**

Seed scenarios should return:

- scoped admin principal
- managed in-scope requester
- out-of-scope requester identifier

The page object should encapsulate:

- navigation to `/data-ops`
- DSR form filling
- preview wait conditions
- recorded-row lookup after reload

**Step 4: Re-run the DSR slice**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/data-subject-requests.spec.ts --project=chromium-real-jwt --reporter=line`

Expected:

- PASS for golden path and closed-failure path.

**Step 5: Commit**

```bash
git add admin-ui/tests/e2e/real-backend/helpers/page-objects/data-subject-requests-page.ts \
  admin-ui/tests/e2e/real-backend/data-subject-requests.spec.ts \
  tldw_Server_API/app/services/admin_e2e_support_service.py \
  tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py
git commit -m "test(admin-ui): add real-backend DSR coverage"
```

### Task 5: Add Backup Scheduling Real-Backend E2E Coverage With Deterministic Scheduler Trigger

**Files:**
- Create: `admin-ui/tests/e2e/real-backend/helpers/page-objects/backups-page.ts`
- Create: `admin-ui/tests/e2e/real-backend/backup-schedules.spec.ts`
- Modify: `tldw_Server_API/app/services/admin_e2e_support_service.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/test_support/admin_e2e.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py`

**Step 1: Write the failing backup browser tests**

```ts
test("creates a schedule and persists it across reload", async ({ seededSession, backupsPage }) => {
  await seededSession.as("platform_admin")
  await backupsPage.gotoScheduleTab()
  await backupsPage.createSchedule({
    dataset: "media",
    targetUserEmail: "managed@example.com",
    frequency: "daily",
    timeOfDay: "02:00",
    retentionCount: 3,
  })
  await backupsPage.reload()
  await backupsPage.expectScheduleRow("media", "02:00")
})
```

```ts
test("scheduler trigger produces visible run metadata", async ({ seededSession, seedClient, backupsPage }) => {
  await seededSession.as("platform_admin")
  await backupsPage.gotoScheduleTab()
  const scheduleId = await backupsPage.createScheduleAndReturnId()
  await seedClient.runDueBackupSchedules()
  await backupsPage.reload()
  await backupsPage.expectLastRunMetadata(scheduleId)
})
```

```ts
test("forbidden schedule target fails closed", async ({ seededSession, backupsPage }) => {
  await seededSession.as("org_admin")
  await backupsPage.gotoScheduleTab()
  await backupsPage.createForbiddenAuthnzSchedule()
  await backupsPage.expectError()
  await backupsPage.expectNoScheduleRow("AuthNZ Users DB")
})
```

**Step 2: Run tests to verify failure**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/backup-schedules.spec.ts --project=chromium-real-jwt --reporter=line`

Expected:

- FAIL because the deterministic scheduler trigger and backup seed support are missing.

**Step 3: Implement the trigger endpoint and page object**

In test-support service/router:

- implement `POST /run-due-backup-schedules`
- trigger one scheduler tick for the active instance

In the page object:

- navigate to the schedule tab
- create/edit/pause/resume/delete schedules
- resolve schedule rows by dataset/description

**Step 4: Re-run the backup slice**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/backup-schedules.spec.ts --project=chromium-real-jwt --reporter=line`

Expected:

- PASS for schedule persistence, deterministic run metadata, and forbidden-target denial.

**Step 5: Commit**

```bash
git add admin-ui/tests/e2e/real-backend/helpers/page-objects/backups-page.ts \
  admin-ui/tests/e2e/real-backend/backup-schedules.spec.ts \
  tldw_Server_API/app/services/admin_e2e_support_service.py \
  tldw_Server_API/app/api/v1/endpoints/test_support/admin_e2e.py \
  tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py
git commit -m "test(admin-ui): add real-backend backup scheduling coverage"
```

### Task 6: Add Monitoring Authority And Debug RBAC Real-Backend E2E Coverage

**Files:**
- Create: `admin-ui/tests/e2e/real-backend/helpers/page-objects/monitoring-page.ts`
- Create: `admin-ui/tests/e2e/real-backend/helpers/page-objects/debug-page.ts`
- Create: `admin-ui/tests/e2e/real-backend/monitoring-authority.spec.ts`
- Create: `admin-ui/tests/e2e/real-backend/debug-rbac.spec.ts`
- Modify: `tldw_Server_API/app/services/admin_e2e_support_service.py`
- Test: `tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py`

**Step 1: Write the failing monitoring and debug tests**

```ts
test("monitoring rule and alert mutation persist across reload", async ({ seededSession, monitoringPage }) => {
  await seededSession.as("platform_admin")
  await monitoringPage.goto()
  await monitoringPage.createRule({ metric: "cpu_percent", operator: ">", threshold: 80 })
  await monitoringPage.assignSeededAlert("alert-cpu-high", "admin")
  await monitoringPage.reload()
  await monitoringPage.expectRulePresent("cpu_percent")
  await monitoringPage.expectAlertAssigned("alert-cpu-high", "admin")
})
```

```ts
test("monitoring mutation failure leaves no fake local state", async ({ seededSession, monitoringPage }) => {
  await seededSession.as("plain_admin")
  await monitoringPage.goto()
  await monitoringPage.tryEscalateSeededAlert("alert-cpu-high")
  await monitoringPage.expectError()
  await monitoringPage.reload()
  await monitoringPage.expectAlertNotEscalated("alert-cpu-high")
})
```

```ts
test("plain multi-user admin is denied from debug", async ({ seededSession, debugPage }) => {
  await seededSession.as("plain_admin")
  await debugPage.goto()
  await debugPage.expectDenied()
})
```

**Step 2: Run tests to verify failure**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/monitoring-authority.spec.ts tests/e2e/real-backend/debug-rbac.spec.ts --project=chromium-real-jwt --project=chromium-real-single-user --reporter=line`

Expected:

- FAIL because seeded alert identities and debug-role scenarios are not exposed yet.

**Step 3: Extend seed support and add page objects**

Seed support must return:

- stable alert IDs/fingerprints
- principals for `plain_admin`, `owner`, `super_admin`
- seeded monitoring rules/history when needed

Page objects should encapsulate:

- rule creation
- alert assignment/snooze/escalation interactions
- reload/persistence checks
- debug page reachability/denial assertions

**Step 4: Re-run the monitoring/debug slice**

Run:

- `cd admin-ui && bunx playwright test tests/e2e/real-backend/monitoring-authority.spec.ts tests/e2e/real-backend/debug-rbac.spec.ts --project=chromium-real-jwt --project=chromium-real-single-user --reporter=line`

Expected:

- PASS for persisted monitoring mutations and debug RBAC allow/deny behavior.

**Step 5: Commit**

```bash
git add admin-ui/tests/e2e/real-backend/helpers/page-objects/monitoring-page.ts \
  admin-ui/tests/e2e/real-backend/helpers/page-objects/debug-page.ts \
  admin-ui/tests/e2e/real-backend/monitoring-authority.spec.ts \
  admin-ui/tests/e2e/real-backend/debug-rbac.spec.ts \
  tldw_Server_API/app/services/admin_e2e_support_service.py \
  tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py
git commit -m "test(admin-ui): add monitoring and debug real-backend coverage"
```

### Task 7: Wire CI, Document The New Lane, And Run Final Verification

**Files:**
- Modify: `admin-ui/README.md`
- Modify: `.github/workflows/frontend-required.yml`
- Modify: `Helper_Scripts/ci/path_classifier.py` (only if needed for gating)
- Test: existing targeted backend/admin-ui tests from prior tasks

**Step 1: Add the failing CI expectation**

Document the intended command in the workflow:

```yaml
- name: Run admin-ui real-backend e2e
  working-directory: admin-ui
  run: bun run test:real-backend -- --project=chromium-real-jwt --project=chromium-real-single-user
```

Add README guidance describing:

- required env vars
- default auto-boot behavior
- how to reuse an already-running backend locally

**Step 2: Run the real-backend lane before editing CI**

Run:

- `cd admin-ui && bun run test:real-backend -- --project=chromium-real-jwt --project=chromium-real-single-user --reporter=line`

Expected:

- PASS locally before the workflow is tightened.

**Step 3: Wire the workflow and docs**

Update `.github/workflows/frontend-required.yml` to run the new suite when `admin_ui_changed == 'true'`.

Keep the first version bounded to the real-backend admin lane only, not the older stub suite.

**Step 4: Run the full verification slice**

Run:

- `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Admin/test_admin_e2e_support_api.py -q`
- `cd admin-ui && bunx playwright test tests/e2e/real-backend --project=chromium-real-jwt --project=chromium-real-single-user --reporter=line`
- `cd admin-ui && bun run lint`
- `cd admin-ui && bun run typecheck`
- `cd admin-ui && bun run build`
- `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/test_support/admin_e2e.py tldw_Server_API/app/services/admin_e2e_support_service.py -f json -o /tmp/bandit_admin_ui_real_backend_e2e.json`

Expected:

- all targeted backend tests pass
- both Playwright real-backend projects pass
- `admin-ui` lint/typecheck/build pass
- Bandit reports no new findings in the touched backend support code

**Step 5: Commit**

```bash
git add admin-ui/README.md .github/workflows/frontend-required.yml Helper_Scripts/ci/path_classifier.py
git commit -m "ci(admin-ui): gate privileged admin flows with real-backend e2e"
```
