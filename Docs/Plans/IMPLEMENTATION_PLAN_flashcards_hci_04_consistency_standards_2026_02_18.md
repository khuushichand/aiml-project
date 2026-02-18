# Implementation Plan: Flashcards H4 - Consistency and Standards

## Scope

Route/components: `FlashcardsManager.tsx`, `tabs/ReviewTab.tsx`, `tabs/ManageTab.tsx`, drawer components under flashcards UI package  
Finding IDs: `H4-1` through `H4-3`

## Finding Coverage

- Tab-level interaction model differs from adjacent app patterns: `H4-1`
- Card creation entry points are fragmented across contexts: `H4-2`
- Drawer sizing and visual rhythm differ between related workflows: `H4-3`

## Stage 1: Interaction Model Alignment
**Goal**: Make flashcards navigation and action placement predictable relative to the rest of the app.
**Success Criteria**:
- Tab labels and descriptions clarify workflow separation (Study, Manage, Transfer) with consistent naming.
- Primary creation entry point is defined and reused across tabs; secondary triggers route to it.
- Empty-state CTAs and top-level CTA copy use a single canonical label.
**Tests**:
- Component tests for tab labels, aria attributes, and active state behavior.
- UX regression tests for CTA routing from Review, Cards, and empty states.
- Snapshot tests for cross-breakpoint layout consistency.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Updated top-level Flashcards tab naming in `FlashcardsManager`:
  - `Review` -> `Study`
  - `Cards` -> `Manage`
  - `Import / Export` -> `Transfer`
- Introduced a single routed create entry point in `FlashcardsManager`:
  - `routeToCreateEntryPoint()` now switches to `Manage` and emits `openCreateSignal`.
  - `ManageTab` consumes `openCreateSignal` and opens `FlashcardCreateDrawer`.
  - Review secondary create CTAs now route through this shared path instead of local divergent behavior.
- Standardized canonical create copy to `"Create card"` across:
  - Review top CTA and no-cards state CTAs
  - Manage empty-state primary CTA
  - Manage floating create button tooltip.
- Added Stage 1 regression test coverage:
  - `FlashcardsManager.consistency.test.tsx` validates `Study/Manage/Transfer` labels and routed create-entry behavior.
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/__tests__/FlashcardsManager.consistency.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.cram-mode.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx` (pass: `5` files, `10` tests)
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/__tests__/FlashcardsManager.consistency.test.tsx src/components/Flashcards/hooks/__tests__/useFlashcardShortcuts.test.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.save.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/KeyboardShortcutsModal.rating-scale.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.cram-mode.test.tsx` (pass: `14` files, `24` tests)

## Stage 2: Shared Drawer and Action Standards
**Goal**: Normalize panel dimensions and action affordances across create/edit/move flows.
**Success Criteria**:
- Shared drawer sizing tokens are introduced and used by Create/Edit/Move drawers.
- Footer action ordering (cancel, secondary, primary) is consistent for all flashcard drawers.
- Form spacing and section headers follow shared UI conventions.
**Tests**:
- Component tests asserting shared size tokens and consistent footer controls.
- Visual regression tests across desktop/mobile widths.
- Accessibility tests for focus order and escape/close interactions.
**Status**: In Progress

**Progress Notes (2026-02-18)**:
- Introduced shared drawer width token:
  - `FLASHCARDS_DRAWER_WIDTH_PX` in `constants/drawer-tokens.ts`.
- Applied shared width token to all three drawer workflows:
  - `FlashcardCreateDrawer`
  - `FlashcardEditDrawer`
  - `ManageTab` Move drawer.
- Normalized footer action ordering:
  - Create: `Cancel -> Create & Add Another -> Create`
  - Edit: `Cancel -> Delete -> Save`
  - Move: `Cancel -> Move`
- Added token usage assertions in existing component tests:
  - `FlashcardCreateDrawer.cloze-help.test.tsx`
  - `FlashcardEditDrawer.scheduling-metadata.test.tsx`
  - `ManageTab.undo-stage3.test.tsx`
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx` (pass: `3` files, `4` tests)
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/__tests__/FlashcardsManager.consistency.test.tsx src/components/Flashcards/hooks/__tests__/useFlashcardShortcuts.test.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.reset-scheduling.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.save.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/KeyboardShortcutsModal.rating-scale.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.undo-stage3.test.tsx src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.cram-mode.test.tsx` (pass: `14` files, `24` tests)

## Stage 3: Flashcards Pattern Documentation
**Goal**: Prevent reintroduction of inconsistencies via lightweight internal standards.
**Success Criteria**:
- Flashcards UI conventions documented in a short design note linked from feature docs.
- New PR checklist items include CTA placement, naming consistency, and drawer standards.
- At least one lint/test guard exists for core pattern invariants (labels, action keys, token usage).
**Tests**:
- Docs link checks and CI validation for updated references.
- Unit test or static rule enforcing shared drawer token usage.
- Regression tests covering primary CTA visibility rules.
**Status**: Not Started

## Dependencies

- Stage 1 decisions should coordinate with product naming in existing route navigation.
- Stage 2 relies on shared UI token availability in the frontend package.
- Stage 3 should reflect outcomes from H8 visual simplification work.
