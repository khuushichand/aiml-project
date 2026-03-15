# RAG Switchable Profiles Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a request-level switchable RAG profile system (`fast`, `balanced`, `accuracy`) that applies paper-informed defaults while preserving explicit request overrides.

**Architecture:** Extend existing RAG profile infrastructure in `rag_service/profiles.py`, expose profile selection in `UnifiedRAGRequest`, and apply profile defaults through a shared endpoint payload resolver used by both standard and streaming paths. Enforce precedence as `explicit request field > profile default > Search-Agent env/config defaults > schema default`. Keep unified pipeline behavior intact, adding profile-resolution metadata and safe feature degradation when unavailable.

**Tech Stack:** FastAPI, Pydantic (v1/v2 compatibility), unified RAG pipeline, pytest (unit/integration), TypeScript API client typings.

---

### Task 1: Add Schema Contract for `rag_profile` and Token Cap 4000

**Files:**
- Create: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_request_schema_profiles.py`
- Modify: `tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py`
- Test: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_request_schema_profiles.py`

**Step 1: Write the failing test**

```python
from pydantic import ValidationError
import pytest

from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest


def test_rag_profile_accepts_switchable_values():
    req = UnifiedRAGRequest(query="q", rag_profile="fast")
    assert req.rag_profile == "fast"


def test_rag_profile_rejects_unknown_value():
    with pytest.raises(ValidationError):
        UnifiedRAGRequest(query="q", rag_profile="production")


def test_max_generation_tokens_allows_2200_but_rejects_4001():
    ok_req = UnifiedRAGRequest(query="q", max_generation_tokens=2200)
    assert ok_req.max_generation_tokens == 2200
    with pytest.raises(ValidationError):
        UnifiedRAGRequest(query="q", max_generation_tokens=4001)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_request_schema_profiles.py -v`  
Expected: FAIL because `rag_profile` does not exist and current token cap rejects >2000.

**Step 3: Write minimal implementation**

```python
# in UnifiedRAGRequest
rag_profile: Optional[Literal["fast", "balanced", "accuracy"]] = Field(
    default=None,
    description="Switchable RAG profile defaults: fast, balanced, accuracy",
)

# existing field update
max_generation_tokens: int = Field(
    default=500,
    ge=50,
    le=4000,
    ...
)
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_request_schema_profiles.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/RAG_NEW/unit/test_rag_request_schema_profiles.py tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py
git commit -m "feat(rag): add switchable rag_profile schema and 4000 token cap"
```

### Task 2: Extend Backend Profile Registry with `fast/balanced/accuracy`

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/profiles.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_profiles.py`
- Test: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_profiles.py`

**Step 1: Write the failing test**

```python
def test_switchable_profiles_are_registered():
    profiles = list_profiles()
    assert "fast" in profiles
    assert "balanced" in profiles
    assert "accuracy" in profiles


def test_switchable_profile_defaults_match_design_targets():
    fast = get_profile_kwargs("fast")
    balanced = get_profile_kwargs("balanced")
    accuracy = get_profile_kwargs("accuracy")

    assert fast["max_generation_tokens"] == 440
    assert balanced["max_generation_tokens"] == 1000
    assert accuracy["max_generation_tokens"] == 2200
    assert accuracy["reranking_strategy"] == "two_tier"
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_profiles.py -v`  
Expected: FAIL because new profile names are not registered.

**Step 3: Write minimal implementation**

```python
# Extend ProfileName literal and add new profile entries
ProfileName = Literal[
    "production", "research", "cheap",
    "fast", "balanced", "accuracy",
]

_PROFILES = {
    ... existing profiles ...,
    "fast": RAGProfile(name="fast", defaults={...}),
    "balanced": RAGProfile(name="balanced", defaults={...}),
    "accuracy": RAGProfile(name="accuracy", defaults={...}),
}
```

Implementation notes:
- Keep existing `production/research/cheap` profiles for backward compatibility.
- Add new profiles with the approved behavior matrix values.

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_profiles.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/profiles.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_profiles.py
git commit -m "feat(rag): add fast balanced accuracy backend profiles"
```

### Task 3: Apply Profile Defaults via Shared Endpoint Resolver (Standard + Streaming)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_search_agent_defaults.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py`
- Test: `tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_search_agent_defaults.py`

**Step 1: Write the failing test**

```python
def test_rag_profile_applies_defaults_when_fields_omitted():
    request = UnifiedRAGRequest(query="profile apply", rag_profile="fast")
    kwargs = rag_ep._build_unified_pipeline_kwargs(
        request=request,
        db_paths=_EMPTY_DB_PATHS,
        media_db=None,  # type: ignore[arg-type]
        chacha_db=None,  # type: ignore[arg-type]
        current_user=None,
    )
    assert kwargs["generation_prompt"] == "instruction_tuned"
    assert kwargs["max_generation_tokens"] == 440


def test_explicit_request_fields_override_profile_defaults():
    request = UnifiedRAGRequest(
        query="profile override",
        rag_profile="accuracy",
        max_generation_tokens=700,
        generation_prompt="concise",
    )
    kwargs = rag_ep._build_unified_pipeline_kwargs(...)
    assert kwargs["max_generation_tokens"] == 700
    assert kwargs["generation_prompt"] == "concise"


def test_profile_defaults_override_search_agent_defaults_when_request_omits_field(monkeypatch):
    monkeypatch.setenv("SEARCH_STRUCTURED_RESPONSE", "false")
    request = UnifiedRAGRequest(query="precedence", rag_profile="balanced")
    kwargs = rag_ep._build_unified_pipeline_kwargs(...)
    # balanced profile requires structured response; profile must beat Search-Agent default
    assert kwargs["enable_structured_response"] is True
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_search_agent_defaults.py -k rag_profile -v`  
Expected: FAIL because profile defaults are not yet applied in payload builder.

**Step 3: Write minimal implementation**

```python
# rag_unified.py
from tldw_Server_API.app.core.RAG.rag_service.profiles import get_profile_kwargs


def _apply_rag_profile_defaults(request: UnifiedRAGRequest, payload: dict[str, Any]) -> None:
    if not request.rag_profile:
        return
    explicit = _request_fields_set(request)
    defaults = get_profile_kwargs(request.rag_profile)
    for key, value in defaults.items():
        if key in explicit:
            continue
        if key in payload:
            payload[key] = value
    payload["rag_profile"] = request.rag_profile


def _build_effective_request_payload(request: UnifiedRAGRequest) -> dict[str, Any]:
    payload = model_dump_compat(request)
    # lower precedence defaults first
    _apply_search_agent_defaults(request, payload)
    # then profile defaults (still below explicit request fields)
    _apply_rag_profile_defaults(request, payload)
    return payload


# in _build_unified_pipeline_kwargs()
payload = _build_effective_request_payload(request)

# in unified_search_stream_endpoint generation config path:
# build from effective payload (not raw request fields) so profile defaults
# also affect stream generation_prompt/max_generation_tokens/provider/model.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_search_agent_defaults.py -k rag_profile -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_search_agent_defaults.py tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py
git commit -m "feat(rag-api): apply request rag_profile defaults with explicit override precedence"
```

### Task 4: Add Paper-Informed Prompt Keys with Cached Loader Fallback

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/generation.py`
- Modify: `tldw_Server_API/Config_Files/Prompts/rag.prompts.yaml`
- Modify: `tldw_Server_API/Config_Files/Prompts/rag.prompts.md`
- Create: `tldw_Server_API/tests/RAG_NEW/unit/test_generation_prompt_loader.py`
- Test: `tldw_Server_API/tests/RAG_NEW/unit/test_generation_prompt_loader.py`

**Step 1: Write the failing test**

```python
from tldw_Server_API.app.core.RAG.rag_service.generation import PromptTemplates


def test_prompt_templates_load_switchable_profile_prompt_keys():
    text = PromptTemplates.get_template("instruction_tuned")
    assert "Use the provided context" in text


def test_prompt_templates_falls_back_to_default_for_unknown_key():
    unknown = PromptTemplates.get_template("does_not_exist")
    assert "Context:" in unknown
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_generation_prompt_loader.py -v`  
Expected: FAIL because `instruction_tuned` key is not available in generator template resolver.

**Step 3: Write minimal implementation**

```python
# generation.py
from tldw_Server_API.app.core.Utils.prompt_loader import load_prompt
from functools import lru_cache


@lru_cache(maxsize=64)
def _load_rag_prompt_cached(name: str) -> str | None:
    return load_prompt("rag", name)

@classmethod
def get_template(cls, name: str) -> str:
    external = _load_rag_prompt_cached(name)
    if isinstance(external, str) and external.strip():
        return external
    return templates.get(name, cls.DEFAULT)
```

```yaml
# rag.prompts.yaml additions
instruction_tuned: |
  Use the provided context to answer the question. Do not use any other knowledge.
  Context:
  {context}
  Question: {question}
  Answer:

multi_hop_compact: |
  Answer using ONLY the provided documents. Connect evidence across sources.
  Context:
  {context}
  Question: {question}
  Provide concise synthesis with inline source citations.

expert_synthesis: |
  You are a meticulous research assistant. Synthesize evidence, resolve contradictions,
  and provide a precise answer grounded ONLY in context.
  Context:
  {context}
  Question: {question}
  Answer with explicit source citations.
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_generation_prompt_loader.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/generation.py tldw_Server_API/Config_Files/Prompts/rag.prompts.yaml tldw_Server_API/Config_Files/Prompts/rag.prompts.md tldw_Server_API/tests/RAG_NEW/unit/test_generation_prompt_loader.py
git commit -m "feat(rag-generation): add profile prompt keys via prompt loader"
```

### Task 5: Add Profile Resolution Metadata and Safe Reranker Degradation

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`
- Create: `tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_profile_metadata.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_pipeline_generation_controls.py`
- Test: `tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_profile_metadata.py`

**Step 1: Write the failing test**

```python
@pytest.mark.asyncio
async def test_pipeline_records_profile_resolution_metadata(monkeypatch):
    # patch retriever + generator to keep test deterministic
    result = await up.unified_rag_pipeline(
        query="q",
        enable_generation=True,
        enable_reranking=False,
        rag_profile="balanced",
    )
    md = result.metadata
    assert md["profile_resolution"]["applied_profile"] == "balanced"


@pytest.mark.asyncio
async def test_two_tier_unavailable_degrades_to_hybrid(monkeypatch):
    def _boom(*args, **kwargs):
        raise RuntimeError("reranker unavailable")
    monkeypatch.setattr(up, "create_reranker", _boom)
    result = await up.unified_rag_pipeline(
        query="q",
        enable_reranking=True,
        reranking_strategy="two_tier",
        rag_profile="accuracy",
    )
    degraded = result.metadata.get("profile_resolution", {}).get("degraded_features", [])
    assert any(item.get("from") == "two_tier" and item.get("to") == "hybrid" for item in degraded)
```

**Step 2: Run test to verify it fails**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_profile_metadata.py -v`  
Expected: FAIL because `rag_profile` metadata and degradation bookkeeping are not implemented.

**Step 3: Write minimal implementation**

```python
# unified_pipeline.py signature
rag_profile: Optional[Literal["fast", "balanced", "accuracy"]] = None,

# early metadata block
result.metadata.setdefault("profile_resolution", {
    "requested_profile": rag_profile,
    "applied_profile": rag_profile,
    "effective_overrides_count": 0,
    "degraded_features": [],
})

# rerank guard
if reranking_strategy == "two_tier" and not (create_reranker and RerankingStrategy and RerankingConfig):
    reranking_strategy = "hybrid"
    result.metadata["profile_resolution"].setdefault("degraded_features", []).append(
        {"component": "reranking_strategy", "from": "two_tier", "to": "hybrid", "reason": "unavailable_dependency"}
    )

# runtime fallback guard around create_reranker/rerank call
try:
    reranker = create_reranker(...)
    reranked = await _resilient_call(...)
except Exception:
    if reranking_strategy == "two_tier":
        reranking_strategy = "hybrid"
        result.metadata["profile_resolution"].setdefault("degraded_features", []).append(
            {"component": "reranking_strategy", "from": "two_tier", "to": "hybrid", "reason": "runtime_failure"}
        )
        # retry once with hybrid
        ...
    else:
        raise
```

**Step 4: Run test to verify it passes**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_profile_metadata.py -v`  
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_profile_metadata.py tldw_Server_API/tests/RAG_NEW/unit/test_pipeline_generation_controls.py
git commit -m "feat(rag-pipeline): emit profile-resolution metadata and degrade two-tier safely"
```

### Task 6: Wire Profile in Frontend RAG Settings Payload

**Files:**
- Modify: `apps/packages/ui/src/services/rag/unified-rag.ts`
- Create: `apps/packages/ui/src/services/rag/unified-rag.test.ts`
- Test: `apps/packages/ui/src/services/rag/unified-rag.test.ts`

**Step 1: Write the failing test/check target**

```ts
import { buildRagSearchRequest, DEFAULT_RAG_SETTINGS } from "./unified-rag"

it("omits rag_profile when set to none", () => {
  const req = buildRagSearchRequest({ ...DEFAULT_RAG_SETTINGS, query: "q", rag_profile: "none" })
  expect((req.options as Record<string, unknown>).rag_profile).toBeUndefined()
})

it("includes rag_profile when set to fast", () => {
  const req = buildRagSearchRequest({ ...DEFAULT_RAG_SETTINGS, query: "q", rag_profile: "fast" })
  expect((req.options as Record<string, unknown>).rag_profile).toBe("fast")
})
```

**Step 2: Run check to verify it fails (if strict typing currently rejects field)**

Run: `bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts --runInBand`  
Expected: FAIL until `rag_profile` is wired and serialization omits `"none"`.

**Step 3: Write minimal implementation**

```ts
export type RagProfile = "fast" | "balanced" | "accuracy" | "none"

export type RagSettings = {
  ...
  rag_profile: RagProfile
}

export const DEFAULT_RAG_SETTINGS: RagSettings = {
  ...
  rag_profile: "none",
}
```

Implementation note:
- In `buildRagSearchRequest`, omit `options.rag_profile` when the UI value is `"none"` to preserve backend default behavior.

**Step 4: Run check to verify it passes**

Run: `bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts --runInBand`  
Expected: PASS.

**Step 5: Commit**

```bash
git add apps/packages/ui/src/services/rag/unified-rag.ts apps/packages/ui/src/services/rag/unified-rag.test.ts
git commit -m "feat(frontend-rag): expose rag_profile in unified settings payload"
```

### Task 7: End-to-End Verification, Security Scan, and Documentation Sync

**Files:**
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py`
- Modify: `tldw_Server_API/app/core/RAG/CAPABILITIES.md`
- Modify: `tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md`

**Step 1: Write failing integration test for profile-driven generation prompt parity**

```python
def test_rag_streaming_profile_fast_applies_instruction_prompt(monkeypatch, client_with_stream_overrides):
    payload = {
        "query": "profile parity",
        "enable_generation": True,
        "rag_profile": "fast",
    }
    # assert generation_config["prompt_template"] == "instruction_tuned"
```

**Step 2: Run focused integration test to verify failure**

Run: `source .venv/bin/activate && python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k profile_fast -v`  
Expected: FAIL before profile payload plumbing is complete.

**Step 3: Implement minimal test/doc updates**

```markdown
# API docs update
- New request field: rag_profile (fast|balanced|accuracy)
- Profile precedence: explicit fields override profile defaults
- max_generation_tokens upper limit: 4000
```

**Step 4: Run full verification suite for touched scope**

Run:

```bash
source .venv/bin/activate
python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_request_schema_profiles.py -v
python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_profiles.py -v
python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_rag_unified_search_agent_defaults.py -k rag_profile -v
python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_generation_prompt_loader.py -v
python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_unified_pipeline_profile_metadata.py -v
python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py -k profile_fast -v
bunx vitest run apps/packages/ui/src/services/rag/unified-rag.test.ts --runInBand
python -m bandit -r tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py tldw_Server_API/app/core/RAG/rag_service/profiles.py tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/app/core/RAG/rag_service/generation.py tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py -f json -o /tmp/bandit_rag_profiles.json
```

Expected:
- All targeted tests PASS.
- Bandit produces no new high/medium issues in touched code.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/RAG_NEW/integration/test_rag_stream_parity.py tldw_Server_API/app/core/RAG/CAPABILITIES.md tldw_Server_API/app/core/RAG/API_DOCUMENTATION.md
git commit -m "test/docs(rag): validate profile parity and document switchable profile API"
```

---

## Implementation Guidance

- Follow @superpowers:test-driven-development for each task.
- Run @superpowers:verification-before-completion before claiming success.
- Keep changes minimal and reversible (YAGNI).
- Prefer frequent small commits as listed above.

## Notes for Executor

1. Reuse existing profile helpers (`get_profile_kwargs`, `apply_profile_to_kwargs`) instead of creating a parallel profile system.
2. Do not remove existing `production/research/cheap` profiles; add switchable profiles as additive behavior.
3. Preserve endpoint behavior for callers that do not pass `rag_profile`.
