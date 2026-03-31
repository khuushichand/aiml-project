## Stage 1: Lock Regressions With Tests
**Goal**: Add failing coverage for the adjacent TTS paths that still rely on implicit `kokoro` defaults or conflate provider with model.
**Success Criteria**: Tests fail before implementation and describe the expected explicit model/default resolution behavior.
**Tests**: `tldw_Server_API/tests/VoiceAssistant/test_rest_endpoints.py`, `tldw_Server_API/tests/VoiceAssistant/test_ws_integration.py`, `tldw_Server_API/tests/Audio/test_speech_chat_service.py`, `tldw_Server_API/tests/Collections/test_reading_api.py`
**Status**: Complete

## Stage 2: Centralize TTS Resolution
**Goal**: Add a shared resolver for provider/model/voice defaults and use it in the surrounding backend codepaths.
**Success Criteria**: Voice assistant, speech chat, and audio streaming no longer fabricate `kokoro` as the implicit model and no longer use provider names as model ids.
**Tests**: Targeted pytest coverage for the touched call sites plus new resolver unit tests if needed.
**Status**: Complete

## Stage 3: Align Reading TTS With User Defaults
**Goal**: Require an explicit reading-item TTS model on the backend and make the frontend send the stored user-configured model and voice.
**Success Criteria**: Reading-item TTS no longer relies on backend fallback defaults; the UI path still works with stored TTS settings.
**Tests**: `tldw_Server_API/tests/Collections/test_reading_api.py` and targeted frontend test coverage if feasible.
**Status**: Complete

## Stage 4: Verify and Security Check
**Goal**: Run the targeted regression suite and Bandit on the touched Python scope.
**Success Criteria**: Relevant tests pass and touched Python files are clean under Bandit.
**Tests**: Targeted `pytest` invocations and `python -m bandit -r ...`
**Status**: Complete
