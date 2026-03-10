# Admin UI Monitoring History Truthful Rendering Plan

## Stage 1: Lock the Synthetic History Fallback in a Failing Test
**Goal**: Add or update hook coverage so the monitoring metrics history logic must not fabricate a chartable time series when the history endpoint fails.
**Success Criteria**: The test fails against the current implementation because the hook still synthesizes history from snapshot endpoints.
**Tests**: `bunx vitest run app/monitoring/use-monitoring-metrics-history.test.tsx`
**Status**: Complete

## Stage 2: Remove Synthetic Monitoring History
**Goal**: Change the monitoring metrics history hook so historical chart data is empty when the authoritative history endpoint fails.
**Success Criteria**: The UI can still log/report the failure, but it must not display invented historical points as real monitoring history.
**Tests**: `bunx vitest run app/monitoring/use-monitoring-metrics-history.test.tsx`
**Status**: Complete

## Stage 3: Verify the Touched Scope
**Goal**: Re-run focused verification for the monitoring metrics history hook after the change.
**Success Criteria**: The focused hook tests pass and the truthful-history regression stays green.
**Tests**: `bunx vitest run app/monitoring/use-monitoring-metrics-history.test.tsx`; `bun run typecheck`; `bun run lint`
**Status**: Complete
