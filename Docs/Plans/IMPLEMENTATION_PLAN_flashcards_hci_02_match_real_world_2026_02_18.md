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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Copy choices should align with H10 onboarding content to avoid contradictory explanations.
- Validation and helper components should reuse H5 prevention logic for cloze syntax.
- Rating explanation needs timing alignment with H1 post-rating status feedback.
