# Persona Garden Live Voice Recovery Design

## Goal

Make Persona Garden Live Session recover cleanly when persona live voice gets stuck in `listening` or `thinking`, without forcing a full page reset and without changing non-persona voice surfaces.

This slice is limited to `Persona Garden -> Live Session`. It layers recovery UX and controller logic on top of the existing persona websocket notice contract.

## Scope

In scope:

- client-side stuck-turn detection for `listening` and `thinking`
- a dedicated recovery panel in the Assistant Voice card
- explicit recovery actions for `Send now`, `Keep listening`, `Wait`, `Reset turn`, `Reconnect voice session`, and `Send text manually`
- route wiring so reconnect can refresh only the persona live voice transport/session path
- regression coverage for hook, component, and route behavior

Out of scope:

- changing the generic audio websocket contract
- server-owned heartbeat/recovery notices
- global voice-chat recovery behavior outside Persona Garden
- persona-scoped VAD tuning controls
- changes to command routing, analytics semantics, or persona defaults

## Recommended Approach

Use client-side recovery timers plus a recovery action panel inside the existing Assistant Voice card.

This is the recommended first slice because it:

- improves the current user experience without widening the persona websocket protocol
- stays isolated to Persona Garden
- avoids inventing destructive auto-recovery behavior
- leaves room for a future server heartbeat or processing-notice contract if false positives remain

Rejected alternatives:

1. Server-owned recovery state
   This would be more authoritative, but it is a larger protocol change than this product gap requires right now.

2. Silent auto-send or auto-reset
   This would appear smoother at first, but it is risky because a slow or delayed turn could be mishandled without the user explicitly choosing the fallback action.

## Recovery Model

The existing base voice states remain unchanged:

- `idle`
- `listening`
- `thinking`
- `speaking`
- `error`

Recovery is modeled as advisory sub-state on top of those states:

- `none`
- `listening_stuck`
- `thinking_stuck`

### Trigger Conditions

`listening_stuck` should appear when:

- the controller is in `listening`
- the current heard transcript is non-empty
- no commit arrives for 4 seconds

`thinking_stuck` should appear when:

- the controller is in `thinking`
- a voice turn has already been committed
- no assistant progress arrives for 8 seconds

These thresholds are intentionally balanced rather than aggressive so the recovery panel appears when the session feels stuck, not at every minor delay.

### Recovery Actions

For `listening_stuck`:

- `Send now`
- `Keep listening`
- `Reset turn`
- `Reconnect voice session`

For `thinking_stuck`:

- `Wait`
- `Send text manually`
- `Reset turn`
- `Reconnect voice session`

No automatic send/reset behavior should be added in this slice.

## Controller Behavior

`usePersonaLiveVoiceController` should gain small recovery-focused state:

- `recoveryMode`
- `recoveryReason`
- `recoveryStartedAt`
- an active local voice-turn token or monotonic counter

### Listening Recovery

When the controller enters `listening` and transcript text becomes non-empty, it should start a 4-second timer.

That timer must clear when:

- transcript becomes empty
- `VOICE_TURN_COMMITTED` arrives
- listening stops
- persona changes
- session disconnects
- the user chooses a recovery action

If the timer fires, the controller should expose `recoveryMode="listening_stuck"`.

### Thinking Recovery

When `VOICE_TURN_COMMITTED` transitions the controller to `thinking`, it should start an 8-second timer.

That timer must clear when:

- `assistant_delta` arrives
- `tts_audio` arrives
- a text-only TTS degradation notice completes the turn
- the user chooses a recovery action
- persona changes
- session disconnects

If the timer fires, the controller should expose `recoveryMode="thinking_stuck"`.

### Turn Fencing

The controller should fence recovery against stale late events by associating recovery state with one active local voice-turn token.

This prevents delayed assistant output from a prior turn from mutating the UI after the user has already chosen `Reset turn` or `Send text manually`.

## UI Design

`AssistantVoiceCard` should keep the current warning banner and live status blocks, then add a dedicated recovery panel below warnings when `recoveryMode !== "none"`.

### Listening-Stuck Copy

- headline: `Voice turn needs attention`
- body: `I heard speech, but this turn has not been committed yet.`
- actions:
  - `Send now`
  - `Keep listening`
  - `Reset turn`
  - `Reconnect voice session`

### Thinking-Stuck Copy

- headline: `Assistant response is delayed`
- body: `This voice turn was sent, but the assistant has not responded yet.`
- actions:
  - `Wait`
  - `Send text manually`
  - `Reset turn`
  - `Reconnect voice session`

The recovery panel should be visually distinct from generic warnings so users understand they have explicit choices, not just passive notices.

## Route Wiring

`sidepanel-persona.tsx` should remain responsible for websocket/session ownership.

The hook should expose a reconnect callback trigger, but the route should perform the actual persona live reconnect so:

- the current persona selection remains intact
- the broader Persona Garden state is preserved
- command/profile/test-lab surfaces are unaffected

`Reconnect voice session` should clear the current recovery state before reconnecting.

## Edge Cases

`Send text manually` in `thinking_stuck` should use `lastCommittedText`, not the raw heard transcript. That preserves whatever trigger stripping or normalization the server already applied.

`Reset turn` should:

- stop the mic if needed
- clear `heardText`
- clear the active turn’s `lastCommittedText`
- clear recovery state and timers
- return the controller to `idle`

Manual-mode and text-only mode should coexist with recovery:

- if VAD is unavailable and the user forgets to press `Send now`, `listening_stuck` should still appear
- if TTS is text-only, `thinking_stuck` should still clear when assistant text progress arrives

## Testing

Hook coverage in `apps/packages/ui/src/hooks/__tests__/usePersonaLiveVoiceController.test.tsx` should prove:

- listening recovery appears after 4 seconds with transcript present and no commit
- `Keep listening` dismisses recovery and restarts the listening timer
- `Reset turn` clears transcript and returns to `idle`
- thinking recovery appears after 8 seconds after commit with no assistant progress
- `assistant_delta` clears thinking recovery
- `Send text manually` uses `lastCommittedText`

Component coverage in `apps/packages/ui/src/components/PersonaGarden/__tests__/LiveSessionPanel.test.tsx` should prove:

- the recovery panel renders the correct copy and actions for each recovery mode

Route coverage in `apps/packages/ui/src/routes/__tests__/sidepanel-persona.test.tsx` should prove:

- reconnect action routes through the Persona Garden websocket/session logic without dropping persona state

## Future Follow-Up

If recovery panels still appear too often for legitimately long-running persona turns, the next slice should add a small server-side activity/heartbeat notice contract rather than making the client timers more complex.
