# TTS Error Mapping Implementation Plan

## Stage 1: Baseline And Test Coverage
**Goal**: Capture the current TTS exception classification behavior in focused unit tests.
**Success Criteria**: New unit tests demonstrate the desired HTTP status and message mapping for provider init/runtime failures.
**Tests**: `python -m pytest tldw_Server_API/tests/Audio/test_audio_tts_error_mapping_unit.py -v`
**Status**: Complete

## Stage 2: Backend Error Classification
**Goal**: Update the backend TTS error mapper to return actionable HTTP statuses for setup/runtime failures instead of a generic 500.
**Success Criteria**: Initialization, model/resource, timeout, and upstream/provider availability errors map to distinct HTTP responses without regressing existing auth/validation handling.
**Tests**: `python -m pytest tldw_Server_API/tests/Audio/test_audio_tts_error_mapping_unit.py -v`
**Status**: Complete

## Stage 3: Verification
**Goal**: Verify the targeted test scope and security scan pass on the touched files.
**Success Criteria**: Focused pytest run passes and Bandit reports no new findings in touched scope.
**Tests**: `python -m pytest tldw_Server_API/tests/Audio/test_audio_tts_error_mapping_unit.py -v`; `python -m bandit -r tldw_Server_API/app/core/Audio/tts_service.py tldw_Server_API/tests/Audio/test_audio_tts_error_mapping_unit.py`
**Status**: Complete
