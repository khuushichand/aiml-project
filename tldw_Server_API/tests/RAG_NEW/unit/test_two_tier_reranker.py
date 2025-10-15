import os
import math
import asyncio

import pytest

from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import (
    TwoTierReranker,
    RerankingConfig,
    ScoredDocument,
    BaseReranker,
)
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource


class _FakeCross(BaseReranker):
    def __init__(self, config: RerankingConfig, scores_map):
        super().__init__(config)
        self._scores_map = scores_map

    async def rerank(self, query, documents, original_scores=None):
        out = []
        for d in documents:
            did = getattr(d, 'id', None)
            sc = float(self._scores_map.get(did, 0.0))
            out.append(ScoredDocument(
                document=d,
                original_score=getattr(d, 'score', 0.0),
                rerank_score=sc,
                relevance_score=sc,
                explanation="fake_ce",
            ))
        out.sort(key=lambda x: x.rerank_score, reverse=True)
        return out[: self.config.top_k]


class _FakeLLM(BaseReranker):
    def __init__(self, config: RerankingConfig, scores_map):
        super().__init__(config)
        self._scores_map = scores_map

    async def rerank(self, query, documents, original_scores=None):
        out = []
        for d in documents:
            did = getattr(d, 'id', None)
            sc = float(self._scores_map.get(did, 0.0))
            out.append(ScoredDocument(
                document=d,
                original_score=getattr(d, 'score', 0.0),
                rerank_score=sc,
                relevance_score=sc,
                explanation="fake_llm",
            ))
        out.sort(key=lambda x: x.rerank_score, reverse=True)
        return out[: self.config.top_k]


@pytest.mark.unit
def test_two_tier_reranker_calibration_and_gating(monkeypatch):
    # Force strict gating to validate the path
    monkeypatch.setenv("RAG_MIN_RELEVANCE_PROB", "0.95")
    monkeypatch.setenv("RAG_SENTINEL_MARGIN", "0.50")

    # Make three simple docs
    d1 = Document(id="d1", content="alpha", metadata={}, source=DataSource.MEDIA_DB, score=0.2)
    d2 = Document(id="d2", content="beta", metadata={}, source=DataSource.MEDIA_DB, score=0.1)
    d3 = Document(id="d3", content="gamma", metadata={}, source=DataSource.MEDIA_DB, score=0.05)
    docs = [d1, d2, d3]

    # Cross-encoder and LLM scores (sentinel appears later; filled by reranker)
    ce_map = {"d1": 0.20, "d2": 0.10, "d3": 0.05, "sentinel:irrelevant": 0.02}
    llm_map = {"d1": 0.40, "d2": 0.30, "d3": 0.10, "sentinel:irrelevant": 0.05}

    cfg = RerankingConfig(top_k=2)
    two = TwoTierReranker(cfg, cross_reranker=_FakeCross(cfg, ce_map), llm_reranker=_FakeLLM(cfg, llm_map))

    # Python 3.12+ uses no default loop in sync context; prefer asyncio.run
    scored = asyncio.run(two.rerank("q?", docs))

    # Returned docs should not include sentinel and should be <= top_k
    ids = [sd.document.id for sd in scored]
    assert "sentinel:irrelevant" not in ids
    assert len(ids) == 2

    # Calibrated probability is attached as rerank_score and criteria_scores
    assert all("calibrated_prob" in (sd.criteria_scores or {}) for sd in scored)
    assert all(isinstance(sd.rerank_score, float) for sd in scored)

    # Metadata exposes gating flag due to strict thresholds set above
    assert isinstance(two.last_metadata, dict)
    assert two.last_metadata.get("strategy") == "two_tier"
    assert bool(two.last_metadata.get("gated")) is True
