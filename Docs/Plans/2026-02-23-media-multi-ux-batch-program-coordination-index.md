# Media Multi UX Program Coordination Index Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Coordinate execution order and dependency boundaries across all Media Multi UX batches so every identified finding (UX-001 through UX-022) is implemented without gaps.

**Architecture:** Execute in five batches with explicit dependency sequencing: selection/IA first, then search controls, then performance hardening, then batch operations, and finally accessibility/mobile parity. Each batch plan remains independently executable and verifiable.

**Tech Stack:** Markdown planning docs, React/TypeScript frontend modules, Vitest, Playwright.

---

## Program Status (2026-02-23)

- Batch 01: Complete
- Batch 02: Complete
- Batch 03: Complete
- Batch 04: Complete
- Batch 05: Complete

Current checkpoint: Batch 05 verification is complete with targeted Vitest (`stage6.*`), Stage1 accessibility augmentation checks, Playwright keyboard/accessibility/mobile coverage, and program-level media-review workflow regression.

---

## Batch Plans

1. `Docs/Plans/2026-02-23-media-multi-ux-batch-01-selection-ia-view-modes.md`
2. `Docs/Plans/2026-02-23-media-multi-ux-batch-02-search-filter-sort.md`
3. `Docs/Plans/2026-02-23-media-multi-ux-batch-03-content-diff-performance.md`
4. `Docs/Plans/2026-02-23-media-multi-ux-batch-04-batch-operations-lifecycle.md`
5. `Docs/Plans/2026-02-23-media-multi-ux-batch-05-responsive-a11y-keyboard.md`

---

## Execution Order

### Task 1: Execute Batch 01 (Selection/IA/View Modes)

**Files:**
- Plan: `Docs/Plans/2026-02-23-media-multi-ux-batch-01-selection-ia-view-modes.md`

**Step 1: Run Batch 01 tasks in order**

Follow all tasks and commits in batch 01.

**Step 2: Verify batch completion**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.*
```

Expected: PASS.

---

### Task 2: Execute Batch 02 (Search/Filter/Sort)

**Files:**
- Plan: `Docs/Plans/2026-02-23-media-multi-ux-batch-02-search-filter-sort.md`

**Step 1: Run Batch 02 tasks in order**

Follow all tasks and commits in batch 02.

**Step 2: Verify batch completion**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.*
```

Expected: PASS.

---

### Task 3: Execute Batch 03 (Diff/Content/Performance)

**Files:**
- Plan: `Docs/Plans/2026-02-23-media-multi-ux-batch-03-content-diff-performance.md`

**Step 1: Run Batch 03 tasks in order**

Follow all tasks and commits in batch 03.

**Step 2: Verify batch completion**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.*
```

Expected: PASS.

---

### Task 4: Execute Batch 04 (Batch Ops/Lifecycle)

**Files:**
- Plan: `Docs/Plans/2026-02-23-media-multi-ux-batch-04-batch-operations-lifecycle.md`

**Step 1: Run Batch 04 tasks in order**

Follow all tasks and commits in batch 04.

**Step 2: Verify batch completion**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.*
```

Expected: PASS.

---

### Task 5: Execute Batch 05 (Responsive/A11y/Keyboard)

**Files:**
- Plan: `Docs/Plans/2026-02-23-media-multi-ux-batch-05-responsive-a11y-keyboard.md`

**Step 1: Run Batch 05 tasks in order**

Follow all tasks and commits in batch 05.

**Step 2: Verify batch completion**

Run:
```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.*
```

Expected: PASS.

---

## Finding-to-Plan Coverage Matrix

| Finding | Batch Plan | Primary Task(s) |
|---|---|---|
| UX-001 | Batch 01 | Task 1, Task 2 |
| UX-002 | Batch 02 | Task 1, Task 2 |
| UX-003 | Batch 04 | Task 3, Task 4 |
| UX-004 | Batch 03 | Task 1, Task 2 |
| UX-005 | Batch 01 | Task 3, Task 5 |
| UX-006 | Batch 01 | Task 4 |
| UX-007 | Batch 01 | Task 5 |
| UX-008 | Batch 01 | Task 3, Task 5 |
| UX-009 | Batch 02 | Task 3, Task 4 |
| UX-010 | Batch 02 | Task 6 |
| UX-011 | Batch 02 | Task 5, Task 6 |
| UX-012 | Batch 03 | Task 5, Task 6 |
| UX-013 | Batch 03 | Task 5, Task 6 |
| UX-014 | Batch 03 | Task 5, Task 6 |
| UX-015 | Batch 04 | Task 4, Task 7 |
| UX-016 | Batch 04 | Task 4 |
| UX-017 | Batch 05 | Task 7 |
| UX-018 | Batch 03 | Task 3, Task 4 |
| UX-019 | Batch 05 | Task 1, Task 2 |
| UX-020 | Batch 05 | Task 5, Task 6 |
| UX-021 | Batch 01 | Task 3, Task 5 |
| UX-022 | Batch 04 | Task 4 |

---

## Program-Level Final Verification

### Task 6: Run End-to-End Program Regression

**Files:**
- Verify all touched frontend and e2e files.

**Step 1: Run aggregate unit suites**

```bash
cd apps && bunx vitest run packages/ui/src/components/Review/__tests__/MediaReviewPage.stage1.selectionLimit.test.tsx packages/ui/src/components/Review/__tests__/MediaReviewPage.stage2.* packages/ui/src/components/Review/__tests__/MediaReviewPage.stage3.* packages/ui/src/components/Review/__tests__/MediaReviewPage.stage4.* packages/ui/src/components/Review/__tests__/MediaReviewPage.stage5.* packages/ui/src/components/Review/__tests__/MediaReviewPage.stage6.* packages/ui/src/components/Media/__tests__/DiffViewModal.stage4.scalability.test.tsx packages/ui/src/services/__tests__/tldw-api-client.media-batch-actions.test.ts
```

Expected: PASS.

**Step 2: Run e2e workflow regression**

```bash
cd apps/tldw-frontend && bunx playwright test e2e/workflows/media-review.spec.ts
```

Expected: PASS.

**Step 3: Final commit (if needed)**

```bash
git add <remaining files>
git commit -m "chore(media-multi): finalize UX batch program verification"
```

---

## Implementation Notes

1. Keep batches independently mergeable; avoid coupling schema-level changes across batches.
2. Do not start batch N+1 before batch N verification is complete.
3. Use `@test-driven-development` and `@verification-before-completion` throughout execution.
