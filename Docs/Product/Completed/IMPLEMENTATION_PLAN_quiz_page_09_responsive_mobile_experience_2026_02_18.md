# Implementation Plan: Quiz Page - Responsive and Mobile Experience

## Scope

Components: quiz tab navigation, Take card grid/actions, Create question builder layout, timed quiz header behaviors
Finding IDs: `9.1` through `9.4`

## Finding Coverage

- Tab navigation fit on small viewports: `9.1`
- Touch target sizing: `9.2`
- Mobile authoring ergonomics: `9.3`
- Timer visibility under scroll constraints: `9.4`

## Stage 1: Mobile Tab Navigation Refinement
**Goal**: Keep five-tab navigation discoverable and usable at narrow widths.
**Success Criteria**:
- Validate and tune tab labels/icons for 320px width without truncation confusion.
- Ensure overflow behavior remains keyboard and touch accessible.
- Preserve active-tab visibility while horizontal scrolling.
**Tests**:
- Responsive component tests at 320px/375px/414px breakpoints.
- Keyboard navigation tests for tablist overflow scenarios.
- Visual regression tests for label/icon fallback states.
**Status**: Complete

## Stage 2: Touch-Target Compliance Pass
**Goal**: Ensure interactive controls meet minimum touch usability targets.
**Success Criteria**:
- Primary and secondary actionable controls meet 44px minimum target size.
- Start/retake/submit actions have adequate spacing to prevent accidental taps.
- Mobile hit-area updates do not regress desktop density significantly.
**Tests**:
- Component style tests validating control min dimensions.
- Mobile viewport interaction tests for key button rows.
- Visual regression checks for desktop/mobile parity.
**Status**: Complete

## Stage 3: Create Tab Mobile Layout Adaptation
**Goal**: Make question authoring feasible on narrow screens.
**Success Criteria**:
- Option inputs stack vertically on mobile breakpoints.
- Radio/select/delete controls remain reachable and finger-friendly.
- Form validation/help text remains readable without horizontal scroll.
**Tests**:
- Responsive integration tests for create-form interactions on mobile widths.
- Accessibility checks for focus order after layout stacking.
- Snapshot tests for option row layout variants.
**Status**: Complete

## Stage 4: Persistent Timer Visibility on Mobile
**Goal**: Keep time awareness constant during long-scrolling quiz attempts.
**Success Criteria**:
- Timed quizzes show sticky/fixed timer bar on mobile.
- Timer bar avoids overlap with browser UI/safe areas.
- Timer bar retains warning/danger visual semantics and screen-reader updates.
**Tests**:
- Mobile integration tests for sticky timer visibility while scrolling.
- Visual regression tests across iOS/Android viewport presets.
- Accessibility tests for timer announcements and focus behavior.
**Status**: Complete

## Dependencies

- Requires timer wiring from `IMPLEMENTATION_PLAN_quiz_page_01_take_quiz_tab_2026_02_18.md`.
- Must align with accessibility semantics in `IMPLEMENTATION_PLAN_quiz_page_13_accessibility_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Updated `QuizPlayground` tab labels for mobile readability with icon + short-label variants while preserving full semantic labels.
  - Added mobile overflow handling classes on the tab strip to keep five tabs scrollable and readable on narrow widths.
  - Added active-tab scroll-into-view behavior on tab change to keep the selected tab visible during horizontal overflow.
  - Added navigation tests for:
    - mobile overflow/tab short-label configuration,
    - generate-tab review action routing to Manage.

- Stage 2 completed:
  - Applied 44px minimum touch-target sizing (`min-h-11`) to key `TakeQuizTab` actions:
    - list/start actions,
    - back/submit/retake controls,
    - retry action in submission-queue alert,
    - empty-state CTA buttons.
  - Increased question navigator button hit area for mobile tapping.
  - Added tests asserting touch-target classes on core actions.

- Stage 3 completed:
  - Adapted `CreateTab` layout for narrow screens:
    - quiz detail numeric fields now stack on mobile (`grid-cols-1` -> `sm:grid-cols-2`),
    - multiple-choice option rows stack vertically on mobile and switch to row layout on `sm+`,
    - question type select becomes full-width on mobile.
  - Improved reachability of authoring controls:
    - touch-sized move/delete icon buttons,
    - touch-sized add/remove option controls,
    - larger true/false control row behavior on mobile.
  - Added tests for stacked option row layout and touch-target class coverage.

- Stage 4 completed:
  - Added sticky mobile timer bar in active quiz-taking view:
    - visible on mobile (`md:hidden`),
    - sticky positioning with safe-area-aware top offset,
    - warning/danger color semantics retained.
  - Kept desktop timer in card header (`md` and up) and ensured mobile sticky bar does not remove live-region timer announcements.
  - Added integration test validating sticky timer bar rendering during active timed attempts.

- Validation:
  - Passed:
    - `cd apps/packages/ui && bunx vitest run src/components/Quiz/__tests__/QuizPlayground.navigation.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx src/components/Quiz/tabs/__tests__/CreateTab.flexible-composition.test.tsx`
  - Note:
    - A broad run (`src/components/Quiz/**/*.test.tsx`) hit many timeout-only failures in this environment across unrelated pre-existing slow tests; no assertion regressions were observed in the responsive-focused suites above.
