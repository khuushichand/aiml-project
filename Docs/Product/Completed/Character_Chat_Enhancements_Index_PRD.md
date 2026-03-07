# Character Chat Enhancements Index - PRD

## Summary
Index and dependency map for the SillyTavern-style character chat enhancement PRDs.

## PRD List
1. `Docs/Product/Completed/Character_Chat_Greeting_Picker_PRD.md`
2. `Docs/Product/Completed/Character_Chat_Prompt_Presets_PRD.md`
3. `Docs/Product/Completed/Character_Chat_Greeting_Inclusion_PRD.md`
4. `Docs/Product/Completed/Character_Chat_Authors_Note_PRD.md`
5. `Docs/Product/Completed/Character_Card_Import_Export_STv2_PRD.md`
6. `Docs/Product/Completed/Lorebook_Trigger_Diagnostics_PRD.md`
7. `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md`
8. `Docs/Product/Completed/Character_Generation_Presets_PRD.md`
9. `Docs/Product/Completed/Group_Multi_Character_Chats_PRD.md`
10. `Docs/Product/Completed/Message_Steering_Controls_PRD.md`
11. `Docs/Product/Completed/Chat_Auto_Summarization_Pinned_PRD.md`
12. `Docs/Product/Completed/Character_Chat_Settings_Metadata_PRD.md`

## Dependencies and Relationships
1. Greeting picker depends on per-chat settings persistence and sync.
2. Greeting inclusion toggle depends on greeting picker and per-chat settings.
3. Author note depends on per-chat settings and prompt assembly ordering.
4. Prompt presets depend on prompt assembly and affect regeneration behavior.
5. Generation presets depend on character metadata and generation pipeline.
6. Lorebook diagnostics depends on existing world book selection and tokenization.
7. Prompt assembly preview depends on all prompt-injected sections and tokenization.
8. Group chats depend on greeting picker, greeting inclusion, author note, and generation presets for scope rules.
9. Message steering controls depend on prompt assembly and regenerate behavior.
10. Auto-summarization depends on prompt assembly budgets and message metadata.
11. Character card import and export is mostly independent, but should preserve fields used by prompt presets and greetings.
12. Settings metadata is a shared foundation for server-backed per-chat settings and sync.

## Shared Constraints
1. Token budgets, truncation order, and section visibility are defined in `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md` and referenced by other PRDs.
2. Per-chat settings persistence and sync rules are defined in `Docs/Product/Completed/Character_Chat_Greeting_Picker_PRD.md` and referenced by other PRDs.
3. Server metadata schema and migration details are defined in `Docs/Product/Completed/Character_Chat_Settings_Metadata_PRD.md`.

## Suggested Implementation Order
1. Per-chat settings storage and migration foundation.
2. Greeting picker and greeting inclusion toggle.
3. Author note injection.
4. Prompt presets and generation presets.
5. Prompt assembly preview and budget enforcement.
6. Lorebook diagnostics.
7. Group and multi-character chat scopes.
8. Message steering controls.
9. Auto-summarization with pinned messages.
10. Character card import and export.
