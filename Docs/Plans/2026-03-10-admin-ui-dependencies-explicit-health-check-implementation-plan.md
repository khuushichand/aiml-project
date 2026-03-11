# Admin UI Dependencies Explicit Health Check Implementation Plan

## Stage 1: Lock Desired Behavior In Tests
**Goal**: Update dependency-page tests to require passive initial load and explicit live checks.
**Success Criteria**: Initial render asserts `Unknown` provider status and no `testLLMProvider` calls; explicit actions drive checks.
**Tests**: `bunx vitest run app/dependencies/__tests__/page.test.tsx`
**Status**: Complete

## Stage 2: Split Passive Refresh From Live Checks
**Goal**: Refactor the dependencies page so initial load fetches telemetry only and live probes run only from explicit actions.
**Success Criteria**: Page shows `Refresh Data` and `Run All Checks`; initial load does not call `api.testLLMProvider`.
**Tests**: `bunx vitest run app/dependencies/__tests__/page.test.tsx`
**Status**: Complete

## Stage 3: Verify Production Readiness For This Change
**Goal**: Run targeted admin-ui verification for the touched scope.
**Success Criteria**: Targeted tests pass and `lint`, `typecheck`, and `build` pass for `admin-ui`.
**Tests**: `bun run lint`, `bun run typecheck`, `bun run build`
**Status**: Complete
