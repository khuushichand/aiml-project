## Stage 1: Inspect Target Modules
**Goal**: Map all direct `TEST_MODE` checks in `auth.py`, `Jobs/manager.py`, and `evaluations_unified.py`.
**Success Criteria**: All occurrences identified with replacement approach.
**Tests**: N/A.
**Status**: Complete

## Stage 2: Normalize to Shared Helpers
**Goal**: Replace direct test-mode env parsing with `app/core/testing.py` helpers.
**Success Criteria**: Touched files no longer parse `TEST_MODE` manually.
**Tests**: Existing tests + targeted regressions.
**Status**: In Progress

## Stage 3: Add Regression Coverage
**Goal**: Add focused tests for `TEST_MODE=y` semantics on touched code paths.
**Success Criteria**: New tests fail before and pass after implementation.
**Tests**: Targeted pytest subset.
**Status**: Not Started

## Stage 4: Validate and Summarize
**Goal**: Run focused test suite and report residual normalization backlog.
**Success Criteria**: Test command passes and remaining scope quantified.
**Tests**: pytest command covering modified paths.
**Status**: Not Started
