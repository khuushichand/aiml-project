## Stage 1: Inspect Remaining Hotspots
**Goal**: Identify exact inline truthiness and raw test-mode env checks in the six requested files.
**Success Criteria**: Precise callsites listed with intended helper replacements.
**Tests**: N/A (inspection only).
**Status**: In Progress

## Stage 2: Normalize To Shared Helpers
**Goal**: Replace inline env-boolean parsing and ad-hoc TEST_MODE getenv checks with shared helpers.
**Success Criteria**: No targeted inline set checks remain in the six files.
**Tests**: Static search on edited files.
**Status**: Not Started

## Stage 3: Add/Adjust Regression Tests
**Goal**: Add targeted tests for any newly normalized semantics lacking coverage.
**Success Criteria**: Tests validate `y` truthiness and test-mode helper behavior where relevant.
**Tests**: Targeted pytest modules for modified areas.
**Status**: Not Started

## Stage 4: Validate And Close
**Goal**: Run targeted tests and summarize remaining normalization backlog.
**Success Criteria**: Targeted tests pass; residual counts updated.
**Tests**: `pytest` subset + quick syntax check.
**Status**: Not Started
