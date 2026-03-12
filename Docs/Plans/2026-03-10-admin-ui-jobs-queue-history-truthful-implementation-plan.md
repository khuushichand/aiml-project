# Admin UI Jobs Queue History Truthful Rendering Plan

## Stage 1: Lock the Current Bug in a Failing Test
**Goal**: Add a jobs-page test that proves the UI must not render a 24-hour queue-history chart from a single current queue-depth metric.
**Success Criteria**: The new test fails against the current implementation because the page still manufactures queue-history points.
**Tests**: `bunx vitest run app/jobs/__tests__/page.test.tsx`
**Status**: Complete

## Stage 2: Remove Synthetic Queue-History Rendering
**Goal**: Change the jobs page so queue-depth history is shown only when the monitoring history endpoint returns real historical points.
**Success Criteria**: Metrics text may still be fetched, but it must not be converted into fabricated queue-history chart data.
**Tests**: `bunx vitest run app/jobs/__tests__/page.test.tsx`
**Status**: Complete

## Stage 3: Verify the Touched Scope
**Goal**: Re-run focused verification for the jobs page after the behavior change.
**Success Criteria**: The jobs-page test suite passes and the new regression test stays green.
**Tests**: `bunx vitest run app/jobs/__tests__/page.test.tsx`
**Status**: Complete
