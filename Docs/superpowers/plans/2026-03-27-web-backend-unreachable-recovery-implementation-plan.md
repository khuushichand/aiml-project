# Web Backend Unreachable Recovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace vague WebUI runtime crashes with a clear full-page backend recovery screen when the browser cannot reach the configured tldw server.

**Architecture:** Add a narrow shared backend-unreachable classifier plus a reusable full-page recovery component, then mount the WebUI error boundary in `_app.tsx` and extend both the top-level web boundary and the shared route boundary to render the recovery UI only for classified backend transport failures. Keep extension behavior unchanged by making route-boundary backend recovery opt-in, and suppress the existing `WebLayout` modal when the fatal recovery state is active.

**Tech Stack:** React, Next.js, TypeScript, Vitest, React Testing Library, shared UI package under `apps/packages/ui`, WebUI shell under `apps/tldw-frontend`

---

## File Structure

- `apps/packages/ui/src/services/backend-unreachable.ts`
  Purpose: classify errors and recent request-error records as backend-unreachable or not, and return structured diagnostics for UI use.
- `apps/packages/ui/src/services/__tests__/backend-unreachable.test.ts`
  Purpose: lock the classifier to strong transport signals only and prevent accidental over-matching.
- `apps/packages/ui/src/components/Common/BackendUnavailableRecovery.tsx`
  Purpose: render the shared full-page recovery UI for backend-unreachable failures.
- `apps/packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx`
  Purpose: prove the shared recovery screen shows the expected copy and actions.
- `apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx`
  Purpose: add opt-in backend recovery rendering for WebUI routes without changing extension defaults.
- `apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx`
  Purpose: verify opt-in backend recovery and default generic fallback behavior.
- `apps/tldw-frontend/components/ErrorBoundary.tsx`
  Purpose: convert the currently-unused web error boundary into a mounted backend-aware fallback that also handles `unhandledrejection`.
- `apps/tldw-frontend/__tests__/components/ErrorBoundary.test.tsx`
  Purpose: verify the mounted web boundary shows the recovery UI for classified backend failures and preserves the generic fallback for normal bugs.
- `apps/tldw-frontend/pages/_app.tsx`
  Purpose: actually mount the web error boundary around app content after `ConfigurationGuard`.
- `apps/tldw-frontend/components/layout/WebLayout.tsx`
  Purpose: suppress the existing backend-unreachable modal while the fatal recovery state is active.
- `apps/tldw-frontend/__tests__/components/layout/WebLayout.backend-unreachable.test.tsx`
  Purpose: verify the modal does not compete with the fatal recovery path.

## Task 1: Build The Backend-Unreachable Classifier

**Files:**
- Create: `apps/packages/ui/src/services/backend-unreachable.ts`
- Create: `apps/packages/ui/src/services/__tests__/backend-unreachable.test.ts`

- [ ] **Step 1: Write the failing classifier tests**

Create `apps/packages/ui/src/services/__tests__/backend-unreachable.test.ts` covering:

1. `status === 0` plus a network-style message classifies as backend unreachable
2. `NetworkError when attempting to fetch resource` classifies
3. `Failed to fetch` classifies
4. `AbortError`, `REQUEST_ABORTED`, and `"The operation was aborted."` do not classify
5. unrelated runtime errors do not classify
6. a recent `__tldwLastRequestError` payload can enrich diagnostics when present

```ts
expect(
  classifyBackendUnreachableError(
    Object.assign(new Error("NetworkError when attempting to fetch resource."), {
      status: 0
    })
  )
).toMatchObject({
  kind: "backend_unreachable"
})
```

- [ ] **Step 2: Run the classifier test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/services/__tests__/backend-unreachable.test.ts --reporter=verbose
```

Expected: FAIL because the classifier module does not exist yet.

- [ ] **Step 3: Implement the classifier module**

Create `apps/packages/ui/src/services/backend-unreachable.ts` with focused helpers:

- `classifyBackendUnreachableError(error, options?)`
- shared message pattern constants
- transport-only guards
- optional recent request-error parsing with freshness limits

Return structured diagnostics, not just a boolean.

- [ ] **Step 4: Re-run the classifier test**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/services/__tests__/backend-unreachable.test.ts --reporter=verbose
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/backend-unreachable.ts \
  apps/packages/ui/src/services/__tests__/backend-unreachable.test.ts
git commit -m "feat: classify backend unreachable errors"
```

## Task 2: Build The Shared Recovery Screen

**Files:**
- Create: `apps/packages/ui/src/components/Common/BackendUnavailableRecovery.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx`

- [ ] **Step 1: Write the failing recovery-component test**

Create `apps/packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx` covering:

1. title and explanatory copy render
2. actions render: `Try again`, `Reload page`, `Open Health & diagnostics`, `Open Settings`
3. request method/path and configured server URL render when provided
4. diagnostics stay hidden when no details are provided

```tsx
render(
  <BackendUnavailableRecovery
    details={{
      title: "Can't reach your tldw server",
      message: "Check that your server is running and accessible.",
      method: "GET",
      path: "/api/v1/llm/models/metadata",
      serverUrl: "http://127.0.0.1:8000"
    }}
    onRetry={vi.fn()}
    onReload={vi.fn()}
    onOpenSettings={vi.fn()}
    onOpenDiagnostics={vi.fn()}
  />
)
```

- [ ] **Step 2: Run the recovery-component test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx --reporter=verbose
```

Expected: FAIL because the component does not exist yet.

- [ ] **Step 3: Implement the shared recovery component**

Create `apps/packages/ui/src/components/Common/BackendUnavailableRecovery.tsx` as a pure presentational component with:

- full-page takeover layout
- clear title/body
- optional diagnostics block
- action buttons wired by props

Keep it free of route/navigation logic so both boundaries can reuse it.

- [ ] **Step 4: Re-run the recovery-component test**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx --reporter=verbose
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/BackendUnavailableRecovery.tsx \
  apps/packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx
git commit -m "feat: add backend unavailable recovery screen"
```

## Task 3: Mount And Extend The Web Error Boundary

**Files:**
- Modify: `apps/tldw-frontend/components/ErrorBoundary.tsx`
- Modify: `apps/tldw-frontend/pages/_app.tsx`
- Create: `apps/tldw-frontend/__tests__/components/ErrorBoundary.test.tsx`

- [ ] **Step 1: Write the failing web-boundary tests**

Create `apps/tldw-frontend/__tests__/components/ErrorBoundary.test.tsx` covering:

1. a caught classified backend-unreachable error renders the shared recovery screen
2. an `unhandledrejection` with a classified backend-unreachable reason renders the shared recovery screen
3. a normal runtime error still renders the generic fallback
4. retry clears backend-recovery state

Mock the shared classifier and recovery component directly so the test stays focused on boundary wiring.

- [ ] **Step 2: Run the web-boundary test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run __tests__/components/ErrorBoundary.test.tsx --reporter=verbose
```

Expected: FAIL because the boundary is not mounted and does not yet special-case backend failures.

- [ ] **Step 3: Update the web error boundary**

Modify `apps/tldw-frontend/components/ErrorBoundary.tsx` to:

- classify caught errors
- store backend recovery state separately from generic error state
- subscribe to `window.unhandledrejection`
- render `BackendUnavailableRecovery` for classified backend failures
- keep the current generic fallback for everything else

- [ ] **Step 4: Mount the boundary in `_app.tsx`**

Modify `apps/tldw-frontend/pages/_app.tsx` so the app content is wrapped with the web error boundary after `ConfigurationGuard`.

- [ ] **Step 5: Re-run the web-boundary test**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run __tests__/components/ErrorBoundary.test.tsx --reporter=verbose
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/tldw-frontend/components/ErrorBoundary.tsx \
  apps/tldw-frontend/pages/_app.tsx \
  apps/tldw-frontend/__tests__/components/ErrorBoundary.test.tsx
git commit -m "feat: add backend-aware web error boundary"
```

## Task 4: Add Opt-In Backend Recovery To RouteErrorBoundary

**Files:**
- Modify: `apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx`
- Create: `apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx`
- Modify: WebUI route wrappers under `apps/packages/ui/src/routes/` as needed

- [ ] **Step 1: Write the failing route-boundary tests**

Create `apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx` covering:

1. opt-in backend recovery renders the shared recovery screen for a classified backend failure
2. default behavior still renders the generic route error card
3. opt-in backend recovery does not activate for a normal runtime error

- [ ] **Step 2: Run the route-boundary test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx --reporter=verbose
```

Expected: FAIL because `RouteErrorBoundary` does not yet support backend recovery.

- [ ] **Step 3: Implement opt-in backend recovery**

Modify `apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx` to:

- accept an opt-in prop such as `enableBackendRecovery`
- classify caught errors only when that prop is enabled
- render the shared recovery screen when the error is a classified backend-unreachable failure
- otherwise preserve existing generic route-boundary behavior

- [ ] **Step 4: Opt WebUI shared routes into backend recovery**

Update relevant files in `apps/packages/ui/src/routes/` to pass `enableBackendRecovery` to `RouteErrorBoundary`.

Do not change extension route wrappers under `apps/tldw-frontend/extension/routes/`.

- [ ] **Step 5: Re-run the route-boundary test**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run ../packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx --reporter=verbose
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add apps/packages/ui/src/components/Common/RouteErrorBoundary.tsx \
  apps/packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx \
  apps/packages/ui/src/routes
git commit -m "feat: add opt-in backend recovery to route boundaries"
```

## Task 5: Suppress Duplicate Fatal And Modal Recovery UI

**Files:**
- Modify: `apps/tldw-frontend/components/layout/WebLayout.tsx`
- Create: `apps/tldw-frontend/__tests__/components/layout/WebLayout.backend-unreachable.test.tsx`

- [ ] **Step 1: Write the failing WebLayout test**

Create `apps/tldw-frontend/__tests__/components/layout/WebLayout.backend-unreachable.test.tsx` covering:

1. the backend-unreachable modal remains available in non-fatal flows
2. the modal is suppressed when fatal backend recovery is active

Prefer mocking the fatal recovery state rather than reproducing the entire crash path.

- [ ] **Step 2: Run the WebLayout test to verify it fails**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run __tests__/components/layout/WebLayout.backend-unreachable.test.tsx --reporter=verbose
```

Expected: FAIL because `WebLayout` does not yet coordinate with fatal recovery state.

- [ ] **Step 3: Implement modal suppression**

Modify `apps/tldw-frontend/components/layout/WebLayout.tsx` so the existing backend-unreachable modal does not show while the fatal full-page recovery screen is active.

Keep the non-fatal modal behavior unchanged otherwise.

- [ ] **Step 4: Re-run the WebLayout test**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run __tests__/components/layout/WebLayout.backend-unreachable.test.tsx --reporter=verbose
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/components/layout/WebLayout.tsx \
  apps/tldw-frontend/__tests__/components/layout/WebLayout.backend-unreachable.test.tsx
git commit -m "fix: prevent duplicate backend recovery surfaces"
```

## Task 6: Final Verification

**Files:**
- Verify touched files from Tasks 1-5

- [ ] **Step 1: Run the focused UI test suite**

Run:

```bash
cd apps/tldw-frontend
bunx vitest run \
  ../packages/ui/src/services/__tests__/backend-unreachable.test.ts \
  ../packages/ui/src/components/Common/__tests__/BackendUnavailableRecovery.test.tsx \
  ../packages/ui/src/components/Common/__tests__/RouteErrorBoundary.backend-recovery.test.tsx \
  __tests__/components/ErrorBoundary.test.tsx \
  __tests__/components/layout/WebLayout.backend-unreachable.test.tsx \
  --reporter=verbose
```

Expected: PASS.

- [ ] **Step 2: Run Bandit on the touched scope**

Run from repo root:

```bash
source .venv/bin/activate && python -m bandit -r \
  apps/packages/ui/src/components/Common \
  apps/packages/ui/src/services \
  apps/tldw-frontend/components \
  apps/tldw-frontend/pages \
  -f json -o /tmp/bandit_web_backend_unreachable_recovery.json
```

Expected: no new findings in changed code.

- [ ] **Step 3: Review the changed UX manually**

Manual verification target:

1. stop the backend
2. open a WebUI route that depends on backend calls, such as `/chat`
3. confirm the full-page recovery screen renders instead of the generic runtime crash
4. verify `Open Settings` and `Open Health & diagnostics` route correctly
5. restore the backend and verify `Try again` or `Reload page` recovers cleanly

- [ ] **Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Common \
  apps/packages/ui/src/services \
  apps/tldw-frontend/components \
  apps/tldw-frontend/pages
git commit -m "fix: add web backend unavailable recovery flow"
```
