# Issue #757 Workflows More Nodes Implementation Plan

## Stage 1: Scope Compression and Coverage Snapshot
**Goal**: Convert the broad “more nodes” request into a concrete runtime coverage baseline.
**Success Criteria**:
- Publish a node-pack matrix with total registry steps, adapter-backed steps, and engine-native special handlers.
- Explicitly identify unresolved gaps.
**Tests**:
- N/A (documentation stage).
**Status**: Complete

## Stage 2: First Delivery Pack (Runtime Coverage Guard)
**Goal**: Ship a concrete quality gate proving registry step types are executable at runtime.
**Success Criteria**:
- Add a test that validates each registry step type is either adapter-registered or engine-native.
- Test fails if a new registry node is added without runtime support.
**Tests**:
- `tldw_Server_API/tests/Workflows/test_step_registry_runtime_coverage.py`
**Status**: Complete

## Stage 3: Verify + Track
**Goal**: Validate the delivery pack and record closure evidence in the local checklist.
**Success Criteria**:
- Targeted workflow coverage test passes.
- Bandit clean for touched scope.
- Checklist updated for #757 completion evidence.
**Tests**:
- `pytest` targeted coverage test.
- `bandit` on touched paths.
**Status**: Complete
