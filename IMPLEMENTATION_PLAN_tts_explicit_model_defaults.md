# TTS Explicit Model Defaults Implementation Plan

## Stage 1: Validate Current Default Flow
**Goal**: Confirm where the TTS model default should come from and identify tests that currently rely on the backend `kokoro` fallback.
**Success Criteria**: Public `/audio/speech` callers and tests depending on omitted `model` are identified.
**Tests**: Inspection only.
**Status**: Complete

## Stage 2: Require Explicit Public TTS Model
**Goal**: Remove the backend `OpenAISpeechRequest.model` default so the public API rejects omitted models instead of silently selecting `kokoro`.
**Success Criteria**: Requests without `model` receive validation failure, while callers using stored UI defaults or explicit server-side values continue working.
**Tests**: `python -m pytest tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k "explicit_model or without_provider or voice_settings" -v`
**Status**: Complete

## Stage 3: Verification
**Goal**: Verify the targeted endpoint tests and touched-scope security scan pass.
**Success Criteria**: Focused pytest scope passes and Bandit reports no new findings in touched files.
**Tests**: `python -m pytest tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py -k "explicit_model or without_provider or voice_settings" -v`; `python -m bandit -r tldw_Server_API/app/api/v1/schemas/audio_schemas.py tldw_Server_API/tests/TTS_NEW/integration/test_tts_endpoints.py`
**Status**: Complete
