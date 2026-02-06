## Stage 1: Baseline And Scope
**Goal**: Enumerate BLE001 findings in `qwen3_tts_adapter.py` and inspect each exception path.
**Success Criteria**: All blind exception sites are identified with local context.
**Tests**: `ruff check --select BLE001 --output-format concise tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
**Status**: In Progress

## Stage 2: Replace Blind Exceptions
**Goal**: Replace blind catches with explicit exception handling while preserving behavior.
**Success Criteria**: `qwen3_tts_adapter.py` has zero BLE001 findings.
**Tests**: `ruff check --select BLE001 --output-format concise tldw_Server_API/app/core/TTS/adapters/qwen3_tts_adapter.py`
**Status**: Not Started

## Stage 3: Verify And Re-Rank
**Goal**: Re-run repository BLE001 stats and identify the next top offender.
**Success Criteria**: Updated BLE001 total and ranking are captured.
**Tests**: `ruff check --select BLE001 --statistics tldw_Server_API`
**Status**: Not Started
