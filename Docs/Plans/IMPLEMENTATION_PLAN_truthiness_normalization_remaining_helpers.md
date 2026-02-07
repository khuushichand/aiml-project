## Stage 1: Rebaseline Remaining Callsites
**Goal**: Enumerate all remaining hardcoded truthiness callsites after prior passes.
**Success Criteria**: A concrete list of files/lines to patch.
**Tests**: N/A
**Status**: Complete

## Stage 2: Normalize Remaining Truthiness Helpers
**Goal**: Replace hardcoded truthy sets with shared helpers (`is_truthy`, `env_flag_enabled`, `is_test_mode`) where applicable.
**Success Criteria**: Targeted app-level hardcoded sets removed or reduced to intentional constants.
**Tests**: Static grep sanity checks.
**Status**: Complete

## Stage 3: Add/Adjust Regression Coverage
**Goal**: Ensure changed semantics remain covered for `y`/test-mode behavior.
**Success Criteria**: Existing/new focused tests pass for touched modules.
**Tests**: Focused pytest modules.
**Status**: Complete

## Stage 4: Validate, Summarize, and Close
**Goal**: Run verification and provide updated residual backlog.
**Success Criteria**: Test pass + updated counts + plan file cleanup.
**Tests**: pytest subset + rg counts.
**Status**: Complete
