# Persona Garden Live VAD Auto-Commit Design

## Goal

Make Persona Garden live voice use server-side VAD auto-commit as the default turn-finalization path while keeping explicit `voice_commit` available as a manual fallback and recovery tool.

This change applies only to the persona-scoped websocket/runtime used by `Persona Garden -> Live Session`. It must not leak into the shared browser voice settings or the generic `/audio/chat/stream` contract.

## Scope

In scope:

- server-side VAD auto-commit for persona websocket live voice
- persona websocket turn-state and dedupe logic for spoken turns
- degraded manual mode when VAD is unavailable
- explicit websocket notices for auto-commit, degraded manual mode, and ignored duplicate manual commits
- Persona Garden controller/UI updates so normal listening relies on server auto-commit
- regression coverage for backend websocket behavior and frontend controller/UI behavior

Out of scope:

- changing the generic `/audio/chat/stream` protocol
- adding persona-specific VAD tuning controls to the UI
- browser-side VAD or client-owned turn-boundary detection
- changing LLM model selection, pause thresholds outside persona live voice, or non-persona voice surfaces
- replacing the current STT backend again; this design builds on the just-added persona live STT reuse

## Recommended Approach

Keep Persona Garden on `/api/v1/persona/stream` and add VAD-driven turn finalization directly inside the persona websocket runtime.

This is the recommended approach because it:

- preserves persona/session binding for every spoken turn
- keeps tool planning, policy checks, analytics, and memory on the same persona execution path as typed turns
- avoids making the browser authoritative for turn boundaries
- reuses the existing `SileroTurnDetector` behavior already used by the generic audio websocket

Rejected alternatives:

1. Client-assisted auto-commit
   This would keep turn-finalization logic in the browser and make persona live voice less authoritative and less predictable.

2. Dual first-class commit authorities
   Letting server VAD and manual client commit race as peers would create duplicate-turn and state-sync problems for little product value.

## Runtime Contract

### Input Frames

`audio_chunk` remains the primary live voice input.

`voice_config` should accept persona-live VAD fields under `stt`, with server defaults used when they are omitted:

- `enable_vad`
- `vad_threshold`
- `min_silence_ms`
- `turn_stop_secs`
- `min_utterance_secs`

The client does not own turn finalization even when it sends these values. They are server hints only.

`voice_commit` remains supported, but only for:

- manual `Send now`
- degraded manual mode when VAD is unavailable
- explicit recovery from edge cases like long pauses or clipped speech

### Server-Side Auto-Commit

For each live persona session, the websocket runtime should maintain one session-local voice turn state containing:

- the streaming STT transcriber
- the `SileroTurnDetector`
- the latest transcript snapshot
- whether the current utterance has already been committed
- the last commit source (`vad_auto` or `manual`)

When `audio_chunk` arrives:

1. decode and normalize audio as the persona live STT path already does
2. feed the chunk into the session transcriber
3. emit safe forward-only `partial_transcript` deltas
4. feed the same chunk into the turn detector when VAD is enabled and available
5. when VAD marks end-of-turn, finalize the current transcript snapshot and route it through the existing `_handle_persona_live_turn(...)` path

The persona websocket should emit a structured notice when auto-commit happens. The exact wire shape can stay within the existing `notice` contract, for example:

- `reason_code: "VOICE_TURN_COMMITTED"`
- `commit_source: "vad_auto"`
- `transcript: "<final transcript>"`

### Manual Fallback And Dedupe

If `voice_commit` arrives:

- if the current utterance is already committed, ignore it and emit a benign notice such as `VOICE_COMMIT_IGNORED_ALREADY_COMMITTED`
- otherwise commit the current transcript snapshot, mark the utterance committed, and emit `VOICE_TURN_COMMITTED` with `commit_source: "manual"`

After any successful commit, the session should reset only the current utterance state:

- clear buffered transcript snapshot
- reset the transcriber for the next utterance
- reset the turn detector state
- clear the committed flag for the next utterance

This state must remain ephemeral and session-local. It is not a second persistence layer.

## VAD Reuse Strategy

Reuse the core `SileroTurnDetector` from `Audio_Streaming_Unified` instead of copying or re-implementing turn detection inside `persona.py`.

The persona websocket should mirror the generic audio websocket’s fail-open behavior:

- if VAD initializes successfully, auto-commit is active
- if VAD is unavailable, the session keeps STT partials but drops into manual commit mode
- the server emits one warning notice for that degraded mode instead of repeatedly warning on every chunk

This keeps behavior aligned without coupling persona live voice to the generic audio endpoint’s full protocol.

## Client And UX Behavior

`usePersonaLiveVoiceController` remains Persona Garden-only, but its default loop changes:

1. start microphone capture
2. stream `audio_chunk`
3. render `partial_transcript`
4. wait for a server `VOICE_TURN_COMMITTED` notice
5. switch to `thinking` only after the server confirms commit

Normal listening should no longer send routine `voice_commit` when the user stops speaking or taps `Stop listening`.

### Manual Controls

The Live Session UI should add a manual `Send now` action. It should be available when:

- there is current heard transcript text
- the session is still in manual fallback mode, or
- the user explicitly wants to force-send the current transcript snapshot

`Stop listening` should stop microphone capture only. It should not implicitly commit the transcript anymore.

### Warning And Degraded Mode

When VAD is unavailable, the UI should:

- keep showing live partial transcript updates
- show a warning that live voice is in manual send mode
- expose `Send now` as the primary action for committing the heard transcript

When the server ignores a duplicate manual commit after an auto-commit, the controller should treat it as informational rather than an error.

### Existing Session-Only Toggles

`auto-resume` and `barge-in` remain client/session-local behaviors:

- `auto-resume` decides whether the client starts listening again after the assistant finishes
- `barge-in` still controls whether current playback is interrupted when the user starts listening again

Neither toggle should change server commit authority.

## Error Handling

Fail-open behavior is required:

- VAD unavailable: continue with partial STT and manual commit fallback
- empty transcript on VAD trigger: do nothing and reset the utterance cleanly
- late duplicate manual commit: ignore with a notice, not an error
- STT failure during an utterance: preserve existing persona live STT fallback behavior where possible

The main safety objective is to avoid duplicate turn execution and avoid trapping the user in a `listening` state with no path to send the transcript.

## Testing

Backend websocket coverage should prove:

- VAD auto-commit routes a spoken turn into the normal persona planning path
- a session emits the degraded manual-mode warning when VAD is unavailable
- manual `voice_commit` still works in degraded mode
- duplicate manual commit after VAD auto-commit is ignored safely
- empty/noise-only VAD finalization does not create a user turn
- transcriber and turn-detector state reset correctly between utterances

Frontend coverage should prove:

- the controller no longer sends routine `voice_commit` on stop-listening
- the controller enters `thinking` only after the server commit notice
- degraded manual mode exposes `Send now` and uses explicit `voice_commit`
- duplicate manual-commit ignore notices do not surface as hard errors
- the Live Session UI reflects warning/manual-mode states clearly

## Follow-Up

Possible follow-up slices after this design:

- persona-specific VAD tuning controls in Assistant Defaults
- richer live voice diagnostics for transcript snapshots and commit source
- analytics on `vad_auto` vs `manual` commit source and degraded-mode frequency
