# Implementation Plan: Quiz Page - Cross-Tab Interaction and Information Flow

## Scope

Components: `QuizPlayground`, tab navigation state, inter-tab callbacks and route/query handoff contracts
Finding IDs: `6.1` through `6.5`

## Finding Coverage

- Results-to-take continuity: `6.1`, `6.5`
- Tab persistence and state retention: `6.2`
- Global discoverability and status cues: `6.3`, `6.4`

## Stage 1: Explicit Inter-Tab Navigation Contracts
**Goal**: Remove ambiguous transitions between Generate, Results, and Take experiences.
**Success Criteria**:
- Introduce structured navigation payloads (e.g., `startQuizId`, `sourceTab`, `highlightQuizId`).
- Results rows can trigger retake flow directly into Take tab.
- Generate success path highlights the newly generated quiz or routes to preview/edit checkpoint.
**Tests**:
- Integration tests for cross-tab callback payload handling.
- Component tests for target tab auto-selection/highlighting behavior.
- Regression tests ensuring deep-link payloads survive refresh when encoded in URL/state.
**Status**: Complete

## Stage 2: Per-Tab State Preservation
**Goal**: Prevent user context loss when moving across tabs.
**Success Criteria**:
- Configure tabs to preserve mounted state (`destroyInactiveTabPane={false}`) or equivalent store persistence.
- Maintain per-tab filters, pagination, selections, and partial form state.
- Define explicit reset actions so persistence does not trap stale state.
**Tests**:
- Integration tests for switching tabs without losing local progress.
- Store tests for state snapshot/restore behavior.
- Regression tests for deliberate reset paths (new session, logout, explicit clear).
**Status**: Complete

## Stage 3: Header-Level Discoverability Enhancements
**Goal**: Improve orientation across a multi-tab workflow.
**Success Criteria**:
- Add optional tab badges for meaningful counts (available quizzes, pending results, etc.).
- Add unified quiz search in `QuizPlayground` header, with tab-scoped filtering behavior.
- Search interactions can navigate to and focus relevant items in destination tab.
**Tests**:
- Component tests for badge count rendering and update triggers.
- Integration tests for global search query routing by tab/domain.
- Keyboard tests for header search accessibility and shortcut behavior.
**Status**: Complete

## Dependencies

- Navigation payload contracts should be consumed by `IMPLEMENTATION_PLAN_quiz_page_02_generate_quiz_tab_2026_02_18.md` and `IMPLEMENTATION_PLAN_quiz_page_05_results_analytics_tab_2026_02_18.md`.
- Preserved state behaviors should account for autosave semantics in `IMPLEMENTATION_PLAN_quiz_page_01_take_quiz_tab_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added shared cross-tab navigation contract in `apps/packages/ui/src/components/Quiz/navigation.ts`:
    - `TakeTabNavigationIntent` with `startQuizId`, `highlightQuizId`, `sourceTab`, and `attemptId`.
  - Updated `QuizPlayground` to route all take-tab transitions through a structured intent payload.
  - Updated `GenerateTab` to return generated quiz intent payload (`highlightQuizId` + `sourceTab: "generate"`).
  - Updated `CreateTab` to return created quiz intent payload (`highlightQuizId` + `sourceTab: "create"`).
  - Updated `ResultsTab` retake action to emit structured intent payload (`startQuizId`, `highlightQuizId`, `sourceTab: "results"`, `attemptId`).
  - Extended `TakeQuizTab` to consume highlight/source intent, reset list filters to reveal highlighted quizzes, and render contextual highlight notices + card emphasis.
  - Added regression coverage:
    - `apps/packages/ui/src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx`
    - updated `apps/packages/ui/src/components/Quiz/tabs/__tests__/ResultsTab.filters-retake.test.tsx` payload assertions.

- Stage 2 started:
  - Added explicit tab-pane preservation config in `QuizPlayground` with `destroyInactiveTabPane={false}`.
  - Extended `QuizPlayground.navigation.test.tsx` to assert explicit non-destroy behavior.
  - Added explicit `Reset Current Tab` action in `QuizPlayground` to clear stale state intentionally without disabling preservation by default.
  - Added tab-scoped remount keys in `QuizPlayground` so reset can clear in-memory form/filter state for the active tab while leaving other tab state intact.
  - Centralized persisted state keys in `apps/packages/ui/src/components/Quiz/stateKeys.ts`.
  - Wired `TakeQuizTab` and `ResultsTab` to the shared state keys.
  - Added reset-path regression coverage in `QuizPlayground.navigation.test.tsx`:
    - take tab reset clears `quiz-take-list-prefs-v1` and take navigation intent.
    - results tab reset clears `quiz-results-filters-v1`.

- Stage 3 completed:
  - Added header-level global search in `QuizPlayground` with tab-scoped routing behavior:
    - if active tab is `manage`, apply search directly to `ManageTab`.
    - otherwise, route search to `TakeQuizTab` and navigate to Take.
  - Added tab-count badges in tab labels for:
    - Take/Manage (quiz count)
    - Results (attempt count)
  - Added cross-tab search-intent contracts:
    - `TakeQuizTab` consumes external search query/token, applies filter, and focuses its search input.
    - `ManageTab` consumes external search query/token, applies filter, and focuses its search input.
  - Added shared quiz state-key constants in `stateKeys.ts` and wired tabs/playground to use them for reset flow consistency.
  - Expanded `QuizPlayground.navigation.test.tsx` with:
    - global search routing assertions for Take/Manage.
    - tab-badge count rendering assertions.
    - explicit reset-path storage clearing assertions.

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx src/components/Quiz/tabs/__tests__/ManageTab.undo-accessibility.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.validation-accessibility.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.details.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.filters-retake.test.tsx src/components/Quiz/tabs/__tests__/ResultsTab.export.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.submission-retry.test.tsx src/components/Quiz/hooks/__tests__/quizSubmissionQueue.test.ts`
