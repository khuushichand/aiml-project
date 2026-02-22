# Implementation Plan: Flashcards H2 - Match Between System and Real World

## Scope

Route/components: `tabs/ReviewTab.tsx`, `components/FlashcardCreateDrawer.tsx`, `components/FlashcardEditDrawer.tsx`, `useFlashcardShortcuts.ts`  
Finding IDs: `H2-1` through `H2-3`

## Finding Coverage

- SM-2 terminology and interval semantics unexplained: `H2-1`
- Cloze template terminology lacks syntax guidance: `H2-2`
- Rating scale mapping (0/2/3/5) is not explained in-product: `H2-3`

## Stage 1: Terminology Clarification Layer
**Goal**: Replace opaque scheduler language with plain-language UI copy while preserving power-user detail.
**Success Criteria**:
- Review and card surfaces show plain labels ("memory strength", "next review gap") with optional technical tooltip terms.
- Interval previews include one-line meaning ("Hard = short interval, Easy = longest interval").
- Terms are consistent across review controls, list rows, and drawers.
**Tests**:
- Copy and tooltip component tests for presence/consistency of term mapping.
- Visual regression coverage for labels in compact and expanded modes.
- i18n placeholder tests to ensure labels remain translatable.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Replaced scheduling jargon labels in Cards list surfaces with plain-language terms:
  - `Memory` / `Memory strength` (technical: SM-2 ease factor)
  - `Next gap` / `Next review gap` (technical: SM-2 interval)
  - `Recall runs` (technical: SM-2 repetitions)
  - `Relearns` (technical: SM-2 lapses)
- Added technical SM-2 explanations as tooltips on compact and expanded scheduling metadata chips.
- Updated edit drawer scheduling panel to the same plain-language terms with matching tooltip help text.
- Added review action-area helper sentence clarifying interval intent:
  - `"Again = shortest gap ... Easy = longest gap."`
- Added/updated tests covering terminology changes and review guidance rendering.
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx` (pass: `4` files, `7` tests)

## Stage 2: Cloze and Template Mental Model Alignment
**Goal**: Make card type selection and cloze authoring understandable on first attempt.
**Success Criteria**:
- Create/Edit drawers include cloze syntax hint and working example (`{{c1::...}}`) near template selector.
- Inline helper explains when to choose Basic, Reverse, or Cloze with concrete study scenarios.
- Invalid cloze syntax shows actionable correction guidance.
**Tests**:
- Form validation tests for cloze syntax and helper visibility by model type.
- Interaction tests for switching model type and preserving field content safely.
- Regression tests for drawer submit payload mapping to `model_type`.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added template scenario helper copy to Create/Edit drawers for all three template types:
  - Basic: direct Q/A recall
  - Basic + Reverse: both directions
  - Cloze: hide key words in context.
- Added explicit cloze syntax helper text beside template selection when `model_type = cloze`:
  - `"Cloze syntax: ... {{c1::answer}} ..."`
- Added front-field cloze validation in both Create and Edit drawers:
  - blocks submit when Cloze is selected and no `{{cN::...}}` pattern exists
  - returns actionable correction copy with working syntax example.
- Added focused tests for Create drawer cloze helper visibility + validation and Edit drawer cloze validation behavior.

## Stage 3: Rating Model Explainability
**Goal**: Explain how ratings map to scheduling outcomes without adding cognitive overload.
**Success Criteria**:
- Shortcut/help modal includes explicit `Again=0`, `Hard=2`, `Good=3`, `Easy=5` mapping and rationale.
- Optional "Why these ratings?" inline disclosure is available from the review action area.
- User can complete a first review without encountering unexplained SM-2 jargon.
**Tests**:
- Component tests for rating explanation panel/modal content.
- UX regression tests validating no layout breakage in button group.
- E2E first-run test confirming explanation discoverability in <=1 click.
**Status**: Complete

**Progress Notes (2026-02-18)**:
- Added inline review disclosure (`"Why these ratings?"`) in the review action area.
- Added explicit rating map and rationale copy in disclosure:
  - `Again = 0`, `Hard = 2`, `Good = 3`, `Easy = 5`.
- Added the same explicit rating mapping to the keyboard shortcuts/help modal for the Review tab.
- Added tests validating:
  - review disclosure discoverability and rendered mapping text
  - shortcuts modal rating-scale mapping content.
- Validation:
  - `cd apps/packages/ui && bunx vitest run --config vitest.config.ts src/components/Flashcards/components/__tests__/FlashcardCreateDrawer.cloze-help.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.save.test.tsx src/components/Flashcards/components/__tests__/FlashcardEditDrawer.scheduling-metadata.test.tsx src/components/Flashcards/components/__tests__/KeyboardShortcutsModal.rating-scale.test.tsx src/components/Flashcards/tabs/__tests__/ManageTab.scheduling-metadata.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.analytics-summary.test.tsx src/components/Flashcards/tabs/__tests__/ReviewTab.create-cta.test.tsx` (pass: `7` files, `11` tests)

## Dependencies

- Copy choices should align with H10 onboarding content to avoid contradictory explanations.
- Validation and helper components should reuse H5 prevention logic for cloze syntax.
- Rating explanation needs timing alignment with H1 post-rating status feedback.
