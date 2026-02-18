## Stage 1: OpenRouter Catalog Refresh Path
**Goal**: Add a server-side optional refresh path that pulls current OpenRouter models from OpenRouter `/models` and merges into provider/model listings.
**Success Criteria**: `/api/v1/llm/models/metadata?refresh_openrouter=true` includes live OpenRouter models when API key is configured; failures degrade gracefully to cached/static list.
**Tests**: Add unit test for llm_providers endpoint with mocked `_http_fetch` and OpenRouter key.
**Status**: Complete

## Stage 2: Frontend Model Fetch Plumbing
**Goal**: Thread refresh options through `TldwApiClient`, `TldwModelsService`, and `fetchChatModels`.
**Success Criteria**: Forced model refresh can request OpenRouter refresh without affecting default fetch paths.
**Tests**: Update/extend existing `TldwModels` tests for updated call signatures and force-refresh behavior.
**Status**: Complete

## Stage 3: Hard Pre-Send Model Guard
**Goal**: Enforce model availability validation in `useMessage` right before submission.
**Success Criteria**: Invalid selected model is blocked before chat request; UI surfaces clear error; stale selected model is cleared.
**Tests**: Add/adjust hook unit tests to cover blocked submit when model unavailable after refresh.
**Status**: Complete

## Stage 4: Verification and Closeout
**Goal**: Run targeted backend/frontend tests for changed paths and update plan statuses.
**Success Criteria**: Targeted tests pass and changed behavior is confirmed.
**Tests**: pytest for new backend test module and vitest for updated frontend tests.
**Status**: Complete (frontend targeted tests passing; backend pytest passing in project `.venv` with Python 3.12)
