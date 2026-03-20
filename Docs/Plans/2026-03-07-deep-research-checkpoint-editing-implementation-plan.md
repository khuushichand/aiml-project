# Deep Research Checkpoint Editing Implementation Plan

## Stage 1: Backend Patch Contracts
**Goal**: Add typed checkpoint patch validation and lock the approval flow with red/green backend tests.
**Success Criteria**: Invalid patch payloads are rejected by checkpoint type; approval writes the correct review artifacts and chooses the correct next phase.
**Tests**: `tldw_Server_API/tests/Research/test_research_jobs_service.py`, `tldw_Server_API/tests/Research/test_research_runs_endpoint.py`
**Status**: Complete

## Stage 2: Backend Lifecycle Updates
**Goal**: Make approved plan/source/outline artifacts influence later collection and synthesis behavior.
**Success Criteria**: Collecting honors edited plans and source curation/recollection; outline edits resynthesize and skip reopening `outline_review`.
**Tests**: `tldw_Server_API/tests/Research/test_research_jobs_worker.py`, `tldw_Server_API/tests/Research/test_research_synthesizer.py`, `tldw_Server_API/tests/e2e/test_deep_research_runs.py`
**Status**: Complete

## Stage 3: Frontend Checkpoint Editors
**Goal**: Replace the run-console checkpoint JSON block with typed editors and validation-aware submit behavior.
**Success Criteria**: Users can edit plan, source, and outline checkpoints; invalid edits block approval; the UI rehydrates from snapshot data.
**Tests**: `apps/tldw-frontend/__tests__/pages/research-run-console.test.tsx`
**Status**: Complete

## Stage 4: Verification And Finish
**Goal**: Run the full targeted verification set, address regressions, and record a clean commit.
**Success Criteria**: Backend and frontend checkpoint-editing suites pass; Bandit stays clean on the touched backend scope.
**Tests**: targeted pytest, targeted Vitest, Bandit on research backend paths
**Status**: Complete
