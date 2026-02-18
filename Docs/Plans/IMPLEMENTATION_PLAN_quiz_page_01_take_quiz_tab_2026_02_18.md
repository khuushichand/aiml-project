# Implementation Plan: Quiz Page - Take Quiz Tab

## Scope

Components: `TakeQuizTab`, `useQuizTimer`, `useQuizAutoSave`, quiz list cards, answer input components
Finding IDs: `1.1` through `1.10`

## Finding Coverage

- Start-flow information clarity: `1.1`, `1.6`, `1.8`, `1.10`
- In-attempt reliability and persistence: `1.2`, `1.3`
- Navigation and completion guidance: `1.4`, `1.5`
- Input discoverability and list scalability: `1.7`, `1.9`

## Stage 1: Pre-Quiz Commit and Metadata Clarity
**Goal**: Ensure users understand quiz expectations before attempt creation.
**Success Criteria**:
- "Start Quiz" opens a pre-quiz interstitial with total questions, time limit, passing score, and difficulty.
- Interstitial supports explicit `Begin` and `Cancel` paths without creating an attempt on cancel.
- Quiz cards display passing score, difficulty, source media link/name, creation date, and last score when available.
- Retake behavior is explained via tooltip or helper text.
**Tests**:
- Component tests for interstitial open/close and metadata rendering.
- Integration test confirming no attempt API call occurs until `Begin`.
- Component tests for new card metadata and retake behavior text.
**Status**: Complete

## Stage 2: Timer and Autosave Wiring
**Goal**: Activate already-implemented timer/autosave hooks for production behavior.
**Success Criteria**:
- `useQuizTimer` is wired into `TakeQuizTab` with visible countdown in header.
- Timer state uses visual thresholds (normal/warning/danger) and auto-submits on expiry.
- `useQuizAutoSave` restores answers on attempt start, saves on answer changes, and clears on successful submit.
- Local-storage failures show a one-time user-visible warning (aligned with `11.6`).
**Tests**:
- Hook integration tests for countdown transitions and expiry submit call.
- Integration tests for restore/save/clear autosave lifecycle.
- Failure-path test for storage-unavailable warning behavior.
**Status**: Complete

## Stage 3: Navigation and Submission Guardrails
**Goal**: Make long quizzes navigable and submission errors actionable.
**Success Criteria**:
- Add numbered question navigator with jump-to-question support.
- Submit with unanswered questions scrolls and highlights first unanswered item.
- Optional unanswered summary list is shown in submit confirmation area.
- Fill-in-the-blank inputs include explicit answer-format guidance based on backend matching rules.
**Tests**:
- Component tests for navigator button state and question jump behavior.
- Integration test for unanswered submit path focusing first missing question.
- Component tests verifying helper text rendering for fill-in-the-blank.
**Status**: Complete

## Stage 4: List Findability and Pass/Fail Messaging
**Goal**: Improve quiz selection efficiency and remove implicit scoring assumptions.
**Success Criteria**:
- Quiz list supports search and sort (name/date/question count).
- If passing score is undefined, UI explicitly states default policy (or "No passing score set").
- Selection/filter state remains stable across pagination and tab transitions.
**Tests**:
- Query-state tests for search/sort/pagination interaction.
- Component tests for pass/fail message behavior with missing `passing_score`.
- Integration tests for stable list state after tab switches.
**Status**: Complete

## Dependencies

- Timer expiry and autosave behavior should align with retry logic defined in `IMPLEMENTATION_PLAN_quiz_page_11_error_handling_edge_cases_2026_02_18.md`.
- Question navigator patterns should remain consistent with accessibility requirements in `IMPLEMENTATION_PLAN_quiz_page_13_accessibility_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added pre-quiz confirmation interstitial (`Begin`/`Cancel`) before attempt creation.
  - Added quiz metadata in interstitial: question count, time limit, passing score (explicit default), and difficulty (when available).
  - Expanded quiz card metadata with passing score, source media link, creation date, and last score (derived from recent attempts).
  - Added retake behavior tooltip/helper text.

- Stage 2 completed:
  - Wired `useQuizTimer` into active attempt view with warning/danger color states and auto-submit on expiry.
  - Wired `useQuizAutoSave` restore/save/clear flow (restore on attempt start, clear on submit).
  - Added submit double-click guard (`disabled` while pending).
  - Added one-time dismissible warning when autosave storage is unavailable.

- Stage 3 completed:
  - Added question navigator (numbered jump-to-question controls).
  - Added unanswered submit guard with question-number summary and automatic scroll/highlight of first missing question.
  - Added fill-in-the-blank guidance text matching backend behavior (trimmed, case-insensitive exact match).
  - Added test coverage for navigator jump behavior, unanswered guard summary, first-missing highlight, and fill-blank guidance rendering.

- Stage 4 completed:
  - Added quiz-list search control and sort options (newest, name, question count).
  - Persisted list controls state (`page`, `pageSize`, `searchQuery`, `sortBy`) in session storage for remount/tab-transition stability.
  - Made pass/fail fallback policy explicit in results when no quiz-specific passing score exists (`70%` default).
  - Added test coverage for search-query forwarding and explicit default passing-score messaging.

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx`
