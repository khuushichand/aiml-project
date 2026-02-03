## Stage 1: Design & Baseline
**Goal**: Confirm current TTS resource manager/model lifecycle and identify integration points for caching.
**Success Criteria**: Relevant files inspected; cache design aligns with existing adapters and tests.
**Tests**: N/A
**Status**: Complete

## Stage 2: Implement LRU Cache + Cleanup Hooks
**Goal**: Add LRU cache tracking, eviction with cleanup, and provider usage updates.
**Success Criteria**: Models are cached, evicted by limit; cleanup called; device cache cleared on eviction.
**Tests**: Unit tests for cache eviction and touch behavior.
**Status**: Complete

## Stage 3: Wire Usage + Verify
**Goal**: Update TTS service to touch cache on use; update tests.
**Success Criteria**: New tests pass; no regressions in existing resource manager tests.
**Tests**: `tldw_Server_API/tests/TTS/test_tts_resource_manager.py`
**Status**: In Progress
