# PR 839 STT Retry Fix Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make the `/stt` page surface a persistent inline model-load error with a Retry action so the PR #839 UX smoke gate passes.

**Architecture:** Keep the change local to `SttPlaygroundPage` by adding explicit model-loading/error state and rendering an inline recovery alert instead of relying only on transient notifications. Validate the behavior with a focused component test that drives the initial failure and the retry path without broad UI changes.

**Tech Stack:** React, Ant Design, Vitest, Testing Library, Bun

---

### Task 1: Add the failing STT recovery test

**Files:**
- Modify: `apps/packages/ui/src/components/Option/STT/__tests__/SttPlaygroundPage.test.tsx`
- Reference: `apps/tldw-frontend/e2e/smoke/stage7-audio-regression.spec.ts`

**Step 1: Write the failing test**

Add a test that:
- Mocks `tldwClient.getTranscriptionModels` to reject once and resolve on retry.
- Renders `SttPlaygroundPage`.
- Asserts the inline model-load warning appears with a `Retry` button.
- Clicks `Retry`.
- Waits for the warning to clear and confirms the fetch mock was called twice.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Option/STT/__tests__/SttPlaygroundPage.test.tsx`

Expected: FAIL because the current page only emits a notification and does not render inline retry UI.

**Step 3: Commit**

Do not commit yet. Continue to implementation once the failure proves the gap.

### Task 2: Implement the minimal STT retry UI

**Files:**
- Modify: `apps/packages/ui/src/components/Option/STT/SttPlaygroundPage.tsx`
- Test: `apps/packages/ui/src/components/Option/STT/__tests__/SttPlaygroundPage.test.tsx`

**Step 1: Write minimal implementation**

Update `SttPlaygroundPage` to:
- Track `serverModelsLoading`, `serverModelsError`, and `modelsLoadAttempt`.
- Re-fetch models when `modelsLoadAttempt` changes.
- Render an inline Ant Design `Alert` with the current error copy and a `Retry` button.
- Clear the inline error when a retry starts or succeeds.
- Preserve existing successful model population behavior.

**Step 2: Run the targeted test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Option/STT/__tests__/SttPlaygroundPage.test.tsx`

Expected: PASS

**Step 3: Run adjacent verification**

Run:
- `bunx vitest run apps/packages/ui/src/components/Option/STT/__tests__/ComparisonPanel.test.tsx`
- `bunx vitest run apps/packages/ui/src/components/Option/Speech/__tests__/RenderStrip.test.tsx`

Expected: PASS

**Step 4: Run security validation on touched scope**

Run: `source .venv/bin/activate && python -m bandit -r apps/packages/ui/src/components/Option/STT -f json -o /tmp/bandit_pr839_stt_retry.json`

Expected: PASS or no new findings in touched code

**Step 5: Commit**

```bash
git add Docs/Plans/2026-03-09-pr-839-stt-retry-implementation-plan.md apps/packages/ui/src/components/Option/STT/SttPlaygroundPage.tsx apps/packages/ui/src/components/Option/STT/__tests__/SttPlaygroundPage.test.tsx
git commit -m "fix(stt): add inline model load retry recovery"
```
