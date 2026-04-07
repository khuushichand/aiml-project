# Quick Ingest Resume And E2E Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make WebUI quick ingest resumable within the current tab, expose the full option surface inside the wizard without forcing a preset, and add real end-to-end coverage for `.mkv`, URL ingest, queue-limit fallback, dismiss/reopen, and refresh restore.

**Architecture:** Add a dedicated tab-scoped quick-ingest session store that persists wizard state, visibility, results, and backend tracking metadata into `sessionStorage`. Keep the quick-ingest host mounted while a session exists, refactor the wizard configure step to reuse the richer shared options panel inline, and add a WebUI-only reattach path for direct backend ingest jobs so refresh can honestly restore or degrade active processing sessions.

**Tech Stack:** React, Zustand, sessionStorage, Ant Design modal primitives, Vitest, React Testing Library, Playwright, shared UI package, direct WebUI ingest APIs

---

## File Structure

- `apps/packages/ui/src/store/quick-ingest-session.ts`
  Purpose: own the tab-scoped quick-ingest session model, persistence, lifecycle helpers, trigger badge summary, and explicit clear/new-session actions.
- `apps/packages/ui/src/store/__tests__/quick-ingest-session.test.ts`
  Purpose: lock persistence, visibility toggling, completed-session retention, and derived trigger-state semantics.
- `apps/packages/ui/src/store/quick-ingest.tsx`
  Purpose: keep legacy badge/last-run summary behavior aligned with the new canonical session store instead of acting as a disconnected source of truth.
- `apps/packages/ui/src/components/Layouts/QuickIngestButton.tsx`
  Purpose: make the normal `Quick Ingest` trigger reopen the existing session, keep the modal host mounted while a session exists, and constrain the secondary CTA to queued-draft sessions only.
- `apps/packages/ui/src/components/Layouts/__tests__/QuickIngestButton.resume.test.tsx`
  Purpose: verify reopen, badge/count text, and secondary CTA visibility semantics from the header entry point.
- `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`
  Purpose: extract the wizard configure step into a focused component that combines presets, inline common/type-specific/advanced options, and wizard navigation.
- `apps/packages/ui/src/components/Common/QuickIngest/IngestOptionsPanel.tsx`
  Purpose: support wizard-mode rendering of the richer options surface without forcing the old tabbed modal footer actions.
- `apps/packages/ui/src/components/Common/QuickIngest/PresetSelector.tsx`
  Purpose: keep presets as optional shortcuts with persistent helper copy and explicit reset/custom-state messaging.
- `apps/packages/ui/src/components/Common/QuickIngest/types.ts`
  Purpose: extend wizard/session types for resumable lifecycle, interrupted refresh state, and persisted tracking metadata.
- `apps/packages/ui/src/components/Common/QuickIngest/IngestWizardContext.tsx`
  Purpose: accept hydrated initial state, write wizard changes back to the session store, and preserve options/results across hide/show.
- `apps/packages/ui/src/components/Common/QuickIngest/FloatingProgressWidget.tsx`
  Purpose: reopen the canonical session instead of relying on transient provider-only minimized state.
- `apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx`
  Purpose: consume the persisted session store, hide instead of destroy, mount the extracted configure step, resume processing state on reopen, and coordinate explicit clear/new-session actions.
- `apps/packages/ui/src/services/tldw/quick-ingest-session-reattach.ts`
  Purpose: reattach persisted WebUI direct-ingest job tracking after refresh and translate backend job states into wizard/session snapshots.
- `apps/packages/ui/src/services/tldw/quick-ingest-batch.ts`
  Purpose: emit/persist direct batch ids and job ids before polling, preserve the recognized-429-only fallback behavior, and expose enough metadata for refresh reattachment.
- `apps/packages/ui/src/services/__tests__/quick-ingest-session-reattach.test.ts`
  Purpose: verify successful reattachment, honest interrupted fallback, and non-WebUI/runtime-guard behavior.
- `apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`
  Purpose: lock tracking-metadata emission and queue-limit fallback constraints.
- `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.session.test.tsx`
  Purpose: verify dismiss/reopen, completed-session retention, refresh hydration, and interruption handling.
- `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx`
  Purpose: verify the extracted configure step exposes presets plus full inline options without requiring a preset selection.
- `apps/packages/ui/src/components/Common/QuickIngest/__tests__/PresetSelector.test.tsx`
  Purpose: lock the “presets are starting points” behavior and reset/custom copy.
- `apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`
  Purpose: keep the older modal and shared scroll-body behavior from regressing while the wizard becomes canonical.
- `apps/tldw-frontend/public/e2e/quick-ingest-source.html`
  Purpose: provide a deterministic local URL target for real ingest completion without relying on third-party sites.
- `apps/tldw-frontend/e2e/fixtures/media/quick-ingest-sample.mkv`
  Purpose: provide a deterministic real `.mkv` upload fixture for WebUI browser tests.
- `apps/tldw-frontend/e2e/utils/journey-helpers.ts`
  Purpose: add helper flows for quick-ingest resume/reopen/refresh assertions that target the actual wizard modal.
- `apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts`
  Purpose: add full WebUI browser coverage for `.mkv`, URL completion, queue-limit fallback, constrained viewport options, dismiss/reopen, refresh restore, and secondary CTA semantics.

## Task 1: Add a persisted quick-ingest session store

**Files:**
- Create: `apps/packages/ui/src/store/quick-ingest-session.ts`
- Create: `apps/packages/ui/src/store/__tests__/quick-ingest-session.test.ts`
- Modify: `apps/packages/ui/src/store/quick-ingest.tsx`

- [ ] **Step 1: Write the failing session-store tests**

```ts
import { beforeEach, describe, expect, it } from "vitest"
import {
  createQuickIngestSessionStore,
  createEmptyQuickIngestSession
} from "@/store/quick-ingest-session"

describe("quick ingest session store", () => {
  beforeEach(() => {
    window.sessionStorage.clear()
  })

  it("persists a hidden completed session and rehydrates it in the same tab", () => {
    const store = createQuickIngestSessionStore()
    store.getState().upsertSession({
      ...createEmptyQuickIngestSession(),
      lifecycle: "completed",
      visibility: "hidden",
      results: [{ id: "result-1", status: "ok", type: "html" }]
    })

    const rehydrated = createQuickIngestSessionStore()
    expect(rehydrated.getState().session?.lifecycle).toBe("completed")
    expect(rehydrated.getState().session?.visibility).toBe("hidden")
    expect(rehydrated.getState().triggerSummary.label).toMatch(/completed/i)
  })

  it("requires explicit clear before removing a completed session", () => {
    const store = createQuickIngestSessionStore()
    store.getState().createDraftSession()
    store.getState().hideSession()
    expect(store.getState().session).not.toBeNull()
    store.getState().clearSession()
    expect(store.getState().session).toBeNull()
  })
})
```

- [ ] **Step 2: Run the store tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/store/__tests__/quick-ingest-session.test.ts --reporter=verbose
```

Expected: FAIL with a missing module/export error for `quick-ingest-session.ts`.

- [ ] **Step 3: Implement the persisted session store**

```ts
type QuickIngestSessionLifecycle =
  | "draft"
  | "processing"
  | "completed"
  | "partial_failure"
  | "cancelled"
  | "interrupted"

type QuickIngestSessionRecord = {
  id: string
  visibility: "visible" | "hidden"
  lifecycle: QuickIngestSessionLifecycle
  currentStep: 1 | 2 | 3 | 4 | 5
  queueItems: WizardQueueItem[]
  results: WizardResultItem[]
  tracking?: {
    mode: "webui-direct" | "extension-runtime" | "unknown"
    sessionId?: string
    batchId?: string
    jobIds?: number[]
    startedAt?: number
  }
}
```

Implementation notes:
- Persist only serializable state to `sessionStorage`.
- Keep raw `File` instances out of the persisted record; store queue stubs and reattach metadata only.
- Add focused store actions:
  - `createDraftSession()`
  - `upsertSession(partial)`
  - `showSession()`
  - `hideSession()`
  - `markProcessingTracking(tracking)`
  - `markInterrupted(reason)`
  - `clearSession()`
  - `replaceWithNewDraft()`
- Make `quick-ingest.tsx` derive `queuedCount` and header-failure hints from the canonical session state instead of staying disconnected.

- [ ] **Step 4: Re-run the store tests and the existing quick-ingest store tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/store/__tests__/quick-ingest-session.test.ts \
  src/store/__tests__/quick-ingest.test.ts \
  --reporter=verbose
```

Expected: PASS for the new persistence cases and the existing last-run-summary cases.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/store/quick-ingest-session.ts apps/packages/ui/src/store/__tests__/quick-ingest-session.test.ts apps/packages/ui/src/store/quick-ingest.tsx
git commit -m "feat: add persisted quick ingest session store"
```

## Task 2: Keep the quick-ingest host mounted and align trigger semantics

**Files:**
- Modify: `apps/packages/ui/src/components/Layouts/QuickIngestButton.tsx`
- Create: `apps/packages/ui/src/components/Layouts/__tests__/QuickIngestButton.resume.test.tsx`

- [ ] **Step 1: Write the failing trigger/host tests**

```tsx
it("reopens the existing hidden session instead of creating a new one", async () => {
  sessionStore.getState().upsertSession({
    ...createEmptyQuickIngestSession(),
    lifecycle: "processing",
    visibility: "hidden"
  })

  render(<QuickIngestButton />)
  await user.click(screen.getByTestId("open-quick-ingest"))

  expect(sessionStore.getState().session?.visibility).toBe("visible")
  expect(screen.queryByTestId("process-queued-ingest-header")).not.toBeInTheDocument()
})

it("shows the secondary CTA only for draft sessions with queued items", () => {
  sessionStore.getState().upsertSession({
    ...createEmptyQuickIngestSession(),
    lifecycle: "draft",
    queueItems: [buildQueuedUrlItem("https://example.com")]
  })

  render(<QuickIngestButton />)
  expect(screen.getByTestId("process-queued-ingest-header")).toBeVisible()
})
```

- [ ] **Step 2: Run the trigger tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Layouts/__tests__/QuickIngestButton.resume.test.tsx --reporter=verbose
```

Expected: FAIL because `QuickIngestButton` still keys rendering off local `quickIngestOpen` state and the secondary CTA appears whenever `queuedCount > 0`.

- [ ] **Step 3: Refactor the trigger and host**

```tsx
const hasMountedSession = Boolean(session)
const shouldRenderHost = quickIngestOpen || hasMountedSession

const openQuickIngest = () => {
  if (session) {
    quickIngestSessionStore.getState().showSession()
  } else {
    quickIngestSessionStore.getState().createDraftSession()
  }
  setQuickIngestOpen(true)
}

const closeQuickIngest = () => {
  quickIngestSessionStore.getState().hideSession()
  setQuickIngestOpen(false)
}
```

Implementation notes:
- Do not let modal visibility control whether the provider/host exists.
- Keep the `QuickIngestModalHost` mounted while `session !== null`.
- Remove or rename the secondary header action to `Start queued ingest` and show it only for `draft + queued items`.
- Keep focus restoration behavior when the modal is merely hidden.

- [ ] **Step 4: Re-run the new trigger tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run src/components/Layouts/__tests__/QuickIngestButton.resume.test.tsx --reporter=verbose
```

Expected: PASS for reopen, badge/label, and queued-draft CTA visibility.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Layouts/QuickIngestButton.tsx apps/packages/ui/src/components/Layouts/__tests__/QuickIngestButton.resume.test.tsx
git commit -m "refactor: keep quick ingest host mounted across hide and reopen"
```

## Task 3: Replace the wizard configure placeholder with the full inline options surface

**Files:**
- Create: `apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/IngestOptionsPanel.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/PresetSelector.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/PresetSelector.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`

- [ ] **Step 1: Write the failing configure-step tests**

```tsx
it("lets the user continue without selecting a preset", async () => {
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  await queueOneVideoItem()
  await user.click(screen.getByRole("button", { name: /configure 1 items/i }))

  expect(
    screen.getByText(/presets are starting points\. you can change any settings below/i)
  ).toBeVisible()

  await user.click(screen.getByRole("button", { name: /^next$/i }))
  expect(screen.getByText(/ready to process/i)).toBeVisible()
})

it("renders common, type-specific, and advanced options inside the wizard", async () => {
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  await queueOneDocumentItem()
  await openConfigureStep()

  expect(screen.getByText(/content-specific options/i)).toBeVisible()
  expect(screen.getByText(/storage/i)).toBeVisible()
  expect(screen.getByText(/advanced options/i)).toBeVisible()
  expect(screen.queryByText(/full ingest modal/i)).not.toBeInTheDocument()
})
```

- [ ] **Step 2: Run the wizard integration tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx \
  src/components/Common/QuickIngest/__tests__/PresetSelector.test.tsx \
  src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the wizard still renders the advanced-options placeholder and the actual wizard configure step is still embedded in `QuickIngestWizardModal.tsx`.

- [ ] **Step 3: Extract and wire the real wizard configure step**

```tsx
export const WizardConfigureStep = () => {
  return (
    <div className="space-y-5 py-3">
      <PresetSelector ... />
      <IngestOptionsPanel
        mode="wizard"
        showPrimaryAction={false}
        showProgressSummary={false}
        ...
      />
      <WizardStepNavigation onBack={goBack} onNext={goNext} />
    </div>
  )
}
```

Implementation notes:
- Reuse `IngestOptionsPanel` instead of rebuilding the richer controls inside the wizard file.
- Add a `wizard` or `embedded` rendering mode to `IngestOptionsPanel` so it can hide the old modal footer actions while keeping common/type-specific/advanced controls.
- Keep the preset helper copy always visible.
- Apply the scroll constraint to the actual wizard modal body, not an inner placeholder-only panel.
- Preserve the existing `.mkv` accept-list fix while ensuring the configure step recognizes video items with blank browser MIME types.

- [ ] **Step 4: Re-run the configure-step tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx \
  src/components/Common/QuickIngest/__tests__/PresetSelector.test.tsx \
  src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx \
  --reporter=verbose
```

Expected: PASS with no `full ingest modal` placeholder left in the wizard path.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/QuickIngest/WizardConfigureStep.tsx apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx apps/packages/ui/src/components/Common/QuickIngest/IngestOptionsPanel.tsx apps/packages/ui/src/components/Common/QuickIngest/PresetSelector.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/PresetSelector.test.tsx apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx
git commit -m "feat: expose full quick ingest options inline in wizard"
```

## Task 4: Persist backend tracking metadata and add refresh reattach

**Files:**
- Create: `apps/packages/ui/src/services/tldw/quick-ingest-session-reattach.ts`
- Create: `apps/packages/ui/src/services/__tests__/quick-ingest-session-reattach.test.ts`
- Modify: `apps/packages/ui/src/services/tldw/quick-ingest-batch.ts`
- Modify: `apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/types.ts`

- [ ] **Step 1: Write the failing service tests**

```ts
it("captures direct batch tracking metadata before polling completes", async () => {
  const onTrackingMetadata = vi.fn()

  await submitQuickIngestBatch({
    entries: [{ id: "entry-1", url: "https://example.com", type: "html" }],
    files: [],
    storeRemote: true,
    processOnly: false,
    __quickIngestSessionId: "qi-direct-1",
    onTrackingMetadata
  })

  expect(onTrackingMetadata).toHaveBeenCalledWith({
    mode: "webui-direct",
    sessionId: "qi-direct-1",
    batchId: "batch-1",
    jobIds: [1234]
  })
})

it("marks a persisted processing session as interrupted when reattachment cannot prove live progress", async () => {
  const result = await reattachQuickIngestSession({
    mode: "webui-direct",
    batchId: "missing",
    jobIds: [77],
    startedAt: Date.now()
  })

  expect(result.lifecycle).toBe("interrupted")
  expect(result.errorMessage).toMatch(/could not reconnect/i)
})
```

- [ ] **Step 2: Run the service tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/services/__tests__/quick-ingest-batch.test.ts \
  src/services/__tests__/quick-ingest-session-reattach.test.ts \
  --reporter=verbose
```

Expected: FAIL because no reattach helper exists and `submitQuickIngestBatch` does not yet emit persisted tracking metadata.

- [ ] **Step 3: Implement tracking and reattach helpers**

```ts
export type PersistedQuickIngestTracking = {
  mode: "webui-direct" | "extension-runtime" | "unknown"
  sessionId?: string
  batchId?: string
  jobIds: number[]
  startedAt: number
}

export async function reattachQuickIngestSession(
  tracking: PersistedQuickIngestTracking
): Promise<ReattachedQuickIngestSnapshot> {
  if (tracking.mode !== "webui-direct" || tracking.jobIds.length === 0) {
    return interruptedSnapshot("Quick ingest could not reconnect to live job status.")
  }
  return await pollTrackedJobsIntoSnapshot(tracking.jobIds)
}
```

Implementation notes:
- Persist only WebUI direct-mode tracking in phase 1.
- Keep extension-runtime sessions safe by returning `mode: "extension-runtime"` without pretending they are refresh-reattachable.
- Emit tracking metadata immediately after `/api/v1/media/ingest/jobs` returns `batch_id` and `jobIds`, before the long poll begins.
- Keep the queue-limit fallback narrow: only recognized concurrent-job-limit `429` responses should fall back to `/api/v1/media/add`.

- [ ] **Step 4: Re-run the service tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/services/__tests__/quick-ingest-batch.test.ts \
  src/services/__tests__/quick-ingest-session-reattach.test.ts \
  --reporter=verbose
```

Expected: PASS for tracking emission, honest interrupted degradation, and existing fallback coverage.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/quick-ingest-session-reattach.ts apps/packages/ui/src/services/__tests__/quick-ingest-session-reattach.test.ts apps/packages/ui/src/services/tldw/quick-ingest-batch.ts apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts apps/packages/ui/src/components/Common/QuickIngest/types.ts
git commit -m "feat: add quick ingest tracking metadata and refresh reattach"
```

## Task 5: Wire the persisted session store into the wizard lifecycle

**Files:**
- Modify: `apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/IngestWizardContext.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/FloatingProgressWidget.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.session.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/__tests__/IngestWizardContext.test.tsx`

- [ ] **Step 1: Write the failing wizard-lifecycle tests**

```tsx
it("hides the modal during processing and restores the same session on reopen", async () => {
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  await queueAndStartProcessing()
  await user.click(screen.getByRole("button", { name: /minimize to background|close/i }))

  expect(sessionStore.getState().session?.visibility).toBe("hidden")

  sessionStore.getState().showSession()
  rerender(<QuickIngestWizardModal open onClose={vi.fn()} />)
  expect(screen.getByTestId("wizard-processing")).toBeVisible()
})

it("restores a URL-only completed session from sessionStorage after refresh", async () => {
  seedSessionStorageWithCompletedUrlSession()
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  expect(await screen.findByTestId("wizard-results")).toHaveTextContent("complete")
})

it("shows a reattach-required message for file stubs restored without live File objects", async () => {
  seedSessionStorageWithQueuedFileStubOnly()
  render(<QuickIngestWizardModal open onClose={vi.fn()} />)
  expect(screen.getByText(/reattach/i)).toBeVisible()
})
```

- [ ] **Step 2: Run the lifecycle tests to verify they fail**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.session.test.tsx \
  src/components/Common/QuickIngest/__tests__/IngestWizardContext.test.tsx \
  --reporter=verbose
```

Expected: FAIL because the wizard provider still resets on unmount and does not hydrate from persisted session state.

- [ ] **Step 3: Hydrate the wizard from the session store and reattach on mount**

```tsx
const persistedSession = useQuickIngestSessionStore((s) => s.session)

<IngestWizardProvider initialState={persistedSession?.wizardState}>
  <QuickIngestWizardContent
    session={persistedSession}
    onHide={() => quickIngestSessionStore.getState().hideSession()}
  />
</IngestWizardProvider>
```

Implementation notes:
- Add `initialState` support to `IngestWizardContext` so it can rehydrate current step, queue items, options, progress, and results.
- Write wizard reducer changes back into the persisted session store on every meaningful transition.
- On mount, if the persisted session is `processing` with WebUI direct tracking metadata, call the reattach helper and update state from the result.
- If reattach fails, land in `interrupted` with explicit retry/dismiss copy instead of fake live progress.
- Keep completed sessions visible until `Start a new ingest` or `Clear session` is chosen.

- [ ] **Step 4: Re-run the lifecycle tests**

Run:

```bash
cd apps/packages/ui && bunx vitest run \
  src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.session.test.tsx \
  src/components/Common/QuickIngest/__tests__/IngestWizardContext.test.tsx \
  --reporter=verbose
```

Expected: PASS for hide/show, completed restore, URL refresh restore, and file-reattach messaging.

- [ ] **Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/QuickIngestWizardModal.tsx apps/packages/ui/src/components/Common/QuickIngest/IngestWizardContext.tsx apps/packages/ui/src/components/Common/QuickIngest/FloatingProgressWidget.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.session.test.tsx apps/packages/ui/src/components/Common/QuickIngest/__tests__/IngestWizardContext.test.tsx
git commit -m "feat: make quick ingest wizard resumable across hide and refresh"
```

## Task 6: Add real WebUI E2E fixtures and end-to-end coverage

**Files:**
- Create: `apps/tldw-frontend/public/e2e/quick-ingest-source.html`
- Create: `apps/tldw-frontend/e2e/fixtures/media/quick-ingest-sample.mkv`
- Modify: `apps/tldw-frontend/e2e/utils/journey-helpers.ts`
- Modify: `apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts`

- [ ] **Step 1: Add the failing browser specs**

```ts
test("quick ingest accepts a real .mkv upload through completion and reopen", async ({ authedPage }) => {
  const mediaId = await ingestAndWaitForReady(authedPage, {
    file: "e2e/fixtures/media/quick-ingest-sample.mkv"
  })

  await dismissQuickIngest(authedPage)
  await reopenQuickIngest(authedPage)
  await expect(authedPage.getByRole("region", { name: /completed items/i })).toContainText(mediaId)
})

test("quick ingest restores a URL session after refresh", async ({ authedPage, baseURL }) => {
  const url = new URL("/e2e/quick-ingest-source.html", baseURL).toString()
  await queueUrlAndStartProcessing(authedPage, url)
  await authedPage.reload()
  await expect(authedPage.getByRole("dialog", { name: /quick ingest/i })).toContainText(/processing|completed/i)
})
```

Required E2E cases in this task:
- `.mkv` upload through visible completion, dismiss, and reopen
- URL ingest against the local static HTML fixture through visible completion, dismiss, and reopen
- recognized-`429` queue-limit fallback to `/api/v1/media/add`
- constrained-viewport configure-step options reachability
- dismiss during processing, reopen via the standard trigger, and verify active session context
- refresh restore for queued, processing, and completed URL sessions
- file refresh edge case showing reattach-required UI
- secondary CTA visible only for queued-draft sessions

- [ ] **Step 2: Run the new browser coverage to verify it fails**

Run:

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-ingest.spec.ts --reporter=line
```

Expected: FAIL because the current WebUI wizard does not yet preserve sessions across dismiss/refresh and still lacks the full inline options surface.

- [ ] **Step 3: Add deterministic fixtures and helper flows**

```html
<!-- apps/tldw-frontend/public/e2e/quick-ingest-source.html -->
<!doctype html>
<html lang="en">
  <head><meta charset="utf-8" /><title>Quick ingest local fixture</title></head>
  <body>
    <main>
      <h1>Quick ingest stable source</h1>
      <p>This page exists only for deterministic WebUI ingest tests.</p>
    </main>
  </body>
</html>
```

Implementation notes:
- Keep the HTML fixture simple and deterministic so backend scraping/URL ingest is stable.
- Commit a very small valid `.mkv` fixture rather than generating it on the fly in Playwright.
- Extend `journey-helpers.ts` with explicit helper methods for:
  - `dismissQuickIngest`
  - `reopenQuickIngest`
  - `queueUrlAndStartProcessing`
  - `assertQuickIngestCompletedResults`
  - constrained viewport option scrolling
- Keep queue-limit fallback validation distinct from full completion tests so the fallback case can inspect network behavior precisely.

- [ ] **Step 4: Re-run the browser coverage**

Run:

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-ingest.spec.ts --reporter=line
```

Expected: PASS for the real `.mkv`, local URL, fallback, resume, refresh, and CTA cases.

- [ ] **Step 5: Commit**

```bash
git add apps/tldw-frontend/public/e2e/quick-ingest-source.html apps/tldw-frontend/e2e/fixtures/media/quick-ingest-sample.mkv apps/tldw-frontend/e2e/utils/journey-helpers.ts apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts
git commit -m "test: add webui quick ingest resume end-to-end coverage"
```

## Final Verification

- [ ] **Step 1: Run the focused shared UI suite**

```bash
cd apps/packages/ui && bunx vitest run \
  src/store/__tests__/quick-ingest-session.test.ts \
  src/store/__tests__/quick-ingest.test.ts \
  src/components/Layouts/__tests__/QuickIngestButton.resume.test.tsx \
  src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.integration.test.tsx \
  src/components/Common/QuickIngest/__tests__/QuickIngestWizardModal.session.test.tsx \
  src/components/Common/QuickIngest/__tests__/IngestWizardContext.test.tsx \
  src/components/Common/QuickIngest/__tests__/PresetSelector.test.tsx \
  src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx \
  src/services/__tests__/quick-ingest-batch.test.ts \
  src/services/__tests__/quick-ingest-session-reattach.test.ts \
  --maxWorkers=1 --no-file-parallelism
```

Expected: PASS for all quick-ingest-focused unit and integration coverage.

- [ ] **Step 2: Run the WebUI Playwright workflow coverage**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-ingest.spec.ts --reporter=line
```

Expected: PASS for the real WebUI end-to-end scenarios.

- [ ] **Step 3: Run Bandit on the touched scope**

```bash
source .venv/bin/activate && python -m bandit -r apps/packages/ui apps/tldw-frontend -f json -o /tmp/bandit_quick_ingest_resume_and_e2e.json
```

Expected: `0` new findings in the touched JS/TS-heavy scope; if Bandit reports no analyzable Python LOC here, record that fact explicitly instead of claiming a security scan was skipped.

- [ ] **Step 4: Review the diff before handoff**

```bash
git status --short
git diff --stat
git diff -- Docs/superpowers/plans/2026-03-24-quick-ingest-resume-and-e2e-implementation-plan.md
```

Expected: only the planned quick-ingest files and fixtures are touched; no unrelated reversions.
