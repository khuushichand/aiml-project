# Character Chat Enhancements Rollout Plan

## Summary
Staged rollout plan for the character chat enhancement PRDs, aligned to dependencies and risk reduction.

## Phase 0: Foundations
Goal:
- Establish server-backed per-chat settings storage and sync.

Deliverables:
- `Docs/Product/Completed/Character_Chat_Settings_Metadata_PRD.md` implemented.
- Server endpoints to read and write conversation settings.
- Client migration to push local settings to server on first sync.

Exit criteria:
- Round-trip settings read and write works for a conversation.
- Last-write-wins reconciliation confirmed in integration tests.

## Phase 1: Greeting and Context Controls
Goal:
- Provide greeting selection, persistence, and inclusion toggles.

Deliverables:
- `Docs/Product/Completed/Character_Chat_Greeting_Picker_PRD.md`
- `Docs/Product/Completed/Character_Chat_Greeting_Inclusion_PRD.md`

Exit criteria:
- Greeting selection persists across refresh and device.
- Greeting inclusion toggle affects prompt history as expected.

## Phase 2: Memory and Presets
Goal:
- Add author notes and prompt formatting presets.

Deliverables:
- `Docs/Product/Completed/Character_Chat_Authors_Note_PRD.md`
- `Docs/Product/Completed/Character_Chat_Prompt_Presets_PRD.md`

Exit criteria:
- Author note injection position is correct and stable.
- Preset rendering and appendable blocks behave deterministically.

## Phase 3: Generation and Preview
Goal:
- Add per-character generation presets and prompt preview with budgets.

Deliverables:
- `Docs/Product/Completed/Character_Generation_Presets_PRD.md`
- `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md`

Exit criteria:
- Generation settings applied per character without overriding explicit per-chat model settings.
- Prompt preview matches actual prompt assembly and flags truncations.

## Phase 4: Diagnostics and Steering
Goal:
- Add lorebook diagnostics and message steering controls.

Deliverables:
- `Docs/Product/Completed/Lorebook_Trigger_Diagnostics_PRD.md`
- `Docs/Product/Completed/Message_Steering_Controls_PRD.md`

Exit criteria:
- Lorebook trigger reasons and token costs surfaced in UI.
- Steering controls apply to a single response and reset as expected.

## Phase 5: Multi-Character and Summarization
Goal:
- Enable multi-character chats and auto-summarization with pinned messages.

Deliverables:
- `Docs/Product/Completed/Group_Multi_Character_Chats_PRD.md`
- `Docs/Product/Completed/Chat_Auto_Summarization_Pinned_PRD.md`

Exit criteria:
- Scope resolution works across greeting, preset, and memory rules.
- Summaries exclude pinned messages and respect token budgets.

## Phase 6: Character Card Interop
Goal:
- Implement ST v2 character card import and export.

Deliverables:
- `Docs/Product/Completed/Character_Card_Import_Export_STv2_PRD.md`

Exit criteria:
- JSON and PNG import validation complete with clear error messaging.
- JSON export matches schema and preserves required fields.

## Cross-Cutting Gates
- Token budgets enforced per `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md`.
- Per-chat settings stored server-side per `Docs/Product/Completed/Character_Chat_Settings_Metadata_PRD.md`.
- Regression tests for non-character chats must remain green.

## Notes
- Phases can overlap if dependencies are satisfied, but each exit criteria should be met before moving to the next phase.
