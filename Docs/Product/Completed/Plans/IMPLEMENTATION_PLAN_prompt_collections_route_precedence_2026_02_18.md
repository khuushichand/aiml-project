## Stage 1: Reproduce and Isolate Collection Endpoint Failures
**Goal**: Confirm why collection list/update integration tests fail.
**Success Criteria**: Root cause identified with exact route/behavior mismatch.
**Tests**: Focused pytest on `TestCollectionEndpoints` cases.
**Status**: Complete

## Stage 2: Fix API Routing and Legacy Create Semantics
**Goal**: Ensure `/collections` routes are not shadowed by dynamic prompt identifier routes; align legacy create HTTP status.
**Success Criteria**: `/api/v1/prompts/collections*` endpoints resolve correctly and `/api/v1/prompts/create` returns expected create semantics.
**Tests**: Focused pytest for collection list/update endpoints.
**Status**: Complete

## Stage 3: Regression Verification
**Goal**: Verify full prompt-management integration suite remains stable.
**Success Criteria**: No new failures introduced beyond known unrelated issues.
**Tests**: `test_prompts_api.py` integration suite.
**Status**: Complete
