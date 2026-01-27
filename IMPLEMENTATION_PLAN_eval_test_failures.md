## Stage 1: Reproduce Failures
**Goal**: Run the failing evaluation and webhook tests with full traces.
**Success Criteria**: I can see the exact stack traces and assertion contexts.
**Tests**: Targeted `pytest` runs for the listed failing tests.
**Status**: Complete

## Stage 2: Inspect Implementation and Test Doubles
**Goal**: Review the relevant endpoints, core services, and DB stubs/mocks.
**Success Criteria**: I identify the expected interfaces and current behavior.
**Tests**: None.
**Status**: Complete

## Stage 3: Pinpoint Root Causes
**Goal**: Map each failure to a specific code-path mismatch or regression.
**Success Criteria**: Each failing test has a clear, evidence-backed explanation.
**Tests**: Re-run small subsets as needed.
**Status**: In Progress

## Stage 4: Summarize Findings and Fix Options
**Goal**: Provide a concise root-cause summary with minimal, safe fix suggestions.
**Success Criteria**: The user can act on the findings without guesswork.
**Tests**: None.
**Status**: Not Started
