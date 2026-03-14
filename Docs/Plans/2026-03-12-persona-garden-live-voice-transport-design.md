# Persona Garden Live Voice Transport Design

Date: 2026-03-12
Status: Implemented
Owner: Codex brainstorming pass

## Summary

Extend Persona Garden Live Session voice support by building on the existing persona websocket transport instead of the generic audio chat stream.

The current persona websocket already carries persona-bound `session_id`, policy context, memory retrieval, tool planning, and approval flow. It also already contains an early-stage audio scaffold with `audio_chunk`, `partial_transcript`, and `tts_audio` events. The next slice should turn that scaffold into the real Persona Garden live voice transport rather than introducing a second spoken-turn runtime.

This keeps spoken and typed turns inside the same persona session and avoids a misleading UI where the user believes they are talking to a selected persona while the runtime is actually using a separate generic chat websocket.

## Goals

- Keep voice turns persona-bound to the active Persona Garden session.
- Make spoken and typed turns use the same persona planning, tool, policy, memory, and analytics path.
- Honor persona voice defaults inside Persona Garden Live Session only.
- Support session-local `auto-resume` and `barge-in` overrides that reset on disconnect or persona switch.
- Preserve text responses when persona TTS is unavailable, with an explicit text-only warning contract.

## Non-Goals

- Do not reuse the generic `/api/v1/audio/chat/stream` runtime for Persona Garden Live Session.
- Do not make persona voice defaults globally override browser-wide voice settings elsewhere in the app.
- Do not expand scope in this slice to persona-specific LLM model selection, pause threshold tuning, or global TTS mode control.
- Do not replace the existing Persona Garden typed composer flow.

## Existing Context

Current constraints in the codebase:

- Persona Garden Live Session creates persona sessions and opens the persona websocket in `apps/packages/ui/src/routes/sidepanel-persona.tsx`.
- The generic voice runtime in `apps/packages/ui/src/hooks/useVoiceChatStream.tsx` uses `/api/v1/audio/chat/stream` and browser-global voice settings.
- Persona websocket text turns already go through the full persona runtime in `tldw_Server_API/app/api/v1/endpoints/persona.py`.
- Persona websocket already has an audio scaffold:
  - inbound `audio_chunk`
  - outbound `partial_transcript`
  - outbound `tts_audio` plus binary chunks
- Persona assistant defaults are already stored on persona profiles and resolved through `useResolvedPersonaVoiceDefaults`.

The design therefore should evolve the persona websocket itself instead of forcing Persona Garden onto the generic voice-chat transport.

## Key Design Decisions

### 1. Persona Websocket Is The Voice Transport

Persona Garden Live Session voice runs over `/api/v1/persona/stream`.

Reasons:

- persona session ownership already exists there
- persona policy and scope enforcement already exists there
- persona memory/state/exemplar logic already exists there
- the backend already has an audio event scaffold there

The generic audio chat stream remains for shared non-persona voice chat surfaces.

### 2. Typed And Spoken Turns Must Share One Turn Executor

The existing `user_message` path inside the persona websocket should be refactored into a shared helper that:

- resolves runtime persona/session context
- applies session preference updates
- records the user turn
- retrieves memory/companion/persona-state context
- proposes and stores the plan
- emits notices and tool plans

Voice turns must call that same helper after STT commit so there is only one persona decision path.

### 3. Voice Commit Is A Persona Turn, Not A Separate Chat Mode

Audio capture can stream partial transcript updates, but a committed spoken utterance should become a normal persona turn.

Recommended event model:

- `voice_config`
  - session-scoped runtime config for STT/TTS/trigger behavior
- `audio_chunk`
  - raw mic audio payloads
- `partial_transcript`
  - incremental transcript deltas for UI feedback
- `voice_commit`
  - commit the accumulated transcript into the shared persona turn executor

Implementation detail:

- the server may internally normalize `voice_commit` into the same helper used by `user_message`
- the client should not send persona/security fields in voice frames any more than it does for text frames

### 4. Persona Voice Defaults Apply Only Inside Persona Garden

Saved persona defaults are the source of truth for Persona Garden Live Session:

- trigger phrases
- STT language
- STT model
- TTS provider
- TTS voice

Session-local overrides are allowed only for:

- `auto-resume`
- `barge-in`

These overrides reset when:

- the live session disconnects
- the selected persona changes

### 5. Trigger Phrases Stay Client-Side

Trigger detection should stay in the Persona Garden live voice controller rather than moving into the server.

Reasons:

- it is a UI activation concern
- it keeps the server contract simpler
- it avoids coupling STT partial handling to one UI surface

The server still receives the resolved trigger list via `voice_config` for observability and future compatibility, but the initial trigger gate lives in the client.

### 6. TTS Failure Must Degrade To Text-Only, Not Fatal Error

If persona TTS provider/voice is unavailable or synthesis fails:

- the persona turn still completes
- assistant text still arrives
- no spoken playback is attempted for that turn
- the server emits a structured non-fatal warning notice
- the client marks the voice session as text-only until reconnect or explicit retry

Recommended notice payload:

```json
{
  "event": "notice",
  "level": "warning",
  "reason_code": "TTS_UNAVAILABLE_TEXT_ONLY",
  "message": "Persona voice playback is unavailable; continuing with text responses only."
}
```

This avoids the current generic voice-chat behavior where TTS failures can collapse into terminal stream errors.

## Protocol Design

### Client To Server

#### `voice_config`

Sent after persona websocket connect and whenever resolved persona voice settings change for the active session.

```json
{
  "type": "voice_config",
  "session_id": "<persona-session-id>",
  "voice": {
    "trigger_phrases": ["hey helper"],
    "auto_resume": true,
    "barge_in": false
  },
  "stt": {
    "language": "en-US",
    "model": "whisper-1"
  },
  "tts": {
    "provider": "openai",
    "voice": "alloy"
  }
}
```

Notes:

- session-local toggle overrides are sent as resolved values
- the server should treat this as runtime state, not persisted profile mutation

#### `audio_chunk`

Existing contract remains, but becomes part of the real live voice path.

```json
{
  "type": "audio_chunk",
  "session_id": "<persona-session-id>",
  "audio_format": "webm",
  "bytes_base64": "<base64>"
}
```

#### `voice_commit`

Commits the accumulated transcript into the shared persona turn executor.

```json
{
  "type": "voice_commit",
  "session_id": "<persona-session-id>",
  "transcript": "search notes for mcp registry",
  "source": "persona_live_voice"
}
```

Server behavior:

- validates session ownership
- routes transcript through the shared persona user-turn helper
- preserves persona session/tool plan semantics

### Server To Client

#### `partial_transcript`

Continue to stream partial text for live UI feedback.

#### `assistant_delta`

No change. Spoken turns should reuse the same assistant delta event already used by typed persona turns.

#### `tool_plan`, `tool_call`, `tool_result`, `notice`

No change. Spoken turns must reuse the current persona event vocabulary.

#### `tts_audio`

Continue to emit binary audio chunks plus metadata events when playback is available.

#### `notice` with `TTS_UNAVAILABLE_TEXT_ONLY`

New explicit degraded-mode contract for non-fatal TTS failure.

## Backend Design

### 1. Refactor Persona Turn Processing

Extract the existing `user_message` handling logic into a shared helper, for example:

```python
async def _handle_persona_user_turn(
    *,
    session_id: str,
    text: str,
    source: str,
    ...
) -> None:
    ...
```

Both `user_message` and `voice_commit` should call this helper.

### 2. Upgrade Persona Audio Path

Replace the current scaffold behavior where `audio_chunk` immediately echoes placeholder transcript/TTS output.

Target behavior:

- `audio_chunk` updates transcript state
- `voice_commit` runs the committed transcript through `_handle_persona_user_turn`
- TTS playback is produced from real persona assistant output, not an audio echo path

### 3. Store Session-Scoped Voice Runtime Config

Session manager preferences should carry non-persisted runtime voice config for the active persona session, for example:

- `voice_runtime.stt_language`
- `voice_runtime.stt_model`
- `voice_runtime.tts_provider`
- `voice_runtime.tts_voice`
- `voice_runtime.trigger_phrases`
- `voice_runtime.auto_resume`
- `voice_runtime.barge_in`
- `voice_runtime.text_only_due_to_tts_failure`

This state should not update persona profile defaults automatically.

### 4. TTS Degradation

If TTS fails during a spoken turn:

- catch provider/validation/synthesis failures in the persona stream path
- emit `TTS_UNAVAILABLE_TEXT_ONLY`
- set session runtime to text-only
- continue to emit assistant text/deltas

### 5. Analytics

Voice analytics should remain persona-scoped and count only live runtime.

Enhancements for this slice:

- distinguish spoken turns from typed turns in live persona events
- count text-only degraded turns separately from successful spoken-playback turns

## Frontend Design

### 1. New Persona Garden Voice Controller

Create a Persona-specific controller hook, for example:

- `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`

Responsibilities:

- connect to the existing persona websocket session
- manage mic capture
- accumulate transcript text from `partial_transcript`
- detect trigger phrases client-side
- send `voice_config`
- send `audio_chunk`
- send `voice_commit`
- receive `tts_audio` and binary chunks
- switch to text-only playback mode on `TTS_UNAVAILABLE_TEXT_ONLY`
- expose session-local `auto-resume` and `barge-in` state

This hook must not mutate global voice chat settings.

### 2. Live Session UI

Extend `LiveSessionPanel` with an `Assistant Voice` card that shows:

- resolved trigger phrases
- resolved STT language
- resolved STT model
- resolved TTS provider
- resolved TTS voice
- live toggles for `auto-resume`
- live toggles for `barge-in`
- current mode:
  - listening
  - thinking
  - speaking
  - text-only fallback
- warning banner when playback is disabled

Trigger/STT/TTS values are read-only in Live Session. Editing remains in `Profile -> Assistant Defaults`.

### 3. Session-Local Override Rules

- `auto-resume` and `barge-in` are mutable in Live Session
- the controller sends updated `voice_config` values without persisting them
- disconnecting or switching personas resets them to resolved persona defaults

## UX Rules

- Never imply that persona defaults affect voice behavior outside Persona Garden.
- Never silently fall back to browser playback while still labeling the session as the persona voice.
- When TTS fails, state that text responses continue and spoken playback is disabled for the current live session.
- Keep the repair path simple:
  - warning in Live Session
  - link back to `Profile -> Assistant Defaults`

## Testing Strategy

Backend:

- persona websocket tests for:
  - `voice_config` accepted and stored as runtime state
  - `voice_commit` routes through the same persona turn executor as `user_message`
  - `audio_chunk` remains session/persona-bound
  - TTS failure emits `TTS_UNAVAILABLE_TEXT_ONLY` and still completes the text turn

Frontend:

- controller tests for:
  - trigger detection
  - session-local override reset
  - text-only degraded mode
- route/panel tests for:
  - resolved voice card rendering
  - live toggles
  - warning banner behavior

## Risks And Mitigations

### Risk: Persona audio path diverges from typed persona path

Mitigation:

- shared `_handle_persona_user_turn` helper
- no duplicate plan/tool logic inside `audio_chunk` handling

### Risk: Users think persona defaults are global

Mitigation:

- explicit Persona Garden-only copy
- no writes to shared voice settings hooks

### Risk: TTS fallback is ambiguous

Mitigation:

- explicit `TTS_UNAVAILABLE_TEXT_ONLY` notice
- explicit client-side text-only mode state

### Risk: Existing persona websocket tests become brittle after refactor

Mitigation:

- keep outward event vocabulary stable for typed turns
- add shared helper unit coverage where possible

## Rollout Order

1. Refactor shared persona user-turn executor.
2. Add persona websocket `voice_config` and `voice_commit`.
3. Route audio commit through the shared helper.
4. Add TTS degraded-mode contract.
5. Add Persona Garden live voice controller and Live Session voice card.
6. Wire session-local override reset behavior.
7. Add analytics and verification coverage for spoken-turn outcomes.
