# Persona Live Voice Processing Notice Design

## Goal

Reduce false `thinking_stuck` recovery states in `Persona Garden -> Live Session` when a committed voice turn is healthy but there is a quiet backend gap before the first visible planner, tool, or assistant output event.

## Scope

This slice is limited to:

- the persona websocket backend in `tldw_Server_API/app/api/v1/endpoints/persona.py`
- the Persona Garden live voice hook in `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- Persona Garden route log handling in `apps/packages/ui/src/routes/sidepanel-persona.tsx`

This slice does not add:

- recurring heartbeats
- new user-facing banners or status copy
- turn correlation identifiers
- progress signals for long-running tool execution after `tool_call`

## Chosen Approach

Use a delayed, one-shot server notice after `VOICE_TURN_COMMITTED`.

If a voice turn is committed and there is still no real progress after roughly `2s`, the backend emits:

- `event: "notice"`
- `level: "info"`
- `reason_code: "VOICE_TURN_PROCESSING"`
- `message: "Still processing this voice turn."`

The client treats that notice as silent progress:

- re-arm the `thinking` recovery timer
- do not surface a warning
- do not add a dedicated status UI
- do not append the notice into the visible Persona log

## Review Adjustments

### Progress Symmetry

The current persona turn handler emits several informational notices before the first real planner output, for example memory-context and persona-state notices.

Those notices must not cancel the delayed processing notice unless the client also treats them as progress. Otherwise the backend would suppress the delayed notice, but the client would continue waiting toward `thinking_stuck`.

For this slice, the delayed processing notice should only be cancelled by signals the client already recognizes as meaningful progress:

- `assistant_delta`
- `tool_plan`
- `tool_call`
- `tool_result`
- `TTS_UNAVAILABLE_TEXT_ONLY`
- terminal cancellation/error/cleanup paths for the active voice turn

Generic informational notices are not progress for this slice.

### Pending Task Lifecycle

The delayed notice must be tracked separately from the existing active-turn transcript state.

A stale task must be cancelled when:

- the websocket disconnects
- the session is explicitly cancelled
- a new `voice_commit` starts for the same session
- a new typed `user_message` starts for the same session
- the route reconnects and reuses the same resumed session id
- real progress is emitted

Without that lifecycle, a delayed notice from an older turn could fire into a later turn or after reconnect.

### Accepted Limitation

This slice only covers the quiet gap before the first visible progress event.

If a turn reaches `tool_call` quickly and then spends a long time inside a slow MCP tool, the client can still later enter `thinking_stuck`. That is acceptable for this slice. If it remains noisy in real use, the next slice should add a richer progress/heartbeat contract around long-running tool execution.

## Backend Design

### Runtime State

Add a per-session delayed processing notice task map, separate from the existing STT state.

Example shape:

- `persona_live_processing_notice_tasks_by_session: dict[str, asyncio.Task[Any]]`

This map is only populated for committed voice turns that have not yet emitted recognized progress.

### Scheduling

After `_commit_persona_live_turn()` emits `VOICE_TURN_COMMITTED`, schedule a delayed async task for that session.

The task should:

1. sleep for the configured delay
2. re-check that the session still has the same pending voice-processing marker
3. emit `VOICE_TURN_PROCESSING`
4. clear its own task entry safely

The implementation should use a small helper so this state is centralized:

- `_schedule_persona_live_processing_notice(session_id)`
- `_cancel_persona_live_processing_notice(session_id)`
- `_mark_persona_live_processing_progress(session_id)`

`_mark_persona_live_processing_progress()` should simply cancel and clear the delayed notice if one exists.

### Cancellation Points

Cancel pending processing notice state when any recognized progress occurs:

- before or during `_emit_assistant_delta`
- before or during `_emit_tool_plan`
- before or during `_emit_tool_call`
- before or during `_emit_tool_result`
- before emitting `TTS_UNAVAILABLE_TEXT_ONLY`
- on cancel paths
- on websocket disconnect/cleanup

To avoid mixing voice-specific behavior into unrelated traffic, the helper should no-op unless a pending processing task exists for that session.

### Testability

The delay must be a module-level constant so tests can monkeypatch it to a short duration. Backend tests should not sleep for real multi-second intervals.

## Client Design

### Hook Behavior

`usePersonaLiveVoiceController` should treat `VOICE_TURN_PROCESSING` as silent progress.

When the hook receives that notice:

- if the state is still `thinking`, clear the current thinking recovery timer
- re-arm the timer from zero
- do not change `warning`
- do not change `state`
- do not show a new UI state

If the recovery panel is already visible because the timer fired first, the processing notice should dismiss it and start a fresh window.

### Route Log Handling

`sidepanel-persona.tsx` should still pass the payload into `liveVoiceController.handlePayload(...)`, but should skip `appendLog(...)` for `reason_code === "VOICE_TURN_PROCESSING"`.

This keeps the notice functional without adding noisy operational log entries.

## Testing

### Backend

Add websocket tests proving:

- delayed `VOICE_TURN_PROCESSING` is emitted after commit with no real progress
- it is not emitted when `tool_plan` arrives before the delay
- it is not emitted when `assistant_delta` arrives before the delay
- it is cleared during cleanup/disconnect

### Frontend

Add hook tests proving:

- `VOICE_TURN_PROCESSING` re-arms the `thinking` recovery window
- a later quiet period still reaches `thinking_stuck`

Add route coverage proving:

- `VOICE_TURN_PROCESSING` is not appended to the visible Persona log

## Success Criteria

- Healthy slow voice turns do not hit `thinking_stuck` during the initial backend quiet gap.
- Fast turns behave exactly as before.
- No new visible warning/banner appears for the processing notice.
- No stale delayed notice survives reconnect, cancel, or later turns in the same session.
