# Workspace Chat Isolation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add strict server-enforced separation between global `/chat` conversations and workspace-scoped `/workspace-playground` conversations, including workspace lifecycle, migration safety, and regression coverage.

**Architecture:** Add explicit chat scope fields plus a minimal server-side workspace registry in `ChaChaNotes_DB.py`, then enforce that scope across both chat API families (`/api/v1/chat/*` and `/api/v1/chats/*`). On the frontend, introduce a shared `ChatScope` type, pass it through the API client and chat hooks, and refactor workspace chat state so server conversations are keyed by `workspaceId + sessionId` instead of a single global server chat pointer.

**Tech Stack:** FastAPI, Pydantic, SQLite/PostgreSQL-compatible DB helpers in `ChaChaNotes_DB.py`, React, Zustand, TanStack Query, Vitest, pytest, Bandit.

---

## Stage 1: Persistence And Scope Primitives
**Goal:** Add durable workspace records plus explicit conversation scope fields at the DB layer, with filtering helpers and soft-delete-aware workspace deletion behavior.
**Success Criteria:** Conversations can be stored and queried as either `global` or `workspace` scoped, workspace metadata is durable per user, and deleting a workspace soft-deletes only that workspace's conversations.
**Tests:** `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py`
**Status:** Not Started

### Task 1: Add workspace registry and conversation scope columns

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Create: `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py`

**Step 1: Write the failing test**

```python
def test_search_conversations_respects_scope_and_workspace(tmp_path):
    db = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    db.upsert_workspace({"id": "workspace-a", "name": "Workspace A", "client_id": "user-1"})
    db.upsert_workspace({"id": "workspace-b", "name": "Workspace B", "client_id": "user-1"})

    global_id = db.add_conversation({"title": "Global chat", "client_id": "user-1"})
    workspace_a_id = db.add_conversation(
        {
            "title": "Workspace A chat",
            "client_id": "user-1",
            "scope_type": "workspace",
            "workspace_id": "workspace-a",
        }
    )
    db.add_conversation(
        {
            "title": "Workspace B chat",
            "client_id": "user-1",
            "scope_type": "workspace",
            "workspace_id": "workspace-b",
        }
    )

    global_results = db.search_conversations(scope_type="global")
    workspace_results = db.search_conversations(scope_type="workspace", workspace_id="workspace-a")

    assert [item["id"] for item in global_results] == [global_id]
    assert [item["id"] for item in workspace_results] == [workspace_a_id]


def test_delete_workspace_soft_deletes_scoped_conversations(tmp_path):
    db = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    db.upsert_workspace({"id": "workspace-a", "name": "Workspace A", "client_id": "user-1"})
    conversation_id = db.add_conversation(
        {
            "title": "Workspace chat",
            "client_id": "user-1",
            "scope_type": "workspace",
            "workspace_id": "workspace-a",
        }
    )

    db.delete_workspace("workspace-a", client_id="user-1")

    assert db.get_conversation_by_id(conversation_id) is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py -v
```

Expected: FAIL because `workspaces`, `scope_type`, `workspace_id`, and workspace delete helpers do not exist yet.

**Step 3: Write minimal implementation**

```python
CREATE TABLE IF NOT EXISTS workspaces(
  id TEXT PRIMARY KEY,
  client_id TEXT NOT NULL,
  name TEXT,
  archived BOOLEAN NOT NULL DEFAULT 0,
  deleted BOOLEAN NOT NULL DEFAULT 0,
  created_at DATETIME NOT NULL,
  last_modified DATETIME NOT NULL,
  version INTEGER NOT NULL DEFAULT 1
);

ALTER TABLE conversations ADD COLUMN scope_type TEXT NOT NULL DEFAULT 'global';
ALTER TABLE conversations ADD COLUMN workspace_id TEXT REFERENCES workspaces(id);

def _normalize_scope(scope_type: str | None, workspace_id: str | None) -> tuple[str, str | None]:
    scope = (scope_type or "global").strip().lower()
    if scope == "global":
        return "global", None
    if scope != "workspace" or not workspace_id:
        raise ValueError("workspace scope requires workspace_id")
    return "workspace", workspace_id

def search_conversations(..., scope_type: str = "global", workspace_id: str | None = None):
    scope_type, workspace_id = _normalize_scope(scope_type, workspace_id)
    filters.append("c.scope_type = ?")
    params.append(scope_type)
    if scope_type == "workspace":
        filters.append("c.workspace_id = ?")
        params.append(workspace_id)
```

Also add:

- `upsert_workspace(...)`
- `get_workspace(...)`
- `list_workspaces(...)`
- `update_workspace(...)`
- `delete_workspace(...)` that marks the workspace deleted and soft-deletes all scoped conversations/messages through existing mutation paths
- indexes on `(client_id, scope_type, workspace_id, deleted, last_modified)`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py
git commit -m "feat: add workspace chat scope primitives"
```

## Stage 2: Scope `/api/v1/chat/*`
**Goal:** Make the conversation-centric chat endpoints explicitly scope-aware and fail closed to global chats when older clients omit scope.
**Success Criteria:** `/api/v1/chat/conversations`, `/tree`, `/analytics`, and share-link related reads/writes return only the requested scope, and wrong-scope IDs return `404`.
**Tests:** `tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py`
**Status:** Not Started

### Task 2: Thread `scope_type` and `workspace_id` through the `/api/v1/chat/*` API

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Modify: `tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py`

**Step 1: Write the failing test**

```python
def test_conversation_list_defaults_to_global_scope(tmp_path):
    db = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    db.upsert_workspace({"id": "workspace-a", "name": "Workspace A", "client_id": "user-1"})
    db.add_conversation({"title": "Global chat", "client_id": "user-1"})
    db.add_conversation(
        {
            "title": "Workspace chat",
            "client_id": "user-1",
            "scope_type": "workspace",
            "workspace_id": "workspace-a",
        }
    )
    app = _build_app(db)

    response = app.get("/api/v1/chat/conversations")

    assert response.status_code == 200
    assert [item["title"] for item in response.json()["items"]] == ["Global chat"]


def test_conversation_tree_404s_on_scope_mismatch(tmp_path):
    db = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    db.upsert_workspace({"id": "workspace-a", "name": "Workspace A", "client_id": "user-1"})
    conversation_id = db.add_conversation(
        {
            "title": "Workspace chat",
            "client_id": "user-1",
            "scope_type": "workspace",
            "workspace_id": "workspace-a",
        }
    )
    app = _build_app(db)

    response = app.get(f"/api/v1/chat/conversations/{conversation_id}/tree")

    assert response.status_code == 404
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py -k scope -v
```

Expected: FAIL because the router still lists user-owned conversations without scope filtering.

**Step 3: Write minimal implementation**

```python
class ConversationScopeParams(BaseModel):
    scope_type: Literal["global", "workspace"] = "global"
    workspace_id: str | None = None

    @model_validator(mode="after")
    def _validate_workspace_scope(self) -> "ConversationScopeParams":
        if self.scope_type == "workspace" and not self.workspace_id:
            raise ValueError("workspace_id is required when scope_type='workspace'")
        if self.scope_type == "global":
            self.workspace_id = None
        return self


def _resolve_scope(scope_type: str | None, workspace_id: str | None) -> tuple[str, str | None]:
    return db.normalize_conversation_scope(scope_type=scope_type, workspace_id=workspace_id)
```

Apply that scope in:

- conversation list/search
- conversation detail/tree
- analytics
- share-link create/list/revoke
- citations

Important behavior:

- omitted scope means `global`
- workspace endpoints require explicit `workspace_id`
- wrong-scope resource access raises `HTTPException(status_code=404, ...)`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py -k scope -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py
git commit -m "feat: scope chat conversation endpoints"
```

## Stage 3: Scope `/api/v1/chats/*` And Add Workspace Lifecycle APIs
**Goal:** Make the resource-style chat session endpoints enforce the same scope rules, and add server CRUD for workspace identity and deletion semantics.
**Success Criteria:** `/api/v1/chats/*` create/list/load/message/completion/search respect scope, `/api/v1/workspaces/*` supports upsert/update/delete, and workspace deletion hides its scoped chats immediately.
**Tests:** `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`, `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`
**Status:** Not Started

### Task 3: Add scope-aware session APIs and workspace CRUD

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/workspace_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/workspaces.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py`
- Create: `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_workspace_chat_list_isolated_from_global():
    create_global = await client.post("/api/v1/chats/", headers=headers, json={"title": "Global chat"})
    await client.put(
        "/api/v1/workspaces/workspace-a",
        headers=headers,
        json={"name": "Workspace A"},
    )
    create_workspace = await client.post(
        "/api/v1/chats/",
        headers=headers,
        json={
            "title": "Workspace chat",
            "scope_type": "workspace",
            "workspace_id": "workspace-a",
        },
    )

    global_list = await client.get("/api/v1/chats/", headers=headers)
    workspace_list = await client.get(
        "/api/v1/chats/",
        headers=headers,
        params={"scope_type": "workspace", "workspace_id": "workspace-a"},
    )

    assert [item["id"] for item in global_list.json()["chats"]] == [create_global.json()["id"]]
    assert [item["id"] for item in workspace_list.json()["chats"]] == [create_workspace.json()["id"]]


@pytest.mark.asyncio
async def test_delete_workspace_soft_deletes_scoped_chats():
    await client.put("/api/v1/workspaces/workspace-a", headers=headers, json={"name": "Workspace A"})
    chat_resp = await client.post(
        "/api/v1/chats/",
        headers=headers,
        json={"title": "Workspace chat", "scope_type": "workspace", "workspace_id": "workspace-a"},
    )

    delete_resp = await client.delete("/api/v1/workspaces/workspace-a", headers=headers)
    assert delete_resp.status_code == 204

    chat_id = chat_resp.json()["id"]
    detail_resp = await client.get(
        f"/api/v1/chats/{chat_id}",
        headers=headers,
        params={"scope_type": "workspace", "workspace_id": "workspace-a"},
    )
    assert detail_resp.status_code == 404
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -k workspace -v
python -m pytest tldw_Server_API/tests/Workspaces/test_workspaces_api.py -v
```

Expected: FAIL because the workspace router and scoped session contract do not exist yet.

**Step 3: Write minimal implementation**

```python
class WorkspaceUpsertRequest(BaseModel):
    name: str
    archived: bool = False


class WorkspacePatchRequest(BaseModel):
    name: str | None = None
    archived: bool | None = None
    deleted: bool | None = None


@router.put("/workspaces/{workspace_id}", status_code=200)
async def upsert_workspace(...):
    return db.upsert_workspace(...)


@router.delete("/workspaces/{workspace_id}", status_code=204)
async def delete_workspace(...):
    db.delete_workspace(workspace_id, client_id=user_id)
```

Also:

- add `scope_type` and `workspace_id` to create/list/detail/search/completion request models in `chat_session_schemas.py`
- enforce scope filters in `character_chat_sessions.py`
- require exact scope match before reading/updating a chat or its messages
- register `workspaces.py` in `app/main.py`

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py -k workspace -v
python -m pytest tldw_Server_API/tests/Workspaces/test_workspaces_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/workspace_schemas.py tldw_Server_API/app/api/v1/endpoints/workspaces.py tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/app/main.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Workspaces/test_workspaces_api.py
git commit -m "feat: add scoped chat sessions and workspace lifecycle api"
```

## Stage 4: Shared UI Scope Contract
**Goal:** Introduce one frontend `ChatScope` type and ensure all shared API helpers and history loaders pass scope explicitly.
**Success Criteria:** The UI defaults to `global` scope unless a workspace scope is explicitly provided, `/chat` history requests never fetch workspace chats, and workspace history/search requests always carry `workspace_id`.
**Tests:** `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`, `apps/packages/ui/src/services/__tests__/tldw-api-client.chat-scope.test.ts`
**Status:** Not Started

### Task 4: Make the shared UI API client and history hooks scope-aware

**Files:**
- Create: `apps/packages/ui/src/types/chat-scope.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/timeline/api.ts`
- Modify: `apps/packages/ui/src/hooks/useServerChatHistory.ts`
- Modify: `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`
- Create: `apps/packages/ui/src/services/__tests__/tldw-api-client.chat-scope.test.ts`

**Step 1: Write the failing test**

```ts
it("defaults listChatsWithMeta to global scope", async () => {
  await client.listChatsWithMeta({ limit: 20 })
  expect(bgRequestMock).toHaveBeenCalledWith(
    expect.objectContaining({
      path: "/api/v1/chats/?limit=20&scope_type=global"
    })
  )
})

it("passes workspace scope through useServerChatHistory", async () => {
  renderHook(() =>
    useServerChatHistory("", {
      scope: { type: "workspace", workspaceId: "workspace-a" }
    }),
    { wrapper }
  )

  await waitFor(() =>
    expect(listChatsWithMetaMock).toHaveBeenCalledWith(
      expect.objectContaining({
        scope_type: "workspace",
        workspace_id: "workspace-a"
      }),
      expect.anything()
    )
  )
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-scope.test.ts
```

Expected: FAIL because the current client/hook do not know about chat scope.

**Step 3: Write minimal implementation**

```ts
export type ChatScope =
  | { type: "global" }
  | { type: "workspace"; workspaceId: string }

export const toChatScopeParams = (scope?: ChatScope) =>
  scope?.type === "workspace"
    ? { scope_type: "workspace", workspace_id: scope.workspaceId }
    : { scope_type: "global" }
```

Apply that helper in:

- `listChats`
- `listChatsWithMeta`
- `createChat`
- timeline API search/list helpers
- `useServerChatHistory`

Do not ship any API call path where omitted scope can accidentally mean "all chats."

**Step 4: Run test to verify it passes**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-scope.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/types/chat-scope.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/services/timeline/api.ts apps/packages/ui/src/hooks/useServerChatHistory.ts apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-scope.test.ts
git commit -m "feat: add frontend chat scope contract"
```

## Stage 5: Workspace Route State, Import Safety, And Rollout Verification
**Goal:** Refactor workspace chat state so each workspace can own multiple scoped sessions, invalidate wrong-scope cached pointers safely, strip `serverChatId` on import, and cover the rollout with end-to-end tests and Bandit.
**Success Criteria:** Switching workspaces only surfaces that workspace's chats, imported bundles never silently reconnect to server chats, stale workspace pointers are cleared with a one-time notice, and targeted backend/frontend/security verification is clean.
**Tests:** `apps/packages/ui/src/store/__tests__/workspace.test.ts`, `apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts`, `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.scope.test.tsx`, `tldw_Server_API/tests/e2e/test_workspace_chat_scope.py`
**Status:** Not Started

### Task 5: Finish workspace UI isolation, rollout safety, and verification

**Files:**
- Modify: `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/store/workspace-bundle.ts`
- Modify: `apps/packages/ui/src/store/workspace-sync-contract.ts`
- Modify: `apps/packages/ui/src/store/__tests__/workspace.test.ts`
- Modify: `apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts`
- Create: `apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.scope.test.tsx`
- Create: `tldw_Server_API/tests/e2e/test_workspace_chat_scope.py`

**Step 1: Write the failing test**

```ts
it("clears imported serverChatId during workspace import", async () => {
  const parsed = await parseWorkspaceImportFile(fileWithServerChatId)
  expect(parsed.workspace.chatSession?.serverChatId).toBeNull()
})

it("drops cached serverChatId when it belongs to the wrong scope", async () => {
  useWorkspaceStore.setState({
    workspaceId: "workspace-a",
    workspaceChatSessions: {
      "workspace-a": { historyId: "history-a", serverChatId: "global-chat", messages: [], history: [] }
    }
  })

  await hydrateWorkspaceStateWithScopeValidation({
    lookupChatScope: async () => ({ scopeType: "global", workspaceId: null })
  })

  expect(useWorkspaceStore.getState().workspaceChatSessions["workspace-a"]?.serverChatId).toBeNull()
})
```

```python
@pytest.mark.asyncio
async def test_workspace_scope_end_to_end():
    global_chat = await client.post("/api/v1/chats/", headers=headers, json={"title": "Global"})
    await client.put("/api/v1/workspaces/workspace-a", headers=headers, json={"name": "Workspace A"})
    workspace_chat = await client.post(
        "/api/v1/chats/",
        headers=headers,
        json={"title": "Workspace", "scope_type": "workspace", "workspace_id": "workspace-a"},
    )

    global_list = await client.get("/api/v1/chats/", headers=headers)
    workspace_list = await client.get(
        "/api/v1/chats/",
        headers=headers,
        params={"scope_type": "workspace", "workspace_id": "workspace-a"},
    )

    assert [c["id"] for c in global_list.json()["chats"]] == [global_chat.json()["id"]]
    assert [c["id"] for c in workspace_list.json()["chats"]] == [workspace_chat.json()["id"]]
```

**Step 2: Run test to verify it fails**

Run:

```bash
bunx vitest run apps/packages/ui/src/store/__tests__/workspace.test.ts apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.scope.test.tsx
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/e2e/test_workspace_chat_scope.py -v
```

Expected: FAIL because the workspace store still assumes one chat per workspace and trusts imported/cached `serverChatId`.

**Step 3: Write minimal implementation**

```ts
type WorkspaceScopedSessionKey = `${string}:${string}`

type WorkspaceChatState = {
  activeSessionIdByWorkspace: Record<string, string | null>
  draftsByWorkspaceAndSession: Record<WorkspaceScopedSessionKey, PersistedWorkspaceChatSession>
}

const sanitizeImportedChatSession = (session?: WorkspaceBundleChatSession) =>
  session
    ? {
        ...session,
        serverChatId: null
      }
    : undefined
```

Also implement:

- route-derived `ChatScope` in `ChatPane/index.tsx`
- scope-aware selection/submission through `useSelectServerChat` and `useChatActions`
- one-time stale-cache notice when a workspace pointer is invalidated because the server reports `global` or a different `workspace_id`
- server workspace sync calls on first persisted workspace chat, rename/archive, and delete

**Step 4: Run verification**

Run:

```bash
bunx vitest run apps/packages/ui/src/store/__tests__/workspace.test.ts apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.scope.test.tsx apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts apps/packages/ui/src/services/__tests__/tldw-api-client.chat-scope.test.ts
```

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py tldw_Server_API/tests/Chat/unit/test_chat_conversations_api.py tldw_Server_API/tests/Character_Chat/test_character_chat_endpoints.py tldw_Server_API/tests/Workspaces/test_workspaces_api.py tldw_Server_API/tests/e2e/test_workspace_chat_scope.py -v
```

```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/app/api/v1/endpoints/workspaces.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_workspace_chat_isolation.json
```

Expected: PASS, with no new Bandit findings in the touched backend scope.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/chat/useSelectServerChat.ts apps/packages/ui/src/hooks/chat/useChatActions.ts apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/store/workspace-bundle.ts apps/packages/ui/src/store/workspace-sync-contract.ts apps/packages/ui/src/store/__tests__/workspace.test.ts apps/packages/ui/src/store/__tests__/workspace-bundle.test.ts apps/packages/ui/src/components/Option/WorkspacePlayground/__tests__/ChatPane.scope.test.tsx tldw_Server_API/tests/e2e/test_workspace_chat_scope.py
git commit -m "feat: isolate workspace chat sessions end to end"
```

## Rollout Notes

- Land Stage 1 before touching any frontend code so omitted scope safely resolves to global chats.
- Land Stage 3 before enabling any workspace multi-session UI so workspace chat creation has a durable server identity.
- Do not infer workspace membership for pre-existing chats from browser-local state.
- Keep share-link and citations scope checks aligned with the same helper used for standard conversation reads.
- Strip `serverChatId` on import even if the origin bundle looks trustworthy; reattachment can be designed later as a separate feature.
