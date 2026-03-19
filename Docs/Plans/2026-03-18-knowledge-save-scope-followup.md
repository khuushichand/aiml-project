# Knowledge Save Scope Followup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Enforce exact chat scope on the knowledge-save mutation and propagate workspace scope from the message UI.

**Architecture:** Extend the knowledge-save request contract with the same `scope_type` and `workspace_id` fields used by scoped chat APIs, then validate ownership through the shared scope helpers. Thread a `ChatScope` prop into `PlaygroundMessage` so workspace saves send the correct scope and global callers keep the default global behavior.

**Tech Stack:** FastAPI, Pydantic, pytest, React, TypeScript, Vitest

---

### Task 1: Backend Scope Regression Test

**Files:**
- Modify: `tldw_Server_API/tests/Chat/unit/test_chat_knowledge_save.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`

**Step 1: Write the failing test**

Add a unit test that creates one workspace-scoped conversation and message, then posts to `/api/v1/chat/knowledge/save` without scope and with the wrong workspace scope. Assert both calls return `404`, and the correct workspace scope returns `201`.

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_knowledge_save.py`
Expected: FAIL because the endpoint currently ignores scope.

**Step 3: Write minimal implementation**

Add optional `scope_type` and `workspace_id` fields to the request schema, resolve them with `_resolve_conversation_scope`, and validate both the conversation and optional message with `_verify_*_ownership`.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_knowledge_save.py`
Expected: PASS.

### Task 2: Frontend Scope Propagation Regression Test

**Files:**
- Modify: `apps/packages/ui/src/components/Common/Playground/__tests__/Message.routing-fallback.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Modify: `apps/packages/ui/src/components/Common/Playground/message-types.ts`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Write the failing test**

Add a message integration test that renders `PlaygroundMessage` with a workspace `ChatScope`, triggers the save-to-notes action, and asserts `tldwClient.saveChatKnowledge` receives the same scope.

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/components/Common/Playground/__tests__/Message.routing-fallback.integration.test.tsx`
Expected: FAIL because the save call currently omits scope.

**Step 3: Write minimal implementation**

Extend `saveChatKnowledge` to accept `options?: { scope?: ChatScope }`, include the scope params in the request body, add a `scope?: ChatScope` message prop, and pass the workspace scope from `WorkspacePlayground`.

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/components/Common/Playground/__tests__/Message.routing-fallback.integration.test.tsx`
Expected: PASS.

### Task 3: Verification

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_knowledge_schemas.py`
- Modify: `tldw_Server_API/tests/Chat/unit/test_chat_knowledge_save.py`
- Modify: `apps/packages/ui/src/components/Common/Playground/Message.tsx`
- Modify: `apps/packages/ui/src/components/Common/Playground/message-types.ts`
- Modify: `apps/packages/ui/src/components/Common/Playground/__tests__/Message.routing-fallback.integration.test.tsx`
- Modify: `apps/packages/ui/src/components/Option/WorkspacePlayground/ChatPane/index.tsx`
- Modify: `apps/packages/ui/src/services/tldw/TldwApiClient.ts`

**Step 1: Run focused backend and frontend tests**

Run:
- `source .venv/bin/activate && python -m pytest -q tldw_Server_API/tests/Chat/unit/test_chat_knowledge_save.py`
- `bunx vitest run apps/packages/ui/src/components/Common/Playground/__tests__/Message.routing-fallback.integration.test.tsx`

Expected: PASS.

**Step 2: Run security validation on touched backend code**

Run: `source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/app/api/v1/schemas/chat_knowledge_schemas.py -f json -o /tmp/bandit_knowledge_save_scope.json`
Expected: no new findings in touched code.
