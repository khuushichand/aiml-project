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
**Status**: Complete

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
**Progress Update (2026-02-18)**:
- Completed: deterministic per-attempt answer-option shuffling with correctness mapping preserved.
- Completed: deterministic draw-N question pools for practice/review sessions (configurable pool size with test seed override).
- Completed: optional per-question timer in practice mode with auto-advance and timer guidance.
**Status**: Complete

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
**Progress Update (2026-02-18)**:
- Completed: quiz question/explanation rendering migrated to safe markdown component across Take and Results surfaces.
- Completed: fill-blank scoring expanded on the frontend for alternates (`answer1 || answer2`), fuzzy tokens (`~answer`, `~0.85:answer`), and JSON config (`accepted_answers`, `fuzzy`, `fuzzy_threshold`) for practice/review feedback and learner-facing answer display.
- Completed: targeted regression coverage for frontend markdown rendering surfaces and fill-blank parsing/matching behavior.
- Validated: backend ChaChaNotesDB grading path already supports these fill-blank variants (`tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py` passing).
- Completed: first-class schema/API/UI support for `multi_select` and `matching` question types, including quiz service typing and authoring/duplication/review rendering paths.
- Completed: backward-compatible DB migrations for quiz question-type expansion (`V22->V23` for `multi_select`, `V23->V24` for `matching`) plus migration regression coverage (`test_quiz_schema_migration_v23_to_v24_supports_matching`).
- Completed: targeted frontend regression coverage for new question-type payload shaping and duplication behavior:
  - `apps/packages/ui/src/components/Quiz/tabs/__tests__/CreateTab.flexible-composition.test.tsx`
  - `apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx`
- Validation notes:
  - Passing: `python -m pytest -q tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py`
  - Passing: `bunx vitest run src/components/Quiz/tabs/__tests__/CreateTab.flexible-composition.test.tsx src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx` (run from `apps/packages/ui`)
  - Passing: `python -m pytest -q tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py` (module now self-disables reading-digest worker/scheduler during import to avoid heavyweight test startup deps)
**Status**: Complete

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
**Progress Update (2026-02-18)**:
- Completed: `ManageTab` now imports `tldw.quiz.export.v1` payloads through `POST /api/v1/quizzes/import/json` (single request), and reports partial-import failures from server-side per-item/per-question results.
- Completed: `ManageTab` now provides a share action that copies a direct retake URL (`/quiz?tab=take&start_quiz_id=...`) for assignment/distribution workflows.
- Completed: print-first quiz output from `ManageTab` using browser print handoff with print-safe markup/styles.
- Completed: targeted UI regression coverage for import/share/print flows in `apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx`.
- Completed: server-side JSON import path at `POST /api/v1/quizzes/import/json` with per-quiz/per-question import result reporting.
- Completed: backend round-trip coverage validating export-compatible payload re-import and grading parity:
  - `tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py::test_quiz_json_import_roundtrip`
- Completed: explicit assignment semantics end-to-end for shared links:
  - `ManageTab` share action now enforces multi-user role gating (`owner`, `admin`, `lead`) before link issuance.
  - Shared links now carry optional `assignment_due_at`, `assignment_note`, and `assigned_by_role` metadata.
  - `QuizPlayground` and Take-tab handoff parsing now preserves assignment metadata and classifies link origin as assignment context.
  - `TakeQuizTab` now renders assignment context (due date, note, assigned-by role, past-due warning) in list/start flows.
  - Targeted regression coverage added for assignment parsing/navigation/display:
    - `apps/packages/ui/src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx`
    - `apps/packages/ui/src/services/__tests__/quiz-flashcards-handoff.test.ts`
    - `apps/packages/ui/src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx`
    - `apps/packages/ui/src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx`
  - Validation: `cd apps/packages/ui && bunx vitest run src/services/__tests__/quiz-flashcards-handoff.test.ts src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx`
**Status**: Complete

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
**Progress Update (2026-02-18)**:
- Completed: end-to-end hint metadata support across quiz schemas, DB storage/migrations (V24->V25), authoring/import/export paths, generator output normalization, and take/results rendering.
- Completed: graded-attempt scoring applies per-question hint penalties only when `hint_used` is true on a correct answer, and reports applied deduction in attempt results.
- Completed: source citation support across question/attempt contracts with persistence in `quiz_questions.source_citations_json`; citations now render in Take/Results review surfaces with source link resolution (`source_url` or `/media?id=...&chunk_id=...&t=...` fallback).
- Completed: duplication/export payload parity for citations in `ManageTab` and queue validation updates for advanced answer shapes (`multi_select`, `matching`) in submission retry storage.
- Completed: citation link behavior is hardened to reject unsafe direct URL schemes (`javascript:`/invalid) and fall back to internal media deep links when available.
- Completed: dedicated citation integrity coverage now verifies create/list/import/attempt round-trips and per-question citation propagation into graded answers.
- Completed: dedicated component coverage now validates citation rendering and link target behavior in `SourceCitations`.
- Validation:
  - Passing: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/ChaChaNotesDB/test_quizzes_basic.py tldw_Server_API/tests/Quizzes/test_quizzes_endpoint_integration.py`
  - Passing: `cd apps/packages/ui && bunx vitest run src/components/Quiz/components/__tests__/SourceCitations.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx --config vitest.config.ts`
  - Passing: `cd apps/packages/ui && bunx vitest run src/components/Quiz/hooks/__tests__/quizSubmissionQueue.test.ts src/components/Quiz/tabs/__tests__/ManageTab.bulk-duplicate.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx`
**Status**: Complete

## Dependencies

- Practice/review mode UX should align with `IMPLEMENTATION_PLAN_quiz_page_01_take_quiz_tab_2026_02_18.md` and `IMPLEMENTATION_PLAN_quiz_page_05_results_analytics_tab_2026_02_18.md`.
- Sharing/import/export contracts should align with `IMPLEMENTATION_PLAN_quiz_page_04_manage_quiz_tab_2026_02_18.md`.
