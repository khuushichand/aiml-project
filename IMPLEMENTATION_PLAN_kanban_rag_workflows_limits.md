## Stage 1: Kanban RAG Integration
**Goal**: Add Kanban as a first-class RAG data source and retriever.
**Success Criteria**: `sources=["kanban"]` accepted; retriever returns cards as Documents; unified pipeline maps `kanban` correctly.
**Tests**: Unit test for KanbanDBRetriever (FTS path); update schema validation tests if needed.
**Status**: Complete

## Stage 2: Limits Alignment + Config
**Goal**: Align Kanban limits with PRD defaults and make them configurable, including per-board card cap.
**Success Criteria**: Limits enforce on create/copy; per-board cap enforced; defaults match PRD.
**Tests**: Unit test for per-board card cap; update comment size limit test if adjusted.
**Status**: Complete

## Stage 3: Workflows + Activity Retention Cleanup
**Goal**: Add workflow adapter(s) for Kanban reads/writes and schedule activity retention cleanup.
**Success Criteria**: Workflow step type executes Kanban actions; background cleanup job registered in app startup.
**Tests**: Unit test for adapter action (read/write); optional scheduler smoke test if feasible.
**Status**: Complete
