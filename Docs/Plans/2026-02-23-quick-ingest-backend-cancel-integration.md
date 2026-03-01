# Quick Ingest Backend-Cancel Integration Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Finish full quick-ingest backend-cancel integration for `storeRemote` flows in extension and webui runtimes using existing media-ingest jobs APIs, with robust cancellation semantics and test coverage.

**Architecture:** Extract a shared remote-ingest jobs orchestration helper (submit tracking, polling, batch cancel), then integrate both direct runtime (`quick-ingest-batch.ts`) and extension background runtime (`background.ts`) to use that shared logic. Keep quick-ingest session runtime event model unchanged; no SSE migration in this checkpoint.

**Tech Stack:** TypeScript, Vitest, Playwright, WXT extension runtime messaging, existing FastAPI media-ingest jobs API.

---

### Task 1: Add Shared Remote Ingest Jobs Orchestration Helper

**Files:**
- Create: `apps/packages/ui/src/services/tldw/ingest-jobs-orchestrator.ts`
- Create: `apps/packages/ui/src/services/__tests__/ingest-jobs-orchestrator.test.ts`

**Step 1: Write the failing test**

```ts
it("tracks batch/job ids and cancels each batch once", async () => {
  const tracker = createIngestJobsTracker()
  tracker.trackSubmit({ batch_id: "b1", jobs: [{ id: 11 }, { id: 12 }] })
  tracker.trackSubmit({ batch_id: "b1", jobs: [{ id: 13 }] })
  tracker.trackSubmit({ batch_id: "b2", jobs: [{ id: 21 }] })

  const calls: string[] = []
  await tracker.cancelAll(async (batchId) => { calls.push(batchId) })
  expect(calls.sort()).toEqual(["b1", "b2"])
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/services/__tests__/ingest-jobs-orchestrator.test.ts
```
Expected: FAIL with missing module/functions.

**Step 3: Write minimal implementation**

```ts
export type IngestSubmitResponse = { batch_id?: string; jobs?: Array<{ id?: number }> }

export const createIngestJobsTracker = () => {
  const batchIds = new Set<string>()
  const jobIds = new Set<number>()
  return {
    trackSubmit(data: IngestSubmitResponse) { /* parse + store */ },
    getJobIds() { return Array.from(jobIds) },
    getBatchIds() { return Array.from(batchIds) },
    async cancelAll(cancelBatch: (batchId: string) => Promise<void>) { /* once per batch */ }
  }
}
```

**Step 4: Run test to verify it passes**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/services/__tests__/ingest-jobs-orchestrator.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/ingest-jobs-orchestrator.ts apps/packages/ui/src/services/__tests__/ingest-jobs-orchestrator.test.ts
git commit -m "feat(ui): add shared ingest jobs orchestration helper"
```

### Task 2: Integrate Direct Runtime (`quick-ingest-batch.ts`) with Jobs Helper

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/quick-ingest-batch.ts`
- Modify: `apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`

**Step 1: Write the failing test**

```ts
it("uses /media/ingest/jobs and batch cancel for direct session cancel", async () => {
  mocks.bgUpload.mockResolvedValueOnce({
    batch_id: "batch-direct-1",
    jobs: [{ id: 101, status: "queued" }]
  })
  mocks.bgRequest
    .mockResolvedValueOnce({ ok: true, data: { status: "processing" } })
    .mockResolvedValueOnce({ ok: true, data: { status: "cancelled" } })

  const run = submitQuickIngestBatch({ /* storeRemote true */ __quickIngestSessionId: "s1" })
  await cancelQuickIngestSession({ sessionId: "s1", reason: "user_cancelled" })
  await run

  expect(mocks.bgRequest).toHaveBeenCalledWith(
    expect.objectContaining({
      path: expect.stringContaining("/api/v1/media/ingest/jobs/cancel?batch_id=batch-direct-1")
    })
  )
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/services/__tests__/quick-ingest-batch.test.ts
```
Expected: FAIL on old endpoint or missing batch cancel assertion.

**Step 3: Write minimal implementation**

```ts
// quick-ingest-batch.ts
// - replace /api/v1/media/add storeRemote direct path with /api/v1/media/ingest/jobs
// - register batch_id per __quickIngestSessionId
// - poll /api/v1/media/ingest/jobs/{job_id} to terminal
// - on cancelQuickIngestSession, call /api/v1/media/ingest/jobs/cancel for tracked batch_ids
```

**Step 4: Run tests to verify they pass**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/services/__tests__/quick-ingest-batch.test.ts src/entries/shared/__tests__/quick-ingest-session-runtime.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/quick-ingest-batch.ts apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts
git commit -m "feat(ui): wire direct quick-ingest storeRemote through media ingest jobs cancel path"
```

### Task 3: Integrate Extension Background Runtime with Shared Jobs Helper

**Files:**
- Modify: `apps/packages/ui/src/entries/background.ts`
- (If needed) Modify: `apps/packages/ui/src/entries/shared/quick-ingest-session-runtime.ts`

**Step 1: Write the failing test (helper-level behavior if no background harness)**

```ts
it("maps cancelled terminal jobs to cancelled results without overriding session cancel", async () => {
  // Add to orchestrator test suite if background direct unit harness is unavailable
  // Assert status mapping and terminal lock behavior.
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/services/__tests__/ingest-jobs-orchestrator.test.ts
```
Expected: FAIL on missing mapping/terminal guard.

**Step 3: Write minimal implementation**

```ts
// background.ts
// - use shared tracker for queued remote jobs
// - collect batch_id from each submit response
// - use POST /media/ingest/jobs/cancel for cancel by batch
// - preserve progress emission and session-scoped cancellation semantics
```

**Step 4: Run targeted test suite**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/entries/shared/__tests__/quick-ingest-session-runtime.test.ts src/services/__tests__/ingest-jobs-orchestrator.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/entries/background.ts apps/packages/ui/src/entries/shared/quick-ingest-session-runtime.ts apps/packages/ui/src/services/tldw/ingest-jobs-orchestrator.ts apps/packages/ui/src/services/__tests__/ingest-jobs-orchestrator.test.ts
git commit -m "feat(ui): unify background quick-ingest remote cancel and polling via ingest jobs helper"
```

### Task 4: Lock Cancelled Terminal UX and Session Event Guards

**Files:**
- Modify: `apps/packages/ui/src/components/Common/QuickIngestModal.tsx`
- Modify: `apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`
- Modify: `apps/packages/ui/src/store/quick-ingest.ts` (only if status/outcome normalization requires)

**Step 1: Write the failing test**

```ts
it("does not dispatch cancel when user picks Keep running", async () => {
  // click cancel -> confirm dialog -> keep running
  // assert cancelQuickIngestSession not called
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx
```
Expected: FAIL before guard/copy adjustments.

**Step 3: Write minimal implementation**

```tsx
// QuickIngestModal.tsx
// - ensure confirmation gating before cancel dispatch
// - keep terminal cancelled summary authoritative against late completion events
```

**Step 4: Run tests**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx src/store/__tests__/quick-ingest.test.ts
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/QuickIngestModal.tsx apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx apps/packages/ui/src/store/quick-ingest.ts apps/packages/ui/src/store/__tests__/quick-ingest.test.ts
git commit -m "test(ui): enforce confirmed cancel behavior and cancelled terminal lock"
```

### Task 5: Update Web E2E Cancel Flow to Jobs Endpoint Contract

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts`

**Step 1: Write/adjust failing e2e assertions**

```ts
// intercept /api/v1/media/ingest/jobs submit (not /media/add)
// ensure cancel flow still shows confirmation and terminal cancelled card
```

**Step 2: Run e2e to verify failure first**

Run:
```bash
cd apps/tldw-frontend
TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/workflows/media-ingest.spec.ts --grep "cancel quick ingest mid-process"
```
Expected: FAIL if interception still points at `/media/add`.

**Step 3: Implement minimal e2e updates**

```ts
// media-ingest.spec.ts
// - replace /media/add mock route with /media/ingest/jobs + job status mock where needed
```

**Step 4: Re-run e2e**

Run:
```bash
cd apps/tldw-frontend
TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/workflows/media-ingest.spec.ts --grep "cancel quick ingest mid-process"
```
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts
git commit -m "test(e2e): align quick-ingest cancel flow with media ingest jobs endpoints"
```

### Task 6: Full Verification Pass and Backend Contract Regression Checks

**Files:**
- No code changes expected unless failures found.

**Step 1: Run UI unit/integration suite for touched scope**

Run:
```bash
cd apps/packages/ui
bunx vitest run src/services/__tests__/ingest-jobs-orchestrator.test.ts src/services/__tests__/quick-ingest-batch.test.ts src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx src/entries/shared/__tests__/quick-ingest-session-runtime.test.ts
```
Expected: PASS.

**Step 2: Run backend ingest contract tests (no API drift)**

Run:
```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_batch_cancel.py -v
python -m pytest tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_events_stream.py -v
```
Expected: PASS.

**Step 3: Run targeted e2e cancel scenario**

Run:
```bash
cd apps/tldw-frontend
TLDW_E2E_SERVER_URL=127.0.0.1:8000 TLDW_E2E_API_KEY=THIS-IS-A-SECURE-KEY-123-FAKE-KEY bunx playwright test e2e/workflows/media-ingest.spec.ts --grep "cancel quick ingest mid-process"
```
Expected: PASS.

**Step 4: Final sanity checks**

Run:
```bash
git status --short
git log --oneline -n 10
```
Expected: only intended files changed and clean commit sequence.

**Step 5: Commit final polish (if needed)**

```bash
git add -A
git commit -m "chore(ui): finalize quick-ingest backend-cancel integration verification"
```

