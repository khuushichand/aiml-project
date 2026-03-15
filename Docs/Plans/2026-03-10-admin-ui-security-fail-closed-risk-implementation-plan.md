# Admin UI Security Dashboard Fail-Closed Risk Rendering Plan

## Stage 1: Lock the Misleading Fallback in a Failing Test
**Goal**: Add a security-page test proving the UI must not render a reassuring zero-risk posture when the security-health endpoint is unavailable.
**Success Criteria**: The new test fails against the current implementation because the page still substitutes zeroed health data.
**Tests**: `bunx vitest run app/security/__tests__/page.test.tsx`
**Status**: Complete

## Stage 2: Fail Closed for Missing Security Health
**Goal**: Remove the fabricated zeroed health payload and render a truthful unavailable state for risk score and summary metrics when the security-health endpoint fails.
**Success Criteria**: Alert status may still render when available, but the page no longer shows a numeric risk score or zeroed summary metrics from fallback data.
**Tests**: `bunx vitest run app/security/__tests__/page.test.tsx`
**Status**: Complete

## Stage 3: Verify the Touched Scope
**Goal**: Re-run focused verification for the security page after the behavior change.
**Success Criteria**: The security-page test suite passes and the regression test stays green.
**Tests**: `bunx vitest run app/security/__tests__/page.test.tsx`; `bun run typecheck`; `bun run lint`
**Status**: Complete
