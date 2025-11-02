"""
Unit tests for LLM reranker guardrails and metrics.

Forces timeouts to ensure metrics counters increment in both the internal RAG
metrics collector and the central metrics registry (Prometheus/OTel backing).
"""

import asyncio
import os
import pytest
from typing import List

from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import LLMReranker, RerankingConfig
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


class SlowLLM:
    def analyze(self, prompt: str) -> str:  # noqa: D401
        import time
        time.sleep(0.2)  # exceeds tiny timeout
        return "0.5"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_llm_reranker_timeout_increments_metrics(monkeypatch):
    # Force very small timeouts
    monkeypatch.setenv("RAG_LLM_RERANK_TIMEOUT_SEC", "0.01")
    monkeypatch.setenv("RAG_LLM_RERANK_TOTAL_BUDGET_SEC", "0.05")
    monkeypatch.setenv("RAG_LLM_RERANK_MAX_DOCS", "3")

    # Prepare documents
    docs: List[Document] = [
        Document(id=str(i), content=f"Doc {i}", metadata={}, source=DataSource.MEDIA_DB) for i in range(5)
    ]

    reranker = LLMReranker(RerankingConfig(top_k=5), llm_client=SlowLLM())
    # Invoke the internal scoring method to isolate behavior
    scores = await reranker._score_batch("what is rag?", docs)
    assert len(scores) >= 1  # we score at least one before timing out

    # Central registry should have increments
    registry = get_metrics_registry()
    # Values are stored as deques of MetricValue; sum them to get total increments in this process
    def _sum_values(name: str) -> float:
        vals = registry.values.get(name)
        return sum(v.value for v in (vals or []))

    assert _sum_values("rag_reranker_llm_timeouts_total") >= 1
    # budget may or may not be exhausted depending on env/platform timing; assert docs_scored increments instead
    assert _sum_values("rag_reranker_llm_docs_scored_total") >= 1
