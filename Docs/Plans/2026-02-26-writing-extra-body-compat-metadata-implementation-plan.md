# Writing Extra-Body Compatibility Metadata Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add additive provider+model `extra_body` compatibility metadata for advanced Mikupad-style params, where `supported` reflects effective runtime support for this deployment, and expose it on both writing capabilities and LLM provider listing endpoints without changing runtime chat validation behavior.

**Architecture:** Introduce one shared compatibility catalog + runtime resolver module under `core/LLM_Calls`, then read provider-default and model-level metadata from that resolver in both writing and provider-listing endpoints. Update writing response schemas to type provider/model metadata, and keep `/api/v1/chat/completions` behavior unchanged by design.

**Tech Stack:** FastAPI, Pydantic, pytest, existing `tldw_Server_API` endpoint/test structure.

---

**Execution skills:** `@test-driven-development`, `@verification-before-completion`

### Task 1: Add Catalog Unit Tests (Failing First)

**Files:**
- Create: `tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.LLM_Calls.extra_body_compat_catalog import (
    get_model_extra_body_compat,
    get_provider_extra_body_compat,
)


def test_known_provider_returns_supported_shape():
    data = get_provider_extra_body_compat("openai")
    assert isinstance(data["known_params"], list)
    assert "source" in data


def test_model_level_shape_present():
    data = get_model_extra_body_compat("openai", "gpt-4o-mini")
    assert isinstance(data["known_params"], list)
    assert "effective_reason" in data


def test_runtime_strict_context_disables_nonstandard_support():
    data = get_model_extra_body_compat(
        "openai",
        "gpt-4o-mini",
        runtime_context={"strict_openai_compat": True},
    )
    assert data["supported"] is False


def test_unknown_provider_returns_safe_fallback():
    data = get_provider_extra_body_compat("definitely-unknown-provider")
    assert data["supported"] is False
    assert data["known_params"] == []
    assert data["example"] == {"extra_body": {}}
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py -v`
Expected: FAIL with `ModuleNotFoundError` for `extra_body_compat_catalog` or missing symbol errors.

**Step 3: Commit**

```bash
git add tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py
git commit -m "test: add failing tests for extra_body compatibility catalog"
```

### Task 2: Implement Catalog Module

**Files:**
- Create: `tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py`
- Test: `tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py`

**Step 1: Write minimal implementation**

```python
from __future__ import annotations

from copy import deepcopy
from typing import Any

_DEFAULT = {
    "supported": False,
    "effective_reason": "unsupported for deployment/runtime configuration",
    "known_params": [],
    "param_groups": [],
    "notes": "No extra_body compatibility metadata registered for this provider/model.",
    "example": {"extra_body": {}},
    "source": "catalog+runtime",
}

_CATALOG: dict[str, dict[str, Any]] = {
    "openai": {
        "provider_default": {
            "supported": True,
            "effective_reason": "supported in current deployment",
            "known_params": [
                "dynatemp_range", "dynatemp_exponent", "repeat_penalty", "repeat_last_n",
                "ignore_eos", "mirostat", "mirostat_tau", "mirostat_eta", "typical_p",
                "min_p", "tfs_z", "xtc_threshold", "xtc_probability", "dry_multiplier",
                "dry_base", "dry_allowed_length", "dry_penalty_last_n", "dry_sequence_breakers",
                "banned_tokens", "grammar", "logit_bias",
            ],
            "param_groups": ["sampling", "penalties", "constraints"],
            "notes": "Provider-specific advanced params should be sent under extra_body.",
            "example": {"extra_body": {"mirostat": 2, "mirostat_tau": 5, "mirostat_eta": 0.1}},
        },
        "models": {},
    }
}


def _apply_runtime_overrides(payload: dict[str, Any], runtime_context: dict[str, Any] | None) -> dict[str, Any]:
    out = deepcopy(payload)
    if runtime_context and runtime_context.get("strict_openai_compat"):
        out["supported"] = False
        out["effective_reason"] = "disabled by strict_openai_compat runtime setting"
    return out


def get_provider_extra_body_compat(provider: str, *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    ...


def get_model_extra_body_compat(provider: str, model: str, *, runtime_context: dict[str, Any] | None = None) -> dict[str, Any]:
    ...
```

**Step 2: Run tests to verify pass**

Run: `pytest tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py -v`
Expected: PASS.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py
git commit -m "feat: add extra_body compatibility catalog"
```

### Task 3: Add Writing Endpoint Tests For New Metadata (Failing First)

**Files:**
- Modify: `tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py`

**Step 1: Write failing tests**

Add tests covering:

1. `providers[0]["extra_body_compat"]` exists in `/api/v1/writing/capabilities` response.
2. `providers[0]["model_extra_body_compat"]` exists and is keyed by model name.
3. `requested["extra_body_compat"]` exists when `provider=openai&model=<model>` is passed.
4. Unknown provider/model in `requested` returns fallback shape (`supported=false`, empty `known_params`).
5. Runtime strict context yields `supported=false`.

```python
def test_writing_capabilities_includes_extra_body_compat(...):
    ...
    assert "extra_body_compat" in providers[0]
    assert isinstance(providers[0]["extra_body_compat"], dict)
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py -k extra_body_compat -v`
Expected: FAIL because response field is missing.

**Step 3: Commit**

```bash
git add tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py
git commit -m "test: add failing writing capabilities extra_body metadata tests"
```

### Task 4: Implement Writing Schema + Endpoint Enrichment

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/writing_schemas.py`
- Modify: `tldw_Server_API/app/api/v1/endpoints/writing.py`
- Create/Use: `tldw_Server_API/app/core/LLM_Calls/extra_body_compat_catalog.py`
- Test: `tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py`

**Step 1: Add typed schema model**

Add a new Pydantic model (for example `WritingExtraBodyCompat`) and optional field:

```python
class WritingExtraBodyCompat(BaseModel):
    supported: bool
    effective_reason: str | None = None
    known_params: list[str] = Field(default_factory=list)
    param_groups: list[str] = Field(default_factory=list)
    notes: str | None = None
    example: dict[str, Any] = Field(default_factory=dict)
    source: str = "catalog+runtime"
```

Attach to:

- `WritingProviderCapabilities.extra_body_compat`
- `WritingProviderCapabilities.model_extra_body_compat`
- `WritingRequestedCapabilities.extra_body_compat`

**Step 2: Populate endpoint response**

In `get_writing_capabilities(...)`, inject resolver metadata:

- `providers_payload[i].extra_body_compat = get_provider_extra_body_compat(name, runtime_context=...)`
- `providers_payload[i].model_extra_body_compat[model] = get_model_extra_body_compat(name, model, runtime_context=...)`
- `requested.extra_body_compat = get_model_extra_body_compat(provider_name, model_name, runtime_context=...)` when model is present
- `requested.extra_body_compat = get_provider_extra_body_compat(provider_name, runtime_context=...)` otherwise

**Step 3: Run tests**

Run:

- `pytest tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py -k "capabilities and extra_body_compat" -v`

Expected: PASS.

**Step 4: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/writing_schemas.py tldw_Server_API/app/api/v1/endpoints/writing.py tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py
git commit -m "feat: expose extra_body compatibility metadata in writing capabilities"
```

### Task 5: Add LLM Providers Endpoint Test (Failing First)

**Files:**
- Modify: `tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py`

**Step 1: Write failing test**

```python
def test_llm_providers_includes_model_level_extra_body_compat(monkeypatch, llm_client):
    ...
    r = llm_client.get("/api/v1/llm/providers")
    data = r.json()
    providers = {p["name"]: p for p in data.get("providers", [])}
    assert "extra_body_compat" in providers["openai"]
    assert isinstance(providers["openai"]["extra_body_compat"].get("known_params"), list)
    if providers["openai"].get("models_info"):
        assert "extra_body_compat" in providers["openai"]["models_info"][0]
```

**Step 2: Run test to verify it fails**

Run: `pytest tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py -k extra_body_compat -v`
Expected: FAIL due missing field.

**Step 3: Commit**

```bash
git add tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py
git commit -m "test: add failing llm providers extra_body metadata test"
```

### Task 6: Implement `/api/v1/llm/providers` Metadata Mirror

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/llm_providers.py`
- Test: `tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py`

**Step 1: Add metadata injection**

In provider loop, add:

```python
runtime_context = {
    "strict_openai_compat": (
        config_parser.get(section_name, "strict_openai_compat", fallback="false").lower() == "true"
    )
}
provider_data["extra_body_compat"] = get_provider_extra_body_compat(provider_name, runtime_context=runtime_context)
for mi in provider_data.get("models_info", []):
    model_name = str(mi.get("name") or "").strip()
    mi["extra_body_compat"] = get_model_extra_body_compat(provider_name, model_name, runtime_context=runtime_context)
```

Use same catalog module as writing endpoint.

**Step 2: Run test suite slices**

Run:

- `pytest tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py -v`
- `pytest tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py -k capabilities -v`

Expected: PASS.

**Step 3: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/llm_providers.py tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py
git commit -m "feat: mirror extra_body compatibility metadata in llm providers endpoint"
```

### Task 7: Verification Pass And Guardrails

**Files:**
- Verify changed files only

**Step 1: Run targeted regression tests**

Run:

```bash
pytest tldw_Server_API/tests/LLM_Adapters/unit/test_extra_body_compat_catalog.py -v
pytest tldw_Server_API/tests/LLM_Adapters/unit/test_llm_providers_capabilities_merge.py -v
pytest tldw_Server_API/tests/Writing/test_writing_endpoint_integration.py -v
```

Expected: PASS.

**Step 2: Confirm no behavior drift in chat path**

Run quick guard check:

```bash
pytest tldw_Server_API/tests/Chat_NEW/unit/test_llm_provider_details.py -v
```

Expected: PASS; no runtime request-validation behavior changes.

**Step 3: Commit final verification note (optional)**

```bash
git add -A
git commit -m "chore: verify extra_body compatibility metadata rollout"
```

(Only if there are actual remaining tracked changes.)

## Definition of Done

1. New shared catalog exists and is unit-tested.
2. `/api/v1/writing/capabilities` includes provider-default and model-level `extra_body_compat` metadata.
3. `/api/v1/llm/providers` includes mirrored provider-default and model-level `extra_body_compat` metadata.
4. Changes are additive only; no new top-level advanced param enforcement.
5. `supported` reflects effective runtime support for this deployment.
6. Targeted tests pass.
