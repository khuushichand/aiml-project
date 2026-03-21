## Stage 1: Reproduce And Trace
**Goal**: Reproduce the `/api/v1/llm/models/metadata` abort path and identify the caller that leaks expected cancellation into the UI.
**Success Criteria**: Exact component/helper path is confirmed with evidence from code and, if needed, browser/dev runtime reproduction.
**Tests**: Focused reproduction or failing unit test that captures the leaking behavior.
**Status**: Complete

## Stage 2: Add Regression
**Goal**: Add a focused test for the abort path before changing production code.
**Success Criteria**: Test fails against current behavior for the confirmed leaking path.
**Tests**: Targeted `vitest` file covering metadata abort handling in the affected component/helper.
**Status**: Complete

## Stage 3: Fix Abort Handling
**Goal**: Handle expected request cancellation without surfacing a fatal route/runtime error.
**Success Criteria**: Aborts are ignored or converted into safe empty/cached state while real failures still surface to the UI.
**Tests**: New regression passes; adjacent touched tests stay green.
**Status**: Complete

## Stage 4: Verify
**Goal**: Confirm the fix in tests and a live browser/dev session.
**Success Criteria**: Targeted tests pass, Bandit reports no new findings in touched files, and the runtime overlay no longer appears in the reproduced flow.
**Tests**: Focused `vitest`, Bandit on touched scope, and browser validation.
**Status**: Complete
