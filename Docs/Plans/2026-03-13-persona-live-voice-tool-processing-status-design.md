# Persona Live Voice Tool Processing Status Design

## Goal

Reduce false or absent recovery states in `Persona Garden -> Live Session` during long-running tool-backed voice turns by:

- showing an honest current-action status line from existing `tool_call` payloads
- reusing one delayed persona-live notice scheduler for quiet periods while the turn is still `thinking`
- preserving a recovery path both after `tool_call` and after `tool_result` when assistant synthesis is still slow

## Scope

This slice is limited to:

- the persona websocket backend in `tldw_Server_API/app/api/v1/endpoints/persona.py`
- the Persona Garden live voice hook in `apps/packages/ui/src/hooks/usePersonaLiveVoiceController.tsx`
- the Live Session UI card in `apps/packages/ui/src/components/PersonaGarden/AssistantVoiceCard.tsx`
- Persona Garden route log handling in `apps/packages/ui/src/routes/sidepanel-persona.tsx`

This slice does not add:

- recurring heartbeats
- MCP-native streaming progress
- per-turn correlation ids
- new approval UX in the Live card

## Problem Statement

The current live voice recovery flow handles the initial quiet gap after `VOICE_TURN_COMMITTED` via `VOICE_TURN_PROCESSING`, but there are still two unhealthy gaps:

1. After `tool_call`, the hook clears `thinking` recovery and can remain quiet until `tool_result`.
2. After `tool_result`, the hook clears `thinking` recovery again, so a slow final assistant response can leave the user without a recovery path.

At the same time, the current Live tab gives the user no compact explanation of what the assistant is doing while a tool is running.

## Chosen Approach

Use existing `tool_call` payloads for user-facing status text and generalize delayed processing notices into a single reusable scheduler that can emit different quiet-gap notices while the voice turn remains in `thinking`.

The two notice types in play become:

- `VOICE_TURN_PROCESSING`
  Used for the initial quiet gap after a committed voice turn and before first real progress.
- `VOICE_TOOL_EXECUTION_PROCESSING`
  Used for quiet gaps after tool progress when the turn is still `thinking`.

The client behavior becomes:

- show a compact current-action line on `tool_call`
- re-arm `thinking` recovery on `tool_call`
- re-arm it again on delayed quiet-gap notices
- re-arm it after `tool_result` if the turn still has not produced assistant output

## Review Adjustments

### One Scheduler, Not Two

The backend already has a per-session delayed processing notice task map for `VOICE_TURN_PROCESSING`.

This slice should not create a second parallel delayed-task mechanism for tool execution. Instead, refactor the scheduler into a generic helper that accepts:

- `session_id`
- `reason_code`
- `message`
- optional extra metadata such as `tool`, `step_idx`, and `why`

That keeps cancellation semantics centralized and reduces races between overlapping delayed notices.

### Close The Post-Tool-Result Gap

This slice should not stop at `tool_call`.

If a tool returns and the backend is still quiet before `assistant_delta` or `tts_audio`, the client still needs a recovery path. For that reason:

- `tool_result` should clear any active tool status line
- `tool_result` should re-arm `thinking` recovery when the turn remains in `thinking`
- the delayed notice scheduler should be reusable for other quiet gaps after recognized progress, not only after commit

### Honest Status Text Only

The current `tool_call` event includes:

- `tool`
- `args`
- `policy`
- `why`

It does not include `description`.

So the user-facing status copy must stay honest:

- preferred: `Running {tool}: {why}`
- fallback: `Running {tool}...`

The status line should truncate long `why` text for the card instead of pretending to know more detail than the event actually carries.

### Approval Handoff

Approval-required `tool_result` payloads already surface route-level approval UI.

For this slice:

- clear the active tool status line when approval is required
- clear recovery so the approval UI becomes the dominant state

A future slice may add a `Waiting for approval` status in the Live card, but that is out of scope here.

## Backend Design

### Runtime State

Keep one per-session delayed notice task map:

- `persona_live_processing_notice_tasks_by_session: dict[str, asyncio.Task[Any]]`

Do not add a second task map for tool execution.

### Generic Delayed Notice Helper

Refactor the current helper shape into:

- `_schedule_persona_live_processing_notice(session_id, reason_code, message, **extra)`
- `_cancel_persona_live_processing_notice(session_id)`
- `_mark_persona_live_processing_progress(session_id)`

`_schedule_persona_live_processing_notice(...)` should:

1. cancel any existing delayed notice for that session
2. sleep for the configured delay
3. verify that its task is still the active scheduled notice for the session
4. emit the requested `notice`
5. clear its own task entry safely

### Scheduling Rules

Schedule delayed notices in these cases:

- after `VOICE_TURN_COMMITTED`
  - reason code: `VOICE_TURN_PROCESSING`
  - message: `Still processing this voice turn.`
- after `tool_call`
  - reason code: `VOICE_TOOL_EXECUTION_PROCESSING`
  - message: `Tool execution is still in progress.`
  - extras: `tool`, `step_idx`, and `why` when present

Re-arm thinking recovery after `tool_result` on the client side. The backend does not need a third notice immediately after `tool_result`; the existing scheduler can be reused later if a follow-up quiet-gap notice is still needed.

### Cancellation Rules

Cancel pending delayed notices when recognized progress or terminal state appears:

- `assistant_delta`
- `tool_plan`
- `tool_call`
- `tool_result`
- `tts_audio`
- `TTS_UNAVAILABLE_TEXT_ONLY`
- explicit cancel/reset paths
- websocket disconnect cleanup

Do not cancel on generic informational notices that the client does not treat as progress.

## Client Design

### Hook State

Add one transient field to `usePersonaLiveVoiceController`:

- `activeToolStatus: string`

This is a compact current-action indicator, not a full trace.

### Event Handling

On `tool_call`:

- derive `activeToolStatus` from `tool` and `why`
- clear any visible `thinking_stuck` panel
- re-arm the thinking recovery timer from zero

On `VOICE_TOOL_EXECUTION_PROCESSING`:

- if still `thinking` and `activeToolStatus` is non-empty, re-arm the timer
- do not change `warning`
- do not create a new banner
- do not append it to the visible Persona log

On `tool_result`:

- clear `activeToolStatus`
- if the turn remains `thinking`, re-arm the thinking recovery timer so the user still gets recovery if final assistant output stalls

On approval-required `tool_result`:

- clear `activeToolStatus`
- clear recovery so the explicit approval UI owns the interaction state

On `assistant_delta`, `tts_audio`, `resetTurn`, reconnect, or disconnect:

- clear `activeToolStatus`

### Live Card UI

Add a compact neutral status block to `AssistantVoiceCard`:

- label: `Current action`
- body: `Running search_notes: looking through your notes`

Only render it when:

- `state === "thinking"`
- `activeToolStatus` is non-empty

It should appear below warning banners and above recovery panels.

## Route Handling

`sidepanel-persona.tsx` should suppress visible log entries for:

- `VOICE_TURN_PROCESSING`
- `VOICE_TOOL_EXECUTION_PROCESSING`

The live voice controller must still receive both notices.

## Testing

### Backend

Add websocket coverage proving:

- delayed `VOICE_TOOL_EXECUTION_PROCESSING` fires after a quiet window following `tool_call`
- it is suppressed when `tool_result` arrives before the delay
- it includes `tool` and `step_idx`
- the generic scheduler still handles `VOICE_TURN_PROCESSING` correctly after refactor

### Frontend Hook

Add tests proving:

- `tool_call` sets `activeToolStatus`
- `tool_call` re-arms `thinking` recovery
- `VOICE_TOOL_EXECUTION_PROCESSING` re-arms recovery without changing warning/state
- `tool_result` clears `activeToolStatus`
- `tool_result` re-arms recovery when still `thinking`
- approval-carrying `tool_result` clears `activeToolStatus` and recovery

### Frontend UI

Add component coverage proving:

- the current-action line renders only while `thinking` with `activeToolStatus`
- it is hidden when status text is empty

### Route

Add route coverage proving:

- `VOICE_TOOL_EXECUTION_PROCESSING` does not append to the visible Persona log

## Success Criteria

- Live voice no longer loses its recovery path after `tool_call` or `tool_result`.
- Users see a compact, honest current-action line while a tool is running.
- Delayed processing notices remain centralized under one scheduler.
- Processing notices stay out of the visible Persona log.
