# Message Steering Controls - PRD

## Summary
Add lightweight message steering controls that let users continue as user, impersonate user, or force narration for a single response, with optional per-message macros later.

## Goals
- Provide quick actions that influence a single response.
- Keep controls optional and non-disruptive to standard chat flow.

## Non-Goals
- Full scripting or automation system for prompts.
- Changes to core prompt assembly beyond adding a short steering snippet.

## Users and Use Cases
- User wants the assistant to continue the user's message in the same voice.
- User wants a response written as the user for roleplay.
- User wants one response forced into narration style.

## Scope
1. Stage J1 (MVP). Continue as user, impersonate user, and force narrate toggle for a single response.
2. Stage J2. Per-message action macros that prepend a style snippet before regenerate.

## Requirements
Functional requirements:
- Add actions for continue as user and impersonate user.
- Add a force narrate toggle that applies to a single response and resets after use.
- Steering actions must apply on regenerate as well as initial generation for that turn.
- Actions should not persist to subsequent messages unless explicitly re-selected.

Non-functional requirements:
- Steering controls must not alter stored chat history beyond the generated message.
- Steering snippets must be visible in the prompt preview when enabled.

## UX Notes
- Place steering actions near the composer or message actions.
- Provide clear labels and brief tooltips for each action.

## Data and Persistence
- Steering actions are per-message and do not require persistence.
- If a per-message macro is used in Stage J2, store it with the message metadata for auditability.

## API and Integration
- If server-side prompt assembly is used, include steering flags in the chat completion request.

## Edge Cases
- If both continue and impersonate are selected, prefer impersonate and show a warning.
- Force narrate should not apply to user messages.

## Risks and Open Questions
- Potential confusion between steering actions and character presets.
- Model-specific adherence to narration and impersonation instructions.

## Testing
- Unit tests for steering flag precedence and reset behavior.
- Integration tests for regenerate with steering actions applied.
- UI tests for action selection and clearing.
