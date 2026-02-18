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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Reorder controls should be shared with Manage edit patterns from `IMPLEMENTATION_PLAN_quiz_page_04_manage_quiz_tab_2026_02_18.md`.
- Validation and helper messaging should align with a11y requirements in `IMPLEMENTATION_PLAN_quiz_page_13_accessibility_2026_02_18.md`.
