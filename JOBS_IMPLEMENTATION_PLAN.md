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
**Status**: Complete

## Stage 16: Prompt Studio Jobs Worker Design (Phase 2)
**Goal**: Define Jobs worker execution plan for Prompt Studio jobs.
**Success Criteria**: Design doc added with job types, payload fields, and run command.
**Tests**: N/A (design-only stage)
**Status**: Complete

## Stage 17: Prompt Studio Jobs Worker Implementation
**Goal**: Implement Jobs worker service for Prompt Studio using core Jobs worker SDK.
**Success Criteria**: Worker processes prompt studio jobs and updates core Jobs status/results.
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_prompt_studio_e2e.py -v`
**Status**: Complete

## Stage 18: Prompt Studio Jobs Worker Validation
**Goal**: Validate prompt studio job execution with the core jobs worker running.
**Success Criteria**: Prompt Studio async E2E or integration tests pass (or failures documented).
**Tests**: `python -m pytest tldw_Server_API/tests/prompt_studio/integration/test_concurrency_jobs.py -v`
**Status**: Complete

## Stage 19: Phase 3 Embeddings Legacy Removal
**Goal**: Remove legacy embeddings job systems (Redis job manager, media_embedding_jobs_db) and update call sites.
**Success Criteria**: No runtime code references legacy embeddings job manager/DB; embeddings jobs flow relies on core Jobs only.
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_embeddings_e2e.py -v`
**Status**: Complete

## Stage 20: Phase 3 Chatbooks Legacy Removal
**Goal**: Remove chatbooks job queue shim and ensure chatbooks endpoints rely on core Jobs only.
**Success Criteria**: No chatbooks shim usage; chatbooks job flows run via core Jobs.
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_chatbooks_roundtrip.py -v`
**Status**: Complete

## Stage 21: Phase 3 Prompt Studio Legacy Removal
**Goal**: Remove Prompt Studio legacy job manager/queue usage; keep jobs adapter + core Jobs only.
**Success Criteria**: No runtime references to prompt_studio/job_manager in endpoints or workers.
**Tests**: `python -m pytest tldw_Server_API/tests/e2e/test_prompt_studio_e2e.py -v`
**Status**: Complete

## Stage 22: Phase 3 Cleanup + Docs
**Goal**: Clean up adapters to disable legacy fallback defaults and update docs/flags.
**Success Criteria**: Legacy read fallback defaults are off; docs updated to reflect core Jobs as the only backend.
**Tests**: `python -m pytest tldw_Server_API/tests/Jobs -v`
**Status**: Not Started
