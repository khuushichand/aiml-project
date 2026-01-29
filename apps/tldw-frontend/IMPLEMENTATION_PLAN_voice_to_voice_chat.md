## Stage 1: Settings + Core Hook
**Goal**: Add voice chat settings + streaming hook scaffold.
**Success Criteria**: Settings exist (defaults), hook can open/close WS and emit events.
**Tests**: Manual smoke - toggle voice chat, connection opens/closes without errors.
**Status**: Complete

## Stage 2: Audio Streaming + Playback
**Goal**: Send mic PCM to server, handle JSON events + audio chunks.
**Success Criteria**: Partial + final transcript events received; audio plays (stream when supported, fallback on full).
**Tests**: Manual - speak, see transcript + hear audio reply.
**Status**: Complete

## Stage 3: UI Integration (Playground + Sidepanel)
**Goal**: Add Voice Chat toggle + model selector in both UIs; wire events to chat store.
**Success Criteria**: Voice chat works in both surfaces and preserves transcript.
**Tests**: Manual - run both UIs, confirm toggles, messages appear, audio plays.
**Status**: Complete

## Stage 4: Polish + i18n + Error Handling
**Goal**: Add user-facing error states, tooltips, and locale strings.
**Success Criteria**: Clear errors for mic/WS; new strings available in locale files.
**Tests**: Manual - deny mic permission; disconnect server; verify errors.
**Status**: Complete
