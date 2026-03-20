# Collections Page Startup Investigation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reproduce the shared Collections empty-on-load regression, identify the exact failing startup boundary, implement the smallest fix at that boundary, and lock it down with regression coverage for both first-load data and at least one follow-on action.

**Architecture:** The Collections page is a shared UI flow used by both the WebUI and the extension. The implementation should trace and then fix the startup chain from the Collections route into `useTldwApiClient()`, through `TldwApiClient`, `bgRequest`, and `request-core`, then back into UI/store rendering. The plan assumes the root cause will land in one of four buckets: transport, auth/bootstrap, backend contract, or UI/store wiring.

**Tech Stack:** React, Zustand, Vitest, Playwright, TypeScript, FastAPI, pytest, loguru

---

### Task 1: Reproduce the startup failure with real user-facing bootstrap

**Files:**
- Inspect: `apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx`
- Inspect: `apps/packages/ui/src/components/Option/Collections/Templates/TemplatesList.tsx`
- Inspect: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Inspect: `apps/packages/ui/src/services/background-proxy.ts`
- Inspect: `apps/packages/ui/src/services/tldw/request-core.ts`
- Inspect: `apps/tldw-frontend/e2e/workflows/collections-stage3.spec.ts`
- Inspect: `apps/extension/tests/e2e/collections.spec.ts`

**Step 1: Reproduce the empty-state failure in WebUI without relying on direct localStorage seeding**

Run:

```bash
source .venv/bin/activate
python -m uvicorn tldw_Server_API.app.main:app --reload
```

Then use the existing WebUI/extension startup flow to reach `/collections` and record:

- whether the Reading tab mounts
- whether `/api/v1/reading/items` is requested
- whether any error is visible in the UI

Expected: The bug reproduces and the page is empty before user interaction.

**Step 2: Capture the first failing request boundary**

Record for the first Reading load and one secondary tab load:

```text
request start
resolved serverUrl
auth mode
transport path (extension messaging vs direct fetch)
HTTP status
minimal payload shape
final UI/store outcome
```

Expected: One of those boundaries fails consistently in both runtimes, or the runtimes diverge in a way that narrows the root cause.

**Step 3: Write down the classification before changing code**

Classify the failure as exactly one of:

```text
transport
auth/bootstrap
backend contract
UI/store wiring
```

Expected: The classification names the first broken boundary, not a secondary symptom like "button is dead."

**Step 4: Commit the reproduction notes if you created any durable artifact**

```bash
git add Docs/Plans/2026-03-13-collections-page-startup-investigation-design.md Docs/Plans/2026-03-13-collections-page-startup-investigation-implementation-plan.md
git commit -m "docs: add collections startup investigation plan"
```

If no additional notes were added beyond the plan docs, skip this step until Task 5.

### Task 2: Add a failing regression test at the confirmed startup boundary

**Files:**
- Create: `apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/ReadingItemsList.startup.test.tsx`
- Create or Modify: `apps/packages/ui/src/services/__tests__/collections-startup-request-path.test.ts`
- Modify if needed: `apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx`
- Modify if needed: `apps/packages/ui/src/services/background-proxy.ts`
- Modify if needed: `apps/packages/ui/src/services/tldw/request-core.ts`
- Modify if needed: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Write the failing UI regression test for the default Reading tab**

Use the smallest stable boundary that reproduces the real bug. If the failure is startup fetch behavior, start with the shared component test:

```tsx
it("surfaces startup fetch failure instead of silently rendering an empty collections state", async () => {
  vi.mock("@/hooks/useTldwApiClient", () => ({
    useTldwApiClient: () => ({
      getReadingList: vi.fn().mockRejectedValue(new Error("401 Unauthorized"))
    })
  }))

  render(<ReadingItemsList />)

  await waitFor(() => {
    expect(screen.getByText(/401 Unauthorized/i)).toBeInTheDocument()
  })
})
```

If the root cause is lower in the request stack, write the failing regression at that lower layer instead.

**Step 2: Run the failing frontend test**

Run:

```bash
bunx vitest run apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/ReadingItemsList.startup.test.tsx
```

Expected: FAIL because the current code path reproduces the empty-silent startup behavior or misroutes the request path.

**Step 3: Write a failing request-layer regression test if the root cause is transport or config related**

Example skeleton:

```ts
it("uses the resolved configured server and auth mode for collections startup requests", async () => {
  const response = await bgRequest({
    path: "/api/v1/reading/items",
    method: "GET"
  })

  expect(fetchMock).toHaveBeenCalledWith(
    expect.stringContaining("/api/v1/reading/items"),
    expect.objectContaining({
      headers: expect.objectContaining({ "X-API-KEY": "test-key" })
    })
  )
})
```

**Step 4: Run the failing request-layer test**

Run:

```bash
bunx vitest run apps/packages/ui/src/services/__tests__/collections-startup-request-path.test.ts
```

Expected: FAIL with the exact mismatch that explains the startup regression.

**Step 5: Commit the failing test baseline**

```bash
git add apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/ReadingItemsList.startup.test.tsx apps/packages/ui/src/services/__tests__/collections-startup-request-path.test.ts
git commit -m "test: capture collections startup regression"
```

### Task 3: Implement the minimal fix at the classified boundary

**Files:**
- Modify: `apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx`
- Modify: `apps/packages/ui/src/components/Option/Collections/Templates/TemplatesList.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/background-proxy.ts`
- Modify: `apps/packages/ui/src/services/tldw/request-core.ts`
- Modify if backend contract is implicated: `tldw_Server_API/app/api/v1/endpoints/reading.py`
- Modify if backend contract is implicated: `tldw_Server_API/app/api/v1/endpoints/outputs_templates.py`

**Step 1: Implement only the smallest fix needed for the failing tests**

Choose the branch that matches the classification from Task 1:

```text
transport:
  fix request routing, runtime fallback, or message transport selection

auth/bootstrap:
  fix config resolution, auth header selection, or startup bootstrap state handling

backend contract:
  align endpoint behavior, accepted auth mode, or response shape with the shared client

UI/store wiring:
  fix error surfacing, state population, or render gating after valid data returns
```

**Step 2: Keep startup visibility explicit**

If the failure currently collapses to a blank state, ensure the page surfaces a concrete startup error:

```tsx
{itemsError ? (
  <Empty description={itemsError}>
    <Button onClick={fetchItems}>Retry</Button>
  </Empty>
) : null}
```

Do not add broad logging that will remain in production. Keep observability bounded to the failing path.

**Step 3: Run the targeted frontend tests**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/ReadingItemsList.startup.test.tsx \
  apps/packages/ui/src/services/__tests__/collections-startup-request-path.test.ts
```

Expected: PASS

**Step 4: Run backend tests if a backend file changed**

Run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Collections/test_reading_api.py \
  tldw_Server_API/tests/Collections/test_outputs_templates_api.py -v
```

Expected: PASS

**Step 5: Commit the minimal fix**

```bash
git add apps/packages/ui/src/components/Option/Collections/ReadingList/ReadingItemsList.tsx apps/packages/ui/src/components/Option/Collections/Templates/TemplatesList.tsx apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/background-proxy.ts apps/packages/ui/src/services/tldw/request-core.ts tldw_Server_API/app/api/v1/endpoints/reading.py tldw_Server_API/app/api/v1/endpoints/outputs_templates.py
git commit -m "fix: restore collections startup data loading"
```

Only include files actually changed.

### Task 4: Verify both runtimes and one follow-on user action

**Files:**
- Modify if needed: `apps/tldw-frontend/e2e/workflows/collections-stage3.spec.ts`
- Modify if needed: `apps/extension/tests/e2e/collections.spec.ts`
- Modify if needed: `apps/packages/ui/src/components/Option/Collections/ReadingList/AddUrlModal.tsx`
- Modify if needed: `apps/packages/ui/src/components/Option/Collections/Templates/TemplateEditor.tsx`

**Step 1: Verify first-load data in WebUI**

Run:

```bash
bunx playwright test apps/tldw-frontend/e2e/workflows/collections-stage3.spec.ts
```

Expected:

- `/collections` shows seeded reading data on first load
- the initial request path completes successfully

**Step 2: Verify first-load data in the extension**

Run:

```bash
bunx playwright test apps/extension/tests/e2e/collections.spec.ts
```

Expected:

- the options-page Collections route shows initial data
- no dead-start empty state remains

**Step 3: Verify one mutation path after startup is healthy**

Use the smallest real action that depends on the same page being healthy:

```text
Add URL
or
Create template
or
Delete reading item
```

Expected: The action issues the correct request and updates the UI.

**Step 4: Tighten the e2e guard if current tests bypass the real startup path**

If the current spec seeds config too aggressively, update the spec so the regression guard covers the real user-facing bootstrap path rather than only a test shortcut.

**Step 5: Commit the runtime verification hardening**

```bash
git add apps/tldw-frontend/e2e/workflows/collections-stage3.spec.ts apps/extension/tests/e2e/collections.spec.ts
git commit -m "test: harden collections startup regression coverage"
```

### Task 5: Final verification, security check, and cleanup

**Files:**
- Review: all files touched in Tasks 2-4
- Modify if needed: `Docs/Plans/2026-03-13-collections-page-startup-investigation-design.md`
- Modify if needed: `Docs/Plans/2026-03-13-collections-page-startup-investigation-implementation-plan.md`

**Step 1: Run the full touched-scope verification set**

Run:

```bash
bunx vitest run \
  apps/packages/ui/src/components/Option/Collections/ReadingList/__tests__/ReadingItemsList.startup.test.tsx \
  apps/packages/ui/src/services/__tests__/collections-startup-request-path.test.ts
```

If backend changed, also run:

```bash
source .venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Collections/test_reading_api.py \
  tldw_Server_API/tests/Collections/test_outputs_templates_api.py -v
```

Expected: PASS

**Step 2: Run Bandit on touched Python scope if any Python files changed**

Run:

```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/app/api/v1/endpoints/reading.py tldw_Server_API/app/api/v1/endpoints/outputs_templates.py -f json -o /tmp/bandit_collections_startup.json
```

Expected: No new findings in changed Python files.

If no Python files changed, note that Bandit is not applicable to the touched TypeScript-only scope.

**Step 3: Remove temporary investigation-only code**

Before finishing, remove any console noise, ad hoc instrumentation, or temporary UI markers that were only useful during diagnosis.

**Step 4: Review the diff and commit the final cleanup**

```bash
git status --short
git diff --stat
git add <touched files>
git commit -m "chore: finalize collections startup investigation cleanup"
```

**Step 5: Report the result in root-cause language**

The final handoff must say:

```text
what broke
where it broke
why both WebUI and extension were affected
what regression test now protects it
```
