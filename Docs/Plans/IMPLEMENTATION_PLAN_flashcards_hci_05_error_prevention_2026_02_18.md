# Implementation Plan: Flashcards H5 - Error Prevention

## Scope

Route/components: `components/FlashcardCreateDrawer.tsx`, `components/FlashcardEditDrawer.tsx`, `tabs/ImportExportTab.tsx`, flashcard validation logic in API schemas/services  
Finding IDs: `H5-1` through `H5-3`

## Finding Coverage

- Cloze syntax is not validated/helped in UI before submit: `H5-1`
- Front/back size and quality constraints are not communicated early: `H5-2`
- Import format and parse errors are not actionable in UI: `H5-3`

## Stage 1: Inline Validation for Authoring
**Goal**: Prevent malformed cards before API submission.
**Success Criteria**:
- Create/Edit forms validate cloze syntax in real time with friendly error text and correction example.
- Front/back fields show character or byte counters with warning thresholds near limits.
- Submit action is blocked only for invalid inputs with explicit field-level messages.
**Tests**:
- Form unit tests for cloze validator success/failure cases.
- Integration tests for limit warnings and submit disable/enable transitions.
- Regression tests for non-cloze templates to ensure no false-positive validation.
**Status**: Not Started

## Stage 2: Import Guardrails and Diagnostics
**Goal**: Catch structural import mistakes before and during upload.
**Success Criteria**:
- Import panel provides clear format rules (accepted columns, delimiters, header assumptions).
- Parse/validation errors show line-level diagnostics and field-specific guidance.
- Partial imports report imported/skipped/error totals in persistent result panel.
**Tests**:
- Integration tests for bad delimiter, malformed row, and encoding error handling.
- Component tests for line error table rendering and summary badges.
- E2E import test covering mixed-validity input and user correction loop.
**Status**: Not Started

## Stage 3: Preventive UX for High-Risk Operations
**Goal**: Reduce accidental invalid state transitions during bulk or advanced actions.
**Success Criteria**:
- Risky operations (bulk edit, schedule reset, large imports) include confirm copy with impact summary.
- Validation rules are consistent between UI and backend schema messages.
- User can resolve all surfaced validation errors without consulting external docs.
**Tests**:
- End-to-end tests for high-risk flows and confirmation messaging.
- Contract tests ensuring backend validation codes map to UI message catalog.
- Accessibility tests for error announcements (`aria-live`) and focus on first invalid field.
**Status**: Not Started

## Dependencies

- Stage 1 and Stage 2 should share error message vocabulary with H2 and H10 documentation.
- Stage 2 depends on API import response carrying structured error metadata.
- Stage 3 confirmation patterns should align with existing bulk delete safety patterns in Cards tab.
