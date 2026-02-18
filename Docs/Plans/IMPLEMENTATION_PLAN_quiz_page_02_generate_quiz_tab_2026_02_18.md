# Implementation Plan: Quiz Page - Generate Quiz Tab

## Scope

Components: `GenerateTab`, media selection query/select controls, generation mutation lifecycle, post-generation routing
Finding IDs: `2.1` through `2.7`

## Finding Coverage

- Source selection scalability: `2.1`
- Trustworthy progress and operation control: `2.2`, `2.3`
- Author guidance and generation intent: `2.4`, `2.5`
- Post-generation review and error feedback: `2.6`, `2.7`

## Stage 1: Scalable Media Selection
**Goal**: Support large media libraries without truncation ambiguity.
**Success Criteria**:
- Replace fixed `results_per_page=100` behavior with server-side search and paged/infinite loading.
- UI communicates truncation/loaded count (e.g., "Showing N of X").
- Selection remains stable when loading additional pages.
**Tests**:
- Query integration tests for paged media loading and search terms.
- Component tests for truncation/count messaging.
- Interaction tests for maintaining selected media across incremental loads.
**Status**: Not Started

## Stage 2: Real Progress and Cancelable Generation
**Goal**: Remove misleading loading states and give users control during long generation.
**Success Criteria**:
- Replace fake `50%` bar with either spinner-only state or real progress updates.
- Add `Cancel` action using `AbortController` wired to `generateQuiz(..., options.signal)`.
- Generation cancel path cleanly resets pending UI state and preserves form inputs.
**Tests**:
- Mutation tests verifying abort signal propagation and cancellation handling.
- Component tests for cancel button visibility/enabled state during pending mutation.
- Integration tests ensuring no success navigation occurs after cancellation.
**Status**: Not Started

## Stage 3: Input Guidance and Focus Topics
**Goal**: Improve quality of generated quizzes by guiding user inputs.
**Success Criteria**:
- Difficulty options include explanatory tooltips.
- Question-count recommendations are shown relative to source size.
- Optional `Focus Topics` field is added and passed to backend request payload.
**Tests**:
- Component tests for tooltip/help text visibility.
- Payload contract tests ensuring `focus_topics` is sent when provided.
- Validation tests for empty/long/multi-topic focus input handling.
**Status**: Not Started

## Stage 4: Preview-First Post-Generation Flow and Actionable Errors
**Goal**: Prevent abrupt tab jumps and improve error diagnosis.
**Success Criteria**:
- Successful generation routes to preview/edit checkpoint before learner-facing take flow.
- Generated quiz ID is carried through navigation context.
- Error toast includes server-provided detail when safe and available.
**Tests**:
- Navigation integration tests for preview-first route flow.
- Component tests confirming generated quiz context is surfaced in next step UI.
- Mutation error tests for detailed message fallback behavior.
**Status**: Not Started

## Dependencies

- Cross-tab handoff contracts should align with `IMPLEMENTATION_PLAN_quiz_page_06_cross_tab_interaction_information_flow_2026_02_18.md`.
- Preview/edit destination should reuse editing semantics in `IMPLEMENTATION_PLAN_quiz_page_04_manage_quiz_tab_2026_02_18.md` where possible.
