# Per-Character Generation Presets - PRD

## Summary
Add per-character generation settings that apply automatically when a character is selected, with optional quick-swap presets and per-chat overrides.

## Goals
- Allow characters to define temperature, top_p, repetition penalty, and stop strings.
- Apply character generation settings by default for character chats.
- Provide simple quick-swap presets in a later stage.

## Non-Goals
- Changing default behavior for non-character chats.
- Adding new model providers or new sampling parameters.

## Users and Use Cases
- Creator wants a specific sampling style for a character.
- User wants a one-click switch between Creative and Strict settings.
- User wants to override character settings per chat when needed.

## Scope
1. Stage H1 (MVP). Store per-character generation settings and apply them when the character is selected.
2. Stage H2. Add quick-swap presets with per-chat override.

## Requirements
Functional requirements:
- Store per-character generation settings: temperature, top_p, repetition penalty, and stop strings.
- Apply these settings when the character is active in a chat.
- Do not override explicit per-chat model settings unless the user opts in.
- Support quick-swap preset labels and values in Stage H2.
- Support per-chat overrides in Stage H2 with clear precedence rules.

Non-functional requirements:
- Ensure compatibility with existing model parameter validation.
- Keep parameter merges deterministic and testable.

## UX Notes
- Settings live in the character editor with a quick access in chat settings.
- Quick-swap presets appear as simple buttons or a dropdown.

## Data and Persistence
- Store generation settings in the character record.
- Store optional per-chat overrides in per-chat settings and sync using the shared rules in `Docs/Product/Character_Chat_Greeting_Picker_PRD.md`.

## API and Integration
- No new endpoints required if character metadata supports custom fields.
- If server storage is needed, extend character metadata for generation parameters.

## Edge Cases
- Missing settings fall back to global defaults.
- Invalid parameter values are rejected with validation errors.

## Risks and Open Questions
- Conflicts between per-chat model settings and per-character defaults.
- Model-specific parameter support differences.

## Testing
- Unit tests for parameter precedence and validation.
- Integration tests for applying settings during generation.
- Regression tests for non-character chat generation unchanged.
