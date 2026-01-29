# IMPLEMENTATION_PLAN_tts_playground_ui_alignment.md

## Stage 1: Provider Surfacing & Naming
**Goal**: Surface all server TTS providers with disabled prompts and fix tldw naming.
**Success Criteria**:
- Provider catalog lists all known engines and indicates availability.
- tldw provider label reads "tldw Server" (not Kokoro).
- Providers with voice cloning show capability badges.
**Tests**:
- Manual: open Speech Playground -> TTS provider panel shows catalog with disabled prompts.
- Manual: provider dropdown shows "tldw Server" label.
**Status**: Complete

## Stage 2: Voice Cloning Manager UI
**Goal**: Add a custom voice manager with upload, list, preview, encode, and delete.
**Success Criteria**:
- Users can upload a voice with provider requirements shown.
- Custom voice list renders with metadata and actions.
- Preview plays audio; delete removes entries.
**Tests**:
- Manual: upload a voice -> list updates.
- Manual: preview plays; delete removes entry.
**Status**: Complete

## Stage 3: Streaming & Segmentation Controls
**Goal**: Add streaming controls and segmentation preview to Speech Playground TTS.
**Success Criteria**:
- Stream toggle starts WS streaming when supported.
- UI shows streaming progress and completion/errors.
- Segmentation preview reflects split settings.
**Tests**:
- Manual: toggle stream -> observe chunks/bytes and playback.
- Manual: change split-by -> preview updates.
**Status**: Complete

## Stage 4: Settings & History Quality
**Goal**: Persist new TTS settings and improve TTS history actions.
**Success Criteria**:
- Settings include normalization, language, streaming, formats.
- TTS history entries can be replayed.
**Tests**:
- Manual: change settings -> persist across refresh.
- Manual: replay history uses stored provider/model/voice.
**Status**: Complete
