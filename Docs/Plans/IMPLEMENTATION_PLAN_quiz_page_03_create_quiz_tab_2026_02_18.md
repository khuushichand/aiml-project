# Implementation Plan: Quiz Page - Create Quiz Tab

## Scope

Components: `CreateTab`, quiz creation form state, question editor rows/options, save mutation pipeline
Finding IDs: `3.1` through `3.7`

## Finding Coverage

- Authoring order and structure control: `3.1`, `3.3`
- Draft resilience and unsaved-change safety: `3.2`
- Author feedback clarity: `3.4`, `3.6`, `3.7`
- Save efficiency and transparency: `3.5`

## Stage 1: Draft Safety and Unsaved-Changes Guard
**Goal**: Prevent author data loss during long quiz creation sessions.
**Success Criteria**:
- Local draft autosave persists quiz and question form state.
- `beforeunload` and tab-switch warnings appear when unsaved changes exist.
- Draft recovery prompt appears when returning to Create tab.
**Tests**:
- Hook/component tests for draft save/restore/clear lifecycle.
- Integration tests for unsaved-change prompts on route/tab changes.
- Failure-path tests for storage-unavailable user messaging.
**Status**: Complete

## Stage 2: Flexible Question Composition
**Goal**: Make question authoring reflect backend schema capabilities.
**Success Criteria**:
- Question list supports reorder via drag-and-drop or move up/down controls.
- Multiple-choice options become dynamic with min=2 and max=6.
- Option removal/addition preserves correct-answer mapping safely.
- Time limit label explicitly communicates minutes (or equivalent explicit control).
**Tests**:
- Component tests for reorder controls and resulting `order_index` updates.
- Validation tests for dynamic option count bounds.
- Integration tests for correct-answer stability after reorder/add/remove operations.
**Status**: Complete

## Stage 3: Preview and Explanation Transparency
**Goal**: Improve author confidence before final save.
**Success Criteria**:
- Add read-only learner preview mode from Create tab.
- Explanation field includes helper text clarifying post-submit learner visibility.
- Preview reflects all supported question types and explanations accurately.
**Tests**:
- Component tests for preview rendering and mode switching.
- Snapshot/integration tests comparing edit model to preview output.
- Field help-text tests for explanation visibility messaging.
**Status**: Complete

## Stage 4: Save Pipeline Feedback and Throughput
**Goal**: Reduce perceived latency and ambiguity for large quiz saves.
**Success Criteria**:
- Save flow shows progress state (e.g., "Saving question 3 of 20") when using sequential calls.
- Evaluate and implement batch save API path if backend supports it.
- Partial failure handling reports exactly which question(s) failed.
**Tests**:
- Mutation tests for progress state transitions.
- Integration tests for partial failure recovery messaging.
- API contract tests for batch path (if implemented) and fallback path.
**Status**: Complete

## Dependencies

- Reorder controls should be shared with Manage edit patterns from `IMPLEMENTATION_PLAN_quiz_page_04_manage_quiz_tab_2026_02_18.md`.
- Validation and helper messaging should align with a11y requirements in `IMPLEMENTATION_PLAN_quiz_page_13_accessibility_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added local draft lifecycle in `CreateTab`:
    - autosave to local storage (`quiz-create-draft-v1`) with debounce.
    - restore/discard recovery prompt when a prior draft exists.
    - draft clearing after successful save or clean-state reset.
  - Added unsaved-change safety:
    - `beforeunload` protection while Create tab is dirty.
    - dirty-state callback from `CreateTab` to `QuizPlayground`.
    - tab-switch confirmation in `QuizPlayground` before leaving dirty Create tab.
  - Added storage failure user feedback:
    - inline warning when draft autosave storage is unavailable.
  - Added/expanded tests:
    - `CreateTab.draft-safety.test.tsx` for recovery, unload protection, and storage-unavailable warning.
    - `QuizPlayground.navigation.test.tsx` for dirty-create tab-switch confirmation behavior.

- Stage 2 completed:
  - Added question reordering controls in `CreateTab`:
    - move up/down actions per question card.
    - persisted order reflected by `order_index` at save time.
  - Added dynamic multiple-choice option composition:
    - add/remove options with bounds `min=2`, `max=6`.
    - remove-option flow safely remaps `correct_answer` index.
    - multiple-choice save validation enforces at least two non-empty options.
  - Added explicit option-level controls and ARIA labels for option correctness/remove actions.
  - Added tests in `CreateTab.flexible-composition.test.tsx`:
    - reorder persistence/order-index assertions.
    - min/max option bound behavior.
    - correct-answer remap behavior after option removal.

- Stage 3 completed:
  - Added read-only learner preview mode in `CreateTab`:
    - preview action opens a modal showing quiz title/description and per-question render output.
    - preview rendering now covers all supported authoring types (`multiple_choice`, `true_false`, `fill_blank`).
    - explanation text is included in preview when present.
  - Added explanation visibility helper text under question explanation input:
    - "Shown to the learner after they submit the quiz."
  - Added tests in `CreateTab.preview.test.tsx`:
    - helper-text visibility assertion.
    - preview rendering assertions across mixed question types and explanation content.

- Stage 4 completed:
  - Added save pipeline progress state in `CreateTab`:
    - explicit "Creating quiz..." state before question writes.
    - incremental "Saving question X of Y..." progress state during sequential question creation.
    - progress bar with ARIA label for save progression.
  - Added save-flow interaction lock while persisting:
    - disables preview/edit/reorder/add/remove interactions during save.
  - Added partial-failure reporting:
    - catches question-level save failures and reports the exact failed question index.
  - Evaluated batch save feasibility:
    - backend currently exposes per-question create (`POST /api/v1/quizzes/{quiz_id}/questions`) and does not expose a batch question-create endpoint, so sequential save with progress/failure reporting is the implemented path.
  - Added tests in `CreateTab.save-progress.test.tsx`:
    - progress-state visibility during in-flight question save.
    - exact failed question index messaging for partial save failure.

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.draft-safety.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.flexible-composition.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.preview.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.save-progress.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.validation-accessibility.test.tsx src/components/Quiz/tabs/__tests__/ManageTab.undo-accessibility.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.filters-retake.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.export.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.submission-retry.test.tsx src/components/Quiz/hooks/__tests__/quizSubmissionQueue.test.ts`
