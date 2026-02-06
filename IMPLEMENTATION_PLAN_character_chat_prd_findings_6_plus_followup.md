## Stage 1: Reproduce and Root-Cause FTS Malformed Update Regression
**Goal**: Isolate deterministic cause of mixed-suite `database disk image is malformed` on first character update.
**Success Criteria**: Root cause documented and tied to specific schema/index lifecycle behavior.
**Tests**: Minimal two-test pytest reproduction and direct DB-level repro scripts.
**Status**: Complete

## Stage 2: Backend Fix for Character Card FTS Bootstrap/Self-Heal
**Goal**: Ensure `character_cards_fts` is properly seeded so first update/delete paths cannot hit malformed FTS delete operations.
**Success Criteria**: Fresh DB initialization self-heals missing `character_cards_fts` index rows before request traffic.
**Tests**: New targeted unit regression + failing mixed-suite scenario.
**Status**: In Progress

## Stage 3: Validation for PRD Batch 6+ Continuation
**Goal**: Re-run targeted backend/frontend tests and summarize remaining 6+ findings work.
**Success Criteria**: Character chat regression path is green and remaining tasks are clearly listed.
**Tests**: Character_Chat_NEW targeted pytest and existing frontend tests touched by prior 6+ work.
**Status**: Not Started
