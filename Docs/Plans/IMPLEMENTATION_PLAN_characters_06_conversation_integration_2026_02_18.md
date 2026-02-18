# Implementation Plan: Characters - Conversation Integration

## Scope

Components: `apps/packages/ui/src/components/Option/Characters/Manager.tsx`, `apps/packages/ui/src/hooks/useSelectedCharacter.ts`, chat services in `apps/packages/ui/src/services/tldw/TldwApiClient.ts`, character/chat APIs in `tldw_Server_API/app/api/v1/endpoints/characters_endpoint.py` and `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
Finding IDs: `C-19` through `C-21`

## Finding Coverage

- No quick-test chat from characters page: `C-19`
- No default-character preference for starting chats: `C-20`
- Conversation analytics are limited to count only: `C-21`

## Stage 1: Implement Quick Chat Without Page Exit
**Goal**: Allow lightweight character testing directly from `/characters`.
**Success Criteria**:
- Character actions include "Quick chat" opening a drawer/modal with compact chat UI.
- User can send and receive a short message loop without route navigation.
- Session context isolates quick chat from full chat history unless explicitly promoted.
**Tests**:
- Component tests for quick-chat open/close and character context binding.
- Integration tests for send/receive flow and error states.
- E2E test for quick chat launch from both table and gallery views.
**Status**: Not Started

## Stage 2: Add Default Character Preference
**Goal**: Let users set a preferred character for new chat sessions.
**Success Criteria**:
- Character menu includes "Set as default" and "Clear default" actions.
- Preference persists in user-scoped storage/preferences endpoint.
- Chat start flow can preselect default character when no explicit override is provided.
**Tests**:
- Unit tests for preference read/write helpers.
- Integration tests for default selection on new chat bootstrap.
- Regression tests ensuring explicit user selection overrides default.
**Status**: Not Started

## Stage 3: Expand Conversation Insights
**Goal**: Improve character usage visibility beyond raw conversation count.
**Success Criteria**:
- Conversations modal/header displays `last_active` and average message count.
- Stats gracefully handle characters with zero conversations.
- Metrics source and refresh strategy are documented.
**Tests**:
- Backend tests for aggregate stat fields and null-safe defaults.
- Component tests for stats rendering and formatting.
- Integration tests for stats update after new chat activity.
**Status**: Not Started

## Stage 4: Navigation and Workflow Cohesion
**Goal**: Keep characters and chat workflows coherent for mixed-depth usage.
**Success Criteria**:
- Full "Chat" action remains available while quick-chat path is discoverable.
- Optional "open in new tab" behavior is available if chosen by product decision.
- No regression in existing selected-character handoff behavior.
**Tests**:
- E2E tests for legacy chat navigation path.
- Manual QA matrix for quick-chat + full-chat transitions.
**Status**: Not Started

## Dependencies

- Stage 1 depends on reusable chat composer/view primitives that can run in a constrained overlay.
- Stage 2 may require user-preference API surface if local-only persistence is insufficient.
