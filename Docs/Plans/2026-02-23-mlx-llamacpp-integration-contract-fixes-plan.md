# MLX + Llama.cpp Contract Fixes Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement high-priority correctness and integration consistency fixes for `mlx-lm` and `llama.cpp`, with regression tests proving each contract.

**Architecture:** Keep current integration architecture (MLX provider registry, llama.cpp managed-server endpoints, llama.cpp provider-mode adapter) but remove contract drift. Prioritize endpoint/auth consistency, explicit handling of currently inert MLX knobs, and provider capability alignment. Ship as small TDD commits.

**Tech Stack:** FastAPI, Pydantic, pytest, TestClient, existing `tldw_Server_API` LLM/provider modules.

---

Using @test-driven-development and @verification-before-completion for all code changes.

### Task 1: Add failing RBAC contract tests for llama.cpp lifecycle endpoints

**Files:**
- Create: `tldw_Server_API/tests/AuthNZ_Unit/test_llamacpp_permissions_claims.py`
- Reference: `tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py`
- Endpoint under test: `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`

**Step 1: Write the failing test**

```python
def test_llamacpp_start_server_403_when_missing_admin_role():
    principal = _make_principal(is_admin=False, roles=["user"])
    app = _build_app_with_overrides(principal=principal)
    with TestClient(app) as client:
        resp = client.post(
            "/api/v1/llamacpp/start_server",
            json={"model_filename": "toy.gguf", "server_args": {}},
        )
    assert resp.status_code == 403
```

Add equivalent tests for:
- `/api/v1/llamacpp/stop_server`
- `/api/v1/llamacpp/status`
- `/api/v1/llamacpp/models`
- success path with admin principal (`200`)

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_llamacpp_permissions_claims.py -v
```

Expected: FAIL because lifecycle endpoints currently do not enforce admin role.

**Step 3: Write minimal implementation**

Add admin role dependency to lifecycle endpoints in:
- `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`

Pattern:
```python
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit, require_roles

@router.post(
    "/llamacpp/start_server",
    dependencies=[Depends(check_rate_limit), Depends(require_roles("admin"))],
)
```

Apply same dependency style to:
- `start_server`
- `stop_server`
- `status`
- `models`
- `metrics`

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/AuthNZ_Unit/test_llamacpp_permissions_claims.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/AuthNZ_Unit/test_llamacpp_permissions_claims.py tldw_Server_API/app/api/v1/endpoints/llamacpp.py
git commit -m "test+auth: enforce admin RBAC for llama.cpp lifecycle endpoints"
```

### Task 2: Add failing lifecycle API contract tests for llama.cpp endpoint behavior

**Files:**
- Create: `tldw_Server_API/tests/LLM_Local/test_llamacpp_lifecycle_api_contract.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`
- Reference: `tldw_Server_API/tests/LLM_Local/test_llamacpp_inference_api.py`

**Step 1: Write the failing test**

Add tests for:
1. `503` with actionable message when manager/handler unavailable.
2. Stable response keys for lifecycle operations.

```python
def test_llamacpp_status_returns_503_with_managed_plane_message(...):
    resp = client.get("/api/v1/llamacpp/status", headers=headers)
    assert resp.status_code == 503
    assert "managed llama.cpp" in resp.json()["detail"].lower()
```

```python
def test_llamacpp_stop_response_contains_status_and_message(...):
    resp = client.post("/api/v1/llamacpp/stop_server", json={}, headers=headers)
    body = resp.json()
    assert resp.status_code == 200
    assert body["status"] == "stopped"
    assert "message" in body
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Local/test_llamacpp_lifecycle_api_contract.py -v
```

Expected: FAIL on message/shape assertions.

**Step 3: Write minimal implementation**

In `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`:
- Update `_llamacpp_unavailable(...)` message to identify managed plane explicitly.
- Normalize lifecycle response envelopes while preserving compatibility:
  - `stop_server`: return `{"status": "stopped", "message": ...}`
  - `start_server`: ensure `status` key always present.
  - `status`: include explicit `backend` identifier when available.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Local/test_llamacpp_lifecycle_api_contract.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/LLM_Local/test_llamacpp_lifecycle_api_contract.py tldw_Server_API/app/api/v1/endpoints/llamacpp.py
git commit -m "test+api: stabilize llama.cpp lifecycle endpoint contracts"
```

### Task 3: Add failing MLX tests for no-op override transparency

**Files:**
- Modify: `tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py`

**Step 1: Write the failing test**

Add a test asserting requested runtime knobs that are not forwarded to `mlx_lm.load(...)` are surfaced explicitly.

```python
def test_load_reports_unapplied_runtime_overrides(monkeypatch):
    _patch_mlx(monkeypatch)
    reg = mp.get_mlx_registry()
    status = reg.load(
        model_path="fake-model",
        overrides={"quantization": "4bit", "max_kv_cache_size": 4096},
    )
    unapplied = status.get("config", {}).get("unapplied_runtime_overrides", {})
    assert unapplied.get("quantization") == "4bit"
    assert unapplied.get("max_kv_cache_size") == 4096
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py::test_load_reports_unapplied_runtime_overrides -v
```

Expected: FAIL because key is not currently exposed.

**Step 3: Write minimal implementation**

In `mlx_provider.py`:
- Track runtime-forwarded keys in `load(...)`.
- Capture non-forwarded runtime-like overrides (`quantization`, `max_kv_cache_size`) under a status-visible field, e.g.:

```python
session.config["unapplied_runtime_overrides"] = {
    "quantization": settings.get("quantization"),
    "max_kv_cache_size": settings.get("max_kv_cache_size"),
}
```

Only include non-`None` values.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py::test_load_reports_unapplied_runtime_overrides -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py
git commit -m "test+mlx: expose unapplied runtime overrides in load status"
```

### Task 4: Add failing MLX embeddings contract test for canonical model id

**Files:**
- Modify: `tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py`

**Step 1: Write the failing test**

```python
def test_embeddings_response_uses_active_session_model(monkeypatch):
    _patch_mlx(monkeypatch)
    reg = mp.get_mlx_registry()
    reg.load(model_path="fake-model", overrides={"max_concurrent": 1})
    emb_adapter = mp.MLXEmbeddingsAdapter()

    resp = emb_adapter.embed({"input": "hello", "model": "wrong-model"})
    assert resp["model"] == "fake-model"
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py::test_embeddings_response_uses_active_session_model -v
```

Expected: FAIL because current response uses request model.

**Step 3: Write minimal implementation**

In `MLXEmbeddingsAdapter.embed(...)` return shape:

```python
return {"data": data, "object": "list", "model": session.model_id}
```

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py::test_embeddings_response_uses_active_session_model -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py
git commit -m "fix+test: use active MLX session model in embeddings response"
```

### Task 5: Add failing llama.cpp tool-capability consistency tests

**Files:**
- Modify: `tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/capability_registry.py`
- Modify: `tldw_Server_API/app/core/LLM_Calls/provider_metadata.py`

**Step 1: Write the failing test**

Add a strict contract test to ensure `tools` are rejected for `llama.cpp` adapter path until explicit support is implemented.

```python
import pytest
from tldw_Server_API.app.core.Chat.Chat_Deps import ChatBadRequestError
from tldw_Server_API.app.core.LLM_Calls.capability_registry import validate_payload


def test_llamacpp_tools_rejected_by_contract():
    with pytest.raises(ChatBadRequestError):
        validate_payload(
            "llama.cpp",
            {
                "messages": [{"role": "user", "content": "hi"}],
                "tools": [{"type": "function", "function": {"name": "x", "parameters": {}}}],
            },
        )
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py -v
```

Expected: FAIL because tools currently pass validation.

**Step 3: Write minimal implementation**

In `capability_registry.py`:
- Add blocked fields for `llama.cpp`:

```python
BLOCKED_FIELDS = {
    ...,
    "llama.cpp": {"tools", "tool_choice"},
}
```

In `provider_metadata.py`:
- Set `"llama.cpp": {"supports_tools": False, ...}`.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py tldw_Server_API/app/core/LLM_Calls/capability_registry.py tldw_Server_API/app/core/LLM_Calls/provider_metadata.py
git commit -m "fix+test: align llama.cpp tools capability and validation contract"
```

### Task 6: Add lifecycle endpoint coverage for llama.cpp managed plane

**Files:**
- Modify: `tldw_Server_API/tests/LLM_Local/test_llamacpp_inference_api.py`
- Create: `tldw_Server_API/tests/LLM_Local/test_llamacpp_management_api.py`

**Step 1: Write the failing test**

Create TestClient tests for:
- `POST /api/v1/llamacpp/start_server`
- `POST /api/v1/llamacpp/stop_server`
- `GET /api/v1/llamacpp/status`
- `GET /api/v1/llamacpp/models`

Use a stubbed `llm_manager` with deterministic responses.

```python
def test_llamacpp_status_happy_path(llamacpp_client, monkeypatch):
    client, headers = llamacpp_client
    stub = _StubMgr(status={"status": "running", "model": "mock.gguf"})
    monkeypatch.setattr(lp, "llm_manager", stub, raising=False)
    monkeypatch.setattr(client.app.state, "llm_manager", stub, raising=False)

    r = client.get("/api/v1/llamacpp/status", headers=headers)
    assert r.status_code == 200
    assert r.json()["model"] == "mock.gguf"
```

**Step 2: Run test to verify it fails**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Local/test_llamacpp_management_api.py -v
```

Expected: initial FAIL until stubs/contracts are aligned.

**Step 3: Write minimal implementation**

Adjust endpoint return envelopes and dependency handling in:
- `tldw_Server_API/app/api/v1/endpoints/llamacpp.py`

Only minimal changes needed to satisfy tests while preserving backward-compatible keys.

**Step 4: Run test to verify it passes**

Run:
```bash
source .venv/bin/activate && python -m pytest tldw_Server_API/tests/LLM_Local/test_llamacpp_management_api.py -v
```

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/LLM_Local/test_llamacpp_management_api.py tldw_Server_API/app/api/v1/endpoints/llamacpp.py
git commit -m "test: add managed llama.cpp lifecycle API endpoint coverage"
```

### Task 7: Update integration docs to remove llama.cpp plane ambiguity

**Files:**
- Create: `Docs/API-related/llamacpp_integration_modes.md`
- Modify: `Docs/Plans/2026-02-23-mlx-llamacpp-integration-design.md`

**Step 1: Write the failing doc check (manual gate)**

Define manual acceptance checklist in commit message/template:
- Managed plane and provider plane both documented.
- Endpoint-to-plane mapping table exists.
- Explicit warning that shared state is not implied.

**Step 2: Run doc validation check**

Run:
```bash
rg -n "managed plane|provider plane|/api/v1/llamacpp|provider=llama.cpp" Docs/API-related/llamacpp_integration_modes.md
```

Expected: no output before file is created.

**Step 3: Write minimal documentation**

Add:
- One-page contract table.
- Common misconfiguration symptoms and correct plane-specific fix path.

**Step 4: Run doc validation check again**

Run:
```bash
rg -n "managed plane|provider plane|/api/v1/llamacpp|provider=llama.cpp" Docs/API-related/llamacpp_integration_modes.md
```

Expected: matches present.

**Step 5: Commit**

```bash
git add Docs/API-related/llamacpp_integration_modes.md Docs/Plans/2026-02-23-mlx-llamacpp-integration-design.md
git commit -m "docs: clarify llama.cpp managed vs provider integration planes"
```

### Task 8: Final verification gate before merge

**Files:**
- No code changes expected.

**Step 1: Run targeted pytest suite**

Run:
```bash
source .venv/bin/activate && python -m pytest -v \
  tldw_Server_API/tests/AuthNZ_Unit/test_mlx_permissions_claims.py \
  tldw_Server_API/tests/AuthNZ_Unit/test_llamacpp_permissions_claims.py \
  tldw_Server_API/tests/LLM_Local/test_llamacpp_inference_api.py \
  tldw_Server_API/tests/LLM_Local/test_llamacpp_management_api.py \
  tldw_Server_API/tests/LLM_Calls/test_mlx_provider.py \
  tldw_Server_API/tests/LLM_Calls/test_llamacpp_strict_filter.py
```

Expected: PASS.

**Step 2: Run Bandit on touched backend scope**

Run:
```bash
source .venv/bin/activate && python -m bandit -r \
  tldw_Server_API/app/api/v1/endpoints/llamacpp.py \
  tldw_Server_API/app/core/LLM_Calls/providers/mlx_provider.py \
  tldw_Server_API/app/core/LLM_Calls/capability_registry.py \
  tldw_Server_API/app/core/LLM_Calls/provider_metadata.py \
  -f json -o /tmp/bandit_mlx_llamacpp_contract_fixes.json
```

Expected: no new high-severity findings in touched code.

**Step 3: Generate concise summary artifact**

Create summary in PR description or commit notes:
- Fixed contracts
- Added tests
- Remaining P2 backlog

**Step 4: Re-run minimal smoke for admin UI API compatibility**

Run:
```bash
source .venv/bin/activate && python -m pytest -v apps/packages/ui/src/components/Option/Admin/__tests__/MlxAdminPage.test.tsx || true
```

Expected: if frontend test runner is unavailable in this environment, record as not run; otherwise pass.

**Step 5: Final commit (if any verification-related metadata changed)**

```bash
git add -A
git commit -m "chore: finalize mlx/llamacpp contract fix verification"
```
