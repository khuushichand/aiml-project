# 2026-03-11 Admin UI Real-Backend E2E Design

## Goal

Add a real-backend Playwright lane for `admin-ui` that proves the newly authoritative admin workflows behave truthfully in a real browser against a real FastAPI backend.

The suite must cover both admin auth modes:

- multi-user JWT mode
- single-user API-key mode

The suite must verify:

- persistence across reloads for DSR, backup scheduling, and monitoring authority
- privileged route protection for `/debug`
- fail-closed behavior for one denial or backend-failure path per feature

## Scope

This design covers:

- `admin-ui` Playwright only
- real browser coverage in `admin-ui/tests/e2e`
- disposable FastAPI backend instances started automatically by the test harness
- test-only backend seed/reset/bootstrap endpoints enabled only in explicit e2e mode

This design does not cover:

- a full rewrite of the existing stub/smoke suite
- broad negative-matrix RBAC coverage for every admin page
- wall-clock waiting for scheduled backups
- alert generation engine changes
- replacing backend unit/integration tests

## High-Level Approach

Keep the current stub-based Playwright smoke tests intact and add a separate real-backend lane beside them.

The real-backend lane will:

1. Auto-start `admin-ui`.
2. Auto-start isolated FastAPI backend instances for each auth mode.
3. Point `NEXT_PUBLIC_API_URL` at the correct backend for the active project.
4. Use test-only backend endpoints to reset and seed deterministic fixture state.
5. Exercise real browser flows against real admin APIs.

## Test Harness Layout

### Existing Tests Stay Intact

These existing tests remain the lightweight smoke/stub layer:

- `admin-ui/tests/e2e/login-and-mfa.spec.ts`
- `admin-ui/tests/e2e/user-privileged-actions.spec.ts`
- `admin-ui/tests/e2e/debug-single-user.spec.ts`

### New Real-Backend Lane

Add a new directory:

- `admin-ui/tests/e2e/real-backend/`

Add shared helpers under:

- `admin-ui/tests/e2e/real-backend/helpers/`

Recommended helper split:

- `backend-lifecycle.ts` — start/stop FastAPI instances via `tldw_Server_API/scripts/server_lifecycle.py`
- `seed-client.ts` — call test-support seed/reset/bootstrap endpoints
- `session.ts` — browser session bootstrap helpers
- `fixtures.ts` — project-specific Playwright fixtures
- `page-objects/` — small helper layer for login, DSR, backups, monitoring, and debug flows

## Playwright Project Model

Extend `admin-ui/playwright.config.ts` with:

- existing `chromium` project for stub/smoke coverage
- `chromium-real-jwt`
- `chromium-real-single-user`

### Project Isolation Rules

Each real-backend project gets its own backend instance with:

- unique `SERVER_LABEL`
- unique port
- isolated database paths
- its own auth mode
- its own test seed state

This avoids cross-project contamination between JWT and single-user flows.

### Startup Model

Default behavior:

- auto-start `admin-ui`
- auto-start both real backend instances as needed for the selected projects

Override behavior for local debugging:

- if explicit backend URL env vars are set, reuse the running backend instead of auto-booting it

Recommended env names:

- `TLDW_ADMIN_E2E_JWT_API_URL`
- `TLDW_ADMIN_E2E_SINGLE_USER_API_URL`
- `TLDW_ADMIN_E2E_AUTOSTART_BACKEND=true|false`

## Backend Boot Strategy

Reuse the existing lifecycle wrapper:

- `tldw_Server_API/scripts/server_lifecycle.py`

The Playwright harness should call it with project-specific env such as:

- `SERVER_LABEL`
- `SERVER_PORT`
- `E2E_TEST_BASE_URL`
- `AUTH_MODE`
- `DATABASE_URL`
- test DB base directories for per-user stores
- `ENABLE_ADMIN_E2E_TEST_MODE=true`

The lifecycle helper already supports labeled instances and port selection, so this design deliberately avoids introducing a second backend process manager.

## Test-Support Endpoint Namespace

Do not expose e2e support endpoints under normal admin routes.

Add a clearly non-production namespace:

- `/api/v1/test-support/admin-e2e/...`

Register these routes only when:

- `ENABLE_ADMIN_E2E_TEST_MODE=true`

And only in explicit e2e/test runtime.

### Required Endpoints

Recommended minimum contract:

- `POST /api/v1/test-support/admin-e2e/reset`
- `POST /api/v1/test-support/admin-e2e/seed`
- `POST /api/v1/test-support/admin-e2e/bootstrap-jwt-session`
- `POST /api/v1/test-support/admin-e2e/run-due-backup-schedules`

Optional if needed later:

- `GET /api/v1/test-support/admin-e2e/state`

### Reset Contract

`reset` must:

- clear seeded admin e2e fixtures
- reset AuthNZ test data for the active project instance
- clear DSR records created for the scenario
- clear backup schedules/artifacts/jobs created for the scenario
- clear monitoring rules, alert overlay state, and alert-event history created for the scenario

### Seed Contract

`seed` must be deterministic and idempotent.

It should support creating:

- orgs, memberships, and roles
- multi-user admins with explicit roles (`admin`, `owner`, `super_admin`)
- non-admin users for denial-path checks
- DSR-visible requesters and preexisting DSR history rows
- backup schedules and optional backup artifacts
- monitoring rules, overlay state, and alert events
- stable alert identities returned to the browser tests

The seed response should return canonical IDs needed by the tests so selectors and API follow-ups are deterministic.

### JWT Session Bootstrap

Most JWT feature tests should not pay the full browser-login cost repeatedly.

Add a test-support session bootstrap endpoint that:

- mints a short-lived, real JWT for a seeded principal
- returns enough information for the Playwright helper to set the same session cookies the app expects

However, v1 must still include one real browser login smoke in multi-user mode.

### Scheduler Trigger Contract

Do not wait for APScheduler wall-clock time in browser tests.

Use:

- `POST /api/v1/test-support/admin-e2e/run-due-backup-schedules`

This endpoint should run one deterministic scheduler tick for the active test instance so the browser test can prove:

- schedule persisted
- scheduler enqueued
- resulting job/artifact state became visible in the admin UI

## Auth Strategy

### Multi-User JWT Project

V1 coverage includes:

- one real browser login smoke using the existing login UI
- seeded-session bootstrap for the rest of the real-backend feature tests

This keeps the suite honest about the login path without making MFA/auth setup the bottleneck for every privileged-flow test.

### Single-User Project

Run the backend with:

- `AUTH_MODE=single_user`

Use the real API-key login flow through the browser.

This is already an important product path for self-hosted deployments and should remain a real UI flow in the suite.

## Feature Matrix

### Auth / Entry

#### JWT

Golden path:

- admin can reach the admin landing route
- one real login smoke succeeds

Denial path:

- non-admin is denied from privileged admin routes

#### Single-User

Golden path:

- API-key login succeeds
- single-user admin can reach `/debug`

### DSR

Golden path:

- admin previews a seeded requester
- admin records a DSR request
- page reload shows the request from backend history

Closed-failure path:

- out-of-scope or unknown requester shows an error
- no success toast implying persistence
- no new history row appears after reload

### Backup Scheduling

Golden path:

- admin creates a schedule
- page reload shows the persisted schedule
- pause/resume or delete persists across reload
- deterministic scheduler trigger produces visible run metadata

Closed-failure path:

- unauthorized target or forbidden dataset schedule attempt fails with no fake persisted row

### Monitoring Authority

Golden path:

- admin creates an alert rule
- admin assigns, snoozes, or escalates a seeded alert
- page reload shows persisted rule state and persisted alert overlay/history

Closed-failure path:

- unauthorized or failed mutation shows an error
- no fake local state survives reload

### Debug RBAC

Golden path:

- single-user admin can reach `/debug`
- multi-user `owner` or `super_admin` can reach `/debug`

Denied path:

- multi-user plain `admin` is denied

## Intentional V1 Exclusions

V1 does not need:

- full login/MFA scenario matrix
- every admin page under real-backend coverage
- dependency-page regression coverage, because that behavior is already primarily a frontend contract and already covered elsewhere
- exhaustive monitoring negative cases

## Page Object Layer

Create a small page-object/helper layer from the start. Do not build a large framework.

Minimum recommended objects:

- `LoginPage`
- `DataSubjectRequestsPage`
- `BackupsPage`
- `MonitoringPage`
- `DebugPage`

These objects should encapsulate:

- navigation
- stable selectors
- common wait conditions
- reload/persistence checks

## CI Integration

The end state should make this suite a real gate for admin-ui changes.

Recommended progression:

1. Add `admin-ui` script support for the real-backend lane.
2. Run the new suite in CI for changed `admin-ui` paths.
3. Promote the suite into the existing frontend gate once runtime is acceptable.

Primary workflow likely affected:

- `.github/workflows/frontend-required.yml`

## Risks And Constraints

### 1. Seed Contract Bloat

Mitigation:

- keep the test-support API narrowly focused on deterministic fixture setup/reset
- do not duplicate production admin APIs

### 2. Alert Identity Drift

Mitigation:

- seed stable alert identities explicitly
- make tests consume those returned IDs instead of guessing from UI text

### 3. Cross-Project State Bleed

Mitigation:

- separate backend instances per auth-mode project
- separate DB paths and ports

### 4. Production Exposure Of Test Routes

Mitigation:

- test-support namespace only
- explicit env gating
- no router registration outside e2e mode

## Completion Criteria

This design is complete when implementation produces:

- a real-backend Playwright lane under `admin-ui/tests/e2e/real-backend`
- separate JWT and single-user projects with isolated backend instances
- deterministic test-support seed/reset/bootstrap routes
- one real JWT login smoke
- one real single-user login smoke
- authoritative persistence checks for DSR, backup scheduling, and monitoring
- debug RBAC coverage for allowed and denied roles
- CI wiring for the new lane
