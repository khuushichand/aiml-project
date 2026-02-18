# Implementation Plan: Quiz Page - Error Handling and Edge Cases

## Scope

Components: quiz submission lifecycle, connectivity recovery, conflict handling, edge-case validation and local persistence
Finding IDs: `11.1` through `11.6`

## Finding Coverage

- Offline/failed submission resilience: `11.1`, `11.5`
- Submission safety guards: `11.2`, `11.3`
- Conflict and recovery affordances: `11.4`
- Local persistence capability transparency: `11.6`

## Stage 1: Reliable Submission Queue and Retry
**Goal**: Prevent answer loss when network fails during manual or timer-driven submission.
**Success Criteria**:
- Failed submissions are persisted locally with retry metadata.
- UI shows explicit "submission failed" state with retry action.
- Optional auto-retry on connectivity restoration is implemented with user-visible status.
- Timer-expiry submission follows same retry queue path.
**Tests**:
- Integration tests simulating offline-at-submit and recovery retry success.
- Unit tests for queued submission payload serialization/deserialization.
- Timer-expiry failure tests ensuring no silent loss.
**Status**: Complete

## Stage 2: Guardrails for Duplicate/Invalid Submissions
**Goal**: Block invalid or duplicate request paths proactively.
**Success Criteria**:
- Submit button is both `loading` and `disabled` while pending.
- Debounce or idempotency key prevents near-simultaneous duplicate submissions.
- Attempt start validates non-zero question set and presents actionable error state.
**Tests**:
- Component tests for submit button state transitions under rapid clicks.
- Integration tests for duplicate-submit suppression.
- Edge-case tests for quizzes with stale/empty question payloads.
**Status**: Complete

## Stage 3: Conflict Recovery UX
**Goal**: Turn conflict errors into recoverable user actions.
**Success Criteria**:
- Conflict messages include explicit `Refresh and retry` action.
- Refresh action invalidates relevant queries and restores actionable UI state.
- Conflict handling is consistent across Take/Create/Manage flows.
**Tests**:
- Mutation error tests for 409 mapping to actionable UI state.
- Integration tests for refresh action and subsequent successful retry.
- Regression tests for non-conflict errors preserving existing messaging.
**Status**: Complete

## Stage 4: Storage Capability Warnings
**Goal**: Avoid hidden data-loss risk when browser storage is unavailable.
**Success Criteria**:
- Show one-time dismissible warning when autosave storage backend is unavailable.
- Warning explains impact (progress may be lost on navigation/refresh).
- Warning suppression state respects session/local preference.
**Tests**:
- Hook tests for storage exception detection and warning trigger.
- Component tests for dismiss behavior and repeat suppression.
- Integration test ensuring warning does not block quiz progression.
**Status**: Complete

## Dependencies

- Closely coupled with timer/autosave integration in `IMPLEMENTATION_PLAN_quiz_page_01_take_quiz_tab_2026_02_18.md`.
- Should provide shared error presentation patterns consumed by `IMPLEMENTATION_PLAN_quiz_page_05_results_analytics_tab_2026_02_18.md` and `IMPLEMENTATION_PLAN_quiz_page_10_performance_perceived_speed_2026_02_18.md`.

## Progress Notes (2026-02-18)

- Stage 1 completed:
  - Added persisted local submission queue (`quizSubmissionQueue`) with retry metadata (`queuedAt`, `retryCount`, `lastAttemptedAt`, `lastError`).
  - Updated Take Quiz submit flow to enqueue failed submissions (manual and timer-expiry) instead of dropping answers.
  - Added inline failure alert with explicit `Retry submission` action and connectivity-aware auto-retry messaging (via `useServerOnline` transition detection).
  - Added test coverage for:
    - queue payload serialization/deserialization and storage lifecycle
    - failed submit -> queued state -> successful retry flow
    - timer-expiry failed submit queueing path

- Stage 2 completed:
  - Submit action now blocks duplicate submissions (`loading` + `disabled`, plus pending guard in submit handler).
  - Attempt start now validates question payload and blocks zero-question attempts with actionable error messaging.
  - Added edge-case test coverage for zero-question start behavior and retained duplicate-submit guard coverage.

- Stage 4 completed:
  - Added one-time dismissible autosave storage-unavailable warning to the Take Quiz workflow.
  - Extended autosave hook to expose storage availability state via health-check and failure-path detection.
  - Added component test coverage for warning visibility path.

- Validation:
  - `cd apps/packages/ui && bunx vitest run src/components/Quiz/hooks/__tests__/quizSubmissionQueue.test.ts src/components/Quiz/tabs/__tests__/TakeQuizTab.empty-state.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.start-flow.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.navigation-guardrails.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.list-controls.test.tsx src/components/Quiz/tabs/__tests__/TakeQuizTab.submission-retry.test.tsx`
