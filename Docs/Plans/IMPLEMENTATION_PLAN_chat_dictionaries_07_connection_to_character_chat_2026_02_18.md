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
**Status**: Not Started

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
**Status**: Not Started

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
**Status**: Not Started

## Dependencies

- Assignment model must align with existing character-chat session data model.
- Audit trail storage strategy should align with retention/privacy policies.
