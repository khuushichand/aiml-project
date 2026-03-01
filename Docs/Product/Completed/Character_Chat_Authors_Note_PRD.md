# Character Chat Author Note and Memory Box - PRD

## Summary
Introduce an author note memory box that can be set per chat, optionally seeded by per-character defaults, and injected at a fixed depth during prompt assembly.

## Goals
- Provide an author note input per chat with persistence.
- Support per-character default notes that merge with chat notes.
- Inject the note at a configurable depth in the prompt.

## Non-Goals
- Full GM tooling or moderation features in MVP.
- Changes to the world book logic.

## Users and Use Cases
- User wants a shared memory note that influences responses.
- Character creator wants a default author note per character.
- User wants to hide or disable the note for a specific chat in the future.

## Scope
1. Stage D1 (MVP). Per-chat author note input, injection at fixed depth, and optional per-character default.
2. Stage D2. GM-only toggle to exclude from prompt, token count indicator, and warning when long.

## Requirements
Functional requirements:
- Add a per-chat author note input in the chat UI.
- Persist the author note per chat and load it on refresh.
- Inject the author note at a fixed depth position, configurable as "before system" or "depth N".
- Allow an optional per-character default author note in character settings.
- Merge per-character default with per-chat note, with chat override precedence.
- Support an optional GM-only toggle to exclude the note from prompt assembly.

Non-functional requirements:
- Enforce shared prompt budget caps for author notes. See `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md`.
- Keep injection order deterministic for testing.

## UX Notes
- Place the author note input in chat settings with a short description of injection depth.
- Show token count and warning when the note is long in Stage D2.

## Data and Persistence
- Store shared author note in per-chat settings as `authorNote`.
- Store per-character notes in per-chat settings as `characterMemoryById` map where needed.
- Store per-character default note in character settings.
- Use the shared sync and migration rules described in `Docs/Product/Completed/Character_Chat_Greeting_Picker_PRD.md`.

## API and Integration
- No new endpoints if per-chat settings and character metadata already support custom fields.
- If needed, extend metadata schemas for `authorNote` and `characterMemoryById`.

## Edge Cases
- Empty note means no injection.
- If injection depth is invalid, fall back to "before system".
- When both shared and per-character notes exist, merge according to memory scope rules in `Docs/Product/Completed/Group_Multi_Character_Chats_PRD.md`.

## Risks and Open Questions
- Best default injection depth and how it interacts with system prompts.
- Long notes that exceed token budgets or degrade latency.

## Testing
- Unit tests for note persistence and merge precedence.
- Integration tests for prompt assembly injection position.
- UI tests for token count display and GM-only toggle in Stage D2.
