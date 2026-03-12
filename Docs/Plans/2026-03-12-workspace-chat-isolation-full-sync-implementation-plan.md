# Workspace Chat Isolation & Full Workspace Sync Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add strict server-enforced separation between global `/chat` and workspace-scoped `/workspace-playground` conversations, then extend workspaces into full server-persisted entities with sub-resource tables (sources, artifacts, notes), CRUD endpoints, and an API-first frontend store.

**Architecture:** Phase 1 adds a `workspaces` table and `scope_type`/`workspace_id` columns to `conversations` in `ChaChaNotes_DB.py` (schema v30), enforces scope across both `/api/v1/chat/*` and `/api/v1/chats/*` API families, and introduces workspace lifecycle APIs. Phase 2 extends the workspace table with banner/audio settings, adds `workspace_sources`, `workspace_artifacts`, and `workspace_notes` sub-resource tables (schema v31), adds full CRUD endpoints, refactors the frontend Zustand store from localStorage-source-of-truth to API-first cache, and ships a one-time client migration.

**Tech Stack:** FastAPI, Pydantic, SQLite (ChaChaNotes_DB.py, schema migrations), pytest, React/Next.js, Zustand, TanStack Query, Vitest.

---

## Phase 1: Chat Isolation + Minimal Workspace Registry

### Stage 1: Persistence And Scope Primitives
**Goal:** Add durable workspace records plus explicit conversation scope fields at the DB layer, with filtering helpers and soft-delete-aware workspace deletion behavior.
**Success Criteria:** Conversations can be stored and queried as either `global` or `workspace` scoped, workspace metadata is durable per user, and deleting a workspace soft-deletes only that workspace's conversations.
**Tests:** `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py`
**Status:** Not Started

#### Task 1: Add workspace registry and conversation scope columns

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Create: `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py`:

```python
"""Tests for workspace registry and conversation scope filtering."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    """Create a fresh ChaChaNotes DB with a default character card."""
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    # Most tests need a character_id; create a minimal one.
    d.add_character_card({"name": "Test Char", "client_id": "user-1"})
    return d


def _char_id(db: CharactersRAGDB) -> int:
    """Return the first character card's id."""
    cards = db.get_character_cards(client_id="user-1")
    return cards[0]["id"]


class TestWorkspaceUpsert:
    def test_upsert_creates_workspace(self, db):
        ws = db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        assert ws is not None
        assert ws["id"] == "ws-a"
        assert ws["name"] == "Workspace A"
        assert ws["version"] == 1

    def test_upsert_is_idempotent(self, db):
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        ws = db.upsert_workspace({"id": "ws-a", "name": "Workspace A Renamed", "client_id": "user-1"})
        assert ws["name"] == "Workspace A Renamed"
        assert ws["version"] == 2

    def test_get_workspace(self, db):
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        ws = db.get_workspace("ws-a", client_id="user-1")
        assert ws is not None
        assert ws["name"] == "Workspace A"

    def test_get_workspace_returns_none_for_missing(self, db):
        assert db.get_workspace("ws-missing", client_id="user-1") is None

    def test_list_workspaces_excludes_deleted(self, db):
        db.upsert_workspace({"id": "ws-a", "name": "A", "client_id": "user-1"})
        db.upsert_workspace({"id": "ws-b", "name": "B", "client_id": "user-1"})
        db.delete_workspace("ws-b", client_id="user-1")
        result = db.list_workspaces(client_id="user-1")
        assert [w["id"] for w in result] == ["ws-a"]


class TestConversationScope:
    def test_add_conversation_defaults_to_global_scope(self, db):
        cid = _char_id(db)
        conv_id = db.add_conversation({"title": "Global chat", "client_id": "user-1", "character_id": cid})
        conv = db.get_conversation_by_id(conv_id)
        assert conv["scope_type"] == "global"
        assert conv["workspace_id"] is None

    def test_add_conversation_with_workspace_scope(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        conv_id = db.add_conversation({
            "title": "Workspace chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })
        conv = db.get_conversation_by_id(conv_id)
        assert conv["scope_type"] == "workspace"
        assert conv["workspace_id"] == "ws-a"

    def test_workspace_scope_without_workspace_id_raises(self, db):
        cid = _char_id(db)
        with pytest.raises(Exception):
            db.add_conversation({
                "title": "Bad", "client_id": "user-1", "character_id": cid,
                "scope_type": "workspace",
            })

    def test_search_conversations_respects_scope_and_workspace(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        db.upsert_workspace({"id": "ws-b", "name": "Workspace B", "client_id": "user-1"})

        global_id = db.add_conversation({"title": "Global chat", "client_id": "user-1", "character_id": cid})
        ws_a_id = db.add_conversation({
            "title": "Workspace A chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })
        db.add_conversation({
            "title": "Workspace B chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-b",
        })

        global_results = db.search_conversations(None, scope_type="global")
        ws_results = db.search_conversations(None, scope_type="workspace", workspace_id="ws-a")

        assert global_id in [r["id"] for r in global_results]
        assert ws_a_id not in [r["id"] for r in global_results]
        assert ws_a_id in [r["id"] for r in ws_results]
        assert global_id not in [r["id"] for r in ws_results]


class TestWorkspaceDeleteCascade:
    def test_delete_workspace_soft_deletes_scoped_conversations(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        conv_id = db.add_conversation({
            "title": "Workspace chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })

        db.delete_workspace("ws-a", client_id="user-1")

        assert db.get_conversation_by_id(conv_id) is None  # soft-deleted

    def test_delete_workspace_does_not_affect_global_chats(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        global_id = db.add_conversation({"title": "Global", "client_id": "user-1", "character_id": cid})

        db.delete_workspace("ws-a", client_id="user-1")

        assert db.get_conversation_by_id(global_id) is not None


class TestWorkspaceOptimisticLocking:
    def test_update_workspace_with_stale_version_raises(self, db):
        db.upsert_workspace({"id": "ws-a", "name": "A", "client_id": "user-1"})
        # Update once so version becomes 2
        db.update_workspace("ws-a", {"name": "A2"}, client_id="user-1", expected_version=1)
        # Now try with stale version 1
        with pytest.raises(Exception):
            db.update_workspace("ws-a", {"name": "A3"}, client_id="user-1", expected_version=1)

    def test_update_workspace_with_correct_version_succeeds(self, db):
        db.upsert_workspace({"id": "ws-a", "name": "A", "client_id": "user-1"})
        ws = db.update_workspace("ws-a", {"name": "A2"}, client_id="user-1", expected_version=1)
        assert ws["name"] == "A2"
        assert ws["version"] == 2
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py -v
```

Expected: FAIL because `upsert_workspace`, `scope_type`, `workspace_id`, and workspace delete helpers do not exist.

**Step 3: Write minimal implementation**

In `ChaChaNotes_DB.py`:

1. Bump `_CURRENT_SCHEMA_VERSION` from 29 to 30.

2. Add migration SQL `_MIGRATION_SQL_V29_TO_V30`:

```sql
/*───────────────────────────────────────────────────────────────
  Migration to Version 30 - Workspace registry + conversation scope
───────────────────────────────────────────────────────────────*/
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS workspaces(
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

ALTER TABLE conversations ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'global';
ALTER TABLE conversations ADD COLUMN IF NOT EXISTS workspace_id TEXT DEFAULT NULL
  REFERENCES workspaces(id);

CREATE INDEX IF NOT EXISTS idx_conversations_scope
  ON conversations(client_id, scope_type, workspace_id, deleted, last_modified);

UPDATE db_schema_version
   SET version = 30
 WHERE schema_name = 'rag_char_chat_schema'
   AND version < 30;
```

3. Wire migration into `_initialize_sqlite_schema()` and `_initialize_postgres_schema()` following existing v28->v29 pattern.

4. Add a `_normalize_scope` static method:

```python
@staticmethod
def _normalize_scope(scope_type: str | None, workspace_id: str | None) -> tuple[str, str | None]:
    scope = (scope_type or "global").strip().lower()
    if scope == "global":
        return "global", None
    if scope != "workspace" or not workspace_id:
        raise InputError("workspace scope requires workspace_id")
    return "workspace", workspace_id
```

5. Modify `add_conversation` to accept and persist `scope_type` and `workspace_id` from `conv_data`, calling `_normalize_scope` for validation and adding the two columns to the INSERT.

6. Modify `search_conversations` to accept `scope_type: str | None = None` and `workspace_id: str | None = None` keyword args. When `scope_type` is provided, add `c.scope_type = ?` filter. When `scope_type == "workspace"`, also add `c.workspace_id = ?` filter. Apply the same logic in both the SQLite and PostgreSQL branches.

7. Add workspace CRUD methods:

```python
def upsert_workspace(self, ws_data: dict[str, Any]) -> dict[str, Any]:
    """Create or update a workspace. Returns the workspace row."""

def get_workspace(self, workspace_id: str, *, client_id: str) -> dict[str, Any] | None:
    """Fetch a non-deleted workspace by id and owner."""

def list_workspaces(self, *, client_id: str, include_archived: bool = False) -> list[dict[str, Any]]:
    """List non-deleted workspaces for a user, ordered by last_modified DESC."""

def update_workspace(self, workspace_id: str, updates: dict[str, Any], *, client_id: str, expected_version: int) -> dict[str, Any]:
    """Update workspace fields with optimistic locking. Raises ConflictError if version mismatch."""

def delete_workspace(self, workspace_id: str, *, client_id: str) -> None:
    """Soft-delete workspace and cascade soft-delete to scoped conversations/messages."""
```

The `delete_workspace` implementation should:
- Mark workspace `deleted = 1`, bump `version`
- Find all conversations with `workspace_id = <id>` and `deleted = 0`
- Soft-delete each via existing `soft_delete_conversation_and_messages` path (or equivalent)

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
git commit -m "feat: add workspace registry and conversation scope primitives (schema v30)"
```

---

### Stage 2: Scope `/api/v1/chat/*` Endpoints
**Goal:** Make the conversation-centric chat endpoints explicitly scope-aware and fail closed to global chats when older clients omit scope.
**Success Criteria:** `/api/v1/chat/conversations`, `/tree`, `/analytics`, and share-link related reads/writes return only the requested scope, and wrong-scope IDs return `404`.
**Tests:** `tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py`
**Status:** Not Started

#### Task 2: Thread `scope_type` and `workspace_id` through the `/api/v1/chat/*` API

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Create: `tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py`:

```python
"""Tests that /api/v1/chat/* endpoints respect scope_type and workspace_id."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.add_character_card({"name": "Test Char", "client_id": "user-1"})
    return d


def _char_id(db: CharactersRAGDB) -> int:
    cards = db.get_character_cards(client_id="user-1")
    return cards[0]["id"]


class TestConversationListScope:
    def test_list_defaults_to_global_scope(self, db):
        """Omitting scope returns only global conversations."""
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        db.add_conversation({"title": "Global chat", "client_id": "user-1", "character_id": cid})
        db.add_conversation({
            "title": "Workspace chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })

        results = db.search_conversations(None, scope_type="global")
        titles = [r["title"] for r in results]
        assert "Global chat" in titles
        assert "Workspace chat" not in titles

    def test_list_workspace_scope_returns_only_that_workspace(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "A", "client_id": "user-1"})
        db.upsert_workspace({"id": "ws-b", "name": "B", "client_id": "user-1"})
        db.add_conversation({
            "title": "A chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })
        db.add_conversation({
            "title": "B chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-b",
        })

        results = db.search_conversations(None, scope_type="workspace", workspace_id="ws-a")
        titles = [r["title"] for r in results]
        assert "A chat" in titles
        assert "B chat" not in titles


class TestConversationDetail404OnScopeMismatch:
    def test_get_conversation_validates_scope(self, db):
        """Attempting to load a workspace conversation without scope match returns None."""
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "A", "client_id": "user-1"})
        conv_id = db.add_conversation({
            "title": "WS chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })
        # Direct get still works (no scope filter at DB level), but the endpoint
        # layer will check scope and return 404. Verify the raw data has scope set.
        conv = db.get_conversation_by_id(conv_id)
        assert conv["scope_type"] == "workspace"
        assert conv["workspace_id"] == "ws-a"
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py -v
```

Expected: FAIL because `search_conversations` does not accept `scope_type`/`workspace_id` yet (unless Stage 1 is already done, in which case this verifies Stage 1 integration).

**Step 3: Write minimal implementation**

Add Pydantic scope params in `chat_conversation_schemas.py`:

```python
from pydantic import BaseModel, model_validator
from typing import Literal

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
```

In `chat.py`, thread scope through every endpoint that lists, searches, loads, or mutates conversations:

- Add `scope_type: str = Query("global")` and `workspace_id: str | None = Query(None)` params
- Pass them to DB queries via `search_conversations(..., scope_type=scope_type, workspace_id=workspace_id)`
- For single-resource endpoints (detail, tree, citations, share-links), after fetching the conversation, validate `conv["scope_type"] == requested_scope_type` and `conv["workspace_id"] == requested_workspace_id`; if mismatch, raise `HTTPException(status_code=404)`

Important: omitted scope means `global`, never "all chats."

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py
git commit -m "feat: scope /api/v1/chat/* conversation endpoints by scope_type"
```

---

### Stage 3: Scope `/api/v1/chats/*` And Add Workspace Lifecycle APIs
**Goal:** Make the resource-style chat session endpoints enforce the same scope rules, and add server CRUD for workspace identity and deletion semantics.
**Success Criteria:** `/api/v1/chats/*` create/list/load/message/completion/search respect scope, `/api/v1/workspaces/*` supports upsert/update/delete, and workspace deletion hides its scoped chats immediately.
**Tests:** `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`
**Status:** Not Started

#### Task 3: Add workspace CRUD endpoints and scope-aware session APIs

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/workspace_schemas.py`
- Create: `tldw_Server_API/app/api/v1/endpoints/workspaces.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/app/main.py` (register workspace router)
- Create: `tldw_Server_API/tests/Workspaces/__init__.py`
- Create: `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`:

```python
"""Tests for workspace CRUD endpoints and scoped chat session isolation."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.add_character_card({"name": "Test Char", "client_id": "user-1"})
    return d


def _char_id(db):
    return db.get_character_cards(client_id="user-1")[0]["id"]


class TestWorkspaceLifecycle:
    def test_upsert_then_get(self, db):
        ws = db.upsert_workspace({"id": "ws-1", "name": "My Workspace", "client_id": "user-1"})
        assert ws["id"] == "ws-1"
        fetched = db.get_workspace("ws-1", client_id="user-1")
        assert fetched["name"] == "My Workspace"

    def test_patch_workspace_name(self, db):
        db.upsert_workspace({"id": "ws-1", "name": "Old", "client_id": "user-1"})
        ws = db.update_workspace("ws-1", {"name": "New"}, client_id="user-1", expected_version=1)
        assert ws["name"] == "New"
        assert ws["version"] == 2

    def test_archive_workspace(self, db):
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        ws = db.update_workspace("ws-1", {"archived": True}, client_id="user-1", expected_version=1)
        assert ws["archived"] in (True, 1)

    def test_delete_workspace_cascade(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        conv_id = db.add_conversation({
            "title": "WS chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-1",
        })
        db.delete_workspace("ws-1", client_id="user-1")

        # Workspace is soft-deleted
        ws = db.get_workspace("ws-1", client_id="user-1")
        assert ws is None  # get_workspace excludes deleted

        # Conversation is also soft-deleted
        conv = db.get_conversation_by_id(conv_id)
        assert conv is None

    def test_list_workspaces_paginated(self, db):
        for i in range(5):
            db.upsert_workspace({"id": f"ws-{i}", "name": f"WS {i}", "client_id": "user-1"})
        result = db.list_workspaces(client_id="user-1")
        assert len(result) == 5

    def test_version_conflict_returns_error(self, db):
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        db.update_workspace("ws-1", {"name": "V2"}, client_id="user-1", expected_version=1)
        with pytest.raises(Exception):  # ConflictError
            db.update_workspace("ws-1", {"name": "V3"}, client_id="user-1", expected_version=1)


class TestScopedChatSessions:
    def test_workspace_chat_not_visible_in_global_list(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        db.add_conversation({"title": "Global", "client_id": "user-1", "character_id": cid})
        db.add_conversation({
            "title": "WS Chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-1",
        })
        global_results = db.search_conversations(None, scope_type="global")
        assert all(r["scope_type"] == "global" for r in global_results)

    def test_global_chat_not_visible_in_workspace_list(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        db.add_conversation({"title": "Global", "client_id": "user-1", "character_id": cid})
        ws_results = db.search_conversations(None, scope_type="workspace", workspace_id="ws-1")
        assert len(ws_results) == 0
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workspaces/test_workspaces_api.py -v
```

Expected: FAIL because workspace methods and scope filtering do not exist yet (unless Stage 1 is done).

**Step 3: Write minimal implementation**

Create `workspace_schemas.py`:

```python
"""Pydantic schemas for workspace CRUD."""
from __future__ import annotations
from pydantic import BaseModel, Field
from typing import Literal


class WorkspaceUpsertRequest(BaseModel):
    name: str
    archived: bool = False


class WorkspacePatchRequest(BaseModel):
    name: str | None = None
    archived: bool | None = None
    version: int = Field(..., description="Current version for optimistic locking")


class WorkspaceDeleteRequest(BaseModel):
    version: int | None = None


class WorkspaceResponse(BaseModel):
    id: str
    name: str | None
    archived: bool
    deleted: bool
    created_at: str
    last_modified: str
    version: int


class WorkspaceListResponse(BaseModel):
    items: list[WorkspaceResponse]
    total: int
```

Create `workspaces.py` endpoint:

```python
"""Workspace lifecycle CRUD endpoints."""
from __future__ import annotations
from fastapi import APIRouter, Depends, HTTPException, Query
from tldw_Server_API.app.api.v1.schemas.workspace_schemas import (
    WorkspaceUpsertRequest,
    WorkspacePatchRequest,
    WorkspaceResponse,
    WorkspaceListResponse,
)

router = APIRouter()


@router.put("/{workspace_id}", response_model=WorkspaceResponse)
async def upsert_workspace(workspace_id: str, body: WorkspaceUpsertRequest, ...):
    ws = db.upsert_workspace({"id": workspace_id, "name": body.name, "archived": body.archived, "client_id": user_id})
    return ws


@router.get("/{workspace_id}", response_model=WorkspaceResponse)
async def get_workspace(workspace_id: str, ...):
    ws = db.get_workspace(workspace_id, client_id=user_id)
    if not ws:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return ws


@router.patch("/{workspace_id}", response_model=WorkspaceResponse)
async def patch_workspace(workspace_id: str, body: WorkspacePatchRequest, ...):
    updates = body.model_dump(exclude_unset=True, exclude={"version"})
    ws = db.update_workspace(workspace_id, updates, client_id=user_id, expected_version=body.version)
    return ws


@router.delete("/{workspace_id}", status_code=204)
async def delete_workspace(workspace_id: str, ...):
    db.delete_workspace(workspace_id, client_id=user_id)


@router.get("/", response_model=WorkspaceListResponse)
async def list_workspaces(...):
    items = db.list_workspaces(client_id=user_id)
    return {"items": items, "total": len(items)}
```

Register in `main.py`:

```python
from tldw_Server_API.app.api.v1.endpoints.workspaces import router as workspaces_router
app.include_router(workspaces_router, prefix=f"{API_V1_PREFIX}/workspaces", tags=["workspaces"])
```

Modify `character_chat_sessions.py`:
- Add `scope_type` and `workspace_id` query params to list/search/create/detail endpoints
- On chat creation with `scope_type="workspace"`, auto-upsert the workspace if it doesn't exist
- On list/search, pass scope filters to DB queries
- On detail/load/message/completion, validate scope match after fetching; return 404 on mismatch

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workspaces/test_workspaces_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/workspace_schemas.py tldw_Server_API/app/api/v1/endpoints/workspaces.py tldw_Server_API/app/api/v1/schemas/chat_session_schemas.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/app/main.py tldw_Server_API/tests/Workspaces/__init__.py tldw_Server_API/tests/Workspaces/test_workspaces_api.py
git commit -m "feat: add workspace lifecycle endpoints and scope-aware /chats/* API"
```

---

### Stage 4: Shared UI Scope Contract
**Goal:** Introduce one frontend `ChatScope` type and ensure all shared API helpers and history loaders pass scope explicitly.
**Success Criteria:** The UI defaults to `global` scope unless a workspace scope is explicitly provided, `/chat` history requests never fetch workspace chats, and workspace history/search requests always carry `workspace_id`.
**Tests:** `apps/packages/ui/src/types/__tests__/chat-scope.test.ts`, `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts` (additions)
**Status:** Not Started

#### Task 4: Make the shared UI API client and history hooks scope-aware

**Files:**
- Create: `apps/packages/ui/src/types/chat-scope.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`
- Modify: `apps/packages/ui/src/services/timeline/api.ts` (if it exists)
- Modify: `apps/packages/ui/src/hooks/useServerChatHistory.ts`
- Modify: `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`
- Create: `apps/packages/ui/src/types/__tests__/chat-scope.test.ts`

**Step 1: Write the failing test**

Create `apps/packages/ui/src/types/__tests__/chat-scope.test.ts`:

```ts
import { describe, it, expect } from "vitest"
import { toChatScopeParams } from "../chat-scope"

describe("toChatScopeParams", () => {
  it("defaults to global when no scope provided", () => {
    expect(toChatScopeParams()).toEqual({ scope_type: "global" })
  })

  it("returns global scope params for global type", () => {
    expect(toChatScopeParams({ type: "global" })).toEqual({ scope_type: "global" })
  })

  it("returns workspace scope params with workspace_id", () => {
    expect(toChatScopeParams({ type: "workspace", workspaceId: "ws-1" })).toEqual({
      scope_type: "workspace",
      workspace_id: "ws-1",
    })
  })
})
```

Add to `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`:

```ts
it("passes workspace scope through useServerChatHistory", async () => {
  renderHook(
    () =>
      useServerChatHistory("", {
        scope: { type: "workspace", workspaceId: "workspace-a" },
      }),
    { wrapper }
  )

  await waitFor(() =>
    expect(listChatsWithMetaMock).toHaveBeenCalledWith(
      expect.objectContaining({
        scope_type: "workspace",
        workspace_id: "workspace-a",
      }),
      expect.anything()
    )
  )
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps && bunx vitest run packages/ui/src/types/__tests__/chat-scope.test.ts
```

Expected: FAIL because `chat-scope.ts` does not exist.

**Step 3: Write minimal implementation**

Create `apps/packages/ui/src/types/chat-scope.ts`:

```ts
/**
 * Discriminated union for chat scope. Thread through all API calls
 * and history hooks so omitted scope always means "global".
 */
export type ChatScope =
  | { type: "global" }
  | { type: "workspace"; workspaceId: string }

/**
 * Convert a ChatScope into the query/body params expected by the backend.
 * Omitted scope defaults to global.
 */
export const toChatScopeParams = (
  scope?: ChatScope
): { scope_type: "global" } | { scope_type: "workspace"; workspace_id: string } =>
  scope?.type === "workspace"
    ? { scope_type: "workspace", workspace_id: scope.workspaceId }
    : { scope_type: "global" }
```

In `TldwApiClient.ts`, modify `listChats`, `listChatsWithMeta`, `createChat`, and related methods to accept an optional `scope?: ChatScope` param. Spread `toChatScopeParams(scope)` into query params or request body. No API call path should ever omit scope.

In `useServerChatHistory.ts`, accept `scope?: ChatScope` in options and forward to the API client.

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps && bunx vitest run packages/ui/src/types/__tests__/chat-scope.test.ts packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/types/chat-scope.ts apps/packages/ui/src/types/__tests__/chat-scope.test.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts apps/packages/ui/src/hooks/useServerChatHistory.ts apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
git commit -m "feat: add frontend ChatScope type and scope-aware API client"
```

---

### Stage 5: Workspace Route State, Import Safety, And Rollout Verification
**Goal:** Refactor workspace chat state so each workspace can own multiple scoped sessions, invalidate wrong-scope cached pointers safely, strip `serverChatId` on import, and cover the rollout with end-to-end tests.
**Success Criteria:** Switching workspaces only surfaces that workspace's chats, imported bundles never silently reconnect to server chats, stale workspace pointers are cleared with a one-time notice, and all backend/frontend tests pass.
**Tests:** `apps/packages/ui/src/store/__tests__/workspace-scope.test.ts`, `tldw_Server_API/tests/e2e/test_workspace_chat_scope.py`
**Status:** Not Started

#### Task 5: Finish workspace UI isolation, import safety, and end-to-end verification

**Files:**
- Modify: `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts`
- Modify: `apps/packages/ui/src/hooks/chat/useChatActions.ts`
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/store/workspace-bundle.ts`
- Modify: `apps/packages/ui/src/store/workspace-sync-contract.ts`
- Create: `apps/packages/ui/src/store/__tests__/workspace-scope.test.ts`
- Create: `tldw_Server_API/tests/e2e/__init__.py`
- Create: `tldw_Server_API/tests/e2e/test_workspace_chat_scope.py`

**Step 1: Write the failing test**

Create `apps/packages/ui/src/store/__tests__/workspace-scope.test.ts`:

```ts
import { describe, it, expect, vi } from "vitest"

describe("workspace import safety", () => {
  it("strips serverChatId during workspace import", () => {
    const session = {
      serverChatId: "server-123",
      messages: [],
      history: [],
    }
    const sanitized = sanitizeImportedChatSession(session)
    expect(sanitized.serverChatId).toBeNull()
  })

  it("clears cached serverChatId when scope validation fails", () => {
    // serverChatId points to a global chat, but we are in a workspace
    const validated = validateCachedServerChatId({
      cachedId: "server-123",
      serverScope: { scope_type: "global", workspace_id: null },
      expectedScope: { type: "workspace", workspaceId: "ws-a" },
    })
    expect(validated).toBeNull()
  })

  it("preserves cached serverChatId when scope matches", () => {
    const validated = validateCachedServerChatId({
      cachedId: "server-123",
      serverScope: { scope_type: "workspace", workspace_id: "ws-a" },
      expectedScope: { type: "workspace", workspaceId: "ws-a" },
    })
    expect(validated).toBe("server-123")
  })
})
```

Create `tldw_Server_API/tests/e2e/test_workspace_chat_scope.py`:

```python
"""End-to-end tests for workspace chat scope isolation at the DB level."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.add_character_card({"name": "Test Char", "client_id": "user-1"})
    return d


def _char_id(db):
    return db.get_character_cards(client_id="user-1")[0]["id"]


class TestWorkspaceScopeEndToEnd:
    def test_full_isolation_workflow(self, db):
        cid = _char_id(db)

        # Create global chat
        global_id = db.add_conversation({"title": "Global", "client_id": "user-1", "character_id": cid})

        # Create workspace A with chat
        db.upsert_workspace({"id": "ws-a", "name": "Workspace A", "client_id": "user-1"})
        ws_a_id = db.add_conversation({
            "title": "WS-A Chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })

        # Create workspace B with chat
        db.upsert_workspace({"id": "ws-b", "name": "Workspace B", "client_id": "user-1"})
        ws_b_id = db.add_conversation({
            "title": "WS-B Chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-b",
        })

        # Verify isolation
        global_results = db.search_conversations(None, scope_type="global")
        ws_a_results = db.search_conversations(None, scope_type="workspace", workspace_id="ws-a")
        ws_b_results = db.search_conversations(None, scope_type="workspace", workspace_id="ws-b")

        global_ids = [r["id"] for r in global_results]
        ws_a_ids = [r["id"] for r in ws_a_results]
        ws_b_ids = [r["id"] for r in ws_b_results]

        assert global_id in global_ids
        assert ws_a_id not in global_ids
        assert ws_b_id not in global_ids

        assert ws_a_id in ws_a_ids
        assert global_id not in ws_a_ids
        assert ws_b_id not in ws_a_ids

        assert ws_b_id in ws_b_ids
        assert global_id not in ws_b_ids
        assert ws_a_id not in ws_b_ids

    def test_workspace_delete_cascade(self, db):
        cid = _char_id(db)
        db.upsert_workspace({"id": "ws-a", "name": "A", "client_id": "user-1"})
        ws_conv = db.add_conversation({
            "title": "WS Chat", "client_id": "user-1", "character_id": cid,
            "scope_type": "workspace", "workspace_id": "ws-a",
        })
        global_conv = db.add_conversation({"title": "Global", "client_id": "user-1", "character_id": cid})

        db.delete_workspace("ws-a", client_id="user-1")

        # Workspace chat gone
        assert db.get_conversation_by_id(ws_conv) is None
        # Global chat untouched
        assert db.get_conversation_by_id(global_conv) is not None
        # Workspace not listed
        assert db.get_workspace("ws-a", client_id="user-1") is None

    def test_existing_conversations_default_to_global(self, db):
        """Pre-existing conversations (before scope was added) should be global."""
        cid = _char_id(db)
        conv_id = db.add_conversation({"title": "Old chat", "client_id": "user-1", "character_id": cid})
        conv = db.get_conversation_by_id(conv_id)
        assert conv["scope_type"] == "global"
        assert conv["workspace_id"] is None
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps && bunx vitest run packages/ui/src/store/__tests__/workspace-scope.test.ts
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/e2e/test_workspace_chat_scope.py -v
```

Expected: FAIL because `sanitizeImportedChatSession` and `validateCachedServerChatId` do not exist yet.

**Step 3: Write minimal implementation**

In `workspace-bundle.ts`, add:

```ts
export const sanitizeImportedChatSession = (session: any) => ({
  ...session,
  serverChatId: null,
})
```

In `workspace-sync-contract.ts` (or new file), add:

```ts
export const validateCachedServerChatId = ({
  cachedId,
  serverScope,
  expectedScope,
}: {
  cachedId: string | null
  serverScope: { scope_type: string; workspace_id: string | null } | null
  expectedScope: ChatScope
}): string | null => {
  if (!cachedId || !serverScope) return null
  if (expectedScope.type === "global" && serverScope.scope_type === "global") return cachedId
  if (
    expectedScope.type === "workspace" &&
    serverScope.scope_type === "workspace" &&
    serverScope.workspace_id === expectedScope.workspaceId
  )
    return cachedId
  return null
}
```

In `workspace.ts`, refactor the chat state from single-session to multi-session:

```ts
type WorkspaceScopedSessionKey = `${string}:${string}` // workspaceId:sessionId

type WorkspaceChatState = {
  activeSessionIdByWorkspace: Record<string, string | null>
  draftsByWorkspaceAndSession: Record<WorkspaceScopedSessionKey, PersistedWorkspaceChatSession>
}
```

In `useSelectServerChat.ts` and `useChatActions.ts`:
- Accept `scope: ChatScope` and thread through to API calls
- On load, validate cached `serverChatId` via `validateCachedServerChatId`
- Clear stale pointers and show a one-time toast

**Step 4: Run verification**

Run all Phase 1 tests:

```bash
cd apps && bunx vitest run packages/ui/src/types/__tests__/chat-scope.test.ts packages/ui/src/store/__tests__/workspace-scope.test.ts packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts

source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py tldw_Server_API/tests/Workspaces/test_workspaces_api.py tldw_Server_API/tests/e2e/test_workspace_chat_scope.py -v
```

Expected: PASS.

**Step 5: Run security verification**

Run:

```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py tldw_Server_API/app/api/v1/endpoints/workspaces.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_workspace_chat_isolation.json
```

Expected: No new Bandit findings in touched files.

**Step 6: Commit**

```bash
git add apps/packages/ui/src/store/__tests__/workspace-scope.test.ts apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/store/workspace-bundle.ts apps/packages/ui/src/store/workspace-sync-contract.ts apps/packages/ui/src/hooks/chat/useSelectServerChat.ts apps/packages/ui/src/hooks/chat/useChatActions.ts tldw_Server_API/tests/e2e/__init__.py tldw_Server_API/tests/e2e/test_workspace_chat_scope.py
git commit -m "feat: isolate workspace chat sessions end to end (Phase 1 complete)"
```

---

## Phase 2: Full Workspace Sync

### Stage 6: Sub-Resource Tables And Schema Migration
**Goal:** Add `workspace_sources`, `workspace_artifacts`, and `workspace_notes` tables plus workspace settings columns (banner, audio) to the workspaces table. Schema v31.
**Success Criteria:** Sub-resource tables exist with proper FK cascade to workspaces, CRUD methods work at the DB layer, and optimistic locking is enforced on all sub-resource mutations.
**Tests:** `tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py`
**Status:** Not Started

#### Task 6: Add Phase 2 tables and DB-layer CRUD

**Files:**
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Create: `tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py`:

```python
"""Tests for workspace sub-resource tables: sources, artifacts, notes."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.upsert_workspace({"id": "ws-1", "name": "Test WS", "client_id": "user-1"})
    return d


class TestWorkspaceSources:
    def test_add_source(self, db):
        src = db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 42, "title": "My Video",
            "source_type": "video", "client_id": "user-1",
        })
        assert src["id"] == "src-1"
        assert src["media_id"] == 42
        assert src["version"] == 1

    def test_list_sources_ordered_by_position(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-a", "media_id": 1, "title": "A",
            "source_type": "video", "position": 2, "client_id": "user-1",
        })
        db.add_workspace_source("ws-1", {
            "id": "src-b", "media_id": 2, "title": "B",
            "source_type": "pdf", "position": 1, "client_id": "user-1",
        })
        sources = db.list_workspace_sources("ws-1")
        assert sources[0]["id"] == "src-b"
        assert sources[1]["id"] == "src-a"

    def test_update_source_with_version_check(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "Old",
            "source_type": "video", "client_id": "user-1",
        })
        updated = db.update_workspace_source("ws-1", "src-1", {"title": "New"}, expected_version=1)
        assert updated["title"] == "New"
        assert updated["version"] == 2

    def test_delete_source(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video", "client_id": "user-1",
        })
        db.delete_workspace_source("ws-1", "src-1")
        assert db.list_workspace_sources("ws-1") == []

    def test_batch_update_selection(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-a", "media_id": 1, "title": "A",
            "source_type": "video", "client_id": "user-1",
        })
        db.add_workspace_source("ws-1", {
            "id": "src-b", "media_id": 2, "title": "B",
            "source_type": "pdf", "client_id": "user-1",
        })
        db.update_workspace_source_selection("ws-1", selected_ids=["src-a"])
        sources = db.list_workspace_sources("ws-1")
        sel = {s["id"]: s["selected"] for s in sources}
        assert sel["src-a"] in (True, 1)
        assert sel["src-b"] in (False, 0)

    def test_batch_reorder(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-a", "media_id": 1, "title": "A",
            "source_type": "video", "client_id": "user-1",
        })
        db.add_workspace_source("ws-1", {
            "id": "src-b", "media_id": 2, "title": "B",
            "source_type": "pdf", "client_id": "user-1",
        })
        db.reorder_workspace_sources("ws-1", ["src-b", "src-a"])
        sources = db.list_workspace_sources("ws-1")
        assert sources[0]["id"] == "src-b"
        assert sources[0]["position"] == 0
        assert sources[1]["id"] == "src-a"
        assert sources[1]["position"] == 1


class TestWorkspaceArtifacts:
    def test_add_artifact(self, db):
        art = db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Summary",
            "client_id": "user-1",
        })
        assert art["id"] == "art-1"
        assert art["artifact_type"] == "summary"

    def test_list_artifacts(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "S1",
            "client_id": "user-1",
        })
        db.add_workspace_artifact("ws-1", {
            "id": "art-2", "artifact_type": "podcast", "title": "P1",
            "client_id": "user-1",
        })
        arts = db.list_workspace_artifacts("ws-1")
        assert len(arts) == 2

    def test_update_artifact_with_version_check(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Old",
            "client_id": "user-1",
        })
        updated = db.update_workspace_artifact("ws-1", "art-1", {"title": "New"}, expected_version=1)
        assert updated["title"] == "New"
        assert updated["version"] == 2

    def test_delete_artifact(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "X",
            "client_id": "user-1",
        })
        db.delete_workspace_artifact("ws-1", "art-1")
        assert db.list_workspace_artifacts("ws-1") == []


class TestWorkspaceNotes:
    def test_add_note(self, db):
        note = db.add_workspace_note("ws-1", {
            "title": "My Note", "content": "Hello", "client_id": "user-1",
        })
        assert note["title"] == "My Note"
        assert note["version"] == 1

    def test_list_notes_excludes_deleted(self, db):
        n1 = db.add_workspace_note("ws-1", {"title": "N1", "content": "", "client_id": "user-1"})
        n2 = db.add_workspace_note("ws-1", {"title": "N2", "content": "", "client_id": "user-1"})
        db.delete_workspace_note("ws-1", n2["id"])
        notes = db.list_workspace_notes("ws-1")
        assert len(notes) == 1
        assert notes[0]["title"] == "N1"

    def test_update_note_with_version_check(self, db):
        note = db.add_workspace_note("ws-1", {"title": "Old", "content": "", "client_id": "user-1"})
        updated = db.update_workspace_note("ws-1", note["id"], {"title": "New"}, expected_version=1)
        assert updated["title"] == "New"
        assert updated["version"] == 2


class TestWorkspaceSettings:
    def test_update_workspace_banner_settings(self, db):
        ws = db.update_workspace("ws-1", {
            "banner_title": "My Project",
            "banner_subtitle": "Research notes",
        }, client_id="user-1", expected_version=1)
        assert ws["banner_title"] == "My Project"
        assert ws["banner_subtitle"] == "Research notes"

    def test_update_workspace_audio_settings(self, db):
        ws = db.update_workspace("ws-1", {
            "audio_provider": "openai",
            "audio_model": "tts-1",
            "audio_voice": "alloy",
        }, client_id="user-1", expected_version=1)
        assert ws["audio_provider"] == "openai"
        assert ws["audio_model"] == "tts-1"


class TestFKCascadeOnHardDelete:
    def test_hard_delete_workspace_cascades_to_sources(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video", "client_id": "user-1",
        })
        # Hard delete = delete the row, not soft delete
        db.hard_delete_workspace("ws-1")
        assert db.list_workspace_sources("ws-1") == []
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py -v
```

Expected: FAIL because sub-resource methods and Phase 2 tables do not exist.

**Step 3: Write minimal implementation**

In `ChaChaNotes_DB.py`:

1. Bump `_CURRENT_SCHEMA_VERSION` from 30 to 31.

2. Add `_MIGRATION_SQL_V30_TO_V31` with the full schema from the design doc:
   - `ALTER TABLE workspaces ADD COLUMN ...` for tag, banner_*, audio_* columns
   - `CREATE TABLE IF NOT EXISTS workspace_sources(...)` with FK CASCADE
   - `CREATE TABLE IF NOT EXISTS workspace_artifacts(...)` with FK CASCADE
   - `CREATE TABLE IF NOT EXISTS workspace_notes(...)` with FK CASCADE
   - Indexes
   - Version bump

3. Wire migration into both SQLite and PostgreSQL paths.

4. Add CRUD methods for each sub-resource, all following the same pattern:

```python
# Sources
def add_workspace_source(self, workspace_id: str, data: dict) -> dict: ...
def list_workspace_sources(self, workspace_id: str) -> list[dict]: ...
def update_workspace_source(self, workspace_id: str, source_id: str, updates: dict, *, expected_version: int) -> dict: ...
def delete_workspace_source(self, workspace_id: str, source_id: str) -> None: ...
def update_workspace_source_selection(self, workspace_id: str, *, selected_ids: list[str]) -> None: ...
def reorder_workspace_sources(self, workspace_id: str, ordered_ids: list[str]) -> None: ...

# Artifacts
def add_workspace_artifact(self, workspace_id: str, data: dict) -> dict: ...
def list_workspace_artifacts(self, workspace_id: str) -> list[dict]: ...
def update_workspace_artifact(self, workspace_id: str, artifact_id: str, updates: dict, *, expected_version: int) -> dict: ...
def delete_workspace_artifact(self, workspace_id: str, artifact_id: str) -> None: ...

# Notes
def add_workspace_note(self, workspace_id: str, data: dict) -> dict: ...
def list_workspace_notes(self, workspace_id: str) -> list[dict]: ...
def update_workspace_note(self, workspace_id: str, note_id: int, updates: dict, *, expected_version: int) -> dict: ...
def delete_workspace_note(self, workspace_id: str, note_id: int) -> None: ...  # soft delete

# Hard purge
def hard_delete_workspace(self, workspace_id: str) -> None: ...  # DELETE FROM workspaces WHERE id=?; FK cascade handles sub-resources
```

All mutating methods enforce optimistic locking: compare `expected_version` against current `version` in DB; raise `ConflictError` on mismatch.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py
git commit -m "feat: add workspace sub-resource tables and CRUD (schema v31)"
```

---

### Stage 7: Sub-Resource CRUD Endpoints
**Goal:** Expose workspace sub-resource (sources, artifacts, notes) management through RESTful API endpoints with optimistic locking.
**Success Criteria:** Full CRUD for sources (including batch selection and reorder), artifacts, and notes. All mutations require version. 409 on conflict with current state in body.
**Tests:** `tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py`
**Status:** Not Started

#### Task 7: Add sub-resource CRUD endpoints

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/workspace_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/workspaces.py`
- Create: `tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py`

**Step 1: Write the failing test**

Create `tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py`:

```python
"""Tests for workspace sub-resource API endpoints."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    d.upsert_workspace({"id": "ws-1", "name": "Test WS", "client_id": "user-1"})
    return d


class TestSourceEndpoints:
    def test_add_and_list_sources(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "Video",
            "source_type": "video", "client_id": "user-1",
        })
        sources = db.list_workspace_sources("ws-1")
        assert len(sources) == 1
        assert sources[0]["title"] == "Video"

    def test_update_source_returns_409_on_stale_version(self, db):
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "X",
            "source_type": "video", "client_id": "user-1",
        })
        db.update_workspace_source("ws-1", "src-1", {"title": "Y"}, expected_version=1)
        with pytest.raises(Exception):
            db.update_workspace_source("ws-1", "src-1", {"title": "Z"}, expected_version=1)


class TestArtifactEndpoints:
    def test_add_and_list_artifacts(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Summary",
            "client_id": "user-1",
        })
        arts = db.list_workspace_artifacts("ws-1")
        assert len(arts) == 1

    def test_update_artifact_returns_409_on_stale_version(self, db):
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "X",
            "client_id": "user-1",
        })
        db.update_workspace_artifact("ws-1", "art-1", {"title": "Y"}, expected_version=1)
        with pytest.raises(Exception):
            db.update_workspace_artifact("ws-1", "art-1", {"title": "Z"}, expected_version=1)


class TestNoteEndpoints:
    def test_add_and_list_notes(self, db):
        db.add_workspace_note("ws-1", {"title": "N1", "content": "body", "client_id": "user-1"})
        notes = db.list_workspace_notes("ws-1")
        assert len(notes) == 1
        assert notes[0]["title"] == "N1"

    def test_soft_delete_note_hides_from_list(self, db):
        note = db.add_workspace_note("ws-1", {"title": "N1", "content": "", "client_id": "user-1"})
        db.delete_workspace_note("ws-1", note["id"])
        assert db.list_workspace_notes("ws-1") == []
```

**Step 2: Run test to verify it fails**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py -v
```

Expected: FAIL if Stage 6 is not yet done; PASS if Stage 6 DB layer is complete (in which case this validates integration).

**Step 3: Write minimal implementation**

Extend `workspace_schemas.py` with Pydantic models for each sub-resource:

```python
class WorkspaceSourceCreateRequest(BaseModel):
    id: str
    media_id: int
    title: str
    source_type: str
    status: str = "ready"
    # ... optional fields from schema

class WorkspaceSourceUpdateRequest(BaseModel):
    title: str | None = None
    selected: bool | None = None
    position: int | None = None
    version: int  # required for optimistic locking

class WorkspaceSourceResponse(BaseModel):
    id: str
    workspace_id: str
    media_id: int
    title: str
    source_type: str
    position: int
    selected: bool
    version: int
    # ... etc

class WorkspaceSourceSelectionRequest(BaseModel):
    selected_ids: list[str]

class WorkspaceSourceReorderRequest(BaseModel):
    ordered_ids: list[str]

# Similar for artifacts and notes...
```

Extend `workspaces.py` with sub-resource routes nested under `/{workspace_id}/`:

```python
@router.post("/{workspace_id}/sources", response_model=WorkspaceSourceResponse, status_code=201)
async def add_source(workspace_id: str, body: WorkspaceSourceCreateRequest, ...): ...

@router.get("/{workspace_id}/sources", response_model=list[WorkspaceSourceResponse])
async def list_sources(workspace_id: str, ...): ...

@router.put("/{workspace_id}/sources/{source_id}", response_model=WorkspaceSourceResponse)
async def update_source(workspace_id: str, source_id: str, body: WorkspaceSourceUpdateRequest, ...): ...

@router.delete("/{workspace_id}/sources/{source_id}", status_code=204)
async def delete_source(workspace_id: str, source_id: str, ...): ...

@router.put("/{workspace_id}/sources/selection", status_code=200)
async def update_source_selection(workspace_id: str, body: WorkspaceSourceSelectionRequest, ...): ...

@router.put("/{workspace_id}/sources/reorder", status_code=200)
async def reorder_sources(workspace_id: str, body: WorkspaceSourceReorderRequest, ...): ...

# Similar for /{workspace_id}/artifacts and /{workspace_id}/notes
```

Important: all mutating endpoints catch `ConflictError` and return `HTTPException(status_code=409)` with the current server state in the response body.

Important: validate workspace ownership before any sub-resource operation. Return 404 if workspace not found or belongs to different user.

**Step 4: Run test to verify it passes**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/workspace_schemas.py tldw_Server_API/app/api/v1/endpoints/workspaces.py tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py
git commit -m "feat: add workspace sub-resource CRUD endpoints (sources, artifacts, notes)"
```

---

### Stage 8: Frontend Store Refactor To API-First
**Goal:** Refactor the Zustand workspace store from localStorage-source-of-truth to an API-first cache that hydrates from server on workspace switch and performs mutations server-side first.
**Success Criteria:** Workspace switch triggers server hydration. Mutations go API-first with optimistic local update and rollback on error/409. Version tracking prevents silent overwrites. localStorage reduced to UI preferences.
**Tests:** `apps/packages/ui/src/store/__tests__/workspace-api-first.test.ts`
**Status:** Not Started

#### Task 8: Refactor workspace store to API-first mutations

**Files:**
- Modify: `apps/packages/ui/src/store/workspace.ts`
- Modify: `apps/packages/ui/src/store/workspace-sync-contract.ts`
- Create: `apps/packages/ui/src/store/__tests__/workspace-api-first.test.ts`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts` (add workspace sub-resource methods)

**Step 1: Write the failing test**

Create `apps/packages/ui/src/store/__tests__/workspace-api-first.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest"

describe("workspace store API-first mutations", () => {
  it("hydrates workspace state from server on workspace switch", async () => {
    const mockFetch = vi.fn().mockResolvedValue({
      id: "ws-1",
      name: "Server WS",
      sources: [{ id: "src-1", title: "Video", version: 1 }],
      artifacts: [],
      notes: [],
      version: 3,
    })
    const state = await hydrateWorkspaceFromServer("ws-1", { fetch: mockFetch })
    expect(state.name).toBe("Server WS")
    expect(state.sources).toHaveLength(1)
    expect(mockFetch).toHaveBeenCalledWith("ws-1")
  })

  it("performs optimistic update with rollback on 409", async () => {
    const mockUpdate = vi.fn().mockRejectedValue({ status: 409, body: { version: 5, name: "Server Name" } })
    const result = await optimisticWorkspaceUpdate(
      { id: "ws-1", name: "Local Name", version: 3 },
      { name: "New Name" },
      { update: mockUpdate }
    )
    // Should rollback to server state
    expect(result.name).toBe("Server Name")
    expect(result.version).toBe(5)
  })

  it("updates local store on successful server mutation", async () => {
    const mockUpdate = vi.fn().mockResolvedValue({ id: "ws-1", name: "New", version: 4 })
    const result = await optimisticWorkspaceUpdate(
      { id: "ws-1", name: "Old", version: 3 },
      { name: "New" },
      { update: mockUpdate }
    )
    expect(result.name).toBe("New")
    expect(result.version).toBe(4)
  })
})
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps && bunx vitest run packages/ui/src/store/__tests__/workspace-api-first.test.ts
```

Expected: FAIL because `hydrateWorkspaceFromServer` and `optimisticWorkspaceUpdate` do not exist.

**Step 3: Write minimal implementation**

In `workspace-sync-contract.ts` (or a new `workspace-api.ts` module):

```ts
export async function hydrateWorkspaceFromServer(
  workspaceId: string,
  deps: { fetch: (id: string) => Promise<ServerWorkspaceState> }
): Promise<LocalWorkspaceState> {
  const server = await deps.fetch(workspaceId)
  return {
    id: server.id,
    name: server.name,
    sources: server.sources ?? [],
    artifacts: server.artifacts ?? [],
    notes: server.notes ?? [],
    version: server.version,
  }
}

export async function optimisticWorkspaceUpdate(
  current: { id: string; name: string; version: number },
  updates: Record<string, unknown>,
  deps: { update: (id: string, body: any) => Promise<any> }
): Promise<{ name: string; version: number }> {
  try {
    const result = await deps.update(current.id, { ...updates, version: current.version })
    return result
  } catch (err: any) {
    if (err.status === 409 && err.body) {
      // Rollback to server state
      return err.body
    }
    throw err
  }
}
```

Refactor `workspace.ts` store actions:
- `switchWorkspace(id)`: call `hydrateWorkspaceFromServer`, replace store state
- `addSource(...)`, `removeSource(...)`, etc.: API-first, then update store on success
- `updateWorkspace(...)`: use `optimisticWorkspaceUpdate`
- Remove direct localStorage writes for workspace data; keep only for UI preferences (pane widths, theme, etc.)

Add workspace sub-resource methods to `TldwApiClient.ts`:

```ts
// Sources
getWorkspaceSources(workspaceId: string): Promise<WorkspaceSource[]>
addWorkspaceSource(workspaceId: string, data: CreateSourceReq): Promise<WorkspaceSource>
updateWorkspaceSource(workspaceId: string, sourceId: string, data: UpdateSourceReq): Promise<WorkspaceSource>
deleteWorkspaceSource(workspaceId: string, sourceId: string): Promise<void>
updateWorkspaceSourceSelection(workspaceId: string, selectedIds: string[]): Promise<void>
reorderWorkspaceSources(workspaceId: string, orderedIds: string[]): Promise<void>

// Artifacts
getWorkspaceArtifacts(workspaceId: string): Promise<WorkspaceArtifact[]>
addWorkspaceArtifact(workspaceId: string, data: CreateArtifactReq): Promise<WorkspaceArtifact>
updateWorkspaceArtifact(workspaceId: string, artifactId: string, data: UpdateArtifactReq): Promise<WorkspaceArtifact>
deleteWorkspaceArtifact(workspaceId: string, artifactId: string): Promise<void>

// Notes
getWorkspaceNotes(workspaceId: string): Promise<WorkspaceNote[]>
addWorkspaceNote(workspaceId: string, data: CreateNoteReq): Promise<WorkspaceNote>
updateWorkspaceNote(workspaceId: string, noteId: number, data: UpdateNoteReq): Promise<WorkspaceNote>
deleteWorkspaceNote(workspaceId: string, noteId: number): Promise<void>
```

**Step 4: Run test to verify it passes**

Run:

```bash
cd apps && bunx vitest run packages/ui/src/store/__tests__/workspace-api-first.test.ts
```

Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/store/workspace.ts apps/packages/ui/src/store/workspace-sync-contract.ts apps/packages/ui/src/store/__tests__/workspace-api-first.test.ts apps/packages/ui/src/services/tldw/TldwApiClient.ts
git commit -m "feat: refactor workspace store to API-first with server hydration"
```

---

### Stage 9: One-Time Client Migration And Rollout
**Goal:** Ship a one-time migration that moves existing browser-local workspaces to the server, removes localStorage as source of truth, and provides rollout UX (toast for stale pointers, migration progress).
**Success Criteria:** Existing local workspaces are synced to server on first load. localStorage is reduced to UI preferences. Migration flag prevents re-runs. All Phase 2 tests pass.
**Tests:** `apps/packages/ui/src/store/__tests__/workspace-migration.test.ts`, `tldw_Server_API/tests/e2e/test_workspace_full_sync.py`
**Status:** Not Started

#### Task 9: One-time client migration and final verification

**Files:**
- Create: `apps/packages/ui/src/store/workspace-migration.ts`
- Create: `apps/packages/ui/src/store/__tests__/workspace-migration.test.ts`
- Create: `tldw_Server_API/tests/e2e/test_workspace_full_sync.py`

**Step 1: Write the failing test**

Create `apps/packages/ui/src/store/__tests__/workspace-migration.test.ts`:

```ts
import { describe, it, expect, vi, beforeEach } from "vitest"

describe("one-time workspace migration", () => {
  beforeEach(() => {
    localStorage.clear()
  })

  it("migrates local workspaces to server", async () => {
    const upsertMock = vi.fn().mockResolvedValue({ id: "ws-1", version: 1 })
    const addSourceMock = vi.fn().mockResolvedValue({ id: "src-1", version: 1 })
    const addArtifactMock = vi.fn().mockResolvedValue({ id: "art-1", version: 1 })

    const localWorkspaces = [
      {
        id: "ws-1",
        name: "Local WS",
        sources: [{ id: "src-1", mediaId: 1, title: "V", sourceType: "video" }],
        artifacts: [{ id: "art-1", type: "summary", title: "S" }],
        notes: [],
      },
    ]

    await migrateLocalWorkspacesToServer(localWorkspaces, {
      upsertWorkspace: upsertMock,
      addSource: addSourceMock,
      addArtifact: addArtifactMock,
      addNote: vi.fn(),
    })

    expect(upsertMock).toHaveBeenCalledWith("ws-1", expect.objectContaining({ name: "Local WS" }))
    expect(addSourceMock).toHaveBeenCalledOnce()
    expect(addArtifactMock).toHaveBeenCalledOnce()
  })

  it("sets migration flag after completion", async () => {
    await migrateLocalWorkspacesToServer([], {
      upsertWorkspace: vi.fn(),
      addSource: vi.fn(),
      addArtifact: vi.fn(),
      addNote: vi.fn(),
    })
    expect(localStorage.getItem("workspace_migrated")).toBe("true")
  })

  it("skips migration if flag already set", async () => {
    localStorage.setItem("workspace_migrated", "true")
    const upsertMock = vi.fn()
    await migrateLocalWorkspacesToServer(
      [{ id: "ws-1", name: "X", sources: [], artifacts: [], notes: [] }],
      { upsertWorkspace: upsertMock, addSource: vi.fn(), addArtifact: vi.fn(), addNote: vi.fn() }
    )
    expect(upsertMock).not.toHaveBeenCalled()
  })
})
```

Create `tldw_Server_API/tests/e2e/test_workspace_full_sync.py`:

```python
"""End-to-end tests for full workspace sync (Phase 2)."""
import pytest
from tldw_Server_API.app.core.DB_Management.ChaChaNotes_DB import CharactersRAGDB


@pytest.fixture
def db(tmp_path):
    d = CharactersRAGDB(db_path=str(tmp_path / "chacha.db"), client_id="user-1")
    return d


class TestFullWorkspaceSync:
    def test_workspace_with_all_sub_resources(self, db):
        db.upsert_workspace({"id": "ws-1", "name": "Full WS", "client_id": "user-1"})
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "Video",
            "source_type": "video", "client_id": "user-1",
        })
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "Summary",
            "client_id": "user-1",
        })
        db.add_workspace_note("ws-1", {"title": "Note", "content": "body", "client_id": "user-1"})

        # Verify all exist
        assert len(db.list_workspace_sources("ws-1")) == 1
        assert len(db.list_workspace_artifacts("ws-1")) == 1
        assert len(db.list_workspace_notes("ws-1")) == 1

        # Verify workspace settings
        ws = db.update_workspace("ws-1", {
            "banner_title": "Project X",
            "audio_provider": "openai",
        }, client_id="user-1", expected_version=1)
        assert ws["banner_title"] == "Project X"
        assert ws["audio_provider"] == "openai"

    def test_hard_delete_cascades_sub_resources(self, db):
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "V",
            "source_type": "video", "client_id": "user-1",
        })
        db.add_workspace_artifact("ws-1", {
            "id": "art-1", "artifact_type": "summary", "title": "S",
            "client_id": "user-1",
        })
        db.add_workspace_note("ws-1", {"title": "N", "content": "", "client_id": "user-1"})

        db.hard_delete_workspace("ws-1")

        assert db.list_workspace_sources("ws-1") == []
        assert db.list_workspace_artifacts("ws-1") == []
        assert db.list_workspace_notes("ws-1") == []

    def test_optimistic_locking_across_sub_resources(self, db):
        db.upsert_workspace({"id": "ws-1", "name": "WS", "client_id": "user-1"})
        db.add_workspace_source("ws-1", {
            "id": "src-1", "media_id": 1, "title": "V",
            "source_type": "video", "client_id": "user-1",
        })

        # First update succeeds
        db.update_workspace_source("ws-1", "src-1", {"title": "V2"}, expected_version=1)
        # Stale version fails
        with pytest.raises(Exception):
            db.update_workspace_source("ws-1", "src-1", {"title": "V3"}, expected_version=1)
```

**Step 2: Run test to verify it fails**

Run:

```bash
cd apps && bunx vitest run packages/ui/src/store/__tests__/workspace-migration.test.ts
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/e2e/test_workspace_full_sync.py -v
```

Expected: FAIL because `migrateLocalWorkspacesToServer` does not exist, and Phase 2 DB methods may not exist yet.

**Step 3: Write minimal implementation**

Create `apps/packages/ui/src/store/workspace-migration.ts`:

```ts
import type { ChatScope } from "../types/chat-scope"

interface MigrationDeps {
  upsertWorkspace: (id: string, body: any) => Promise<any>
  addSource: (workspaceId: string, data: any) => Promise<any>
  addArtifact: (workspaceId: string, data: any) => Promise<any>
  addNote: (workspaceId: string, data: any) => Promise<any>
}

interface LocalWorkspace {
  id: string
  name: string
  sources: any[]
  artifacts: any[]
  notes: any[]
}

const MIGRATION_FLAG = "workspace_migrated"

export async function migrateLocalWorkspacesToServer(
  localWorkspaces: LocalWorkspace[],
  deps: MigrationDeps
): Promise<void> {
  if (localStorage.getItem(MIGRATION_FLAG) === "true") return

  for (const ws of localWorkspaces) {
    await deps.upsertWorkspace(ws.id, { name: ws.name })
    for (const src of ws.sources) {
      await deps.addSource(ws.id, src)
    }
    for (const art of ws.artifacts) {
      await deps.addArtifact(ws.id, art)
    }
    for (const note of ws.notes) {
      await deps.addNote(ws.id, note)
    }
  }

  localStorage.setItem(MIGRATION_FLAG, "true")
}
```

Integrate the migration into the app startup flow:
- On first load, detect existing local workspaces from Zustand persisted state
- Call `migrateLocalWorkspacesToServer` with API client methods
- After success, clear local workspace data (keep UI preferences)
- Show a brief toast: "Workspaces synced to server"

**Step 4: Run full verification**

Run all tests:

```bash
cd apps && bunx vitest run packages/ui/src/types/__tests__/chat-scope.test.ts packages/ui/src/store/__tests__/workspace-scope.test.ts packages/ui/src/store/__tests__/workspace-api-first.test.ts packages/ui/src/store/__tests__/workspace-migration.test.ts packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts

source .venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py tldw_Server_API/tests/Workspaces/test_workspaces_api.py tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py tldw_Server_API/tests/e2e/test_workspace_chat_scope.py tldw_Server_API/tests/e2e/test_workspace_full_sync.py -v
```

Expected: All PASS.

**Step 5: Run security verification**

Run:

```bash
source .venv/bin/activate
python -m bandit -r tldw_Server_API/app/api/v1/endpoints/workspaces.py tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py -f json -o /tmp/bandit_workspace_full_sync.json
```

Expected: No new Bandit findings.

**Step 6: Commit**

```bash
git add apps/packages/ui/src/store/workspace-migration.ts apps/packages/ui/src/store/__tests__/workspace-migration.test.ts tldw_Server_API/tests/e2e/test_workspace_full_sync.py
git commit -m "feat: add one-time client workspace migration (Phase 2 complete)"
```

---

## Rollout Notes

### Ordering Constraints
- Stage 1 (DB primitives) must land before any other stage.
- Stage 2-3 (API scoping) must land before Stage 4-5 (frontend scope).
- Stage 6 (Phase 2 DB) must land before Stage 7 (Phase 2 endpoints).
- Stage 8 (store refactor) must land before Stage 9 (migration).
- Phase 1 (Stages 1-5) can ship independently before Phase 2.

### Migration Safety
- Existing conversations get `scope_type='global'`, `workspace_id=NULL` via column defaults.
- No inference of workspace membership from browser-local data.
- Old browser-local workspace sessions that referenced server chats may not resolve after scope enforcement; show a one-time toast explaining this.
- Strip `serverChatId` on import; never silently reconnect.

### Backward Compatibility
- Omitted scope defaults to `global` -- old clients see the same behavior.
- Phase 2 workspace columns have defaults; the Phase 1 workspace row remains valid.
- Sub-resource tables use FK CASCADE for hard purge only; soft delete is at workspace level.

### Key Files Summary

**Backend:**
- `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py` -- schema v30 (Phase 1), v31 (Phase 2)
- `tldw_Server_API/app/api/v1/schemas/workspace_schemas.py` -- Pydantic models
- `tldw_Server_API/app/api/v1/endpoints/workspaces.py` -- workspace + sub-resource CRUD
- `tldw_Server_API/app/api/v1/schemas/chat_conversation_schemas.py` -- ConversationScopeParams
- `tldw_Server_API/app/api/v1/endpoints/chat.py` -- scope enforcement
- `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py` -- scope enforcement
- `tldw_Server_API/app/main.py` -- router registration

**Frontend:**
- `apps/packages/ui/src/types/chat-scope.ts` -- ChatScope type
- `apps/packages/ui/src/store/workspace.ts` -- API-first store
- `apps/packages/ui/src/store/workspace-bundle.ts` -- import sanitization
- `apps/packages/ui/src/store/workspace-sync-contract.ts` -- hydration/locking helpers
- `apps/packages/ui/src/store/workspace-migration.ts` -- one-time migration
- `apps/packages/ui/src/services/tldw/TldwApiClient.ts` -- workspace API methods
- `apps/packages/ui/src/hooks/useServerChatHistory.ts` -- scope-aware history
- `apps/packages/ui/src/hooks/chat/useSelectServerChat.ts` -- scope validation
- `apps/packages/ui/src/hooks/chat/useChatActions.ts` -- scoped chat actions

**Tests:**
- `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_scope_db.py`
- `tldw_Server_API/tests/ChaChaNotesDB/test_workspace_sub_resources_db.py`
- `tldw_Server_API/tests/Chat/unit/test_chat_conversations_scope.py`
- `tldw_Server_API/tests/Workspaces/test_workspaces_api.py`
- `tldw_Server_API/tests/Workspaces/test_workspace_sub_resources_api.py`
- `tldw_Server_API/tests/e2e/test_workspace_chat_scope.py`
- `tldw_Server_API/tests/e2e/test_workspace_full_sync.py`
- `apps/packages/ui/src/types/__tests__/chat-scope.test.ts`
- `apps/packages/ui/src/store/__tests__/workspace-scope.test.ts`
- `apps/packages/ui/src/store/__tests__/workspace-api-first.test.ts`
- `apps/packages/ui/src/store/__tests__/workspace-migration.test.ts`
