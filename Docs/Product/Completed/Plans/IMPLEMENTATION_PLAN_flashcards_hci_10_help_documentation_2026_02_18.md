# Implementation Plan: Flashcards H10 - Help and Documentation

## Scope

Route/components: `tabs/ReviewTab.tsx`, `components/FlashcardCreateDrawer.tsx`, `components/FlashcardEditDrawer.tsx`, `tabs/ImportExportTab.tsx`, feature docs under `Docs/`  
Finding IDs: `H10-1` through `H10-3`

## Finding Coverage

- No first-use explanation of spaced repetition and flashcards value: `H10-1`
- Cloze syntax guidance is missing where users author cloze cards: `H10-2`
- Import format documentation is incomplete and hard to discover: `H10-3`

## Stage 1: First-Run Onboarding for Flashcards
**Goal**: Provide concise first-use guidance that drives immediate successful action.
**Success Criteria**:
- Empty review state includes quick explanation of spaced repetition and expected daily workflow.
- First-run actions present clear paths: create first card, import deck, generate from text.
- Onboarding can be dismissed and reopened from a help entry point.
**Tests**:
- Component tests for first-run onboarding visibility and dismiss persistence.
- E2E tests for each first-run branch completing successfully.
- Accessibility tests for onboarding focus order and screen-reader copy.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added first-run onboarding guidance card to the Study tab empty state with concise spaced-repetition workflow copy.
- Added explicit first-run action CTAs for create, import, and generate-from-text pathways.
- Added persisted onboarding dismissal preference with an inline "Show study guide" reopen entry point.

**Validation (2026-02-18)**:
- `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`
- `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.cram-mode.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.edit-in-review.test.tsx`

## Stage 2: Contextual Authoring and Import Help
**Goal**: Deliver help exactly where users need it during card creation and data transfer.
**Success Criteria**:
- Cloze helper text and examples appear inline when cloze model is selected in create/edit drawers.
- Import panel includes expandable accepted-column reference and delimiter guidance.
- Error messages link directly to relevant help snippets where applicable.
**Tests**:
- Component tests for conditional help visibility by model/import mode.
- Integration tests for help links from validation/import errors.
- Regression tests ensuring help UI does not block normal workflows.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Verified existing inline cloze syntax helper + validation coverage in both create and edit drawers.
- Added an expandable import help accordion with dedicated sections for accepted columns, delimiter troubleshooting, cloze syntax, and JSON field mapping.
- Added contextual "View format help" links from import error guidance to jump users directly to the relevant help section.

**Validation (2026-02-18)**:
- `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx -u`
- `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`

## Stage 3: Durable Documentation and Support Loop
**Goal**: Keep in-app guidance and docs synchronized as flashcards features expand.
**Success Criteria**:
- A dedicated flashcards UX help doc covers review ratings, scheduling basics, cloze syntax, and import/export formats.
- In-app help links target versioned docs sections rather than generic pages.
- Docs update checklist is added to PR workflow for flashcards UI/API changes.
**Tests**:
- Link integrity tests for all in-app documentation anchors.
- Docs smoke test to verify examples align with current accepted payload fields.
- Process test/checklist validation in CI or PR template.
**Status**: Complete

**Implementation Notes (2026-02-18)**:
- Added dedicated user guide: `Docs/User_Guides/Flashcards_Study_Guide.md` (study loop, ratings/scheduling, cloze syntax, import/export, troubleshooting).
- Added centralized versioned help URLs + section anchors in `apps/packages/ui/src/components/Flashcards/constants/help-links.ts`.
- Wired in-app doc links from Study onboarding and Transfer import help surfaces to section-specific anchors.
- Added flashcards docs-sync checklist item to `.github/pull_request_template.md`.

**Validation (2026-02-18)**:
- `source .venv/bin/activate && cd apps/packages/ui && bunx vitest run src/components/Flashcards/constants/__tests__/help-links.test.ts src/components/Flashcards/tabs/__tests__/ImportExportTab.import-results.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx`

## Dependencies

- Stage 1 onboarding should incorporate H2 terminology decisions and H7 generation workflow.
- Stage 2 helper patterns should reuse H5 validation components and copy tokens.
- Stage 3 docs ownership should be assigned to flashcards maintainers to avoid drift.
