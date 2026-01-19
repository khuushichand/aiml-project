## Stage 1: Retrieval + Metrics Correctness
**Goal**: Fix hybrid/vector result handling, media-id metrics, and corpus filtering.
**Success Criteria**: Hybrid runs no longer crash; vector metrics use media IDs when metric_level=media; hybrid respects media_ids.
**Tests**: Unit tests for hybrid run result insertion and media-id metrics mapping.
**Status**: Complete

## Stage 2: Reuse + Cleanup Safety
**Goal**: Enable deterministic reuse across tests with safe cleanup guards.
**Success Criteria**: Reuse reuses existing collections for same user/hash; cleanup skips shared collections; reuse path doesn’t rebuild.
**Tests**: Unit test for cross-test reuse without embedding calls.
**Status**: Complete

## Stage 3: Persistence + Export Schema
**Goal**: Enable SQLAlchemy repo for Postgres and stabilize JSON export payloads.
**Success Criteria**: SQLAlchemy repo can be initialized for Postgres URLs; JSON export returns parsed arrays/objects.
**Tests**: Unit test for JSON export parsing and repo URL handling.
**Status**: Complete
