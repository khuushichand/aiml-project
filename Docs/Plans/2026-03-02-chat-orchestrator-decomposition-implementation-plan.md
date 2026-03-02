# Chat Orchestrator Decomposition Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Decompose `chat_orchestrator.py` into testable components so chat behavior changes are isolated and less regression-prone.

**Architecture:** Preserve the public orchestration entrypoint, but extract validation, provider/model resolution, and streaming execution into dedicated modules behind a thin facade. Lock current behavior with characterization tests first.

**Tech Stack:** FastAPI chat endpoints, provider adapters, pytest, asyncio.

---

### Task 1: Add Characterization Tests for Existing Orchestrator Behavior

**Files:**
- Create: `tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py`
- Reference: `tldw_Server_API/app/core/Chat/chat_orchestrator.py`

**Step 1: Write the failing tests**

```python
def test_orchestrator_preserves_message_order():
    output = run_orchestrator_stub(messages=[{"role": "user", "content": "A"}])
    assert output.messages[0]["content"] == "A"


def test_orchestrator_emits_stream_chunks_in_order():
    chunks = list(run_stream_stub())
    assert chunks == sorted(chunks, key=lambda c: c["index"])
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py -v`
Expected: FAIL until stubs/fixtures are wired.

**Step 3: Write minimal implementation**

```python
# Add minimal fixture wrappers around existing orchestrator calls.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py
git commit -m "test(chat): add orchestrator behavior contract tests"
```

### Task 2: Extract Request Validation and Provider Resolution

**Files:**
- Create: `tldw_Server_API/app/core/Chat/orchestrator/request_validation.py`
- Create: `tldw_Server_API/app/core/Chat/orchestrator/provider_resolution.py`
- Create: `tldw_Server_API/app/core/Chat/orchestrator/__init__.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_orchestrator.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py`

**Step 1: Write the failing test**

```python
def test_provider_resolution_applies_default_provider_when_missing():
    provider = resolve_provider(model="gpt-4o-mini", provider=None)
    assert provider is not None
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py::test_provider_resolution_applies_default_provider_when_missing -v`
Expected: FAIL with missing module/function.

**Step 3: Write minimal implementation**

```python
# provider_resolution.py

def resolve_provider(model: str, provider: str | None) -> str:
    return provider or "openai"
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/orchestrator/request_validation.py tldw_Server_API/app/core/Chat/orchestrator/provider_resolution.py tldw_Server_API/app/core/Chat/orchestrator/__init__.py tldw_Server_API/app/core/Chat/chat_orchestrator.py tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py
git commit -m "refactor(chat): extract validation and provider resolution from orchestrator"
```

### Task 3: Extract Streaming Execution and Error Mapping

**Files:**
- Create: `tldw_Server_API/app/core/Chat/orchestrator/stream_execution.py`
- Create: `tldw_Server_API/app/core/Chat/orchestrator/error_mapping.py`
- Modify: `tldw_Server_API/app/core/Chat/chat_orchestrator.py`
- Test: `tldw_Server_API/tests/Streaming/test_chat_completions_sse_unified_flag.py`
- Test: `tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py`

**Step 1: Write the failing test**

```python
def test_stream_execution_maps_provider_errors_to_chat_error_shape():
    err = map_stream_error(RuntimeError("provider exploded"))
    assert "message" in err
    assert "code" in err
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py::test_stream_execution_maps_provider_errors_to_chat_error_shape -v`
Expected: FAIL because mapping is still inlined.

**Step 3: Write minimal implementation**

```python
# error_mapping.py

def map_stream_error(exc: Exception) -> dict:
    return {"code": "provider_error", "message": str(exc)}
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py tldw_Server_API/tests/Streaming/test_chat_completions_sse_unified_flag.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/Chat/orchestrator/stream_execution.py tldw_Server_API/app/core/Chat/orchestrator/error_mapping.py tldw_Server_API/app/core/Chat/chat_orchestrator.py tldw_Server_API/tests/Chat/unit/test_chat_orchestrator_contract.py
git commit -m "refactor(chat): extract stream execution and error mapping"
```

### Task 4: Keep Endpoint Contracts Stable

**Files:**
- Modify: `tldw_Server_API/tests/Chat/integration/test_chat_completions_integration.py`
- Modify: `tldw_Server_API/tests/Chat/integration/test_chat_endpoint_streaming_normalization.py`

**Step 1: Write the failing test**

```python
def test_chat_completions_response_shape_unchanged(client):
    payload = {...}
    body = client.post("/api/v1/chat/completions", json=payload).json()
    assert "choices" in body
    assert "model" in body
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/integration/test_chat_completions_integration.py -v`
Expected: FAIL if orchestrator extraction changed response shape.

**Step 3: Write minimal implementation**

```python
# Normalize response in orchestrator facade before endpoint returns.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/Chat/integration/test_chat_completions_integration.py tldw_Server_API/tests/Chat/integration/test_chat_endpoint_streaming_normalization.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/Chat/integration/test_chat_completions_integration.py tldw_Server_API/tests/Chat/integration/test_chat_endpoint_streaming_normalization.py tldw_Server_API/app/core/Chat/chat_orchestrator.py
git commit -m "test(chat): enforce endpoint response parity after orchestrator split"
```
