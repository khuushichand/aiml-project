# Implementation Plan: Quiz Page - Results and Analytics Tab

## Scope

Components: `ResultsTab`, attempt history list/table, quiz metadata mapping, analytics summary and charts
Finding IDs: `5.1` through `5.7`

## Finding Coverage

- Attempt-level review and learning loop closure: `5.1`
- Filtering and quick actions: `5.2`, `5.5`
- Analytics correctness and pass/fail logic: `5.4`, `5.7`
- Trend and portability features: `5.3`, `5.6`

## Stage 1: Attempt Drill-Down Details
**Goal**: Restore ability to review question-by-question outcomes for any past attempt.
**Success Criteria**:
- Attempt rows include `View Details` action.
- Details view shows answers, correctness, explanations, and elapsed time context.
- Details are accessible both immediately post-submit and from historical results.
**Tests**:
- Integration tests for row action to detail view navigation/loading.
- Component tests for answer breakdown rendering by question type.
- Regression tests ensuring historical attempts render with existing schema versions.
**Status**: Complete

## Stage 2: Filtering and Retake Workflow
**Goal**: Make large attempt histories navigable and actionable.
**Success Criteria**:
- Add filters for quiz, date range, and pass/fail status.
- Add per-attempt `Retake` action that deep-links to Take tab with selected quiz context.
- Filter and pagination state are preserved across tab switches.
**Tests**:
- Query tests for filter parameter serialization and server requests.
- Integration tests for retake navigation with `startQuizId` handling.
- Component tests for filter reset and empty-state messaging.
**Status**: Complete

## Stage 3: Analytics Correctness and Trend Views
**Goal**: Ensure displayed statistics reflect true all-time performance.
**Success Criteria**:
- Replace current-page-only stats with aggregate stats endpoint or full dataset aggregation.
- Pass/fail status uses each quiz's actual `passing_score` rather than hardcoded `70`.
- Add time-series trend visualization (line chart/sparkline) and score distribution summary.
**Tests**:
- API contract tests for stats endpoint/aggregation fields.
- Unit tests for pass/fail computation with mixed quiz thresholds.
- Component tests for trend chart rendering and empty-data behavior.
**Status**: Complete

## Stage 4: Results Export
**Goal**: Support external reporting and learner progress archiving.
**Success Criteria**:
- Add CSV export for filtered attempt history (PDF optional follow-up).
- Export respects currently applied filters/date ranges.
- Export filenames and schema include date bounds and quiz identifiers.
**Tests**:
- Integration tests for export with and without filters.
- Schema tests for stable CSV headers/order.
- UI tests for export error handling and download feedback.
**Status**: Complete

## Dependencies

- Retake navigation should align with `IMPLEMENTATION_PLAN_quiz_page_06_cross_tab_interaction_information_flow_2026_02_18.md`.
- Attempt detail rendering should align with resilience/error states in `IMPLEMENTATION_PLAN_quiz_page_11_error_handling_edge_cases_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added `View Details` action on attempt rows in `ResultsTab`.
  - Added attempt-detail modal with quiz metadata, timestamps, elapsed time, and per-question answer breakdown.
  - Wired detail fetch to `getAttempt(..., { include_questions, include_answers })` via `useAttemptQuery` params.
  - Added fallback rendering for historical attempts that lack question snapshots (`Question #<id>` label path).
  - Added test coverage in `ResultsTab.details.test.tsx` for both snapshot and fallback scenarios.

- Stage 2 completed:
  - Added Results filters: quiz selector, pass/fail selector, and date-range selector (all/7d/30d/90d).
  - Added per-attempt `Retake` action and wired `ResultsTab -> QuizPlayground -> TakeQuizTab` navigation using `startQuizId`.
  - Persisted Results filter + pagination state to session storage and restored it on remount/tab return.
  - Added no-match filtered empty state messaging.
  - Added test coverage in `ResultsTab.filters-retake.test.tsx` for query filter restoration, retake callback, filtered empty state, and pagination restoration.

- Stage 3 completed:
  - Added all-attempt aggregation hook (`useAllAttemptsQuery`) that paginates through all attempt pages (200/page) so analytics no longer reflect only a single page slice.
  - Updated Results pass/fail determination to use per-quiz `passing_score` (with explicit default fallback) in row badges and pass/fail filtering.
  - Added score trend visualization (recent-attempt sparkline) and score distribution summary bars to Results analytics.
  - Added test coverage for per-quiz pass-threshold filtering and trend-chart rendering in `ResultsTab.filters-retake.test.tsx`.

- Stage 4 completed:
  - Added `Export CSV` action in Results filter controls.
  - CSV export now respects active filters (quiz/pass/date) by exporting the filtered attempt set.
  - Export schema includes filter metadata columns (`filter_quiz_id`, `filter_pass_state`, `filter_date_range`, `filter_date_start_iso`, `filter_date_end_iso`).
  - Export filename includes quiz/date context (`quiz-results-<quiz-scope>-<date-scope>-<YYYY-MM-DD>.csv`).
  - Added test coverage in `ResultsTab.export.test.tsx` for filtered export behavior and CSV metadata columns.

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.filters-retake.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.export.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.submission-retry.test.tsx src/components/Quiz/hooks/__tests__/quizSubmissionQueue.test.ts`
