# Media Multi UX Batch 03 - Content Inspection, Diff Scalability, and Rendering Performance Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Keep compare and stack workflows reliable for long documents by adding scalable diff behavior, virtualized stack rendering, and lower-noise card content controls.

**Architecture:** Keep existing comparison and card models, but move expensive diff computation off the main thread with guarded fallbacks. Replace non-virtualized stack rendering with virtualized rendering shared with existing viewer virtualizer patterns, and reduce card chrome by consolidating secondary actions.

**Tech Stack:** React, TypeScript, Ant Design Modal/Dropdown, TanStack Virtual, Web Worker (`postMessage`), Vitest + Testing Library, Playwright.

---

## Execution Status (2026-02-23)

- Task 1: Complete (stage4 scalability tests added for hard-threshold warning and worker dispatch path).
- Task 2: Complete (worker-backed diff pipeline, hard threshold sampling flow, and sync fallback integrated in `DiffViewModal`).
- Task 3: Complete (stack virtualization failing test added and preserved as regression coverage).
- Task 4: Complete (stack mode now renders through dedicated virtualizer with validated estimate/overscan settings).
- Task 5: Complete (card-density stage4 tests added for adaptive heights, copy-menu path, and empty-analysis suppression).
- Task 6: Complete (adaptive content sizing helper wired, unified copy dropdown shipped, empty-analysis compact state + reveal action implemented).
- Task 7: Complete (Playwright scenarios added for long compare workflow and 30-item stack virtualization responsiveness).
- Task 8: Complete (targeted Vitest suite and Playwright subset pass for Batch 03 scope).

---

## Covered Findings

- UX-004, UX-012, UX-013, UX-014, UX-018

---

### Task 1: Add Failing Tests for Long-Diff Guardrails and Worker Mode

**Files:**
- Create: `apps/packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx`
- Modify: `apps/packages/ui/src/components/Media/DiffViewModal.tsx`

**Step 1: Write failing tests**

```tsx
it('shows large-document warning before computing diff over threshold', async () => {
  render(<DiffViewModal open leftText={veryLongText()} rightText={veryLongText2()} onClose={() => {}} />)
  expect(screen.getByText(/large comparison/i)).toBeInTheDocument()
})

it('uses worker-backed diff pipeline when document length exceeds sync threshold', async () => {
  render(<DiffViewModal open leftText={longText()} rightText={longText()} onClose={() => {}} />)
  await waitFor(() => expect(mockWorkerPostMessage).toHaveBeenCalled())
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx
git commit -m "test(media-multi): add failing scalability tests for diff modal"
```

---

### Task 2: Implement Worker-Backed Diff with Size Guardrails

**Files:**
- Create: `apps/packages/ui/src/components/Media/diff-worker-client.ts`
- Create: `apps/packages/ui/src/components/Media/diff.worker.ts`
- Modify: `apps/packages/ui/src/components/Media/DiffViewModal.tsx`
- Test: `apps/packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx`

**Step 1: Add worker client + threshold constants**

```ts
export const DIFF_SYNC_LINE_THRESHOLD = 4000
export const DIFF_HARD_CHAR_THRESHOLD = 300_000
```

**Step 2: Update modal flow**

- For small docs: keep sync path.
- For large docs: show warning + compute in worker.
- For too-large docs: allow user-confirmed “sampled diff” fallback.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Media/diff-worker-client.ts apps/packages/ui/src/components/Media/diff.worker.ts apps/packages/ui/src/components/Media/DiffViewModal.tsx apps/packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx
git commit -m "feat(media-multi): move large diff computation off main thread with guardrails"
```

---

### Task 3: Add Failing Tests for Stack Virtualization at High Selection Counts

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('virtualizes stack mode cards rather than rendering all selected cards eagerly', async () => {
  render(<MediaReviewPage />)
  selectN(30)
  setMode('all')

  expect(renderedCardCount()).toBeLessThan(30)
  expect(getStackVirtualizer()).toBeDefined()
})
```

**Step 2: Run test (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing test**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx
git commit -m "test(media-multi): add failing test for stack mode virtualization"
```

---

### Task 4: Implement Virtualized Stack Rendering and Lazy Expansion

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/stack-virtualization.ts`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx`

**Step 1: Implement virtualized stack behavior**

- Reuse `useVirtualizer` in `all` mode.
- Render only visible cards.
- Keep stable item keys and scroll restoration.

**Step 2: Add lazy mounting for heavy sections**

- Delay analysis/content block render until card enters viewport.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/stack-virtualization.ts apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx
git commit -m "feat(media-multi): virtualize stack mode rendering for large selections"
```

---

### Task 5: Add Failing Tests for Card Density Improvements

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('uses adaptive content-height behavior for short vs long content', async () => {
  render(<MediaReviewPage />)
  selectShortAndLongItems()
  expect(shortCardHasNoForcedScroll()).toBe(true)
  expect(longCardIsCollapsedByDefault()).toBe(true)
})

it('uses unified copy menu and suppresses empty analysis block by default', async () => {
  render(<MediaReviewPage />)
  selectItemWithoutAnalysis()
  expect(screen.getByRole('button', { name: /copy/i })).toBeInTheDocument()
  expect(screen.queryByText(/no analysis available/i)).not.toBeInTheDocument()
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx
git commit -m "test(media-multi): add failing tests for card density improvements"
```

---

### Task 6: Implement Adaptive Content Sections, Unified Copy Menu, and Empty-Analysis Suppression

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/card-content-density.ts`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx`

**Step 1: Implement adaptive content sizing helper**

```ts
export function getContentLayout(contentLength: number) {
  if (contentLength < 500) return { minHeightEm: 6, capped: false }
  if (contentLength < 5000) return { minHeightEm: 10, capped: true }
  return { minHeightEm: 14, capped: true }
}
```

**Step 2: Replace dual copy buttons with split menu**

- `Copy` dropdown items: `Copy content`, `Copy analysis`, `Copy both`.

**Step 3: Hide empty analysis by default**

- Render compact badge only.
- Expandable panel appears on demand.

**Step 4: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/card-content-density.ts apps/packages/ui/src/public/_locales/en/review.json apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx
git commit -m "feat(media-multi): reduce card density and improve content/analysis ergonomics"
```

---

### Task 7: Add E2E Regression Coverage for Long Compare and 30-Item Stack

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/media-review.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts`

**Step 1: Add scenarios**

- Long-doc compare shows non-blocking status and renders diff view.
- 30 selected in stack mode remains interactive and scrollable.

**Step 2: Run e2e subset**

Run:
```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "diff|stack|performance"
```

Expected: PASS.

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-review.spec.ts apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts
git commit -m "test(media-multi): add e2e checks for long compare and stack performance"
```

---

### Task 8: Final Verification for Batch 03

**Files:**
- Verify touched files only.

**Step 1: Run targeted unit tests**

```bash
cd apps && bunx vitest run packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.stack-virtualization.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.card-density.test.tsx
```

Expected: PASS.

**Step 2: Run e2e subset**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "diff|stack"
```

Expected: PASS.

**Step 3: Final commit (if needed)**

```bash
git add <remaining files>
git commit -m "chore(media-multi): finalize batch 03 content and performance verification"
```

---

## Implementation Notes

1. Keep existing compare contract (`DiffViewModal` props) backward compatible.
2. Prefer worker fallback instead of hard failure for very large diffs.
3. Use `@test-driven-development` and `@verification-before-completion` during execution.
