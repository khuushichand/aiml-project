# OpenRouter Model Inventory Sync Implementation Plan

## Stage 1: Reproduce and Lock the Regression
**Goal**: Add tests that fail for OpenRouter display ID vs canonical slug mismatch under strict model validation.
**Success Criteria**:
- New tests demonstrate that `moonshotai/kimi-k2.5` should be accepted when inventory contains `moonshotai/kimi-k2.5-0127` (or equivalent aliases).
- Tests fail before implementation changes.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_service_normalization.py -k openrouter -v`
**Status**: Complete

## Stage 2: Implement Shared OpenRouter Inventory Normalization
**Goal**: Update model availability logic so OpenRouter validation can use discovered IDs and canonical aliases, not only static pricing keys.
**Success Criteria**:
- `is_model_known_for_provider("openrouter", ...)` accepts known OpenRouter IDs across canonical/display variants.
- Non-OpenRouter providers retain existing strict behavior.
**Tests**:
- Existing and new unit tests in `test_chat_service_normalization.py` pass.
**Status**: Complete

## Stage 3: Integrate and Verify Strict Validation Paths
**Goal**: Ensure strict checks in chat and character chat paths benefit from improved OpenRouter availability matching.
**Success Criteria**:
- Targeted integration/unit checks for strict model precheck remain green.
- No regression in explicit unavailable-model 400 behavior.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Chat/integration/test_chat_endpoint_simplified.py -k strict_model_selection -v`
- `python -m pytest tldw_Server_API/tests/Character_Chat_NEW/unit/test_chat_completion_precheck.py -k unavailable_model -v`
**Status**: In Progress (unit verification complete; integration command aborted in this environment during heavy native `torch/ctranslate2` import)

## Stage 4: Security and Completion Validation
**Goal**: Run required security scan and summarize outcomes.
**Success Criteria**:
- Bandit run on touched files completes and no new high-confidence issues are introduced.
- Plan statuses updated to complete.
**Tests**:
- `python -m bandit -r tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/tests/Chat/unit/test_chat_service_normalization.py -f json -o /tmp/bandit_openrouter_model_inventory_sync.json`
**Status**: Complete
