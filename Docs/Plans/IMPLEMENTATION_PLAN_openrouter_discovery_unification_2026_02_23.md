# OpenRouter Discovery Unification Plan

## Stage 1: Extract Shared Discovery Helper
**Goal**: Create a core OpenRouter discovery module with one parser and one cache implementation.
**Success Criteria**:
- Shared module provides URL resolution, TTL handling, model extraction, and cached discovery.
- Discovery supports canonical/display OpenRouter IDs in one place.
**Tests**:
- Existing unit tests consuming wrappers continue to pass.
**Status**: Complete

## Stage 2: Wire llm_providers to Shared Helper
**Goal**: Replace duplicate OpenRouter discovery logic in llm_providers with wrapper calls to the shared helper.
**Success Criteria**:
- `/api/v1/llm/models/metadata` refresh path uses shared helper.
- OpenRouter metadata refresh unit test remains green.
**Tests**:
- `python -m pytest --confcutdir=tldw_Server_API/tests/LLM_Adapters/unit tldw_Server_API/tests/LLM_Adapters/unit/test_llm_openrouter_models_refresh.py -v`
**Status**: Complete

## Stage 3: Wire chat_service to Shared Helper
**Goal**: Replace chat-side duplicate OpenRouter parsing/discovery with shared helper while preserving strict-validation behavior.
**Success Criteria**:
- Strict model availability keeps canonical/display equivalence behavior.
- Test-time network suppression behavior remains intact.
**Tests**:
- `python -m pytest --confcutdir=tldw_Server_API/tests/Chat/unit tldw_Server_API/tests/Chat/unit/test_chat_service_normalization.py -v`
**Status**: Complete

## Stage 4: Verify and Security Scan
**Goal**: Run targeted tests and Bandit for touched scope.
**Success Criteria**:
- Targeted tests pass.
- Bandit reports no new findings in production code touched.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/LLM_Calls/openrouter_model_inventory.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/api/v1/endpoints/llm_providers.py -f json -o /tmp/bandit_openrouter_discovery_unification_2026_02_23.json`
**Status**: Complete
