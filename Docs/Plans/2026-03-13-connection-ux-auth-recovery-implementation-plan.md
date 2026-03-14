# Connection UX Auth Recovery Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix the shared connection UX so sidepanel auth recovery updates real request config, Collections distinguishes auth/setup from offline, and onboarding entry becomes resumable instead of destructive.

**Architecture:** Split onboarding entry from onboarding reset in the shared connection store, migrate inline auth repair to `tldwConfig`, and update blocking/guidance surfaces to use richer connection UX state instead of only `useServerOnline()`.

**Tech Stack:** React, Zustand, Vitest, Ant Design, shared UI package connection store/hooks

---

### Task 1: Add Failing Connection Store Regression Tests

**Files:**
- Modify: `apps/packages/ui/src/store/__tests__/connection.test.ts`
- Modify: `apps/packages/ui/src/store/connection.tsx`

**Step 1: Write the failing test**

Add tests for:
- entering onboarding with a saved server URL and missing single-user auth preserves `hasCompletedFirstRun` and lands on `configStep: "auth"`
- restarting onboarding clears first-run completion and returns to `configStep: "url"`

**Step 2: Run test to verify it fails**

Run: `bunx vitest run src/store/__tests__/connection.test.ts`

Expected: FAIL on missing action behavior or current destructive reset behavior.

**Step 3: Write minimal implementation**

Split the current `beginOnboarding()` behavior into:
- `enterOnboarding()`
- `restartOnboarding()`

Update action exports and call sites after the tests drive the behavior.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run src/store/__tests__/connection.test.ts`

Expected: PASS for the new onboarding action coverage and prior connection tests.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/__tests__/connection.test.ts apps/packages/ui/src/store/connection.tsx
git commit -m "refactor(ui): split onboarding enter and restart state"
```

### Task 2: Add Failing Sidepanel Auth Recovery Tests

**Files:**
- Create or modify: `apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ConnectionBanner.test.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/ConnectionBanner.tsx`

**Step 1: Write the failing test**

Add a test that renders the banner in `error_auth`, enters an API key, clicks save, and expects:
- shared config update path to be called
- connection re-check to be triggered
- no legacy `tldwApiKey` write path to be used

**Step 2: Run test to verify it fails**

Run: `bunx vitest run src/components/Sidepanel/Chat/__tests__/ConnectionBanner.test.tsx`

Expected: FAIL because the banner currently writes to legacy storage.

**Step 3: Write minimal implementation**

Use the shared config client/store path to persist `apiKey` into `tldwConfig`, then re-run connection checks.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run src/components/Sidepanel/Chat/__tests__/ConnectionBanner.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Sidepanel/Chat/__tests__/ConnectionBanner.test.tsx apps/packages/ui/src/components/Sidepanel/Chat/ConnectionBanner.tsx
git commit -m "fix(ui): route sidepanel api key repair through shared config"
```

### Task 3: Add Failing Collections UX Tests

**Files:**
- Create or modify: `apps/packages/ui/src/components/Option/Collections/__tests__/CollectionsPlaygroundPage.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/Collections/index.tsx`

**Step 1: Write the failing test**

Add tests covering:
- auth/setup state shows auth-required guidance and CTA
- unreachable state shows offline guidance
- connected state still renders tabs

**Step 2: Run test to verify it fails**

Run: `bunx vitest run src/components/Option/Collections/__tests__/CollectionsPlaygroundPage.test.tsx`

Expected: FAIL because the page currently renders only a generic offline empty state when not online.

**Step 3: Write minimal implementation**

Replace the boolean-only gate with `useConnectionUxState()` or equivalent derived state and render targeted empty states.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run src/components/Option/Collections/__tests__/CollectionsPlaygroundPage.test.tsx`

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Option/Collections/__tests__/CollectionsPlaygroundPage.test.tsx apps/packages/ui/src/components/Option/Collections/index.tsx
git commit -m "fix(ui): show collections auth and setup guidance"
```

### Task 4: Update Onboarding Entry Call Sites

**Files:**
- Modify: `apps/packages/ui/src/hooks/useConnectionState.ts`
- Modify: `apps/packages/ui/src/components/Option/Onboarding/OnboardingWizard.tsx`
- Modify: `apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx`
- Modify: `apps/packages/ui/src/routes/option-index.tsx`
- Modify: `apps/tldw-frontend/extension/routes/option-index.tsx`
- Modify: `apps/packages/ui/src/components/Option/Settings/general-settings.tsx`

**Step 1: Write the failing test**

If existing route/component tests cover onboarding entry, extend them. Otherwise rely on the connection store tests and add a narrow behavior test where useful.

**Step 2: Run test to verify it fails**

Run the touched onboarding or route tests if present, otherwise re-run the connection store tests.

**Step 3: Write minimal implementation**

Use:
- `enterOnboarding()` for initial route entry and wizard mount
- `restartOnboarding()` for explicit reset from Settings

**Step 4: Run test to verify it passes**

Run the touched onboarding/connection tests.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useConnectionState.ts apps/packages/ui/src/components/Option/Onboarding/OnboardingWizard.tsx apps/packages/ui/src/components/Option/Onboarding/OnboardingConnectForm.tsx apps/packages/ui/src/routes/option-index.tsx apps/tldw-frontend/extension/routes/option-index.tsx apps/packages/ui/src/components/Option/Settings/general-settings.tsx
git commit -m "refactor(ui): make onboarding entry resumable"
```

### Task 5: Verify the Touched Scope

**Files:**
- Verify all files touched in Tasks 1-4

**Step 1: Run targeted tests**

Run:
- `bunx vitest run src/store/__tests__/connection.test.ts`
- `bunx vitest run src/components/Sidepanel/Chat/__tests__/ConnectionBanner.test.tsx`
- `bunx vitest run src/components/Option/Collections/__tests__/CollectionsPlaygroundPage.test.tsx`

Workdir: `apps/packages/ui`

**Step 2: Run formatting/whitespace sanity check**

Run:
- `git diff --check`

**Step 3: Run Bandit on touched scope per repo policy**

Run from repo root with project venv:

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/store apps/packages/ui/src/components/Sidepanel/Chat apps/packages/ui/src/components/Option/Collections apps/packages/ui/src/components/Option/Onboarding apps/packages/ui/src/routes apps/tldw-frontend/extension/routes -f json -o /tmp/bandit_connection_ux.json
```

Expected: No new findings in the touched scope.

**Step 4: Commit final integrated fix**

```bash
git add <touched files>
git commit -m "fix(ui): repair connection auth recovery and onboarding guidance"
```
