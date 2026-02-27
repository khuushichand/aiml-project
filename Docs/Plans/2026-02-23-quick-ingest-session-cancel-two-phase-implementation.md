# Quick Ingest Session-Cancel Two-Phase Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Deliver a session-native quick-ingest experience (extension + WebUI modals) with confirmed mid-process cancel in Phase 1 (no backend changes), then harden backend ergonomics/performance in Phase 2.

**Architecture:** Phase 1 moves modal flows from blocking batch completion to ack + async session events keyed by `sessionId`, using existing `/api/v1/media/ingest/jobs` APIs for store-remote and client-side abort for process-only. Phase 2 adds user-scoped media ingest event streaming, first-class batch/session cancel endpoint(s), and indexed batch lookup improvements so clients can shift from polling-heavy behavior.

**Tech Stack:** TypeScript (React/Zustand/WXT background), Playwright E2E, FastAPI/Python, JobManager + media ingest jobs worker, pytest.

---

## Execution Rules

1. Use @test-driven-development for every behavior change.
2. Use @verification-before-completion before closing each phase.
3. Keep commits small and phase-labeled.
4. Phase 1 must not modify backend API contracts.

---

### Task 1: Define Session Message Contracts (Phase 1)

**Files:**
- Modify: `apps/packages/ui/src/services/tldw/quick-ingest-batch.ts`
- Modify: `apps/packages/ui/src/entries/background.ts`
- Test: `apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`

**Step 1: Write the failing tests**

Add tests that assert:
- `submitQuickIngestBatch` no longer waits for full results payload.
- `start` request returns ack payload with `sessionId`.
- cancel message type `tldw:quick-ingest/cancel` is supported by service wrapper.

```ts
it("returns start ack with session id", async () => {
  // mock runtime sendMessage => { ok: true, sessionId: "qi-123" }
  // expect submitQuickIngestBatch(...) to resolve ack contract only
})
```

**Step 2: Run tests to verify failure**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`
Expected: FAIL because current code expects blocking `{ ok, results }`.

**Step 3: Write minimal implementation**

Implement new contracts:
- Start message: `tldw:quick-ingest/start`.
- Cancel message helper: `tldw:quick-ingest/cancel`.
- Keep compatibility wrappers only where needed by existing callers.

```ts
type QuickIngestStartAck = { ok: true; sessionId: string }
```

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/tldw/quick-ingest-batch.ts apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts apps/packages/ui/src/entries/background.ts
git commit -m "feat(quick-ingest): add session start/cancel message contracts"
```

---

### Task 2: Implement Background Session Runtime for Quick Ingest (Phase 1)

**Files:**
- Modify: `apps/packages/ui/src/entries/background.ts`
- Test: `apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts` (create if absent)

**Step 1: Write the failing tests**

Add tests for:
- `tldw:quick-ingest/start` returns immediate `{ ok, sessionId }`.
- progress/completed/failed/cancelled events include `sessionId`.
- store-remote path tracks job ids and polls existing media ingest job status.

```ts
it("acks immediately and emits session-keyed progress", async () => {
  // start -> ack
  // simulate polling response transitions
  // assert events include sessionId
})
```

**Step 2: Run tests to verify failure**

Run: `bunx vitest run apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts`
Expected: FAIL because message handlers/events are still batch-result oriented.

**Step 3: Write minimal implementation**

In background:
- Add quick-ingest session registry keyed by `sessionId`.
- Implement handlers:
  - `tldw:quick-ingest/start`
  - `tldw:quick-ingest/cancel`
- Emit:
  - `tldw:quick-ingest/progress`
  - `tldw:quick-ingest/completed`
  - `tldw:quick-ingest/failed`
  - `tldw:quick-ingest/cancelled`
- For store-remote: use existing `/api/v1/media/ingest/jobs` submit/poll/delete only.

```ts
const sessionId = `qi-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`
```

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/entries/background.ts apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts
git commit -m "feat(quick-ingest): add background session runtime with async events"
```

---

### Task 3: Add Process-Only Client Abort Semantics (Phase 1)

**Files:**
- Modify: `apps/packages/ui/src/entries/background.ts`
- Modify: `apps/packages/ui/src/services/background-proxy.ts` (if signal plumbing needed)
- Test: `apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts`

**Step 1: Write the failing tests**

Add tests for process-only mode:
- cancel aborts active request/upload controllers.
- cancelled terminal event is emitted.
- item outcomes resolve as cancelled, not failed.

```ts
it("aborts process-only in-flight requests on cancel", async () => {
  // start processOnly session
  // cancel
  // assert AbortController.abort called + cancelled event
})
```

**Step 2: Run tests to verify failure**

Run: `bunx vitest run apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts`
Expected: FAIL due missing abort-controller linkage per session.

**Step 3: Write minimal implementation**

Track per-session AbortController instances in background runtime and call `abort()` on cancel for process-only sessions.

```ts
session.activeControllers.forEach((c) => c.abort())
```

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/entries/background.ts apps/packages/ui/src/services/background-proxy.ts apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts
git commit -m "feat(quick-ingest): add process-only cancel via session abort controllers"
```

---

### Task 4: Wire Modal to Session Lifecycle + Confirmed Cancel (Phase 1)

**Files:**
- Modify: `apps/packages/ui/src/components/Common/QuickIngestModal.tsx`
- Test: `apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx` (create)

**Step 1: Write the failing tests**

Add tests that assert:
- `run()` uses start ack and sets `activeSessionId`.
- modal ignores events without matching `sessionId`.
- cancel button opens confirmation first.
- confirming cancel sends cancel message and immediately sets terminal cancelled UI.
- choosing keep-running does not dispatch cancel.

```tsx
it("requires confirmation before sending cancel", async () => {
  // click cancel
  // expect confirm modal
  // click keep running
  // expect no cancel message sent
})
```

**Step 2: Run tests to verify failure**

Run: `bunx vitest run apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`
Expected: FAIL because modal currently awaits full blocking batch response and lacks confirm-cancel flow.

**Step 3: Write minimal implementation**

In modal:
- replace blocking response handling with session start + event-driven completion.
- add `activeSessionId` guard.
- add cancel confirm dialog and immediate cancelled terminal state on confirm.
- enforce terminal lock against late session events.

```tsx
if (payload.sessionId !== activeSessionIdRef.current) return
```

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Common/QuickIngestModal.tsx apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx
git commit -m "feat(quick-ingest): modal session lifecycle with confirmed cancel"
```

---

### Task 5: Add First-Class Cancelled State in Store and Outcome Mapping (Phase 1)

**Files:**
- Modify: `apps/packages/ui/src/store/quick-ingest.tsx`
- Modify: `apps/packages/ui/src/components/Common/QuickIngest/types.ts`
- Modify: `apps/packages/ui/src/components/Common/QuickIngestModal.tsx`
- Test: `apps/packages/ui/src/store/__tests__/quick-ingest.test.ts`
- Test: `apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`

**Step 1: Write the failing tests**

Add tests that assert:
- store supports `cancelled` last-run status.
- cancelled outcomes are tracked distinctly from failed.
- summary/copy calculations include cancelled counts.

```ts
it("records cancelled run summary", () => {
  // expect status === "cancelled"
})
```

**Step 2: Run tests to verify failure**

Run: `bunx vitest run apps/packages/ui/src/store/__tests__/quick-ingest.test.ts apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`
Expected: FAIL because status types currently omit cancelled.

**Step 3: Write minimal implementation**

Extend status and outcome types:
- last run status: include `cancelled`.
- result outcome: include `cancelled` handling in normalization and summary logic.

```ts
export type QuickIngestLastRunStatus = "idle" | "success" | "error" | "cancelled"
```

**Step 4: Run tests to verify pass**

Run: `bunx vitest run apps/packages/ui/src/store/__tests__/quick-ingest.test.ts apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/quick-ingest.tsx apps/packages/ui/src/components/Common/QuickIngest/types.ts apps/packages/ui/src/components/Common/QuickIngestModal.tsx apps/packages/ui/src/store/__tests__/quick-ingest.test.ts apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx
git commit -m "feat(quick-ingest): add first-class cancelled state and outcome semantics"
```

---

### Task 6: Add Extension E2E Mid-Process Cancel Coverage (Phase 1)

**Files:**
- Modify/Create: `apps/extension/tests/e2e/quick-ingest-cancel.spec.ts`
- Modify (if needed): `apps/extension/tests/e2e/quick-ingest-ui.spec.ts`

**Step 1: Write the failing e2e test**

Create extension e2e scenario:
- open quick ingest modal
- start run with delayed mocked ingestion responses
- click cancel, confirm
- assert immediate `Quick ingest cancelled` terminal UI and cancelled counts.

```ts
test("quick ingest cancel mid-process is immediate after confirmation", async ({ page }) => {
  // ...
})
```

**Step 2: Run e2e test to verify failure**

Run: `bunx playwright test apps/extension/tests/e2e/quick-ingest-cancel.spec.ts --reporter=line`
Expected: FAIL until session/cancel UI is wired.

**Step 3: Minimal implementation adjustments**

Adjust selectors/copy test ids in modal only if needed to make behavior testable and stable.

```tsx
data-testid="quick-ingest-cancel-confirm"
```

**Step 4: Run e2e test to verify pass**

Run: `bunx playwright test apps/extension/tests/e2e/quick-ingest-cancel.spec.ts --reporter=line`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/extension/tests/e2e/quick-ingest-cancel.spec.ts apps/extension/tests/e2e/quick-ingest-ui.spec.ts apps/packages/ui/src/components/Common/QuickIngestModal.tsx
git commit -m "test(extension): add quick ingest mid-process cancel e2e coverage"
```

---

### Task 7: Add WebUI E2E Mid-Process Cancel Coverage (Phase 1)

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts`

**Step 1: Write the failing e2e test**

Add WebUI quick-ingest test:
- run ingest with delayed responses
- cancel -> confirm
- assert immediate cancelled terminal state and no generic failure messaging.

```ts
test("should cancel quick ingest mid-process with confirmation", async ({ page }) => {
  // ...
})
```

**Step 2: Run e2e test to verify failure**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts --grep "cancel quick ingest" --reporter=line`
Expected: FAIL until behavior is implemented.

**Step 3: Minimal implementation adjustments**

Only add deterministic hooks/selectors/copy IDs where required for stable assertions.

**Step 4: Run e2e test to verify pass**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts --grep "cancel quick ingest" --reporter=line`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts apps/packages/ui/src/components/Common/QuickIngestModal.tsx
git commit -m "test(webui): add quick ingest cancel mid-process e2e coverage"
```

---

### Task 8: Phase 1 Verification + Security Scan

**Files:**
- Modify (if needed): touched files from Tasks 1-7

**Step 1: Run focused unit/integration checks**

Run:
```bash
bunx vitest run apps/packages/ui/src/services/__tests__/quick-ingest-batch.test.ts apps/packages/ui/src/store/__tests__/quick-ingest.test.ts apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx apps/packages/ui/src/entries/__tests__/background.quick-ingest-session.test.ts
```

Expected: PASS.

**Step 2: Run focused e2e checks**

Run:
```bash
bunx playwright test apps/extension/tests/e2e/quick-ingest-cancel.spec.ts apps/tldw-frontend/e2e/workflows/media-ingest.spec.ts --reporter=line
```

Expected: PASS for new cancel scenarios.

**Step 3: Run Bandit for touched backend scope (if backend files changed)**

If no backend files touched in Phase 1, document N/A.
If touched:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/media tldw_Server_API/app/services -f json -o /tmp/bandit_quick_ingest_phase1.json
```

Expected: no new high-severity findings in touched code.

**Step 4: Fix regressions (if any)**

Apply minimal fixes and re-run failed checks.

**Step 5: Commit**

```bash
git add -A
git commit -m "chore(quick-ingest): phase 1 verification and test stabilization"
```

---

### Task 9: Add User-Scoped Media Ingest Event Stream (Phase 2)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py`
- Modify (if needed): `tldw_Server_API/app/core/Jobs/manager.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_events_stream.py` (create)

**Step 1: Write failing backend integration tests**

Add tests that verify:
- authenticated user can open media-ingest progress stream for owned jobs/batch.
- non-owner denied.
- stream emits snapshot + subsequent events.

```py
def test_media_ingest_events_stream_user_scoped(client, auth_headers):
    ...
```

**Step 2: Run tests to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_events_stream.py
```

Expected: FAIL (endpoint missing).

**Step 3: Write minimal implementation**

Add media-domain SSE endpoint with user ownership checks and optional batch filter.

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_events_stream.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_events_stream.py
git commit -m "feat(media-ingest): add user-scoped ingest event stream"
```

---

### Task 10: Add Batch/Session Cancel Endpoint (Phase 2)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_batch_cancel.py` (create)

**Step 1: Write failing tests**

Add tests:
- cancel by `batch_id` cancels all non-terminal owned jobs.
- ownership is enforced.
- response includes summary counts (`requested`, `cancelled`, `already_terminal`).

```py
def test_cancel_batch_ingest_jobs(client, auth_headers):
    ...
```

**Step 2: Run tests to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_batch_cancel.py
```

Expected: FAIL (endpoint missing).

**Step 3: Write minimal implementation**

Add new batch cancel endpoint and call existing `jm.cancel_job` internally per matched job.

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_batch_cancel.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_batch_cancel.py
git commit -m "feat(media-ingest): add batch/session cancel endpoint"
```

---

### Task 11: Optimize Batch Lookup Path (Phase 2)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py`
- Modify: `tldw_Server_API/app/core/Jobs/manager.py`
- Test: `tldw_Server_API/tests/MediaIngestion_NEW/unit/test_ingest_jobs_batch_lookup.py` (create)

**Step 1: Write failing tests**

Add tests:
- list-by-batch uses indexed grouping/filter path (e.g., `batch_group`) not payload scan loop.
- output parity with previous behavior.

```py
def test_list_media_ingest_jobs_by_batch_group():
    ...
```

**Step 2: Run tests to verify failure**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/unit/test_ingest_jobs_batch_lookup.py
```

Expected: FAIL until manager/list filter support is added.

**Step 3: Write minimal implementation**

Add/filter support in JobManager list path and switch media list endpoint to indexed batch filtering.

**Step 4: Run tests to verify pass**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/unit/test_ingest_jobs_batch_lookup.py
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Jobs/manager.py tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py tldw_Server_API/tests/MediaIngestion_NEW/unit/test_ingest_jobs_batch_lookup.py
git commit -m "perf(media-ingest): optimize batch lookup via indexed grouping"
```

---

### Task 12: Phase 2 Verification + Docs Update

**Files:**
- Modify: `Docs/Plans/2026-02-23-quick-ingest-session-cancel-two-phase-design.md` (if implementation deltas)
- Modify: `Docs/Development/*` relevant docs (as needed)
- Modify: added tests/files from Tasks 9-11

**Step 1: Run backend test slice**

Run:
```bash
source .venv/bin/activate && python -m pytest -v tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_events_stream.py tldw_Server_API/tests/MediaIngestion_NEW/integration/test_ingest_jobs_batch_cancel.py tldw_Server_API/tests/MediaIngestion_NEW/unit/test_ingest_jobs_batch_lookup.py
```

Expected: PASS.

**Step 2: Run Bandit on touched backend scope**

Run:
```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/media/ingest_jobs.py tldw_Server_API/app/core/Jobs/manager.py -f json -o /tmp/bandit_quick_ingest_phase2.json
```

Expected: no new high-severity findings in changed code.

**Step 3: Run targeted frontend regression checks**

Run:
```bash
bunx vitest run apps/packages/ui/src/components/Common/__tests__/QuickIngestModal.session-cancel.test.tsx apps/packages/ui/src/store/__tests__/quick-ingest.test.ts
```

Expected: PASS.

**Step 4: Update docs for new backend endpoints/events**

Document stream endpoint and batch cancel endpoint usage/caveats.

**Step 5: Commit**

```bash
git add -A
git commit -m "docs(quick-ingest): document phase 2 backend hardening and verification"
```

---

## Rollout and Risk Controls

1. Keep feature-gating for new session protocol in extension/WebUI until E2E stable.
2. Log session lifecycle transitions at debug level for initial rollout.
3. Preserve compatibility shim for old `tldw:quick-ingest-batch` for one release window.
4. Roll out Phase 2 backend changes behind additive endpoints first, then switch clients.

## Done Criteria

1. Phase 1:
   - Extension + WebUI modals are session-native with confirmed cancel.
   - `storeRemote` uses existing ingest jobs submit/poll/cancel path.
   - `processOnly` uses client abort semantics.
   - E2E mid-process cancel passes for extension + WebUI.
2. Phase 2:
   - user-scoped media ingest event stream exists.
   - batch/session cancel endpoint exists.
   - batch listing path is optimized and tested.
   - verification + Bandit checks are clean for changed scope.
