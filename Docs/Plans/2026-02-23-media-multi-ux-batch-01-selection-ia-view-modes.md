# Media Multi UX Batch 01 - Selection Safety, IA, and View Mode Orientation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate accidental selection loss and reduce orientation friction by making selection scope explicit, stabilizing mode transitions, and clarifying navigation relationships.

**Architecture:** Introduce a dedicated selection-scope action model (`add visible`, `replace with visible`, `clear with undo`) and explicit UI affordances that show cross-page selection state. Keep existing data fetching and detail-loading architecture intact, but route all selection mutations through shared helpers so keyboard, sidebar clicks, and toolbar actions are consistent.

**Tech Stack:** React, TypeScript, Ant Design, i18n (`review.json`), TanStack Virtual, Vitest + Testing Library, Playwright.

---

## Execution Status (2026-02-23)

- Task 1: Complete (implemented inside existing stage1 test suite with failing/then-passing assertions for selection scope behaviors).
- Task 2: Complete (shared add vs replace selection pathways wired into keyboard and options menu).
- Task 3: Complete (cross-page selection count + selected-items drawer with jump/remove controls implemented).
- Task 4: Complete (manual mode pinning + inline auto-switch notice implemented).
- Task 5: Complete (remove-from-selection copy + explicit sidebar/viewer/open-items relationship hint copy implemented).
- Task 6: Complete (Playwright scenario + page-object support added for cross-page selection preservation).
- Task 7: Complete (2026-02-23 verification: `bunx vitest run src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx` passed in `apps/packages/ui`; cross-page Playwright scenario passed with in-test seeding via `TLDW_WEB_AUTOSTART=false TLDW_WEB_URL=http://localhost:3000 bunx playwright test e2e/workflows/media-review.spec.ts --grep "cross-page selection" --reporter=line`).

---

## Covered Findings

- UX-001, UX-005, UX-006, UX-007, UX-008, UX-021

---

### Task 1: Add Failing Tests for Selection Scope Safety and Replacement Undo

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx`
- Reference: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write the failing tests**

```tsx
it('adds visible items without replacing existing cross-page selection', async () => {
  render(<MediaReviewPage />)
  seedSelection([101, 102])

  await user.click(screen.getByRole('button', { name: /options/i }))
  await user.click(screen.getByRole('menuitem', { name: /add visible to selection/i }))

  expect(selectionIds()).toEqual(expect.arrayContaining([101, 102]))
  expect(selectionIds().length).toBeGreaterThan(2)
})

it('replace-visible action offers undo restoring prior cross-page selection', async () => {
  render(<MediaReviewPage />)
  seedSelection([101, 102, 103])

  await user.click(screen.getByRole('button', { name: /options/i }))
  await user.click(screen.getByRole('menuitem', { name: /replace selection with visible/i }))
  await user.click(screen.getByRole('button', { name: /undo/i }))

  expect(selectionIds()).toEqual([101, 102, 103])
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx
```

Expected: FAIL because actions and behavior do not exist yet.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx
git commit -m "test(media-multi): add failing tests for selection scope safety"
```

---

### Task 2: Implement Shared Selection Action Model in MediaReviewPage

**Files:**
- Create: `apps/packages/ui/src/components/Review/selection-actions.ts`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx`

**Step 1: Add minimal selection action helpers**

```ts
export function addVisibleSelection(prev: Array<string | number>, visible: Array<string | number>, limit: number) {
  const merged = [...prev]
  for (const id of visible) {
    if (merged.includes(id)) continue
    if (merged.length >= limit) break
    merged.push(id)
  }
  return merged
}

export function replaceSelectionWithVisible(visible: Array<string | number>, limit: number) {
  return visible.slice(0, limit)
}
```

**Step 2: Wire helpers to Options menu and Ctrl/Cmd+A**

- Keep `Ctrl/Cmd+A` as additive by default.
- Add explicit option item for replace action.
- Reuse existing undo infrastructure for replace action.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/selection-actions.ts apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx
git commit -m "feat(media-multi): add explicit additive vs replace selection actions"
```

---

### Task 3: Add Cross-Page Selection Scope Indicator and Selected-Items Drawer

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope-indicator.test.tsx`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`

**Step 1: Write failing test for scope indicator/drawer**

```tsx
it('shows selected-across-pages count and opens selected-items drawer', async () => {
  render(<MediaReviewPage />)
  seedSelection([11, 12, 13, 14])

  expect(screen.getByText(/selected across pages: 4/i)).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: /view selected items/i }))
  expect(screen.getByRole('dialog', { name: /selected items/i })).toBeInTheDocument()
})
```

**Step 2: Run test to verify it fails**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope-indicator.test.tsx
```

Expected: FAIL.

**Step 3: Implement indicator + drawer**

- Add header-level scope line: `Selected across pages: N`.
- Add drawer listing selected IDs/titles with quick remove controls.
- Ensure drawer remove action updates selection and focus safely.

**Step 4: Run test to verify it passes**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope-indicator.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope-indicator.test.tsx apps/packages/ui/src/public/_locales/en/review.json
git commit -m "feat(media-multi): add cross-page selection scope indicator and selected-items drawer"
```

---

### Task 4: Stabilize Auto-Mode Transitions with Sticky Manual Mode and Inline Transition Banner

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.view-mode-transitions.test.tsx`

**Step 1: Write failing tests**

```tsx
it('keeps user-pinned mode when auto-mode is disabled', async () => {
  render(<MediaReviewPage />)
  disableAutoMode()
  setMode('spread')
  selectN(6)
  expect(currentMode()).toBe('spread')
})

it('shows inline mode-change banner when auto-mode changes mode', async () => {
  render(<MediaReviewPage />)
  selectN(5)
  expect(screen.getByText(/auto-switched to stack/i)).toBeInTheDocument()
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.view-mode-transitions.test.tsx
```

Expected: FAIL.

**Step 3: Implement sticky mode + inline transition banner**

- Track `manualModePinned` in state.
- Skip auto transitions when pinned.
- Render persistent inline banner near view mode controls (dismissable).

**Step 4: Re-run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.view-mode-transitions.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.view-mode-transitions.test.tsx
git commit -m "feat(media-multi): stabilize auto view transitions with sticky manual mode"
```

---

### Task 5: Clarify “Unstack” Semantics and IA Relationship Copy

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.copy-clarity.test.tsx`

**Step 1: Add failing tests for updated labels**

```tsx
it('uses remove-from-selection language instead of unstack', async () => {
  render(<MediaReviewPage />)
  selectN(2)
  expect(screen.getAllByRole('button', { name: /remove from selection/i }).length).toBeGreaterThan(0)
})
```

**Step 2: Run test (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.copy-clarity.test.tsx
```

Expected: FAIL.

**Step 3: Update copy and hint text**

- Rename `Unstack` to `Remove from selection`.
- Update sidebar/minimap orientation text so relationship is explicit: `Search/filter in sidebar, inspect in viewer, jump using open items`.

**Step 4: Re-run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.copy-clarity.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.copy-clarity.test.tsx apps/packages/ui/src/public/_locales/en/review.json
git commit -m "chore(media-multi): clarify selection language and IA guidance copy"
```

---

### Task 6: Playwright Coverage for Cross-Page Selection Preservation

**Files:**
- Modify: `apps/tldw-frontend/e2e/workflows/media-review.spec.ts`
- Modify: `apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts`

**Step 1: Add e2e scenario**

```ts
test('preserves cross-page selection when adding visible page items', async ({ authedPage }) => {
  const reviewPage = new MediaReviewPage(authedPage)
  await reviewPage.goto()
  await reviewPage.waitForReady()

  await reviewPage.clickItem(0)
  await reviewPage.goToPage(2)
  await reviewPage.openOptionsMenu()
  await reviewPage.clickAddVisibleToSelection()

  await expect(await reviewPage.getSelectionCount()).toBeGreaterThan(1)
})
```

**Step 2: Run e2e test**

Run:
```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "cross-page selection"
```

Expected: PASS.

**Step 3: Commit**

```bash
git add apps/tldw-frontend/e2e/workflows/media-review.spec.ts apps/tldw-frontend/e2e/utils/page-objects/MediaReviewPage.ts
git commit -m "test(media-multi): verify cross-page selection is preserved in add-visible flow"
```

---

### Task 7: Final Verification for Batch 01

**Files:**
- Verify touched files only.

**Step 1: Run unit tests for batch scope**

```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.selection-scope-indicator.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.view-mode-transitions.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.copy-clarity.test.tsx
```

Expected: PASS.

**Step 2: Run relevant e2e test subset**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "selection|view mode"
```

Expected: PASS.

**Step 3: Final commit (if needed)**

```bash
git add <remaining files>
git commit -m "chore(media-multi): finalize batch 01 selection and IA verification"
```

---

## Implementation Notes

1. Keep all selection mutations in shared helper functions; avoid direct `setSelectedIds` branching spread across handlers.
2. Preserve existing undo duration and 30-item cap while adding explicit replace/add pathways.
3. Use `@test-driven-development` and `@verification-before-completion` during execution.
