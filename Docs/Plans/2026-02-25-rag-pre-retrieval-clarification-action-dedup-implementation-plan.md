# Pre-Retrieval Clarification and Research Action Dedup Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add default-on (for generation requests) pre-retrieval clarification gating and broaden research-loop dedup from URL-only to action-signature dedup, while preserving backward compatibility.

**Architecture:** Introduce a small `clarification_gate` module with heuristic-first ambiguity detection plus bounded LLM fallback, then wire it into `unified_rag_pipeline` before retrieval fan-out. Extend `research_agent` with deterministic action signature reuse. Keep response contract unchanged (`200` + `generated_answer`) and expose behavior in metadata, features/docs, and tests.

**Tech Stack:** Python 3.11+, FastAPI, Pydantic, pytest, async pipeline in `tldw_Server_API`.

---

### Task 1: Build Clarification Gate Module (TDD)

**Files:**
- Create: `tldw_Server_API/app/core/RAG/rag_service/clarification_gate.py`
- Test: `tldw_Server_API/tests/RAG_NEW/unit/test_clarification_gate.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/RAG_NEW/unit/test_clarification_gate.py
import pytest

from tldw_Server_API.app.core.RAG.rag_service.clarification_gate import (
    ClarificationDecision,
    assess_query_for_clarification,
)


@pytest.mark.asyncio
async def test_pronoun_without_context_requires_clarification():
    d = await assess_query_for_clarification(
        query="Can you fix this?",
        chat_history=None,
        timeout_sec=0.1,
        llm_call=None,
    )
    assert isinstance(d, ClarificationDecision)
    assert d.required is True
    assert "clarify" in (d.question or "").lower()
    assert d.detector in {"heuristic", "hybrid"}


@pytest.mark.asyncio
async def test_specific_query_does_not_require_clarification():
    d = await assess_query_for_clarification(
        query="Summarize the key findings from the 2025 RAG benchmark section",
        chat_history=[],
        timeout_sec=0.1,
        llm_call=None,
    )
    assert d.required is False


@pytest.mark.asyncio
async def test_borderline_query_uses_llm_and_fails_open_on_timeout():
    async def _slow_llm(_query, _history):
        raise TimeoutError("simulated timeout")

    d = await assess_query_for_clarification(
        query="What about that one?",
        chat_history=[{"role": "user", "content": "Discuss retrieval methods."}],
        timeout_sec=0.01,
        llm_call=_slow_llm,
    )
    assert d.required is False
    assert d.reason in {"llm_timeout_fallback", "fail_open"}
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_clarification_gate.py -v`
Expected: FAIL with `ModuleNotFoundError` for `clarification_gate`.

**Step 3: Write minimal implementation**

```python
# tldw_Server_API/app/core/RAG/rag_service/clarification_gate.py
from __future__ import annotations

import asyncio
import re
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Literal, Optional


@dataclass
class ClarificationDecision:
    required: bool
    question: str | None
    reason: str
    confidence: float
    detector: Literal["heuristic", "llm", "hybrid"]


_AMBIGUOUS_PATTERNS = [
    re.compile(r"\b(this|that|it|they|those)\b", re.IGNORECASE),
    re.compile(r"^(fix|improve|update|debug)\b", re.IGNORECASE),
]


def _heuristic_decision(query: str, chat_history: list[dict[str, str]] | None) -> ClarificationDecision | None:
    q = (query or "").strip()
    if not q:
        return ClarificationDecision(False, None, "empty_query", 1.0, "heuristic")
    if any(p.search(q) for p in _AMBIGUOUS_PATTERNS) and not chat_history:
        return ClarificationDecision(
            True,
            "Could you clarify what specific item or context you want me to focus on?",
            "ambiguous_reference_without_context",
            0.92,
            "heuristic",
        )
    if len(q.split()) >= 6 and not re.search(r"\b(this|that|it)\b", q, flags=re.IGNORECASE):
        return ClarificationDecision(False, None, "specific_enough", 0.85, "heuristic")
    return None


async def assess_query_for_clarification(
    query: str,
    chat_history: list[dict[str, str]] | None = None,
    *,
    timeout_sec: float = 1.5,
    llm_call: Optional[Callable[[str, list[dict[str, str]]], Awaitable[dict[str, Any]]]] = None,
) -> ClarificationDecision:
    heuristic = _heuristic_decision(query, chat_history)
    if heuristic is not None:
        return heuristic
    if llm_call is None:
        return ClarificationDecision(False, None, "fail_open", 0.5, "hybrid")
    try:
        payload = await asyncio.wait_for(llm_call(query, chat_history or []), timeout=timeout_sec)
        needs = bool(payload.get("needs_clarification", False))
        return ClarificationDecision(
            required=needs,
            question=(payload.get("clarifying_question") or None),
            reason=str(payload.get("reason", "llm_decision")),
            confidence=float(payload.get("confidence", 0.6)),
            detector="llm",
        )
    except TimeoutError:
        return ClarificationDecision(False, None, "llm_timeout_fallback", 0.5, "hybrid")
    except Exception:
        return ClarificationDecision(False, None, "fail_open", 0.5, "hybrid")
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_clarification_gate.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/clarification_gate.py tldw_Server_API/tests/RAG_NEW/unit/test_clarification_gate.py
git commit -m "feat(rag): add clarification gate module with heuristic-first ambiguity detection"
```

### Task 2: Add Request Surface for Clarification Controls (TDD)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py`
- Modify: `tldw_Server_API/tests/RAG/test_unified_schema_and_pipeline.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
# append to tldw_Server_API/tests/RAG/test_unified_schema_and_pipeline.py
def test_unified_schema_accepts_pre_retrieval_clarification_fields():
    from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest

    req = UnifiedRAGRequest(
        query="Explain this",
        enable_generation=True,
        enable_pre_retrieval_clarification=None,
        clarification_timeout_sec=1.2,
        enable_research_action_dedup=True,
    )
    assert req.enable_pre_retrieval_clarification is None
    assert req.clarification_timeout_sec == pytest.approx(1.2)
    assert req.enable_research_action_dedup is True
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/RAG/test_unified_schema_and_pipeline.py::test_unified_schema_accepts_pre_retrieval_clarification_fields -v`
Expected: FAIL with validation error for unknown fields.

**Step 3: Write minimal implementation**

```python
# in UnifiedRAGRequest generation/search-agent area
enable_pre_retrieval_clarification: Optional[bool] = Field(
    default=None,
    description="When None, defaults to true if enable_generation=true. Enables pre-retrieval clarification gating.",
    example=None,
)
clarification_timeout_sec: Optional[float] = Field(
    default=None,
    ge=0.05,
    le=10.0,
    description="Timeout budget for LLM clarification decision on borderline queries.",
    example=1.5,
)
enable_research_action_dedup: bool = Field(
    default=True,
    description="Skip duplicate research loop actions by reusing prior results for equivalent action signatures.",
    example=True,
)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/RAG/test_unified_schema_and_pipeline.py::test_unified_schema_accepts_pre_retrieval_clarification_fields -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/schemas/rag_schemas_unified.py tldw_Server_API/tests/RAG/test_unified_schema_and_pipeline.py
git commit -m "feat(rag): expose pre-retrieval clarification and action dedup request fields"
```

### Task 3: Wire Pre-Retrieval Clarification Into Unified Pipeline (TDD)

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py`
- Create: `tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_pipeline.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_pipeline.py
import pytest
from unittest.mock import AsyncMock, patch, MagicMock

import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up


@pytest.mark.asyncio
async def test_pre_retrieval_clarification_short_circuits_retrieval():
    with patch.object(up, "assess_query_for_clarification", new=AsyncMock(return_value=up.ClarificationDecision(
        required=True,
        question="Could you clarify which document you mean?",
        reason="ambiguous",
        confidence=0.9,
        detector="heuristic",
    ))), patch.object(up, "MultiDatabaseRetriever") as mock_retriever:
        res = await up.unified_rag_pipeline(
            query="What about that one?",
            enable_generation=True,
        )
        assert res.generated_answer == "Could you clarify which document you mean?"
        assert res.metadata["clarification"]["required"] is True
        assert res.metadata["retrieval_bypassed"]["reason"] == "pre_retrieval_clarification"
        mock_retriever.assert_not_called()
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_pipeline.py -v`
Expected: FAIL because `unified_rag_pipeline` does not yet short-circuit retrieval for clarification.

**Step 3: Write minimal implementation**

```python
# unified_pipeline.py (early in unified_rag_pipeline after input validation)
from .clarification_gate import ClarificationDecision, assess_query_for_clarification

effective_pre_clarify = (
    enable_pre_retrieval_clarification
    if enable_pre_retrieval_clarification is not None
    else bool(enable_generation)
)

if effective_pre_clarify:
    decision = await assess_query_for_clarification(
        query=query,
        chat_history=chat_history,
        timeout_sec=float(clarification_timeout_sec or 1.5),
    )
    if decision.required:
        result.generated_answer = decision.question or "Could you clarify your request?"
        result.documents = []
        result.metadata.setdefault("clarification", {})
        result.metadata["clarification"].update({
            "required": True,
            "stage": "pre_retrieval",
            "reason": decision.reason,
            "confidence": decision.confidence,
            "detector": decision.detector,
        })
        result.metadata.setdefault("retrieval_bypassed", {})
        result.metadata["retrieval_bypassed"]["reason"] = "pre_retrieval_clarification"
        return to_response(result)
```

**Step 4: Run test to verify it passes**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_pipeline.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_pipeline.py
git commit -m "feat(rag): add pre-retrieval clarification short-circuit for generation requests"
```

### Task 4: Add Research Action Signature Dedup (TDD)

**Files:**
- Modify: `tldw_Server_API/app/core/RAG/rag_service/research_agent.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/unit/test_research_agent.py`
- Modify: `tldw_Server_API/tests/RAG_NEW/integration/test_research_agent_loop.py`

**Skill:** @test-driven-development

**Step 1: Write the failing test**

```python
# append to test_research_agent.py
@pytest.mark.asyncio
async def test_research_loop_skips_duplicate_web_search_signature(monkeypatch):
    import tldw_Server_API.app.core.Chat.chat_service as chat_service

    llm_responses = iter([
        '{"reasoning":"first","action":"web_search","params":{"query":"rag updates","result_count":1}}',
        '{"reasoning":"duplicate","action":"web_search","params":{"query":"rag updates","result_count":1}}',
        '{"reasoning":"done","action":"done","params":{"reason":"enough"}}',
    ])

    async def _fake_chat_call_async(**_kwargs):
        return next(llm_responses)

    monkeypatch.setattr(chat_service, "perform_chat_api_call_async", _fake_chat_call_async)

    classification = QueryClassification(skip_search=False, search_local_db=False, search_web=True, standalone_query="rag updates")
    out = await ra.research_loop(query="rag updates", classification=classification, mode="speed", max_iterations=3)
    assert out.metadata["action_dedup"]["duplicates_skipped"] >= 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_research_agent.py::test_research_loop_skips_duplicate_web_search_signature -v`
Expected: FAIL because `action_dedup` metadata does not exist yet.

**Step 3: Write minimal implementation**

```python
# research_agent.py
seen_action_signatures: dict[tuple[Any, ...], ActionOutput] = {}
action_dedup_skipped = 0
action_dedup_reused = 0

def _action_signature(action_name: str, params: dict[str, Any]) -> tuple[Any, ...]:
    q = str(params.get("query", "")).strip().lower()
    if action_name == "web_search":
        return (action_name, q, str(params.get("engine", "duckduckgo")), int(params.get("result_count", 5)))
    if action_name == "academic_search":
        return (action_name, q, int(params.get("result_count", 5)))
    if action_name == "discussion_search":
        plats = tuple(sorted(params.get("platforms") or []))
        return (action_name, q, plats, int(params.get("max_results", 10)))
    if action_name == "local_db_search":
        src = tuple(sorted(params.get("sources") or []))
        return (action_name, q, src, int(params.get("top_k", 10)))
    return (action_name,)

# in loop before execute:
sig = _action_signature(action_name, action_params)
cached = seen_action_signatures.get(sig)
if enable_action_dedup and cached is not None and cached.success and cached.result_count > 0:
    action_output = cached
    action_dedup_skipped += 1
    action_dedup_reused += int(cached.result_count)
else:
    action_output = await registry.execute(action_name, action_params)
    seen_action_signatures[sig] = action_output

# finalize metadata:
output.metadata["action_dedup"] = {
    "enabled": bool(enable_action_dedup),
    "duplicates_skipped": action_dedup_skipped,
    "reused_results_count": action_dedup_reused,
}
```

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_research_agent.py tldw_Server_API/tests/RAG_NEW/integration/test_research_agent_loop.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/core/RAG/rag_service/research_agent.py tldw_Server_API/tests/RAG_NEW/unit/test_research_agent.py tldw_Server_API/tests/RAG_NEW/integration/test_research_agent_loop.py
git commit -m "feat(rag): deduplicate repeated research actions by signature"
```

### Task 5: API Feature Surfacing and Docs (TDD + Docs)

**Files:**
- Modify: `tldw_Server_API/app/api/v1/endpoints/rag_unified.py:2235-2294`
- Create: `tldw_Server_API/tests/RAG_NEW/integration/test_rag_unified_features_endpoint.py`
- Modify: `Docs/API-related/RAG-API-Guide.md`
- Modify: `tldw_Server_API/app/core/RAG/CAPABILITIES.md`

**Skill:** @verification-before-completion

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/RAG_NEW/integration/test_rag_unified_features_endpoint.py
def test_features_endpoint_includes_clarification_and_action_dedup(client_with_overrides):
    r = client_with_overrides.get("/api/v1/rag/features")
    assert r.status_code == 200
    payload = r.json()
    generation_params = payload["features"]["generation"]["parameters"]
    assert "enable_pre_retrieval_clarification" in generation_params
    assert "clarification_timeout_sec" in generation_params
    assert "enable_research_action_dedup" in payload["features"]["query_expansion"]["parameters"] or "enable_research_action_dedup" in generation_params
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_unified_features_endpoint.py -v`
Expected: FAIL because new parameters are missing from `/features`.

**Step 3: Write minimal implementation**

```python
# rag_unified.py features_out update
"generation": {
    "description": "Generate answers from retrieved context",
    "parameters": [
        "enable_generation",
        "generation_provider",
        "generation_model",
        "generation_prompt",
        "enable_pre_retrieval_clarification",
        "clarification_timeout_sec",
    ],
},
"resilience": {
    "description": "Fault tolerance with retries and circuit breakers",
    "parameters": [
        "enable_resilience",
        "retry_attempts",
        "circuit_breaker",
        "enable_research_action_dedup",
    ],
},
```

Also update consumer docs with request-field descriptions and clarification response metadata examples.

**Step 4: Run tests to verify they pass**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_unified_features_endpoint.py -v`
Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/app/api/v1/endpoints/rag_unified.py tldw_Server_API/tests/RAG_NEW/integration/test_rag_unified_features_endpoint.py Docs/API-related/RAG-API-Guide.md tldw_Server_API/app/core/RAG/CAPABILITIES.md
git commit -m "docs(rag): surface clarification and action-dedup capabilities in API docs and features endpoint"
```

### Task 6: End-to-End Verification and Quality/Latency Gates

**Files:**
- Modify: `tldw_Server_API/tests/e2e/test_rag_generation_grounding_smoke.py`
- Create: `tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_metrics.py`

**Skill:** @verification-before-completion

**Step 1: Write the failing test**

```python
# tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_metrics.py
import pytest


@pytest.mark.asyncio
async def test_pre_retrieval_clarification_sets_metrics_and_metadata(monkeypatch):
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up

    calls = {"counter": 0}

    def _fake_increment_counter(*_a, **_k):
        calls["counter"] += 1

    monkeypatch.setattr(up, "increment_counter", _fake_increment_counter, raising=False)
    monkeypatch.setattr(up, "assess_query_for_clarification", pytest.AsyncMock(return_value=up.ClarificationDecision(
        required=True, question="Clarify?", reason="ambiguous", confidence=0.9, detector="heuristic"
    )))

    res = await up.unified_rag_pipeline(query="Fix this", enable_generation=True)
    assert res.metadata["clarification"]["required"] is True
    assert calls["counter"] >= 1
```

**Step 2: Run test to verify it fails**

Run: `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_metrics.py -v`
Expected: FAIL before metrics wiring.

**Step 3: Write minimal implementation**

```python
# unified_pipeline.py clarification short-circuit block
try:
    from tldw_Server_API.app.core.Metrics.metrics_manager import increment_counter, observe_histogram
    increment_counter("rag_clarification_triggered_total", 1, labels={"stage": "pre_retrieval", "detector": decision.detector})
except Exception:
    pass
```

Add e2e assertion path in smoke test to verify ambiguous prompt produces clarifying question and bypass reason.

**Step 4: Run verification suite**

Run:
1. `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_clarification_gate.py -v`
2. `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_pipeline.py -v`
3. `python -m pytest tldw_Server_API/tests/RAG_NEW/unit/test_research_agent.py -v`
4. `python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_research_agent_loop.py -v`
5. `python -m pytest tldw_Server_API/tests/RAG_NEW/integration/test_rag_unified_features_endpoint.py -v`
6. `python -m pytest tldw_Server_API/tests/e2e/test_rag_generation_grounding_smoke.py -v`

Expected: PASS.

**Step 5: Commit**

```bash
git add tldw_Server_API/tests/RAG_NEW/unit/test_pre_retrieval_clarification_metrics.py tldw_Server_API/tests/e2e/test_rag_generation_grounding_smoke.py tldw_Server_API/app/core/RAG/rag_service/unified_pipeline.py
git commit -m "test(rag): add clarification metrics and end-to-end coverage"
```

## Final Validation Checklist (Release Gate)

1. Run all commands in Task 6 Step 4 and capture pass/fail.
2. Run ambiguous-query evaluation slice and confirm unsupported ratio improves vs baseline.
3. Run labeled ambiguity set and confirm clarification precision improves vs baseline.
4. Compare p95 latency for `enable_generation=true` baseline vs branch and confirm <=10% regression.
5. If any gate fails, revert only the relevant task commit and re-run focused tests.

Plan complete and saved to `docs/plans/2026-02-25-rag-pre-retrieval-clarification-action-dedup-implementation-plan.md`. Two execution options:

1. Subagent-Driven (this session) - I dispatch fresh subagent per task, review between tasks, fast iteration
2. Parallel Session (separate) - Open new session with executing-plans, batch execution with checkpoints

Which approach?

