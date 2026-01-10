## Stage 1: Embeddings Adapter Design
**Goal**: Define the Jobs-backed adapter surface, status mapping, and flags for embeddings jobs.
**Success Criteria**: Adapter contract documented (inputs/outputs), env flags decided, and mapping rules captured in code comments.
**Tests**: N/A (design-only stage)
**Status**: Complete

## Stage 2: Embeddings Jobs Adapter + Endpoint Wiring
**Goal**: Implement the Jobs-backed adapter, wire `/api/v1/media/embeddings/jobs*` + job updates to it, and add any JobManager helpers needed.
**Success Criteria**: Embeddings endpoints read/write Jobs rows; legacy DB only used via read fallback when enabled; jobs updates mark completed/failed in Jobs.
**Tests**: `python -m pytest tldw_Server_API/tests/Embeddings/test_media_embedding_jobs.py -v`
**Status**: Complete

## Stage 3: Validation + Docs Touchups
**Goal**: Validate embeddings job flow and record any new config defaults or caveats.
**Success Criteria**: Target tests pass locally (or failures documented); PRD/Docs updated if new flags or behaviors are introduced.
**Tests**: `python -m pytest tldw_Server_API/tests/Embeddings_NEW/integration/test_embeddings_api.py::TestEmbeddingGenerationPipeline::test_full_pipeline_text_to_storage -v`
**Status**: Not Started

## Stage 4: Chatbooks Adapter Design
**Goal**: Define the Jobs-backed adapter surface and status mappings for Chatbooks export/import jobs.
**Success Criteria**: Adapter contract documented in code (mapping + matching rules) and integration points identified.
**Tests**: N/A (design-only stage)
**Status**: Complete

## Stage 5: Chatbooks Adapter + Service Wiring
**Goal**: Wire Chatbooks export/import job reads to core Jobs with legacy fallback; keep existing API behavior.
**Success Criteria**: Chatbooks job endpoints read status from Jobs when core backend is enabled; cancellation aligns Jobs rows with chatbooks job IDs.
**Tests**: `python -m pytest tldw_Server_API/tests/Chatbooks/test_chatbooks_cancellation.py -v`
**Status**: Complete

## Stage 6: Chatbooks Validation
**Goal**: Validate chatbooks job status views and ensure API parity.
**Success Criteria**: Chatbooks async job tests pass locally (or failures documented).
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_chatbooks_roundtrip.py -v`
**Status**: Complete

## Stage 7: Prompt Studio Adapter Design
**Goal**: Define the Jobs-backed adapter surface and status mappings for Prompt Studio job views.
**Success Criteria**: Adapter contract documented in code (mapping + selection rules) and integration points identified.
**Tests**: N/A (design-only stage)
**Status**: Complete

## Stage 8: Prompt Studio Adapter + Endpoint Wiring
**Goal**: Wire optimization job status/history (and SSE initial state) to the Jobs-backed adapter with legacy fallback.
**Success Criteria**: Prompt Studio job status endpoints read from core Jobs when enabled; legacy job queue used as fallback.
**Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_api_endpoints.py::TestOptimizationEndpoints::test_get_optimization_status -v`
**Status**: Complete

## Stage 9: Prompt Studio Validation
**Goal**: Validate Prompt Studio job history/status views for both backends.
**Success Criteria**: Target tests pass locally (or failures documented).
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_prompt_studio_e2e.py -v`
**Status**: Complete

## Stage 10: Embeddings Jobs Worker Design (Phase 2)
**Goal**: Define a Jobs worker execution plan for embeddings and document payload/flow.
**Success Criteria**: Design doc added under `Docs/Design/Embeddings_Jobs_Worker_Migration.md` with job types, payload shape, and cutover flags.
**Tests**: N/A (design-only stage)
**Status**: Complete

## Stage 11: Embeddings Jobs Worker Implementation
**Goal**: Implement Jobs-backed worker execution for media embeddings and gate API endpoints with `EMBEDDINGS_JOBS_BACKEND`.
**Success Criteria**: Jobs worker processes `media_embeddings` jobs; API enqueues only in jobs mode; legacy mode unchanged.
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_embeddings_e2e.py -v`
**Status**: Complete

## Stage 12: Embeddings Jobs Worker Validation
**Goal**: Validate embeddings Jobs pipeline end-to-end with the worker running.
**Success Criteria**: Target E2E tests pass in jobs mode (or failures documented with cause).
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_media_update_propagation.py -v`
**Status**: Complete

## Stage 13: Chatbooks Jobs Worker Design (Phase 2)
**Goal**: Define Jobs worker execution plan for chatbooks export/import.
**Success Criteria**: Worker approach documented (job types, payload fields, run command).
**Tests**: N/A (design-only stage)
**Status**: Complete

## Stage 14: Chatbooks Jobs Worker Implementation
**Goal**: Implement Jobs worker service for chatbooks export/import using core Jobs worker SDK.
**Success Criteria**: Worker processes `chatbooks` jobs and updates export/import job tables.
**Tests**: `python -m pytest tldw_Server_API/tests/Chatbooks/test_chatbooks_cancellation.py -v`
**Status**: Complete

## Stage 15: Chatbooks Jobs Worker Validation
**Goal**: Validate chatbooks async job execution with the worker running.
**Success Criteria**: Chatbooks async E2E or integration jobs pass (or failures documented).
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_chatbooks_roundtrip.py -v`
**Status**: Not Started
