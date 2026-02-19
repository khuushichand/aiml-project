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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

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
**Status**: Complete

## Dependencies

- Cross-tab handoff contracts should align with `IMPLEMENTATION_PLAN_quiz_page_06_cross_tab_interaction_information_flow_2026_02_18.md`.
- Preview/edit destination should reuse editing semantics in `IMPLEMENTATION_PLAN_quiz_page_04_manage_quiz_tab_2026_02_18.md` where possible.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Replaced fixed `results_per_page=100` assumptions with paged media loading (`MEDIA_PAGE_SIZE=50`) and incremental `Load More`.
  - Added server-side search behavior (`searchMedia`) when a query is entered and list behavior (`listMedia`) otherwise.
  - Added loaded/total status messaging:
    - `Showing N of X media items` when total is known and truncated.
    - `Showing N media items` fallback when total is unknown.
  - Preserved selected media value while loading additional pages by maintaining a merged item map.

- Stage 2 completed:
  - Removed fake fixed progress bar (`50%`) and replaced with spinner + truthful duration hint text.
  - Added generation cancellation via `AbortController` and wired abort signal through:
    - `GenerateTab` -> `useGenerateQuizMutation` -> `generateQuiz(..., { signal })`.
  - Added `Cancel` action during generation and ensured cancellation:
    - stops in-flight request,
    - resets pending UI state,
    - preserves form inputs and selected media,
    - avoids success navigation side effects.

- Stage 3 completed:
  - Added difficulty guidance with explicit descriptions for `easy`, `medium`, `hard`, and `mixed`.
  - Added source-length-aware question count recommendation text:
    - generic recommendation when source length is unknown,
    - dynamic recommendation when media word count is available.
  - Added optional `Focus Topics` field (`Select` tags mode) and sent normalized `focus_topics` in generation payload when provided.

- Stage 4 completed:
  - Replaced auto-navigation to Take tab with a preview-first checkpoint card:
    - shows generated quiz name and question count,
    - offers explicit actions: `Take Quiz`, `Review in Manage`, `Generate Another`.
  - Passed generated quiz ID through explicit navigation action (`startQuizId` + `highlightQuizId`) instead of implicit auto-transition.
  - Added actionable error messaging by surfacing server detail when available (`Failed to generate quiz: <detail>`).

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/tabs/__tests__/GenerateTab.media-selection.test.tsx src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx`
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/**/*.test.tsx`
