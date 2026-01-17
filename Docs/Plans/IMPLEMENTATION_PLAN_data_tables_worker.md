## Stage 1: Worker scaffolding
**Goal**: Define the data tables JobManager worker entrypoint and wiring helpers.
**Success Criteria**: Worker module exists with queue/domain config and job handler skeleton.
**Tests**: N/A (scaffolding only).
**Status**: Complete

## Stage 2: Generation pipeline
**Goal**: Resolve sources, build prompts, call LLM, and persist columns/rows/sources.
**Success Criteria**: Jobs update progress, persist snapshots, and set table status.
**Tests**: Unit tests for normalization/parsing helpers.
**Status**: Complete

## Stage 3: Cancellation + docs updates
**Goal**: Respect job cancellation and finalize documentation.
**Success Criteria**: Cancelled jobs exit early with table status updated; design doc updated.
**Tests**: Integration test for cancel path if feasible.
**Status**: Complete
