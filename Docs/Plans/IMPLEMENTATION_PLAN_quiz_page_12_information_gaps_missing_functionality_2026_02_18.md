# Implementation Plan: Quiz Page - Information Gaps and Missing Functionality

## Scope

Components: quiz modes, randomization engine, question types/content rendering, sharing/import/export/hints/citation features
Finding IDs: `12.1` through `12.13`

## Finding Coverage

- Study mode variants: `12.1`, `12.2`
- Randomization and pacing controls: `12.3`, `12.4`, `12.11`
- Richness of question content/types and grading: `12.5`, `12.6`, `12.9`
- Portability, sharing, and offline support: `12.7`, `12.10`, `12.12`
- Guidance quality and traceability: `12.8`, `12.13`

## Stage 1: New Learning Modes (Practice and Review)
**Goal**: Add non-graded and immediate-feedback paths for study workflows.
**Success Criteria**:
- Practice mode supports immediate correctness feedback per question.
- Review mode allows browsing questions/answers/explanations without graded attempt creation.
- Mode selection is explicit and persisted per user/session preference.
**Tests**:
- Integration tests for practice immediate feedback behavior.
- Component tests for review-mode read-only rendering.
- Regression tests confirming graded mode remains unchanged.
**Status**: Not Started

## Stage 2: Randomization and Pacing Enhancements
**Goal**: Improve retake validity and configurable assessment difficulty.
**Success Criteria**:
- Answer option order shuffles per attempt while preserving correctness mapping.
- Support draw-N-of-M question pools with deterministic seed option for testing.
- Optional per-question timer supports auto-advance and clear UX safeguards.
**Tests**:
- Unit tests for shuffle determinism and correctness mapping.
- Integration tests for pool draw constraints and attempt reproducibility.
- Timer behavior tests for per-question expiry and transition handling.
**Status**: Not Started

## Stage 3: Content and Question-Type Expansion
**Goal**: Increase pedagogical range and richer source expression.
**Success Criteria**:
- Question text and explanations support markdown/rich media rendering safely.
- Add prioritized new question types (multi-select, matching) with grading support.
- Fill-blank scoring supports multiple accepted answers and/or fuzzy matching.
**Tests**:
- Rendering tests for markdown/media safety and formatting.
- Scoring tests for new question types and partial/fuzzy match behavior.
- Migration tests for backward compatibility with existing quizzes.
**Status**: Not Started

## Stage 4: Sharing, Import/Export, and Printability
**Goal**: Improve portability and collaborative workflows.
**Success Criteria**:
- Add quiz sharing/assignment primitives for multi-user mode.
- Add JSON import path compatible with planned export schema.
- Add print-friendly layout (`@media print`) and/or PDF export path.
**Tests**:
- API/UI tests for share/assignment permissions and due-date handling.
- Import/export round-trip tests validating schema compatibility.
- Visual tests for printable output readability.
**Status**: Not Started

## Stage 5: Hints and Source Citation in Explanations
**Goal**: Improve learning guidance quality and evidence traceability.
**Success Criteria**:
- Questions can include optional hints with configurable scoring penalty.
- Generated explanations can include source chunk citations/links.
- Citation links resolve to source location in associated media view.
**Tests**:
- Scoring tests for hint penalty application.
- Component tests for citation rendering and link behavior.
- Integration tests validating source-reference integrity.
**Status**: Not Started

## Dependencies

- Practice/review mode UX should align with `IMPLEMENTATION_PLAN_quiz_page_01_take_quiz_tab_2026_02_18.md` and `IMPLEMENTATION_PLAN_quiz_page_05_results_analytics_tab_2026_02_18.md`.
- Sharing/import/export contracts should align with `IMPLEMENTATION_PLAN_quiz_page_04_manage_quiz_tab_2026_02_18.md`.
