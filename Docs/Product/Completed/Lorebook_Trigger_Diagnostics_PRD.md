# Lorebook Trigger Diagnostics - PRD

## Summary
Add a Lorebook Debug view that shows which entries triggered for a chat turn, why they triggered, and their token cost, with later warnings and exportable diagnostics.

## Goals
- Make lorebook activation transparent for users and debuggers.
- Show token impact per triggered entry.
- Provide exportable diagnostics for troubleshooting.

## Non-Goals
- Changing core lorebook logic or storage.
- Replacing existing world book UI.

## Users and Use Cases
- Power user wants to see why a lorebook entry triggered.
- Developer needs a diagnostics log for a support ticket.
- User wants a warning when lorebook entries exceed budget.

## Scope
1. Stage F1 (MVP). Add a Lorebook Debug view listing triggered entries and token cost with activation reason.
2. Stage F2. Inline warnings for budget overflow or conflicts and export diagnostic log for a conversation.

## Requirements
Functional requirements:
- Add a chat settings view that lists triggered lorebook entries for the latest turn.
- Show activation reason, such as keyword match, regex match, or depth rule.
- Display token cost per entry and total lorebook tokens.
- Provide an export option for the diagnostics log in Stage F2.

Non-functional requirements:
- Use existing world book data without schema changes unless required.
- Respect shared prompt budget caps for lorebook entries. See `Docs/Product/Character_Chat_Prompt_Assembly_Preview_PRD.md`.

## UX Notes
- Place the debug view in chat settings under a collapsible section.
- Use concise labels for activation reasons.

## Data and Persistence
- Diagnostics can be computed at prompt assembly time and stored in a transient client state.
- If persistence is needed, store diagnostics in conversation metadata with a size cap.

## API and Integration
- No new endpoints required if diagnostics are computed client-side.
- If server-side prompt assembly owns lorebook selection, add a debug metadata payload in the chat completion response.

## Edge Cases
- No entries triggered should show an empty state message.
- Regex activation without a specific match location should still show reason.

## Risks and Open Questions
- Ensuring diagnostic detail does not leak sensitive prompt content.
- Potential performance overhead when computing token costs per entry.

## Testing
- Unit tests for activation reason mapping and token cost calculation.
- Integration tests for debug view rendering and export behavior.
- Regression tests for prompt assembly outputs unchanged when diagnostics are disabled.
