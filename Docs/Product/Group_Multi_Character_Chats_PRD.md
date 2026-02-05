# Group and Multi-Character Chats - PRD

## Summary
Enable chats with multiple characters, including turn-taking, directed replies, and explicit scoping for greetings, presets, and memory.

## Goals
- Allow selecting multiple characters in a single chat.
- Provide clear scope controls for greetings, presets, and memory.
- Preserve message attribution per character.

## Non-Goals
- Full group chat UI parity with SillyTavern.
- Major changes to server chat schema beyond metadata fields.

## Users and Use Cases
- User wants a round-robin conversation among multiple characters.
- User wants to direct a reply to a specific character.
- User wants memory to be shared or per-character depending on the scenario.

## Scope
1. Stage I1 (MVP). Multi-character selection, turn-taking mode, greeting scope control, preset scope control, and memory scope control.
2. Stage I2. Directed replies plus per-character memory blocks and greeting control refinements.

## Requirements
Functional requirements:
- Allow selecting multiple characters for a chat.
- Support turn-taking mode with per-character prompt injection.
- Provide greeting scope control with labels "Per chat" and "Per character".
- Provide preset scope control with labels "Chat override" and "Per character".
- Provide memory scope control with labels "Shared", "Per character", and "Both".
- Preserve chat history attribution per character on each message.

Interaction rules:
- Greeting inclusion respects the greeting scope and the "Include greeting in context" toggle.
- Preset precedence order is per-message override, chat-level override, speaking character preset, then global default.
- Memory injection respects memory scope with shared and per-character notes.

Greeting rules:
- Per chat scope applies a single greeting to the conversation.
- Per character scope applies each character greeting only on that character's first reply.
- Directed replies apply the greeting only when the selected character responds first in per-character mode.

Preset precedence rules:
- When preset scope is chat, the chat override applies to every turn until cleared.
- When preset scope is character, each turn uses the speaking character preset.

Memory rules:
- Shared scope injects one author note for all turns.
- Per character scope injects only the speaking character note.
- Both scope injects shared note first, then the speaking character note.

## Scope Interaction Decision Matrix
Legend:
- Greeting injected assumes greetingEnabled is true and at least one greeting exists.
- Preset order abbreviations are PM for per-message override, Chat for chat override, Char for character preset, Global for global default.
- Memory truncation applies shared token caps, then truncates character note first if needed.

| greetingScope | presetScope | memoryScope | Greeting injected | Preset resolution | Memory injection and truncation |
| --- | --- | --- | --- | --- | --- |
| chat | chat | shared | chat-first | PM then Chat then Global | shared only |
| chat | chat | character | chat-first | PM then Chat then Global | character only |
| chat | chat | both | chat-first | PM then Chat then Global | shared then character |
| chat | character | shared | chat-first | PM then Char then Global | shared only |
| chat | character | character | chat-first | PM then Char then Global | character only |
| chat | character | both | chat-first | PM then Char then Global | shared then character |
| character | chat | shared | per-character-first | PM then Chat then Global | shared only |
| character | chat | character | per-character-first | PM then Chat then Global | character only |
| character | chat | both | per-character-first | PM then Chat then Global | shared then character |
| character | character | shared | per-character-first | PM then Char then Global | shared only |
| character | character | character | per-character-first | PM then Char then Global | character only |
| character | character | both | per-character-first | PM then Char then Global | shared then character |

## Edge Cases
- Single character with per-character greeting behaves like chat-first to avoid repeated greetings.
- greetingEnabled false or no eligible greeting means no greeting is injected.

## Fallbacks and Defaults
- Missing or invalid scope values fall back to greetingScope chat, presetScope character, and memoryScope shared.

## Data and Persistence
- Store `greetingScope`, `presetScope`, `memoryScope`, `chatPresetOverrideId`, and `characterMemoryById` in per-chat settings.
- Use the shared sync and migration rules described in `Docs/Product/Character_Chat_Greeting_Picker_PRD.md`.

## UX Notes
- Scope labels must be explicit and visible in chat settings.
- Directed replies should clearly show the selected responder.

## API and Integration
- No new endpoints required if per-chat settings are stored in history metadata.
- If server support is required, extend chat metadata schemas to store scope fields.

## Risks and Open Questions
- Complexity of scope interactions for users without strong mental models.
- Ensuring turn-taking remains predictable with manual directed replies.

## Testing
- Unit tests for scope resolution and greeting, preset, and memory precedence.
- Integration tests for turn-taking and directed reply flows.
- Regression tests for single-character chats and non-character chats.
