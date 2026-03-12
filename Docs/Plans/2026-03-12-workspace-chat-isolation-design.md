# Workspace Chat Isolation Design

Date: 2026-03-12
Status: Approved

## Summary

Introduce explicit chat scoping so global `/chat` conversations and `/workspace-playground` conversations are permanently isolated. Global chats remain visible only on `/chat`. Workspace chats are permanently bound to one workspace and become visible only when that workspace is active.

## Product Decisions (Approved)

1. Chats created on `/chat` must never appear in any workspace.
2. Each workspace can own multiple persistent chat sessions.
3. All list, search, history, load, and message APIs must enforce scope boundaries.
4. Omitted scope defaults to `global` only and must never mean "all chats."
5. Deleting a workspace deletes its chats from product behavior.
6. Existing unscoped chats migrate to global chats; no attempt is made to infer workspace membership from local browser data.
7. Imported or restored workspace sessions do not automatically rebind to server chats unless scope validation succeeds.

## Goals

- Enforce strict server-side separation between global and workspace chat history.
- Allow each workspace to own multiple durable conversations.
- Prevent chat leakage through listing, search, history, load, or stale client caches.
- Keep deletion behavior consistent with the existing soft-delete and sync model.
- Roll out safely without losing existing global chat history.

## Non-Goals

- Migrating existing browser-local workspace sessions into server workspace chats automatically.
- Allowing a chat to move freely between global and workspace scope after creation.
- Redesigning the entire workspace store beyond what is required for multiple scoped chat sessions.
- Changing unrelated chat semantics such as model selection, prompt format, or share-link UX.

## Existing Repo Anchors

The design should reuse current chat and workspace paths rather than inventing a parallel system:

- Chat API and orchestration:
  - `tldw_Server_API/app/api/v1/endpoints/chat.py`
  - `tldw_Server_API/app/core/Chat/chat_orchestrator.py`
- Resource-style chat session APIs:
  - `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Chat DB and soft-delete model:
  - `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Frontend server chat history and selection:
  - `apps/packages/ui/src/hooks/useServerChatHistory.ts`
  - `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
  - `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Workspace store and bundle format:
  - `apps/packages/ui/src/store/workspace.ts`
  - `apps/packages/ui/src/store/workspace-bundle.ts`

## Critical Risks And Design Adjustments

### 1. Partial API Scoping Leaves Leakage Paths

Risk: scoping only `/api/v1/chat/conversations` would still leak conversations through `/api/v1/chats/*`.

Adjustment:

- Apply the same scope contract to both chat API families.
- Treat omitted scope as `global` only.
- Enforce exact scope match on list, search, load, message, citations, share-link, and history endpoints.

### 2. Browser-Local Workspaces And Server Chat Ownership Can Drift

Risk: the workspace UI currently manages workspace lifecycle locally, while durable chat ownership needs a server identity.

Adjustment:

- Add a minimal server `workspaces` registry.
- Keep the browser store as the source of UI state.
- Use idempotent workspace upsert/update/delete APIs so local and server state converge.

### 3. Raw FK Cascade Conflicts With Existing Soft Deletes

Risk: hard `ON DELETE CASCADE` would bypass existing delete/version/sync patterns for conversations and messages.

Adjustment:

- Delete workspaces through a service layer.
- Mark the workspace deleted.
- Soft-delete its scoped conversations and messages through normal mutation paths.
- Optionally hard-purge later with a cleanup job.

### 4. Cached Or Imported `serverChatId` Can Reattach The Wrong Conversation

Risk: local workspace bundles and stale browser state can point at conversations from the wrong scope or a different environment.

Adjustment:

- Treat `serverChatId` as ephemeral.
- Strip it on import.
- Validate it on hydration before reuse.
- Clear it immediately if the conversation is missing or the scope does not match.

### 5. Multi-Session Workspace Support Can Expand The Change Surface

Risk: the current workspace store behaves like one local chat session per workspace. Rewriting the entire store at once would raise delivery risk.

Adjustment:

- Make the server the source of truth for workspace conversations.
- Store only active workspace session selection plus local drafts/caches keyed by `workspaceId + sessionId`.
- Stage the UX refactor after backend scoping lands.

## Recommended Architecture

Introduce explicit chat scope at the persistence, API, and route-state layers.

### Scope Model

Every conversation has one of two scopes:

- `global`: visible only on `/chat`
- `workspace`: visible only within one workspace

Scope is immutable after creation in normal product flows.

### Workspace Registry

Add a server-owned workspace identity table so workspace conversations have a durable foreign key target. The client continues generating the workspace UUID locally and syncs it to the server on first use.

## Data Model

### `workspaces`

Suggested fields:

- `id TEXT PRIMARY KEY`
- `client_id TEXT NOT NULL`
- `name TEXT`
- `archived BOOLEAN NOT NULL DEFAULT 0`
- `deleted BOOLEAN NOT NULL DEFAULT 0`
- `created_at`
- `last_modified`
- `version`

Suggested indexes:

- `(client_id, deleted, archived, last_modified)`

### `conversations`

Extend the existing table with:

- `scope_type TEXT NOT NULL CHECK(scope_type IN ('global', 'workspace')) DEFAULT 'global'`
- `workspace_id TEXT NULL REFERENCES workspaces(id)`
- `CHECK((scope_type = 'global' AND workspace_id IS NULL) OR (scope_type = 'workspace' AND workspace_id IS NOT NULL))`

Suggested indexes:

- `(client_id, scope_type, workspace_id, deleted, last_modified)`

Notes:

- `scope_type` is explicit instead of relying on `NULL` semantics alone.
- `workspace_id` should not use raw cascade delete.
- Scope changes should be rejected after creation unless a future explicit migration tool is introduced.

## API Contract

### Scope-Aware Chat Requests

Both chat API surfaces must accept and enforce the same scope contract:

- `/api/v1/chat/*`
- `/api/v1/chats/*`

Request rules:

- Global UI sends `scope_type='global'` and no `workspace_id`
- Workspace UI sends `scope_type='workspace'` and the active `workspace_id`
- Omitted scope is interpreted as `global`

Response and authorization rules:

- Reads and writes must validate current user ownership
- Reads and writes must validate exact scope match
- Wrong-scope resources return `404`

### Workspace Lifecycle APIs

Add minimal workspace lifecycle endpoints:

- `PUT /api/v1/workspaces/{id}`: create-or-upsert
- `PATCH /api/v1/workspaces/{id}`: rename, archive, restore
- `DELETE /api/v1/workspaces/{id}`: terminal delete

Behavior:

- The first persisted workspace chat may upsert the workspace automatically.
- Archived workspaces retain their chats.
- Deleted workspaces hide their chats immediately and trigger soft deletion of scoped chat data.

## Deletion Semantics

### Archive

- Workspace remains restorable
- Conversations remain attached to the workspace
- Restoring the workspace restores the same conversations

### Delete

Deletion is service-driven, not raw FK-driven:

1. Mark workspace `deleted = true`
2. Soft-delete all scoped conversations
3. Soft-delete all messages and related rows through existing DB management paths
4. Exclude deleted workspace chats from every query immediately
5. Optionally hard-purge later in a maintenance job

This matches the current chat database model better than physical cascade delete.

## Frontend Routing And State

### Route-Level Scope

Represent scope explicitly in the UI:

- `{ type: 'global' }`
- `{ type: 'workspace', workspaceId }`

Thread that scope through:

- history loading
- chat search
- chat selection
- chat submission
- conversation restoration

### `/chat`

- Always queries global scope
- Never renders workspace conversations
- Restores only global `serverChatId` references

### `/workspace-playground`

- Always queries workspace scope for the active workspace
- Never renders global or other-workspace conversations
- Maintains multiple sessions per workspace

### Workspace Store Shape

Refactor toward:

- `activeSessionIdByWorkspace`
- `draftsByWorkspaceAndSession`
- workspace conversation metadata sourced from the server

The local store should stop acting as the canonical durable chat catalog.

### Defensive Hydration

On load:

- validate cached `serverChatId`
- clear it if the server conversation is missing
- clear it if the server conversation belongs to a different scope
- fall back to a safe empty session if validation fails

## Import, Export, And Cache Safety

Update workspace bundle handling so `serverChatId` is not portable.

Rules:

- export transcript and local metadata
- import restores local-only workspace sessions by default
- import strips `serverChatId`
- hydrated `serverChatId` must pass existence and scope validation before reuse

This prevents scope leakage through import/export and stale browser caches.

## Migration Path

### Schema Migration

1. Create `workspaces`
2. Add `scope_type` and `workspace_id` to `conversations`
3. Backfill existing conversations to:
   - `scope_type='global'`
   - `workspace_id=NULL`
4. Add indexes and constraints after backfill

### Existing User Data

- Existing chats remain visible on `/chat`
- No automatic reassignment to workspaces
- Old browser-local workspace sessions that referenced server chats may no longer resolve after scope enforcement

### Rollout UX

Show a one-time notice when a stale workspace pointer is invalidated:

- earlier workspace chats were stored as global chats
- those chats remain available on `/chat`
- provide a safe "open global history" path

## Rollout Plan

1. Add the scope columns, constraints, and backend filtering to both chat API families.
2. Add the server workspace registry and lifecycle APIs.
3. Pass explicit scope through `/chat` and `/workspace-playground`.
4. Add multiple-session workspace chat UX on top of scoped server conversations.
5. Ship stale-cache cleanup, migration notice, and optional purge tooling.

## Testing Strategy

### Backend

- Unit tests for conversation queries filtered by `scope_type` and `workspace_id`
- API tests for both `/api/v1/chat/*` and `/api/v1/chats/*`
- Regression tests proving omitted scope returns only global chats
- Scope-mismatch tests returning `404`
- Workspace delete tests proving scoped chats disappear immediately

### Frontend

- `/chat` never renders workspace chats
- workspace A never renders workspace B chats
- cached wrong-scope `serverChatId` is cleared during hydration
- workspace archive preserves access after restore
- workspace delete clears local references

### End-To-End

1. Create a global chat and confirm it appears only on `/chat`
2. Create chats in workspace A and confirm they are absent from `/chat` and workspace B
3. Switch between workspaces and verify each workspace sees only its own chats
4. Delete workspace A and confirm its chats disappear everywhere

## Open Questions Resolved

- What happens on workspace delete?
  - Delete the workspace's chats from product behavior via service-driven soft deletion, with optional later purge.
