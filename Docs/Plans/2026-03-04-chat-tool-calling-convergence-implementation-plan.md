# Chat Tool-Calling Convergence Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Converge WebUI and extension chat tool-calling onto one server-driven chat loop with per-call risky-tool approval, while preserving existing streaming compatibility and preventing double execution.

**Architecture:** Introduce a server-side chat loop protocol and event persistence layer, route tool-enabled chat requests through the loop engine, and dual-emit legacy SSE semantics during migration. Add a shared `apps/packages/ui` chat-loop client reducer so `/chat`, sidepanel chat, and options chat consume one lifecycle model while preserving existing mode-specific behavior.

**Tech Stack:** FastAPI, Pydantic, SSE streaming utilities, existing Chat/MCP services, React + TypeScript (`apps/packages/ui`), Zustand store slices, pytest, Playwright.

---

### Task 1: Define loop protocol types and API schemas

**Files:**
- Create: `tldw_Server_API/app/api/v1/schemas/chat_loop_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/__init__.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_schemas.py`

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_schemas.py
from tldw_Server_API.app.api.v1.schemas.chat_loop_schemas import ChatLoopEvent


def test_chat_loop_event_requires_monotonic_seq_fields_present():
    event = ChatLoopEvent(
        run_id="run_1",
        seq=1,
        event="run_started",
        data={"conversation_id": "conv_1"}
    )
    assert event.run_id == "run_1"
    assert event.seq == 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_schemas.py -v`
Expected: FAIL with `ModuleNotFoundError` for `chat_loop_schemas`.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/api/v1/schemas/chat_loop_schemas.py
from pydantic import BaseModel, Field
from typing import Any


class ChatLoopEvent(BaseModel):
    run_id: str
    seq: int = Field(..., ge=1)
    event: str
    data: dict[str, Any]
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_schemas.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/chat_loop_schemas.py tldw_Server_API/app/api/v1/schemas/__init__.py tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_schemas.py
git commit -m "feat(chat): add chat loop protocol schemas"
```

### Task 2: Add chat loop event store with replay cursor support

**Files:**
- Create: `tldw_Server_API/app/core/Chat/chat_loop_store.py`
- Modify: `tldw_Server_API/app/core/Chat/__init__.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.Chat.chat_loop_store import InMemoryChatLoopStore


def test_store_replays_events_after_seq_cursor():
    store = InMemoryChatLoopStore()
    store.append("run_1", "run_started", {"ok": True})
    store.append("run_1", "llm_chunk", {"text": "Hi"})

    tail = store.list_after("run_1", 1)
    assert len(tail) == 1
    assert tail[0].event == "llm_chunk"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store.py -v`
Expected: FAIL because `chat_loop_store` does not exist.

**Step 3: Write minimal implementation**

```python
# Pseudocode target behavior
# append(run_id, event, data) increments seq and stores ChatLoopEvent
# list_after(run_id, seq) returns items with event.seq > seq
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_loop_store.py tldw_Server_API/app/core/Chat/__init__.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store.py
git commit -m "feat(chat-loop): add event store and replay cursor"
```

### Task 3: Implement loop executor with single-execution gate for tools

**Files:**
- Create: `tldw_Server_API/app/core/Chat/chat_loop_engine.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `tldw_Server_API/app/core/Chat/tool_auto_exec.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_engine.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_service_tool_autoexec.py`

**Step 1: Write the failing test**

```python

def test_loop_mode_disables_legacy_autoexec_path(monkeypatch):
    calls = {"legacy": 0, "loop": 0}

    def _legacy(*_args, **_kwargs):
        calls["legacy"] += 1

    def _loop(*_args, **_kwargs):
        calls["loop"] += 1

    # monkeypatch chat_service legacy and loop handlers
    # issue one tool-enabled request with loop mode enabled
    assert calls["legacy"] == 0
    assert calls["loop"] == 1
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_engine.py -v`
Expected: FAIL due missing loop engine and behavior.

**Step 3: Write minimal implementation**

```python
# Add request-scoped flag:
# if loop_mode: skip legacy should_auto_execute_tools branch in chat_service
# execute tool calls only from chat_loop_engine
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_engine.py tldw_Server_API/tests/Chat/unit/test_chat_service_tool_autoexec.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_loop_engine.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/core/Chat/tool_auto_exec.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_engine.py tldw_Server_API/tests/Chat/unit/test_chat_service_tool_autoexec.py
git commit -m "feat(chat-loop): add loop executor and disable duplicate autoexec"
```

### Task 4: Add per-call approval tokens bound to run/seq/tool/args

**Files:**
- Create: `tldw_Server_API/app/core/Chat/chat_loop_approval.py`
- Modify: `tldw_Server_API/app/core/Tools/tool_executor.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_approval.py`

**Step 1: Write the failing test**

```python

def test_approval_token_rejects_mismatched_args_hash():
    token = mint_approval_token(
        run_id="run_1",
        seq=7,
        tool_call_id="tc_1",
        args_hash="hash_a",
    )

    ok, error = verify_approval_token(
        token=token,
        run_id="run_1",
        seq=7,
        tool_call_id="tc_1",
        args_hash="hash_b",
    )

    assert ok is False
    assert "args_hash" in error
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_approval.py -v`
Expected: FAIL due missing approval module.

**Step 3: Write minimal implementation**

```python
# approval token payload includes:
# run_id, seq, tool_call_id, args_hash, exp, nonce
# verify enforces one-time use + exact field match
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_approval.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_loop_approval.py tldw_Server_API/app/core/Tools/tool_executor.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_approval.py
git commit -m "feat(chat-loop): add bound one-time approval tokens"
```

### Task 5: Add loop endpoints and SSE replay API

**Files:**
- Create: `tldw_Server_API/app/api/v1/endpoints/chat_loop.py`
- Modify: `tldw_Server_API/app/main.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/chat.py`
- Test: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_endpoints.py`

**Step 1: Write the failing test**

```python

def test_chat_loop_start_then_replay_events(client, auth_headers):
    start = client.post("/api/v1/chat/loop/start", json={"messages": [{"role": "user", "content": "hi"}]}, headers=auth_headers)
    assert start.status_code == 200
    run_id = start.json()["run_id"]

    replay = client.get(f"/api/v1/chat/loop/{run_id}/events?after_seq=0", headers=auth_headers)
    assert replay.status_code == 200
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_endpoints.py -v`
Expected: FAIL with 404 endpoint not found.

**Step 3: Write minimal implementation**

```python
# Add start/events/approve/reject/cancel routes
# wire to chat_loop_engine + chat_loop_store
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_endpoints.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/chat_loop.py tldw_Server_API/app/main.py tldw_Server_API/app/api/v1/endpoints/chat.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_endpoints.py
git commit -m "feat(api): add chat loop endpoints and replay stream"
```

### Task 6: Add dual-emission compatibility bridge in streaming path

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/streaming_utils.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_streaming_utils.py`
- Test: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_dual_emit_compat.py`

**Step 1: Write the failing test**

```python

def test_dual_emit_preserves_legacy_and_loop_events(client, auth_headers):
    with client.stream(
        "POST",
        "/api/v1/chat/completions",
        headers={**auth_headers, "X-TLDW-Loop-Compat": "1"},
        json={"model": "test", "messages": [{"role": "user", "content": "hi"}], "stream": True},
    ) as resp:
        lines = [line for line in resp.iter_lines() if line]

    payload = "\n".join(lines)
    assert "event: stream_start" in payload
    assert "event: stream_end" in payload
    assert "event: tool_results" in payload or "tool_results" in payload
    assert "event: run_started" in payload or "event: tool_proposed" in payload
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_dual_emit_compat.py -v`
Expected: FAIL due missing dual emit.

**Step 3: Write minimal implementation**

```python
# Extend save_callback extra events with loop event frames
# keep existing [DONE] and stream_* emission unchanged
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_streaming_utils.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_dual_emit_compat.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/streaming_utils.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/tests/Chat/unit/test_streaming_utils.py tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_dual_emit_compat.py
git commit -m "feat(chat): dual-emit loop and legacy SSE events"
```

### Task 7: Implement shared client loop SDK and reducer

**Files:**
- Create: `apps/packages/ui/src/services/chat-loop/types.ts`
- Create: `apps/packages/ui/src/services/chat-loop/client.ts`
- Create: `apps/packages/ui/src/services/chat-loop/reducer.ts`
- Create: `apps/packages/ui/src/services/chat-loop/hooks.ts`
- Test: `apps/packages/ui/src/services/chat-loop/__tests__/reducer.test.ts`

**Step 1: Write the failing test**

```ts
import { reduceLoopEvent } from "@/services/chat-loop/reducer"

test("approval_required adds pending approval", () => {
  const state = { pendingApprovals: [] } as any
  const next = reduceLoopEvent(state, {
    run_id: "run_1",
    seq: 3,
    event: "approval_required",
    data: { approval_id: "a1", tool_call_id: "tc1" }
  } as any)
  expect(next.pendingApprovals).toHaveLength(1)
})
```

**Step 2: Run test to verify it fails**

Run: `bunx vitest run apps/packages/ui/src/services/chat-loop/__tests__/reducer.test.ts`
Expected: FAIL because reducer file does not exist.

**Step 3: Write minimal implementation**

```ts
// reducer handles run_started, llm_chunk, tool_proposed,
// approval_required/resolved, tool_started/finished/failed, run_complete/error
```

**Step 4: Run test to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/chat-loop/__tests__/reducer.test.ts`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/chat-loop/types.ts apps/packages/ui/src/services/chat-loop/client.ts apps/packages/ui/src/services/chat-loop/reducer.ts apps/packages/ui/src/services/chat-loop/hooks.ts apps/packages/ui/src/services/chat-loop/__tests__/reducer.test.ts
git commit -m "feat(ui): add shared chat loop sdk and reducer"
```

### Task 8: Migrate `/chat` playground and extension sidepanel/options chat to loop SDK

**Files:**
- Modify: `apps/packages/ui/src/hooks/useMessageOption.tsx`
- Modify: `apps/packages/ui/src/hooks/useMessage.tsx`
- Modify: `apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/form.tsx`
- Modify: `apps/packages/ui/src/components/Sidepanel/Chat/ControlRow.tsx`
- Test: `apps/tldw-frontend/e2e/workflows/chat-tool-approval-parity.spec.ts`
- Test: `apps/extension/tests/e2e/chat-tool-approval-parity.spec.ts`

**Step 1: Write the failing test**

```ts
import { test, expect } from "@playwright/test"

test("webui and extension show identical risky-tool approval states", async ({ page }) => {
  // Arrange mocked loop events with approval_required + tool_started + tool_finished
  // Assert both surfaces render Pending approval, Running, Done in same order
  await expect(page.getByText(/pending approval/i)).toBeVisible()
})
```

**Step 2: Run test to verify it fails**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/chat-tool-approval-parity.spec.ts --reporter=line`
Expected: FAIL before migration due missing parity behavior.

**Step 3: Write minimal implementation**

```ts
// wire useMessage/useMessageOption submission through chat-loop client
// keep existing mode preflight logic; only replace tool lifecycle state source
// map loop pending approvals into existing ToolCallBlock/toolbar UI
```

**Step 4: Run test to verify it passes**

Run: `bunx playwright test apps/tldw-frontend/e2e/workflows/chat-tool-approval-parity.spec.ts apps/extension/tests/e2e/chat-tool-approval-parity.spec.ts --reporter=line`
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/hooks/useMessageOption.tsx apps/packages/ui/src/hooks/useMessage.tsx apps/packages/ui/src/components/Option/Playground/PlaygroundForm.tsx apps/packages/ui/src/components/Sidepanel/Chat/form.tsx apps/packages/ui/src/components/Sidepanel/Chat/ControlRow.tsx apps/tldw-frontend/e2e/workflows/chat-tool-approval-parity.spec.ts apps/extension/tests/e2e/chat-tool-approval-parity.spec.ts
git commit -m "feat(chat-ui): migrate chat surfaces to shared loop state"
```

### Task 9: Add server normalization for guided default tool choice and policy edge cases

**Files:**
- Modify: `tldw_Server_API/app/core/LLM_Calls/capability_registry.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py`
- Test: `tldw_Server_API/tests/LLM_Calls/test_capability_registry.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_tool_choice_normalization.py`

**Step 1: Write the failing test**

```python

def test_auto_tool_choice_with_empty_toolset_is_normalized_safely():
    payload = {
        "messages": [{"role": "user", "content": "hi"}],
        "model": "test",
        "tool_choice": "auto",
        "tools": [],
    }
    normalized = normalize_tool_payload(payload)
    assert normalized.get("tools") in (None, [])
    assert normalized.get("tool_choice") in (None, "none")
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_tool_choice_normalization.py -v`
Expected: FAIL due missing normalization behavior.

**Step 3: Write minimal implementation**

```python
# If executable_tools == []:
# - drop tools list
# - normalize tool_choice to omitted or "none" as provider contract permits
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_capability_registry.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_tool_choice_normalization.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/capability_registry.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/app/api/v1/schemas/chat_request_schemas.py tldw_Server_API/tests/LLM_Calls/test_capability_registry.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_tool_choice_normalization.py
git commit -m "fix(chat-loop): normalize guided tool choice when toolset unavailable"
```

### Task 10: Add observability, compaction, and release gates

**Files:**
- Modify: `tldw_Server_API/app/core/Chat/chat_loop_store.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_metrics.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_service.py`
- Test: `tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store_compaction.py`
- Test: `tldw_Server_API/tests/Metrics/test_chat_metrics_reset_safety.py`

**Step 1: Write the failing test**

```python

def test_loop_store_compaction_retains_checkpoint_and_tail():
    store = InMemoryChatLoopStore()
    for i in range(1000):
        store.append("run_1", "llm_chunk", {"i": i})

    store.compact("run_1")
    rebuilt = store.replay("run_1")
    assert rebuilt is not None
    assert rebuilt.last_seq >= 1000
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store_compaction.py -v`
Expected: FAIL due missing compaction/checkpoint support.

**Step 3: Write minimal implementation**

```python
# Keep semantic milestones + checkpoint snapshots + bounded tail
# emit metrics for compaction and replay success
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store_compaction.py tldw_Server_API/tests/Metrics/test_chat_metrics_reset_safety.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/chat_loop_store.py tldw_Server_API/app/core/Chat/chat_metrics.py tldw_Server_API/app/core/Chat/chat_service.py tldw_Server_API/tests/Chat_NEW/unit/test_chat_loop_store_compaction.py tldw_Server_API/tests/Metrics/test_chat_metrics_reset_safety.py
git commit -m "feat(chat-loop): add event compaction, metrics, and release safeguards"
```

### Task 11: Security validation and completion checks

**Files:**
- Modify: `Docs/Plans/2026-03-04-chat-tool-calling-convergence-implementation-plan.md`
- Test: `tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_endpoints.py`
- Test: `apps/tldw-frontend/e2e/workflows/chat-tool-approval-parity.spec.ts`
- Test: `apps/extension/tests/e2e/chat-tool-approval-parity.spec.ts`

**Step 1: Run focused regression suites**

Run:

```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat_NEW/integration/test_chat_loop_endpoints.py -v
bunx playwright test apps/tldw-frontend/e2e/workflows/chat-tool-approval-parity.spec.ts --reporter=line
bunx playwright test apps/extension/tests/e2e/chat-tool-approval-parity.spec.ts --reporter=line
```

Expected: PASS.

**Step 2: Run Bandit on touched backend scope**

Run:

```bash
source .venv/bin/activate && python -m bandit -r tldw_Server_API/app/core/Chat tldw_Server_API/app/api/v1/endpoints/chat_loop.py -f json -o /tmp/bandit_chat_loop.json
```

Expected: no new high-severity findings in changed code.

**Step 3: Finalize docs and commit**

```bash
git add Docs/Plans/2026-03-04-chat-tool-calling-convergence-implementation-plan.md
git commit -m "docs(plan): add execution and validation gates for chat loop convergence"
```
