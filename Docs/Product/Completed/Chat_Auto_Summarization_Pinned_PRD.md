# Chat Auto-Summarization with Pinned Messages - PRD

## Summary
Introduce automatic chat summarization after a configurable threshold, while allowing users to pin messages that are excluded from compression.

## Goals
- Reduce prompt length growth by summarizing older messages.
- Allow users to protect important messages from compression.
- Keep summaries consistent and easy to refresh.

## Non-Goals
- Replacing existing manual summarization tools.
- Changing chat message storage format beyond adding minimal metadata.

## Users and Use Cases
- User with long chats wants faster performance and lower token usage.
- User wants to keep key messages verbatim by pinning them.
- User wants to see when and how summaries are created.

## Scope
1. MVP. Auto-summarization when a threshold is reached, pin or unpin messages, and exclude pinned messages from compression.
2. V2. Manual "summarize now" and "rebuild summary" actions, plus summary preview panel.

## Requirements
Functional requirements:
- Define a configurable threshold for summarization, based on message count or token count.
- When threshold is reached, summarize older messages while excluding pinned messages.
- Preserve pinned messages verbatim in the prompt history.
- Store the summary per conversation and update it when new messages exceed the threshold.
- Provide a pin toggle on messages and a pinned messages view in chat settings.

Non-functional requirements:
- Summarization must be deterministic given the same inputs and configuration.
- Summaries must respect shared prompt budget caps and truncation rules. See `Docs/Product/Completed/Character_Chat_Prompt_Assembly_Preview_PRD.md`.

## UX Notes
- Show a small pin icon on each message with clear tooltip.
- In chat settings, list pinned messages with quick navigation.

## Data and Persistence
- Add a `pinned` boolean to message metadata.
- Store a conversation-level summary with `updatedAt` and a source window marker.

## API and Integration
- If summaries are server-side, add an endpoint to compute and store summaries.
- If client-side, store summaries in local metadata and sync to server for server-backed chats.

## Edge Cases
- If all older messages are pinned, summarization should skip or warn.
- If a pinned message is deleted, remove it from the pinned list and rebuild summary if needed.

## Risks and Open Questions
- How to balance summary freshness with compute cost.
- Model-specific variability in summarization quality.

## Testing
- Unit tests for pinned message exclusion and threshold logic.
- Integration tests for summary injection and refresh behavior.
- Regression tests to ensure non-summarized chats behave unchanged.
