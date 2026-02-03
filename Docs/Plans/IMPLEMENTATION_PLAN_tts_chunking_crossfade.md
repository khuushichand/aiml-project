## Stage 1: Design & Audit
**Goal**: Identify TTS adapters that can support chunking and crossfade.
**Success Criteria**: Target adapter(s) selected with safe defaults.
**Tests**: N/A
**Status**: Complete

## Stage 2: Implement Chunking + Crossfade
**Goal**: Add text chunking and crossfade merge for long-form TTS.
**Success Criteria**: Long text splits into chunks, merged audio is seamless.
**Tests**: Unit tests for chunking/crossfade helpers.
**Status**: Complete

## Stage 3: Verification
**Goal**: Run tests and confirm no regressions.
**Success Criteria**: Tests pass.
**Tests**: `tldw_Server_API/tests/TTS_NEW/unit/test_tts_audio_utils.py`
**Status**: In Progress
