from unittest.mock import AsyncMock

import pytest


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_pre_retrieval_clarification_sets_metrics_and_metadata(monkeypatch):
    import tldw_Server_API.app.core.Metrics.metrics_manager as metrics_manager
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up

    calls = {"counter": 0}

    def _fake_increment_counter(metric_name, *_args, **_kwargs):  # noqa: ANN001
        if metric_name == "rag_clarification_triggered_total":
            calls["counter"] += 1

    monkeypatch.setattr(metrics_manager, "increment_counter", _fake_increment_counter, raising=False)
    monkeypatch.setattr(
        up,
        "assess_query_for_clarification",
        AsyncMock(
            return_value=up.ClarificationDecision(
                required=True,
                question="Clarify?",
                reason="ambiguous",
                confidence=0.9,
                detector="heuristic",
            )
        ),
    )

    res = await up.unified_rag_pipeline(query="Fix this", enable_generation=True)
    assert res.metadata["clarification"]["required"] is True
    assert res.metadata["retrieval_bypassed"]["reason"] == "pre_retrieval_clarification"
    assert calls["counter"] >= 1
