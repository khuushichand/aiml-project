## Stage 1: Plan And Contract Validation
**Goal**: Confirm existing data contracts and define implementation boundaries for branching, share tokens, and comparison workspace.
**Success Criteria**: Required frontend and backend touchpoints identified; compatibility assumptions documented; no unresolved blocker.
**Tests**: N/A (analysis stage).
**Status**: Complete

## Stage 2: True Conversation Branching
**Goal**: Implement actual branch creation from a prior turn in `ConversationThread.tsx` and provider/backend integration.
**Success Criteria**:
- Users can branch from a selected historical turn.
- A new thread is created and seeded with prior messages through the selected turn.
- The branch relationship is persisted (`parent_conversation_id`, fork source message when provided).
- UI no longer shows a staged placeholder for branching.
**Tests**:
- `ConversationThread` interaction test for branch action wiring.
- Provider test validating `branchFromTurn` behavior and state hydration.
**Status**: Complete

## Stage 3: Share Token/Public Link Permission Model
**Goal**: Replace direct thread-link sharing with tokenized share links that can be managed separately from standard thread access.
**Success Criteria**:
- Backend supports creating/listing/revoking share links per conversation.
- Public read endpoint resolves a valid share token to sanitized thread data.
- `ExportDialog.tsx` uses token links (not raw thread IDs) and supports regeneration/revocation actions.
- Existing auth-based thread links remain optional/internal and are not the default share path.
**Tests**:
- Backend unit/API tests for token generation/validation/revocation behavior.
- Export dialog tests for share-link generation and disabled/error states.
**Status**: Complete

## Stage 4: Arbitrary Cross-Thread Comparison Workspace
**Goal**: Expand comparison mode from prior-vs-latest (single thread) to arbitrary turn-vs-turn across selectable threads.
**Success Criteria**:
- Users can pick left and right threads independently.
- Users can pick a completed turn in each thread.
- Side-by-side comparison renders selected queries/answers/citations from both threads.
**Tests**:
- `ConversationThread` tests for cross-thread selectors and rendering behavior.
- Model tests for comparison draft updates with explicit thread/turn IDs.
**Status**: Complete

## Stage 5: Verification, Regression Guardrails, And Plan Closure
**Goal**: Validate all changed behavior and update this plan with completion state.
**Success Criteria**:
- Targeted frontend and backend tests pass for touched modules.
- No unresolved TODOs for the three requested gaps.
- Plan statuses updated to complete with validation notes.
**Tests**:
- Targeted Vitest suites under KnowledgeQA.
- Targeted backend pytest for share-link endpoints (if added).
**Validation Notes**:
- `bunx vitest run src/components/Option/KnowledgeQA/__tests__/ConversationThread.test.tsx src/components/Option/KnowledgeQA/__tests__/ExportDialog.a11y.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQAProvider.branch-share.test.tsx src/components/Option/KnowledgeQA/__tests__/KnowledgeQA.golden-layout.test.tsx` passed.
- `python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py -q` passed.
- `python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_share_links_api.py -q` passed.
**Status**: Complete
