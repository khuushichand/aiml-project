# Character Chat Greeting Inclusion Toggle and Regenerate Behavior - PRD

## Summary
Add a per-chat toggle to include or exclude the greeting from prompt context and ensure regenerate behavior consistently applies character presets, generation settings, and author notes.

## Goals
- Provide a reliable per-chat toggle for greeting inclusion in prompt context.
- Make regenerate behavior consistent for character chats.
- Surface toggle controls in a discoverable UI location.

## Non-Goals
- Overhauling prompt history storage or chat message rendering.
- Changing default behavior for non-character chats.

## Users and Use Cases
- User wants the greeting shown but excluded from the model context.
- User wants regenerate to honor the same settings as initial generation.
- User toggles greeting inclusion per conversation and expects it to persist.

## Scope
1. Stage C1 (MVP). Per-chat toggle for "Include greeting in context" with default on, and regenerate behavior that always applies character preset, generation settings, and author note.
2. Stage C2. Toggle surfaced in composer header with tooltip and persistence, plus a visual indicator when greeting is excluded from context.

## Requirements
Functional requirements:
- Add a per-chat toggle `greetingEnabled` that controls whether greeting messages are included in prompt history.
- Default `greetingEnabled` to true for character chats.
- Persist the toggle per conversation with the shared per-chat settings record.
- Regenerate behavior in character chats must apply the character prompt preset, per-character generation settings, and author note.
- Regenerate behavior must respect the current greeting toggle state.
- Non-character chats use the default global prompt mode.

Non-functional requirements:
- Avoid altering chat history persistence semantics.
- Keep regenerate behavior deterministic and testable.

## UX Notes
- Place the toggle in the composer header with a concise tooltip.
- If greeting is excluded, render a visual indicator on the greeting message.

## Data and Persistence
- Store `greetingEnabled` in the per-chat settings record.
- Use the shared sync and migration rules described in `Docs/Product/Character_Chat_Greeting_Picker_PRD.md`.

## API and Integration
- No new endpoints if per-chat settings are stored in history metadata.
- If needed, extend per-chat settings schema to include `greetingEnabled`.

## Edge Cases
- If no greeting exists, the toggle has no effect and should be disabled or hidden.
- If the greeting is deleted after the toggle was set, the toggle persists but no greeting is injected.

## Risks and Open Questions
- Ensuring regenerate behavior remains consistent across different chat modes.
- Interaction with group chat greeting scope, see `Docs/Product/Group_Multi_Character_Chats_PRD.md`.

## Testing
- Unit tests for prompt history construction with greeting included and excluded.
- Integration tests for regenerate behavior respecting preset, generation settings, author note, and greeting toggle.
- UI tests for toggle persistence and indicator rendering.
