## Stage 1: Inspect Service Hotspots
**Goal**: Locate inline truthiness and raw test-mode checks in `workflows_scheduler.py` and `jobs_webhooks_service.py`.
**Success Criteria**: Exact callsites identified for helper replacement.
**Tests**: N/A.
**Status**: In Progress

## Stage 2: Normalize To Shared Helpers
**Goal**: Replace ad-hoc env bool parsing with `app.core.testing` helpers.
**Success Criteria**: No targeted inline legacy checks remain in those files.
**Tests**: Static grep on edited files.
**Status**: Not Started

## Stage 3: Add Regression Tests
**Goal**: Validate `y` semantics in the updated service gates.
**Success Criteria**: Targeted tests assert behavior for `TEST_MODE=y` and related flags.
**Tests**: New/updated pytest tests under `tests/Services`.
**Status**: Not Started

## Stage 4: Validate And Close
**Goal**: Run focused tests and report remaining normalization backlog.
**Success Criteria**: Targeted tests pass; backlog counts updated; plan file removed.
**Tests**: pytest subset + ripgrep counts.
**Status**: Not Started
