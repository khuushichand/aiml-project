# Implementation Plan: Quiz Page - Performance and Perceived Speed

## Scope

Components: quiz queries/mutations (TanStack Query), loading states, results quiz-name mapping strategy
Finding IDs: `10.1` through `10.4`

## Finding Coverage

- Mutation responsiveness: `10.1`
- Query freshness/caching policy: `10.2`
- Data-fetch scope optimization: `10.3`
- Loading-state quality: `10.4`

## Stage 1: Query and Fetch Scope Optimization
**Goal**: Reduce unnecessary network work without stale UX.
**Success Criteria**:
- Set explicit `staleTime` and refetch policy for quiz list queries.
- Remove blanket `limit: 200` quiz fetch from Results where avoidable.
- Prefer denormalized quiz metadata in attempt responses or on-demand lookup.
**Tests**:
- Query tests for stale/refetch behavior on tab switches.
- Integration tests for results rendering with reduced quiz metadata fetch.
- Performance baseline comparison for request counts before/after.
**Status**: Complete

## Stage 2: Optimistic Mutation Paths
**Goal**: Improve perceived speed for create/update/delete operations.
**Success Criteria**:
- Add optimistic updates for safe mutations with rollback on failure.
- UI clearly indicates optimistic/pending states and rollback outcomes.
- Optimistic behavior remains consistent with undo/delete semantics.
**Tests**:
- Mutation tests for optimistic cache write/rollback cycles.
- Integration tests for user-visible state during slow network conditions.
- Regression tests for conflict/error handling with optimistic paths.
**Status**: Complete

## Stage 3: Skeleton-Based Loading States
**Goal**: Replace non-informative spinners with layout-revealing loading placeholders.
**Success Criteria**:
- Introduce Ant `Skeleton` patterns for cards, tables, and detail panes.
- Skeleton variants mirror final layout across major tabs.
- Loading transitions avoid major layout shift.
**Tests**:
- Component tests for skeleton render conditions.
- Visual regression tests comparing loading and loaded layout continuity.
- Accessibility checks for loading announcements where needed.
**Status**: Complete

## Dependencies

- Optimistic behavior should reuse error-recovery patterns from `IMPLEMENTATION_PLAN_quiz_page_11_error_handling_edge_cases_2026_02_18.md`.
- Query-scope changes must not break analytics correctness in `IMPLEMENTATION_PLAN_quiz_page_05_results_analytics_tab_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added explicit query caching policy in `useQuizQueries`:
    - `useQuizzesQuery`, `useQuizQuery`, `useQuestionsQuery`: `staleTime: 30_000`, `refetchOnWindowFocus: false`.
    - `useAttemptsQuery`, `useAllAttemptsQuery`, `useAttemptQuery`: `staleTime: 30_000`, `refetchOnWindowFocus: false`.
  - Reduced blanket fetch scope in `ResultsTab`:
    - replaced fixed `limit: 200` quiz lookup with dynamic limit derived from attempted quiz cardinality (`20..100` range).
    - quiz filter options now derive from attempted quiz IDs with resilient fallback labels (`Quiz #id`) when lookup data is missing.
  - Added query-configuration test coverage in `useQuizQueries.performance.test.ts`.

- Stage 2 completed:
  - Added optimistic mutation paths for quiz-level create/update/delete in `useQuizQueries`:
    - `useCreateQuizMutation`: optimistic temp row insertion on page-0 list caches + replacement on success + rollback on error.
    - `useUpdateQuizMutation`: optimistic patching of list/detail caches + rollback on error.
    - `useDeleteQuizMutation`: optimistic list removal + detail cache removal + rollback on error.
  - Preserved eventual consistency by active-query invalidation on settled mutation lifecycle.
  - Added mutation lifecycle configuration tests in `useQuizQueries.performance.test.ts`.

- Stage 3 completed:
  - Replaced spinner-only loading with layout-preserving skeletons in major quiz tabs:
    - `TakeQuizTab`: list/loading skeleton (`take-loading-skeleton`).
    - `ManageTab`: list/loading skeleton (`manage-loading-skeleton`).
    - `ResultsTab`: page-level and details-modal skeletons (`results-loading-skeleton`, `results-detail-loading-skeleton`).
  - Added/updated tests validating skeleton render conditions:
    - `ResultsTab.filters-retake.test.tsx`
    - `TakeQuizTab.list-controls.test.tsx`
    - `ManageTab.undo-accessibility.test.tsx`

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/hooks/__tests__/useQuizQueries.performance.test.ts src/components/Quiz/tabs/__tests__/ResultsTab.filters-retake.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.export.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx src/components/Quiz/tabs/__tests__/ManageTab.undo-accessibility.test.tsx`
