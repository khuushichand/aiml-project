# Character Chat Greeting Picker and Persistence - PRD

## Summary
Provide a greeting picker that is visible before the first message in a character chat, allow reroll and list selection, and persist the chosen greeting per conversation with robust staleness detection when greetings change.

## Goals
- Make greeting selection user-controlled and stable across refresh.
- Persist greeting selection per conversation with deterministic fallbacks.
- Detect stale greeting selections when character greetings are edited.

## Non-Goals
- Full SillyTavern UI parity.
- Overhauling world book logic or server APIs.
- New model providers or core schema changes unless required.

## Users and Use Cases
- Chat user wants to pick a specific greeting and keep it across refresh.
- Chat user wants to reroll a greeting without changing the character.
- Editor changes character greetings and expects stale selections to self-heal.

## Scope
1. Stage A1 (MVP). Inline picker above the first message when the chat is empty and a character is selected, reroll action, auto-select random greeting on first load, and persistent selection per conversation.
2. Stage A2. List picker with greeting preview and source, plus a "Use character default" option for deterministic first greeting.

## Requirements
Functional requirements:
- Show an inline greeting picker when no non-greeting messages exist and a character is selected.
- Provide a "Reroll" action that selects a new greeting from available variants.
- Persist the selected greeting per conversation using historyId or serverChatId.
- Default behavior selects a random greeting on first load when greetings exist.
- Provide a "Pick from list" dropdown with greeting source and preview length.
- Provide a "Use character default" option that deterministically selects the first greeting.
- Clear the persisted selection when the character changes or the chat is reset.
- Apply display-name replacements during greeting injection.

Staleness detection requirements:
- Maintain `greetingsVersion` and or `greetingsChecksum` on any greeting add, edit, delete, or reorder.
- Persist the selection with the `greetingsVersion` or `greetingsChecksum` used at selection time.
- On load, compare the current version or checksum with the persisted value.
- If stale and "Use character default" is enabled, select the deterministic first greeting and persist it.
- If stale and "Use character default" is disabled, reroll randomly from remaining greetings and persist it.
- If no greetings exist, hide the picker and skip greeting injection.

Deterministic fallback rules:
- If multiple greetings have identical text, the deterministic first greeting is the first in source order.
- Persist using a stable greeting ID when available, otherwise persist by index with staleness checks.
- If a persisted greeting is deleted or missing, apply the same fallback rules as stale detection.

Non-functional requirements:
- Persist selection across refresh and client restarts.
- Avoid server schema changes unless required for history metadata storage.
- Respect shared prompt budget caps for greetings. See `Docs/Product/Character_Chat_Prompt_Assembly_Preview_PRD.md`.

## UX Notes
- Show the picker only when the chat has no non-greeting messages.
- Do not auto-change after the initial selection unless the user rerolls or greetings become stale.
- Display labels for "Reroll" and "Pick from list" with clear affordances.

## Data and Persistence
Storage strategy:
- Use a hybrid model with local storage for offline-first and sync to server history metadata when serverChatId exists.
- Store `greetingSelectionId` and `greetingsVersion` or `greetingsChecksum` in per-chat settings.
- Store `useCharacterDefault` and `greetingEnabled` when present in the chat settings record.

Per-chat settings record:
- Fields for this PRD: `greetingSelectionId`, `greetingsVersion`, `greetingsChecksum`, `useCharacterDefault`, `updatedAt`, `schemaVersion`.
- Keyed by historyId with optional serverChatId mapping.

Sync and conflict resolution:
- Last-write-wins per field group using `updatedAt` timestamps.
- Tie-breaker: server wins for server-backed chats, local wins for local-only chats.

Migration and compatibility:
- Add `schemaVersion` and `updatedAt` to per-chat settings records, default schemaVersion to 1 for existing data and 2 for new records.
- One-release backward read path migrates legacy greeting fields into the new record and saves once.
- For server-backed chats, reconcile local and server metadata once on upgrade and persist the merged record.

## API and Integration
- No new endpoints required if history metadata supports arbitrary per-chat settings fields.
- If metadata storage is limited, add a minimal settings blob field on conversation history.

## Edge Cases
- No greetings available hides the picker and skips injection.
- Greeting list changes reorder or delete selections and triggers staleness handling.
- Character switch clears selection and re-initializes on first load.

## Risks and Open Questions
- How to scope greeting IDs if greetings are stored as plain text only.
- Ensuring staleness detection is efficient for large greeting lists.

## Testing
- Unit tests for greeting selection persistence by historyId and serverChatId.
- Unit tests for staleness detection with version and checksum changes.
- Integration tests for reroll, list selection, and character switch behavior.
- Regression tests to ensure non-character chats are unchanged.
