# Workspace Chat Isolation & Full Workspace Sync Design

Date: 2026-03-12
Status: Approved
Supersedes: `2026-03-12-workspace-chat-isolation-design.md` (merged and extended)

## Summary

Introduce strict server-enforced chat scoping between global `/chat` and per-workspace `/workspace-playground` conversations, backed by a full server-side workspace entity that persists all workspace state (sources, artifacts, notes, settings, banner). The frontend transitions from being the source of truth (localStorage/IndexedDB) to a cache layer backed by server APIs.

This design merges two parallel efforts:
- **Chat isolation design**: focused on scope enforcement, defensive hydration, import safety, and dual API family scoping
- **Full workspace sync design**: focused on normalized sub-resource tables, complete CRUD, and stateless frontend

## Product Decisions (Approved)

1. Chats created on `/chat` must never appear in any workspace.
2. Each workspace can own multiple persistent chat sessions.
3. All list, search, history, load, and message APIs must enforce scope boundaries.
4. Omitted scope defaults to `global` only and must never mean "all chats."
5. Deleting a workspace soft-deletes its chats (cascade via service layer, not raw FK).
6. Existing unscoped chats migrate to global scope; no inference from browser-local data.
7. Imported or restored workspace sessions strip `serverChatId`; reattachment requires scope validation.
8. Workspaces become a full backend-persisted entity (sources, artifacts, notes, banner, audio settings).
9. Optimistic locking (version fields) for conflict detection on all mutable resources.
10. Soft delete for workspaces, consistent with existing conversation/message patterns.

## Goals

- Enforce strict server-side separation between global and workspace chat history.
- Allow each workspace to own multiple durable conversations.
- Prevent chat leakage through listing, search, history, load, or stale client caches.
- Persist complete workspace state server-side for cross-device continuity.
- Keep deletion behavior consistent with the existing soft-delete model.
- Roll out safely without losing existing global chat history.

## Non-Goals

- Migrating existing browser-local workspace sessions into server workspace chats automatically.
- Allowing a chat to move freely between global and workspace scope after creation.
- Real-time multi-device sync (WebSockets for workspace state). Fetch-on-load is sufficient.
- Changing unrelated chat semantics such as model selection, prompt format, or share-link UX.

## Existing Repo Anchors

- Chat API and orchestration: `tldw_Server_API/app/api/v1/endpoints/chat.py`, `app/core/Chat/chat_orchestrator.py`
- Resource-style chat session APIs: `app/api/v1/endpoints/character_chat_sessions.py`
- Chat DB and soft-delete model: `app/core/DB_Management/ChaChaNotes_DB.py`
- Frontend server chat history: `apps/packages/ui/src/hooks/useServerChatHistory.ts`, `src/hooks/chat/useSelectServerChat.ts`, `src/hooks/chat/useChatActions.ts`
- Workspace store and bundle: `apps/packages/ui/src/store/workspace.ts`, `src/store/workspace-bundle.ts`
- Workspace types: `apps/packages/ui/src/types/workspace.ts`

## Critical Risks And Design Adjustments

### 1. Partial API Scoping Leaves Leakage Paths

Risk: Scoping only `/api/v1/chat/conversations` would still leak conversations through `/api/v1/chats/*`.

Adjustment: Apply the same scope contract to both chat API families. Treat omitted scope as `global` only. Enforce exact scope match on list, search, load, message, citations, share-link, and history endpoints.

### 2. Browser-Local Workspaces And Server Chat Ownership Can Drift

Risk: The workspace UI currently manages workspace lifecycle locally, while durable chat ownership needs a server identity.

Adjustment: Add a full server workspace entity. Use idempotent workspace upsert APIs so local and server state converge. Frontend becomes a cache, not the source of truth.

### 3. Raw FK Cascade Conflicts With Existing Soft Deletes

Risk: Hard `ON DELETE CASCADE` would bypass existing delete/version/sync patterns for conversations and messages.

Adjustment: Delete workspaces through a service layer. Mark the workspace deleted. Soft-delete its scoped conversations and messages through normal mutation paths. Sub-resource tables (sources, artifacts, notes) use FK cascade for hard purge only; soft delete is handled at the workspace level.

### 4. Cached Or Imported `serverChatId` Can Reattach The Wrong Conversation

Risk: Local workspace bundles and stale browser state can point at conversations from the wrong scope or a different environment.

Adjustment: Treat `serverChatId` as ephemeral. Strip it on import. Validate it on hydration before reuse. Clear it immediately if the conversation is missing or the scope does not match.

### 5. Conflict Resolution Without Real-Time Sync

Risk: Two devices editing the same workspace can overwrite each other.

Adjustment: Optimistic locking with `version` fields on all mutable resources. PUT/DELETE requires current version; stale writes get 409 Conflict with current server state in the response body. Frontend replaces local state with server version and shows a brief toast. No automatic merging.

## Phased Delivery

### Phase 1: Chat Isolation + Minimal Workspace Registry (Ship First)

- `workspaces` table (identity only: id, name, archived, deleted, version)
- `scope_type` + `workspace_id` on `conversations`
- Scope enforcement across both `/api/v1/chat/*` and `/api/v1/chats/*`
- Workspace lifecycle APIs (upsert, patch, delete with cascade soft-delete)
- Frontend `ChatScope` type, scoped API client, defensive hydration
- Import/export `serverChatId` stripping
- Migration: existing conversations get `scope_type='global'`, `workspace_id=NULL`

### Phase 2: Full Workspace Sync (Builds On Phase 1)

- Sub-resource tables: `workspace_sources`, `workspace_artifacts`, `workspace_notes`
- Extend `workspaces` table with banner and audio settings columns
- Full CRUD endpoints for all sub-resources
- Frontend store refactor: API-first mutations, server hydration on workspace switch
- One-time client-side migration of existing localStorage workspaces to server
- localStorage reduced to UI preferences and optional offline cache

---

## Data Model

All tables in per-user `ChaChaNotes.db`.

### Phase 1 Tables

#### `workspaces`

```sql
CREATE TABLE IF NOT EXISTS workspaces (
  id             TEXT PRIMARY KEY,
  client_id      TEXT NOT NULL,
  name           TEXT,
  archived       BOOLEAN NOT NULL DEFAULT 0,
  deleted        BOOLEAN NOT NULL DEFAULT 0,
  created_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified  DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  version        INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_workspaces_client_state
  ON workspaces(client_id, deleted, archived, last_modified);
```

#### `conversations` (extend existing)

```sql
ALTER TABLE conversations ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'global'
  CHECK(scope_type IN ('global', 'workspace'));
ALTER TABLE conversations ADD COLUMN workspace_id TEXT DEFAULT NULL
  REFERENCES workspaces(id);

-- Enforce: global scope must have NULL workspace_id, workspace scope must have non-NULL
-- Note: SQLite CHECK constraints on ALTER TABLE are limited; enforce via trigger or app layer
CREATE INDEX IF NOT EXISTS idx_conversations_scope
  ON conversations(client_id, scope_type, workspace_id, deleted, last_modified);
```

Scope invariant (enforced at app layer):
- `scope_type = 'global'` requires `workspace_id IS NULL`
- `scope_type = 'workspace'` requires `workspace_id IS NOT NULL`
- Scope is immutable after creation.

### Phase 2 Tables

#### `workspaces` (extend with settings)

```sql
ALTER TABLE workspaces ADD COLUMN tag TEXT NOT NULL DEFAULT '';
ALTER TABLE workspaces ADD COLUMN banner_title TEXT NOT NULL DEFAULT '';
ALTER TABLE workspaces ADD COLUMN banner_subtitle TEXT NOT NULL DEFAULT '';
ALTER TABLE workspaces ADD COLUMN banner_image BLOB DEFAULT NULL;
ALTER TABLE workspaces ADD COLUMN banner_image_mime TEXT DEFAULT NULL;
ALTER TABLE workspaces ADD COLUMN banner_image_width INTEGER DEFAULT NULL;
ALTER TABLE workspaces ADD COLUMN banner_image_height INTEGER DEFAULT NULL;
ALTER TABLE workspaces ADD COLUMN audio_provider TEXT NOT NULL DEFAULT 'browser';
ALTER TABLE workspaces ADD COLUMN audio_model TEXT NOT NULL DEFAULT 'kokoro';
ALTER TABLE workspaces ADD COLUMN audio_voice TEXT NOT NULL DEFAULT 'af_heart';
ALTER TABLE workspaces ADD COLUMN audio_speed REAL NOT NULL DEFAULT 1.0;
ALTER TABLE workspaces ADD COLUMN audio_format TEXT NOT NULL DEFAULT 'mp3';
```

#### `workspace_sources`

```sql
CREATE TABLE IF NOT EXISTS workspace_sources (
  id                TEXT PRIMARY KEY,
  workspace_id      TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  media_id          INTEGER NOT NULL,
  title             TEXT NOT NULL,
  source_type       TEXT NOT NULL,
  status            TEXT NOT NULL DEFAULT 'ready',
  status_message    TEXT DEFAULT NULL,
  thumbnail_url     TEXT DEFAULT NULL,
  url               TEXT DEFAULT NULL,
  file_size         INTEGER DEFAULT NULL,
  duration          REAL DEFAULT NULL,
  page_count        INTEGER DEFAULT NULL,
  position          INTEGER NOT NULL DEFAULT 0,
  selected          BOOLEAN NOT NULL DEFAULT 0,
  source_created_at DATETIME DEFAULT NULL,
  added_at          DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  client_id         TEXT NOT NULL,
  version           INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_ws_sources_workspace ON workspace_sources(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ws_sources_media ON workspace_sources(media_id);
```

#### `workspace_artifacts`

```sql
CREATE TABLE IF NOT EXISTS workspace_artifacts (
  id                    TEXT PRIMARY KEY,
  workspace_id          TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  artifact_type         TEXT NOT NULL,
  title                 TEXT NOT NULL,
  status                TEXT NOT NULL DEFAULT 'pending',
  content               TEXT DEFAULT NULL,
  data                  TEXT DEFAULT NULL,
  server_id             TEXT DEFAULT NULL,
  previous_version_id   TEXT DEFAULT NULL REFERENCES workspace_artifacts(id) ON DELETE SET NULL,
  estimated_tokens      INTEGER DEFAULT NULL,
  estimated_cost_usd    REAL DEFAULT NULL,
  total_tokens          INTEGER DEFAULT NULL,
  total_cost_usd        REAL DEFAULT NULL,
  audio_url             TEXT DEFAULT NULL,
  audio_format          TEXT DEFAULT NULL,
  presentation_id       TEXT DEFAULT NULL,
  presentation_version  INTEGER DEFAULT NULL,
  error_message         TEXT DEFAULT NULL,
  created_at            DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  completed_at          DATETIME DEFAULT NULL,
  client_id             TEXT NOT NULL,
  version               INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_ws_artifacts_workspace ON workspace_artifacts(workspace_id);
CREATE INDEX IF NOT EXISTS idx_ws_artifacts_type ON workspace_artifacts(artifact_type);
```

#### `workspace_notes`

```sql
CREATE TABLE IF NOT EXISTS workspace_notes (
  id            INTEGER PRIMARY KEY AUTOINCREMENT,
  workspace_id  TEXT NOT NULL REFERENCES workspaces(id) ON DELETE CASCADE,
  title         TEXT NOT NULL DEFAULT '',
  content       TEXT NOT NULL DEFAULT '',
  keywords      TEXT NOT NULL DEFAULT '[]',
  created_at    DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  last_modified DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  deleted       BOOLEAN NOT NULL DEFAULT 0,
  client_id     TEXT NOT NULL,
  version       INTEGER NOT NULL DEFAULT 1
);
CREATE INDEX IF NOT EXISTS idx_ws_notes_workspace ON workspace_notes(workspace_id);
```

## API Contract

### Scope-Aware Chat Requests (Phase 1)

Both chat API surfaces must accept and enforce the same scope contract:

- `/api/v1/chat/*` (conversation-centric)
- `/api/v1/chats/*` (resource-style sessions)

Request rules:
- Global UI sends `scope_type='global'` and no `workspace_id`
- Workspace UI sends `scope_type='workspace'` and the active `workspace_id`
- Omitted scope is interpreted as `global`

Response and authorization rules:
- Reads and writes must validate current user ownership
- Reads and writes must validate exact scope match
- Wrong-scope resources return `404`

### Workspace Lifecycle APIs (Phase 1)

| Method | Path | Purpose |
|---|---|---|
| `PUT` | `/api/v1/workspaces/{id}` | Create-or-upsert workspace |
| `PATCH` | `/api/v1/workspaces/{id}` | Rename, archive, restore |
| `DELETE` | `/api/v1/workspaces/{id}` | Terminal soft-delete |
| `GET` | `/api/v1/workspaces/` | List user's workspaces (paginated, excludes deleted) |
| `GET` | `/api/v1/workspaces/{id}` | Get workspace detail |

Behavior:
- The first persisted workspace chat may upsert the workspace automatically.
- Archived workspaces retain their chats.
- Deleted workspaces hide their chats immediately and trigger soft-deletion of scoped conversations.

### Workspace Sub-Resource APIs (Phase 2)

#### Sources

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/{workspace_id}/sources` | Add source(s) |
| `GET` | `/{workspace_id}/sources` | List sources (ordered by position) |
| `PUT` | `/{workspace_id}/sources/{source_id}` | Update source |
| `DELETE` | `/{workspace_id}/sources/{source_id}` | Remove source |
| `PUT` | `/{workspace_id}/sources/selection` | Batch update selected IDs |
| `PUT` | `/{workspace_id}/sources/reorder` | Batch reorder |

#### Artifacts

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/{workspace_id}/artifacts` | Create artifact |
| `GET` | `/{workspace_id}/artifacts` | List artifacts |
| `PUT` | `/{workspace_id}/artifacts/{artifact_id}` | Update artifact |
| `DELETE` | `/{workspace_id}/artifacts/{artifact_id}` | Remove artifact |

#### Notes

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/{workspace_id}/notes` | Create note |
| `GET` | `/{workspace_id}/notes` | List notes |
| `PUT` | `/{workspace_id}/notes/{note_id}` | Update note |
| `DELETE` | `/{workspace_id}/notes/{note_id}` | Soft delete note |

### Versioning / Conflict Detection (All Phases)

All mutating endpoints (`PUT`, `PATCH`, `DELETE`) require `version` in the request body. If `version` doesn't match the current DB value, return `409 Conflict` with the current server state so the client can reconcile.

## Deletion Semantics

### Archive
- Workspace remains restorable
- Conversations remain attached to the workspace
- Restoring the workspace restores the same conversations

### Soft Delete (Service-Driven, Not Raw FK)

1. Mark workspace `deleted = true`, bump version
2. Soft-delete all scoped conversations (`deleted = true` where `workspace_id = <id>`)
3. Soft-delete all messages in those conversations through existing DB management paths
4. Exclude deleted workspace chats from every query immediately
5. Sub-resource tables (sources, artifacts, notes) become inaccessible because parent workspace is deleted

### Recovery

Restoring a workspace (`deleted = false`) also restores its conversations. Sources, artifacts, and notes become accessible again automatically.

### Hard Purge (Future)

Deleting the workspace row triggers FK cascade for sources, artifacts, and notes. Conversations and messages are hard-deleted through the existing purge paths. Implemented as an optional maintenance job.

## Frontend Architecture

### Shared ChatScope Type (Phase 1)

```typescript
export type ChatScope =
  | { type: "global" }
  | { type: "workspace"; workspaceId: string }

export const toChatScopeParams = (scope?: ChatScope) =>
  scope?.type === "workspace"
    ? { scope_type: "workspace", workspace_id: scope.workspaceId }
    : { scope_type: "global" }
```

Thread through: history loading, chat search, chat selection, chat submission, conversation restoration.

### Route-Level Scope (Phase 1)

- `/chat` always uses `{ type: 'global' }` — never renders workspace conversations
- `/workspace-playground` always uses `{ type: 'workspace', workspaceId }` — never renders global or other-workspace conversations

### Defensive Hydration (Phase 1)

On load:
- Validate cached `serverChatId` against server
- Clear it if the server conversation is missing
- Clear it if the server conversation belongs to a different scope
- Fall back to a safe empty session if validation fails

### Import/Export Safety (Phase 1)

- Export: include transcript and local metadata
- Import: strip `serverChatId` — imported bundles never silently reconnect to server chats
- Hydrated `serverChatId` must pass existence and scope validation before reuse

### Store Refactor (Phase 2)

The Zustand workspace store shifts from source of truth to cache:
- Actions become API-first: mutate server, then update local store on success
- Hydration on workspace switch: `GET /api/v1/workspaces/{id}` populates the store
- Optimistic updates with rollback on 409/error
- Version tracking for workspace and each sub-resource
- localStorage reduced to UI preferences (pane state, theme) and auth tokens

### Workspace Chat Sessions (Phase 2)

Refactor from single-session-per-workspace to multi-session:

```typescript
type WorkspaceChatState = {
  activeSessionIdByWorkspace: Record<string, string | null>
  draftsByWorkspaceAndSession: Record<string, PersistedWorkspaceChatSession>
}
```

Server conversations keyed by `workspaceId + sessionId`, not a single global pointer.

### One-Time Client Migration (Phase 2)

On first load after upgrade:
1. Detect existing local workspaces via Zustand store
2. For each: call `PUT /api/v1/workspaces/{id}` (idempotent upsert)
3. POST sources, artifacts, notes as sub-resources
4. Re-link chats: set `workspace_id` on existing server conversations
5. Store `migrated: true` flag in localStorage
6. Clear local workspace data after successful sync

### Rollout UX

Show a one-time notice when a stale workspace pointer is invalidated:
- Earlier workspace chats were stored as global chats
- Those chats remain available on `/chat`
- Provide a "open global history" link

## Migration Path

### Schema Migration

1. Create `workspaces` table
2. Add `scope_type` and `workspace_id` columns to `conversations`
3. Backfill existing conversations: `scope_type='global'`, `workspace_id=NULL`
4. Add indexes after backfill
5. (Phase 2) Add workspace settings columns, sub-resource tables

### Existing User Data

- Existing chats remain visible on `/chat` as global conversations
- No automatic reassignment to workspaces
- Old browser-local workspace sessions that referenced server chats may no longer resolve after scope enforcement

## Error Handling

### 409 Conflict
Response body includes current server state. Frontend replaces local state, shows toast: "Updated elsewhere -- refreshed to latest." User re-applies edit on fresh state.

### 404 Workspace Not Found
Frontend redirects to workspace list or prompts to create a new workspace.

### Permissions
Workspace ownership: `workspace.client_id == current_user.id`. Returns 404 (not 403) for other users' workspaces.

### Rate Limiting
Same as existing ChaChaNotes endpoints.

## Testing Strategy

### Backend

- Unit tests for conversation queries filtered by `scope_type` and `workspace_id`
- API tests for both `/api/v1/chat/*` and `/api/v1/chats/*`
- Regression tests proving omitted scope returns only global chats
- Scope-mismatch tests returning `404`
- Workspace delete tests proving scoped chats disappear immediately
- Workspace sub-resource CRUD tests (Phase 2)
- Optimistic locking 409 tests

### Frontend

- `/chat` never renders workspace chats
- Workspace A never renders workspace B chats
- Cached wrong-scope `serverChatId` is cleared during hydration
- Imported bundles have `serverChatId` stripped
- Workspace archive preserves access after restore
- Workspace delete clears local references
- Store hydration from server on workspace switch (Phase 2)
- Migration flow from localStorage to server (Phase 2)

### End-To-End

1. Create a global chat and confirm it appears only on `/chat`
2. Create chats in workspace A and confirm they are absent from `/chat` and workspace B
3. Switch between workspaces and verify each workspace sees only its own chats
4. Delete workspace A and confirm its chats disappear everywhere
5. (Phase 2) Create workspace with sources/artifacts/notes, switch devices, verify all state synced

## Rollout Plan

### Phase 1 (Chat Isolation)

1. Add scope columns, constraints, and backend filtering to both chat API families
2. Add server workspace registry and lifecycle APIs
3. Pass explicit scope through `/chat` and `/workspace-playground`
4. Add multiple-session workspace chat UX on top of scoped server conversations
5. Ship stale-cache cleanup, migration notice, and import safety

### Phase 2 (Full Workspace Sync)

6. Add workspace settings columns and sub-resource tables
7. Add sub-resource CRUD endpoints
8. Refactor frontend store to API-first with server hydration
9. Ship one-time client-side migration of existing local workspaces
10. Remove localStorage as source of truth; reduce to cache/preferences

## Open Questions Resolved

- What happens on workspace delete? Service-driven soft delete cascade, with optional later hard purge.
- How to handle conflicts? Optimistic locking with version fields; 409 returns server state; no auto-merge.
- Existing chats? Become global scope; no inference from browser data.
- Import safety? Strip `serverChatId`; validate scope on hydration.
- Phase 2 scope? Full sync of sources, artifacts, notes, banner, audio settings.
