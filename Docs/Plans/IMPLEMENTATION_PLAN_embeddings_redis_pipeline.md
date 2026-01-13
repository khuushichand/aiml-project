# IMPLEMENTATION_PLAN_embeddings_redis_pipeline.md

## Stage 1: Redis Pipeline Skeleton
**Goal**: Introduce a minimal Redis Streams pipeline for embeddings stages.
**Success Criteria**: New worker module can consume chunking/embedding/storage streams and call stage handlers; root Jobs are updated on completion/failure.
**Tests**: Unit test(s) for enqueue + worker stage progression with Redis stub (async).
**Status**: Complete

## Stage 2: Adapter + Status Mapping
**Goal**: Wire EmbeddingsJobsAdapter to enqueue Redis messages while keeping Jobs root records for status/billing.
**Success Criteria**: Create/list/get use root Jobs; status reflects progress without stage Jobs; stage Jobs no longer created.
**Tests**: Update adapter tests for Redis enqueue + derived status.
**Status**: Complete

## Stage 3: Docs + Config Updates
**Goal**: Update PRD/notes to reflect Redis pipeline decision and usage.
**Success Criteria**: PRD + migration docs mention Redis stage transport and benchmark outcome.
**Tests**: N/A.
**Status**: Complete
