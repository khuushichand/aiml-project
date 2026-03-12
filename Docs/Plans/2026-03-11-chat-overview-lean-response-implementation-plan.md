# Chat Overview Lean Response Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Make `/api/v1/chats/` overview traffic cheaper by skipping message-count enrichment when callers do not need it, and add the smallest useful set of conversation indexes for long-term stability.

**Architecture:** Keep `/api/v1/chats/` as the existing overview endpoint and add one opt-in lightweight behavior via `include_message_counts=false`. Pair that with a schema migration adding composite indexes for the main conversation list/count orderings. Update only the sidebar overview caller to use the lean mode.

**Tech Stack:** FastAPI, Python 3.11, SQLite/PostgreSQL-compatible schema bootstrap in `CharactersRAGDB`, React Query, TypeScript, pytest, Vitest, Bandit.

---

### Task 1: Add Failing Tests for Lean Chat Overview

**Files:**
- Modify: `tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py`
- Modify: `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`

**Step 1: Write the failing backend test**

Add a test that calls:

```python
response = app.get("/api/v1/chats/", params={"include_message_counts": False})
```

and asserts:

- response is `200`
- returned chat items still contain IDs/titles
- `count_messages_for_conversation` is never called
- `count_messages_for_conversations` is never called
- `message_count` is `None` in the payload

**Step 2: Run it to verify RED**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py -v
```

Expected: FAIL because the endpoint still computes message counts unconditionally.

**Step 3: Write the failing frontend test**

Add a hook test asserting paged overview requests call:

```ts
listChatsWithMeta({
  limit: 25,
  offset: 0,
  ordering: "-updated_at",
  include_message_counts: false
})
```

for standard overview mode.

**Step 4: Run it to verify RED**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
```

Expected: FAIL because the hook does not send the flag yet.

### Task 2: Add Failing Schema Test for New Conversation Indexes

**Files:**
- Create: `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_list_indexes.py`

**Step 1: Write the failing schema test**

Add a SQLite test that initializes `CharactersRAGDB`, inspects:

```sql
PRAGMA index_list('conversations')
```

and asserts the new indexes exist:

- `idx_conversations_client_deleted_last_modified`
- `idx_conversations_client_character_deleted_last_modified`
- `idx_conversations_client_deleted_created_at`

**Step 2: Run it to verify RED**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest tldw_Server_API/tests/ChaChaNotesDB/test_conversation_list_indexes.py -v
```

Expected: FAIL because those indexes do not exist yet.

### Task 3: Implement Backend Lean Overview and Index Migration

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py`
- Modify: `tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py`
- Test: `tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py`
- Test: `tldw_Server_API/tests/ChaChaNotesDB/test_conversation_list_indexes.py`

**Step 1: Implement the endpoint flag**

Add:

```python
include_message_counts: bool = Query(True, description="Include message counts for each returned chat.")
```

to `list_chat_sessions(...)`.

When `include_message_counts` is `False`:

- skip `count_messages_for_conversations(...)`
- skip `count_messages_for_conversation(...)`
- set `conv["message_count"] = None`

Keep default behavior unchanged when the flag is omitted.

**Step 2: Implement the schema migration**

Bump `_CURRENT_SCHEMA_VERSION` and add a migration creating:

```sql
CREATE INDEX IF NOT EXISTS idx_conversations_client_deleted_last_modified
ON conversations(client_id, deleted, last_modified DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_client_character_deleted_last_modified
ON conversations(client_id, character_id, deleted, last_modified DESC);

CREATE INDEX IF NOT EXISTS idx_conversations_client_deleted_created_at
ON conversations(client_id, deleted, created_at DESC);
```

Also add the same `CREATE INDEX IF NOT EXISTS` statements to new-db bootstrap and PostgreSQL-safe index bootstrap paths.

**Step 3: Run backend tests to verify GREEN**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_conversation_list_indexes.py -v
```

Expected: PASS.

### Task 4: Update Frontend Sidebar Overview Calls

**Files:**
- Modify: `apps/packages/ui/src/hooks/useServerChatHistory.ts`
- Test: `apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts`

**Step 1: Implement the minimal frontend change**

For overview list requests to `/api/v1/chats/`, add:

```ts
include_message_counts: false
```

Search requests to `/api/v1/chats/conversations` stay unchanged.

**Step 2: Run the frontend test**

Run:

```bash
bunx vitest run apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
```

Expected: PASS.

### Task 5: Verify the Full Slice

**Files:**
- Verify only

**Step 1: Run the targeted suite**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m pytest \
  tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_conversation_list_indexes.py \
  tldw_Server_API/tests/ChaChaNotesDB/test_conversation_character_scope_filters.py -v

bunx vitest run \
  apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts \
  apps/packages/ui/src/components/Option/Playground/__tests__/Playground.request-budget.test.tsx
```

Expected: PASS.

**Step 2: Run Bandit on touched backend scope**

Run:

```bash
source /Users/macbook-dev/Documents/GitHub/tldw_server2/.venv/bin/activate
python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
  tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
  -f json -o /tmp/bandit_chat_overview_lean.json
```

Expected: no new findings on changed lines.

**Step 3: Commit**

```bash
git add Docs/Plans/2026-03-11-chat-overview-lean-response-design.md \
        Docs/Plans/2026-03-11-chat-overview-lean-response-implementation-plan.md \
        tldw_Server_API/app/api/v1/endpoints/character_chat_sessions.py \
        tldw_Server_API/app/core/DB_Management/ChaChaNotes_DB.py \
        tldw_Server_API/tests/Character_Chat/unit/test_chat_session_character_scope_api.py \
        tldw_Server_API/tests/ChaChaNotesDB/test_conversation_list_indexes.py \
        apps/packages/ui/src/hooks/useServerChatHistory.ts \
        apps/packages/ui/src/hooks/__tests__/useServerChatHistory.test.ts
git commit -m "feat(chat): add lean chat overview mode"
```
