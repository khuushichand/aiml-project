# Media Multi UX Batch 05 - Responsive Parity, Accessibility, and Keyboard Safety Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Improve cross-device usability and accessibility by scoping shortcuts safely, strengthening focus management, increasing touch target reliability, and restoring key multi-item capabilities on mobile.

**Architecture:** Keep existing single-page component structure but introduce explicit interaction-context guards (`viewer`, `modal`, `dropdown`, `input`) so keyboard handlers trigger only when intended. Expand responsive behavior with a mobile-capable stacked review mode and enforce minimum target sizing and non-color status semantics.

**Tech Stack:** React, TypeScript, Ant Design, ARIA semantics, CSS utility classes, Vitest + Testing Library + axe-core, Playwright.

---

## Covered Findings

- UX-017, UX-019, UX-020

---

### Task 1: Add Failing Tests for Keyboard Shortcut Scope Gating

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('does not trigger global j/k navigation when options menu is open', async () => {
  render(<MediaReviewPage />)
  selectN(2)
  await user.click(screen.getByRole('button', { name: /options/i }))
  fireEvent.keyDown(document, { key: 'j' })
  expect(currentFocusedIndex()).toBe(1)
})

it('does not clear selection on escape when diff modal is focused', async () => {
  render(<MediaReviewPage />)
  selectN(2)
  openDiff()
  fireEvent.keyDown(document, { key: 'Escape' })
  expect(selectionCount()).toBe(2)
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx
git commit -m "test(media-multi): add failing tests for keyboard shortcut scope"
```

---

### Task 2: Implement Interaction Context Guards for Keyboard Handlers

**Files:**
- Create: `apps/packages/ui/src/components/Review/interaction-context.ts`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx`

**Step 1: Add context helper**

```ts
export function shouldHandleGlobalShortcut(target: EventTarget | null): boolean {
  // false for input/textarea/select/contenteditable, open menu items, modal dialogs
}
```

**Step 2: Gate global handlers**

- Apply helper before switch statement.
- Add modal-open checks (`helpModalOpen`, `compareDiffOpen`).

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/interaction-context.ts apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx
git commit -m "feat(media-multi): scope global shortcuts by interaction context"
```

---

### Task 3: Add Failing Tests for Focus Recovery After Clear/Undo and Modal Close

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx`
- Modify: `apps/packages/ui/src/components/Media/DiffViewModal.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('returns focus to previously focused result row after undo restore', async () => {
  render(<MediaReviewPage />)
  focusResultRow('Item 4')
  clearSelectionAndUndo()
  expect(getResultRow('Item 4')).toHaveFocus()
})

it('restores focus to compare trigger after closing diff modal', async () => {
  render(<MediaReviewPage />)
  openDiff()
  closeDiff()
  expect(screen.getByRole('button', { name: /compare content/i })).toHaveFocus()
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx
git commit -m "test(media-multi): add failing tests for focus recovery"
```

---

### Task 4: Implement Deterministic Focus Restoration Paths

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Modify: `apps/packages/ui/src/components/Media/DiffViewModal.tsx`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx`

**Step 1: Track explicit focus anchors**

- Before clear/replacement actions, store focused row ID and control source.
- Restore on undo with `requestAnimationFrame` after state commit.

**Step 2: Harden modal focus return**

- In `DiffViewModal`, restore to trigger only if still connected and visible.
- Fall back to compare button query.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Media/DiffViewModal.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx
git commit -m "feat(media-multi): improve focus restoration after clear/undo and diff close"
```

---

### Task 5: Add Failing Tests for Touch Targets and Non-Color Selection Status Cues

**Files:**
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx`
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`

**Step 1: Write failing tests**

```tsx
it('adds explicit textual selection status labels independent of color', async () => {
  render(<MediaReviewPage />)
  selectN(25)
  expect(screen.getByText(/selection status: warning/i)).toBeInTheDocument()
})

it('ensures key icon controls meet minimum 44x44 touch target', async () => {
  render(<MediaReviewPage />)
  const helpBtn = screen.getByRole('button', { name: /keyboard shortcuts/i })
  expect(helpBtn).toHaveClass(expect.stringMatching(/min-h-\[44px\]|h-11/))
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx
```

Expected: FAIL.

**Step 3: Commit failing tests**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx
git commit -m "test(media-multi): add failing tests for touch target and non-color status cues"
```

---

### Task 6: Implement Touch-Target and Status-Semantic Improvements

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`
- Test: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx`

**Step 1: Add textual selection status labels**

- Add explicit status text: `Safe`, `Warning`, `Limit reached`.
- Keep color bar but do not rely on color-only communication.

**Step 2: Enforce min target sizing on critical controls**

- Help button, sidebar toggle, minimap items, options button, expand/collapse triggers.
- Use `min-h-[44px] min-w-[44px]` where practical.

**Step 3: Run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/public/_locales/en/review.json apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx
git commit -m "feat(media-multi): add explicit status semantics and larger touch targets"
```

---

### Task 7: Add Optional Mobile Stack Review Mode (Capability Parity)

**Files:**
- Modify: `apps/packages/ui/src/components/Review/MediaReviewPage.tsx`
- Create: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.mobile-parity.test.tsx`
- Modify: `apps/packages/ui/src/public/_locales/en/review.json`

**Step 1: Write failing tests**

```tsx
it('offers optional stack mode on mobile for multi-selection', async () => {
  setMobileViewport(true)
  render(<MediaReviewPage />)
  selectN(3)
  expect(screen.getByRole('button', { name: /stack/i })).toBeInTheDocument()
})
```

**Step 2: Run tests (expect fail)**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.mobile-parity.test.tsx
```

Expected: FAIL.

**Step 3: Implement mobile parity mode**

- Keep Focus as default.
- Expose compact `Stack` toggle on mobile when `selectedIds.length > 1`.
- Use safe vertical-only rendering for readability.

**Step 4: Re-run tests**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.mobile-parity.test.tsx
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/components/Review/MediaReviewPage.tsx apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.mobile-parity.test.tsx apps/packages/ui/src/public/_locales/en/review.json
git commit -m "feat(media-multi): add optional mobile stack mode for multi-item parity"
```

---

### Task 8: Accessibility and E2E Verification

**Files:**
- Modify: `apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx`
- Modify: `apps/tldw-frontend/e2e/workflows/media-review.spec.ts`

**Step 1: Extend axe rules coverage**

- Add checks for focus order and aria naming on new controls.

**Step 2: Add e2e keyboard-only scenario**

- Navigate, select, open options, open diff, close diff, undo clear.
- Assert no unintended global shortcut side effects.

**Step 3: Run verification**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.mobile-parity.test.tsx
```

Run:
```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "keyboard|accessibility|mobile"
```

Expected: PASS.

**Step 4: Commit**

```bash
git add apps/packages/ui/src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx apps/tldw-frontend/e2e/workflows/media-review.spec.ts
git commit -m "test(media-multi): verify keyboard safety, accessibility, and mobile parity"
```

---

### Task 9: Final Verification for Batch 05

**Files:**
- Verify touched files only.

**Step 1: Run all stage6 unit tests**

```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.keyboard-scope.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.focus-recovery.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.touch-status-a11y.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.mobile-parity.test.tsx
```

Expected: PASS.

**Step 2: Run e2e keyboard/mobile subset**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts --grep "keyboard|mobile"
```

Expected: PASS.

**Step 3: Final commit (if needed)**

```bash
git add <remaining files>
git commit -m "chore(media-multi): finalize batch 05 responsive and a11y verification"
```

---

## Implementation Notes

1. Global shortcuts must be context-aware and never fire while modal/menu layers are active.
2. Preserve existing keyboard affordances; improve safety, not reduce power-user speed.
3. Use `@test-driven-development` and `@verification-before-completion` during execution.
