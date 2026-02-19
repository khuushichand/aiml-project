# Implementation Plan: Chat Dictionaries - Connection to Character Chat

## Scope

Components: dictionary list/actions in `apps/packages/ui/src/components/Option/Dictionaries/Manager.tsx`, chat assignment surfaces, dictionary processing orchestration in `ChatDictionaryService`, related chat APIs
Finding IDs: `7.1` through `7.5`

## Finding Coverage

- Relationship visibility and assignment UX: `7.1`
- Safety prompts for deactivate/delete in active use: `7.2`
- Multi-dictionary execution priority transparency: `7.3`
- Token budget defaults and metadata integration: `7.4`
- Processing audit history and explainability: `7.5`

## Stage 1: Expose Dictionary-to-Chat Relationships
**Goal**: Make dictionaries first-class entities in chat workflows.
**Success Criteria**:
- Dictionary UI displays linked chats and active-session counts.
- Quick-assign action allows attaching dictionary to selected chat(s).
- Users can navigate from dictionary to associated chat context directly.
- Relationship data is available via stable API contract.
**Tests**:
- API integration tests for chat-assignment list/query endpoints.
- Component tests for linked-chat rendering and quick-assign flow.
- E2E tests for assign/unassign dictionary from chat session.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Added inline chat-context navigation from dictionary usage metadata in the list.
- Added quick-assign workflow in dictionary actions using existing `/api/v1/chats` + `/api/v1/chats/{chat_id}/settings` APIs.
- Added component coverage in `apps/packages/ui/src/components/Option/Dictionaries/__tests__/Manager.chatIntegrationStage1.test.tsx`.

## Stage 2: Safe Operational Controls and Priority Management
**Goal**: Prevent high-impact misconfiguration when multiple dictionaries are active.
**Success Criteria**:
- Deactivate/delete actions show affected chat count in confirmation copy.
- Multi-dictionary processing order is documented and visible in UI.
- If priority is user-controlled, reorder controls persist deterministic order.
- Processing order behavior is consistent across preview and runtime chat processing.
**Tests**:
- Integration tests for warning prompts with active chat dependencies.
- Backend tests verifying priority order application.
- E2E tests for reorder + processed output determinism.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Added deterministic multi-dictionary processing order in backend runtime queries (`LOWER(d.name)` then entry order), aligning preview and runtime processing.
- Added `processing_priority` in dictionary list responses and surfaced it in the dictionaries table with explicit UI guidance.
- Added component coverage for deactivate/delete linked-chat warning copy in `Manager.chatIntegrationStage2.test.tsx`.

## Stage 3: Token-Budget Defaults and Transformation Audit Trail
**Goal**: Improve explainability of dictionary effects in real conversations.
**Success Criteria**:
- Dictionary metadata optionally stores default token budget.
- Chat processing uses dictionary default token budget when request omits one.
- Recent activity view lists transformation events with dictionary and entry context.
- Audit records include timestamp, chat context, and transformed snippet metadata.
**Tests**:
- API tests for default-token-budget read/write and fallback behavior.
- Integration tests for audit event emission during `process_text`.
- UI tests for recent-activity list rendering and pagination.
**Status**: Complete
**Completion Notes (2026-02-18)**:
- Added dictionary `default_token_budget` support end-to-end: schema, create/update endpoint wiring, service persistence, JSON export/import round-trip, and create/edit UI fields.
- Added runtime fallback behavior in `process_text`: if request omits `token_budget`, the service resolves dictionary defaults (specific dictionary or conservative minimum across active dictionaries) and returns `token_budget_used` in API response.
- Added transformation audit trail storage + API surface:
  - service records per-dictionary activity (timestamped `created_at`, `chat_id`, entry IDs, replacement/iteration counts, preview snippets),
  - new endpoint `GET /api/v1/chat/dictionaries/{dictionary_id}/activity`.
- Added UI “Recent activity” rendering in dictionary statistics modal and default budget visibility.
- Added tests:
  - frontend: `Manager.chatIntegrationStage3.test.tsx` (create payload includes default token budget, stats modal renders recent activity),
  - backend: new unit tests in `test_chat_dictionary_endpoints.py` for default budget update/clear, fallback behavior, and activity endpoint response model path.

## Dependencies

- Assignment model must align with existing character-chat session data model.
- Audit trail storage strategy should align with retention/privacy policies.
