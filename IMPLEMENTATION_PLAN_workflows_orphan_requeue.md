## Stage 1: Orphan Requeue Design
**Goal**: Define how stale step leases are detected, cleaned up, and requeued.
**Success Criteria**: Plan documented with requeue + subprocess cleanup flow.
**Tests**: N/A
**Status**: Complete

## Stage 2: Engine + DB Updates
**Goal**: Implement orphan requeue with subprocess cleanup and context recovery.
**Success Criteria**: Stale running steps are marked as orphan-requeued, subprocesses terminated, and runs resumed from the stale step.
**Tests**: Unit stale requeue logic
**Status**: Not Started

## Stage 3: Integration Coverage
**Goal**: Verify requeued runs resume and complete via API.
**Success Criteria**: Integration test covers blocked/allowed resume path.
**Tests**: Integration requeue resume
**Status**: Not Started

## Stage 4: Checklist + Validation
**Goal**: Update gap checklist and validate changes.
**Success Criteria**: Checklist item checked; targeted tests pass.
**Tests**: Relevant pytest targets
**Status**: Not Started
