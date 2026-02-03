## Stage 1: Audit & Design
**Goal**: Identify adapters that can consume min/max token settings and where to compute defaults.
**Success Criteria**: Target adapters listed; default heuristic chosen.
**Tests**: N/A
**Status**: Complete

## Stage 2: Implement Defaults + Adapter Wiring
**Goal**: Add max/min token estimation and pass through to supported adapters.
**Success Criteria**: Defaults applied when not provided; adapters use overrides.
**Tests**: Unit tests or manual verification of parameter plumbing.
**Status**: Complete

## Stage 3: Verification
**Goal**: Run unit tests and ensure no regressions.
**Success Criteria**: Tests pass; no lint errors.
**Tests**: `tldw_Server_API/tests/TTS/test_tts_resource_manager.py` (plus any adapter unit tests if present)
**Status**: In Progress
