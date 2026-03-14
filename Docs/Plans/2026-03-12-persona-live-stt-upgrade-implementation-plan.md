# Persona Live STT Upgrade Implementation Plan

Execution Status: Complete

## Stage 1: Define Scope And Reuse Strategy
**Goal**: Upgrade persona websocket `audio_chunk` transcription quality without forking the existing realtime STT stack.
**Success Criteria**:
- Persona websocket reuses the shared streaming transcriber path instead of the UTF-8 placeholder.
- Scope stays limited to explicit client commit; no server-side auto-commit or VAD-triggered turn execution in this slice.
- Audio format expectations are explicit and safe.
**Tests**:
- None; design and implementation constraints only.
**Status**: Complete

## Stage 2: Add Red Tests For Persona STT Runtime
**Goal**: Lock the desired websocket behavior before implementation.
**Success Criteria**:
- New tests fail against the current scaffold.
- Coverage proves `audio_chunk` can emit transcriber-backed partials and `voice_commit` can consume/reset the transcriber state.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q -k 'persona_audio_chunk_uses_streaming_transcriber or persona_voice_commit_uses_transcriber_snapshot'`
**Status**: Complete

## Stage 3: Implement Session-Scoped Persona STT
**Goal**: Replace scaffold STT with a per-session streaming transcriber and transcript snapshot handling.
**Success Criteria**:
- Persona websocket creates and reuses one streaming transcriber per live session.
- `pcm16` chunks are normalized before transcription.
- `partial_transcript` events emit only safe forward progress for the current UI contract.
- `voice_commit` can fall back to the current transcriber snapshot when the client omits a transcript.
- Session transcriber state resets cleanly on commit/config change/close.
**Tests**:
- Stage 2 tests pass.
- Existing persona websocket audio tests still pass.
**Status**: Complete

## Stage 4: Verify And Harden
**Goal**: Confirm the backend slice is stable and does not introduce hygiene/security regressions.
**Success Criteria**:
- Targeted persona websocket suite passes.
- `py_compile`, `git diff --check`, and Bandit pass on the touched backend scope.
**Tests**:
- `python -m pytest tldw_Server_API/tests/Persona/test_persona_ws.py -q`
- `python -m py_compile tldw_Server_API/app/api/v1/endpoints/persona.py`
- `python -m bandit -r tldw_Server_API/app/api/v1/endpoints/persona.py -f json -o /tmp/bandit_persona_live_stt.json`
- `git diff --check`
**Status**: Complete
