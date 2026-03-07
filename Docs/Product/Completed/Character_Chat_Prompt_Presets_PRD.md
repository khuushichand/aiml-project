# Character Chat Prompt Formatting Presets - PRD

## Summary
Add per-character prompt formatting presets that control how character fields and world books are assembled into the prompt, with appendable text blocks and deterministic conflict resolution.

## Goals
- Allow each character to choose a formatting preset that affects prompt assembly.
- Preserve existing actor and world book injection order while enabling appendable blocks.
- Provide a preset editor and compatibility presets in a later stage.

## Non-Goals
- Full SillyTavern UI parity.
- Replacing the existing prompt assembly pipeline for non-character chats.
- Introducing new provider-specific prompt engines.

## Users and Use Cases
- Roleplay user wants a compact or ST-style formatting style per character.
- Creator wants to tune how examples and scenario text are structured.
- Power user wants to preview and edit preset templates later.

## Scope
1. Stage B1 (MVP). Per-character preset selection stored with the character, using existing character fields and world books, applied in character chat prompt assembly.
2. Stage B2. Preset editor UI with template tokens list and preview, plus preset bundles: ST default, Roleplay compact, Instructional.

## Requirements
Functional requirements:
- Store the selected preset per character and apply it only in character chat mode.
- Preset template supports name, system prompt, personality, scenario, message_example, post_history_instructions, and world books.
- Preserve existing actor and world book injection logic and ordering.
- Apply preset formatting first, then apply actor and world book injections.
- Conflict resolution for scalar parameters uses later injection to override earlier values.
- Conflict resolution for text blocks replaces earlier content unless both blocks are appendable.
- Appendable text blocks concatenate only when both source and target have `appendable=true`.

Appendable metadata requirements:
- Add a boolean `appendable` field to each text block in preset templates and actor or world book entries.
- UI exposes an "Appendable" checkbox for applicable text fields.
- Default behavior when absent is `appendable=false`.

Non-functional requirements:
- Keep prompt assembly deterministic and testable.
- Avoid regressions in non-character chat prompt assembly.
- Enforce shared prompt budget caps for presets. See `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md`.

## UX Notes
- Preset selection lives in the character edit UI with optional quick access in chat settings.
- Preset editor is Stage B2 only and should include a preview of the assembled prompt.

## Data and Persistence
- Store `promptPresetId` with the character profile in local character storage.
- If characters are synced to server metadata, mirror `promptPresetId` in the character record.
- Store preset templates locally, with optional export later.

## API and Integration
- No new endpoints required if character metadata already supports custom fields.
- If server storage is needed, extend character metadata schema for `promptPresetId` and template references.

## Edge Cases
- Missing preset falls back to the global default formatting.
- Missing fields in the character do not produce empty placeholders in the prompt.
- When actor or world book entries override system directives, they replace preset content unless appendable.

## Risks and Open Questions
- Balancing flexibility with predictable prompt formatting across models.
- Ensuring appendable semantics do not introduce duplicated or contradictory blocks.

## Testing
- Unit tests for preset selection, template rendering, and appendable concatenation.
- Integration tests for prompt assembly ordering with actor and world book injections.
- Regression tests for non-character chat prompt assembly.
