## Stage 1: Soft-Delete Purge Scheduler
**Goal**: Add scheduled purge for soft-deleted kanban entities across users.
**Success Criteria**: New scheduler runs `purge_deleted_items` per user with configurable interval/grace days and startup hook in `main.py`.
**Tests**: Unit test for scheduler helper or DB purge invocation (mocked), plus coverage in kanban DB tests if feasible.
**Status**: Not Started

## Stage 2: Redis-Queued Kanban Embeddings
**Goal**: Route Kanban vector indexing through the Redis embeddings queue and extend embeddings worker to support custom collections/doc IDs.
**Success Criteria**: Kanban card indexing enqueues a content job; worker stores embeddings into `kanban_user_{id}` with `card_{id}` IDs and metadata.
**Tests**: Embeddings jobs worker unit test for custom content payload; kanban vector search/unit test for enqueue behavior.
**Status**: Not Started

## Stage 3: Pagination Alignment (limit/offset)
**Goal**: Align kanban search/filter/comments pagination to limit/offset (per decision).
**Success Criteria**: Endpoints and DB methods accept limit/offset, tests updated accordingly.
**Tests**: Existing kanban API/DB tests updated to new pagination params.
**Status**: Not Started
