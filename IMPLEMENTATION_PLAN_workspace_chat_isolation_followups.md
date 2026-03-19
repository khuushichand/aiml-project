## Stage 1: Backend Scope Contract
**Goal**: Make omitted scope default to global across both chat API families and enforce exact scope matching on resource reads/writes.
**Success Criteria**: Listing/searching without scope only returns global chats; wrong-scope chat/message/history/share-link requests return 404.
**Tests**: Targeted pytest coverage for `/api/v1/chat/*` and `/api/v1/chats/*` list/load/message/share-link scope behavior.
**Status**: Complete

## Stage 2: Workspace Deletion Semantics
**Goal**: Route workspace deletion through service-driven soft deletion semantics so workspace chats and their messages disappear immediately.
**Success Criteria**: Deleting a workspace soft-deletes its conversations/messages and message-level access no longer succeeds afterward.
**Tests**: Targeted pytest coverage for workspace delete and message lookup after delete.
**Status**: Complete

## Stage 3: Frontend Scope Propagation And Hydration Safety
**Goal**: Pass workspace scope into all workspace chat creation/load flows and validate cached/imported `serverChatId` before reuse.
**Success Criteria**: Workspace chat creation uses workspace scope; imported sessions strip `serverChatId`; cached wrong-scope ids are cleared on hydration.
**Tests**: Targeted vitest coverage for workspace import/hydration and client normalization of scope metadata.
**Status**: Complete

## Stage 4: Multi-Session Workspace Persistence
**Goal**: Replace the single workspace chat slot model with multiple persistent sessions per workspace and track active session selection separately.
**Success Criteria**: Workspace store can persist multiple sessions per workspace and the playground resolves sessions by `workspaceId + sessionId`.
**Tests**: Targeted vitest coverage for store session creation/selection/import/export behavior.
**Status**: Complete

## Stage 5: Verification And Hardening
**Goal**: Run focused backend/frontend test suites plus Bandit on touched Python scope and address any regressions.
**Success Criteria**: Relevant tests pass; Bandit reports no new issues in touched backend paths.
**Tests**: Pytest, vitest, Bandit.
**Status**: Complete
