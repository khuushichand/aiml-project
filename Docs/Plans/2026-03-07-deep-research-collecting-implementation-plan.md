# Deep Research Collecting Slice Implementation Plan

## Stage 1: Broker And Normalization
**Goal**: Add a deterministic `ResearchBroker` that selects local, academic, and web collection lanes by source policy and normalizes results into source and evidence records.
**Success Criteria**: The broker emits deduped source records and evidence notes for a focus area; policy selection is unit-tested.
**Tests**: `python -m pytest tldw_Server_API/tests/Research/test_research_broker.py -v`
**Status**: Complete

## Stage 2: Collecting Phase Execution
**Goal**: Extend the research Jobs handler to execute the `collecting` phase and persist `source_registry.json`, `evidence_notes.jsonl`, and `collection_summary.json`.
**Success Criteria**: A collecting job writes artifacts idempotently and transitions to `awaiting_source_review` for checkpointed runs or `synthesizing` otherwise.
**Tests**: `python -m pytest tldw_Server_API/tests/Research/test_research_jobs_worker.py -v`
**Status**: Complete

## Stage 3: Session Advancement And End-To-End Verification
**Goal**: Update session approval flow to enqueue `collecting`, then verify an end-to-end plan approval to source review flow.
**Success Criteria**: Approving a `plan_review` checkpoint creates the next job and the run can advance through collecting in tests.
**Tests**: `python -m pytest tldw_Server_API/tests/Research/test_research_jobs_service.py tldw_Server_API/tests/Research/test_research_runs_endpoint.py tldw_Server_API/tests/e2e/test_deep_research_runs.py -v`
**Status**: Complete
