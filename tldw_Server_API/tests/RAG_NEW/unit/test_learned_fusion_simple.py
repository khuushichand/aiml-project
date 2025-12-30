"""
Tests for learned-fusion calibration on non Two-Tier strategies (e.g. cross_encoder).
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.RAG.rag_service.advanced_reranking import (
    BaseReranker,
    ScoredDocument,
)


class _DummyReranker(BaseReranker):
    def __init__(self, config, score: float = 0.1):
        super().__init__(config)
        self._score = float(score)

    async def rerank(self, query, documents, original_scores=None):
        out = []
        for d in documents:
            out.append(
                ScoredDocument(
                    document=d,
                    original_score=getattr(d, "score", 0.0),
                    rerank_score=self._score,
                )
            )
        # Keep ordering but with uniform rerank_score
        return out[: self.config.top_k]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_learned_fusion_calibration_for_cross_encoder(monkeypatch):
    """
    When enable_learned_fusion is true for a non Two-Tier strategy (cross_encoder),
    the pipeline should compute a simple fused probability and use abstention_policy
    when gating generation.
    """
    # Make gating very strict so fused_prob < threshold
    monkeypatch.setenv("RAG_MIN_RELEVANCE_PROB", "0.99")

    with patch(
        "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever"
    ) as mock_retriever:
        mock_instance = MagicMock()
        mock_instance.retrieve = AsyncMock(
            return_value=[
                Document(
                    id="d1",
                    content="alpha",
                    metadata={},
                    source=DataSource.MEDIA_DB,
                    score=0.2,
                )
            ]
        )
        mock_retriever.return_value = mock_instance

        from tldw_Server_API.app.core.RAG.rag_service import advanced_reranking as ar

        def _fake_create(strategy, cfg, llm_client=None):
            # For cross_encoder, return a dummy reranker that assigns low scores
            if strategy == ar.RerankingStrategy.CROSS_ENCODER:
                return _DummyReranker(cfg, score=0.1)
            return ar.create_reranker(strategy, cfg, llm_client=llm_client)

        with patch(
            "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.create_reranker",
            side_effect=_fake_create,
        ):
            res = await unified_rag_pipeline(
                query="What is RAG?",
                sources=["media_db"],
                enable_reranking=True,
                reranking_strategy="cross_encoder",
                enable_generation=True,
                top_k=1,
                enable_learned_fusion=True,
                abstention_policy="decline",
            )

            cal = (res.metadata or {}).get("reranking_calibration") or {}
            assert cal.get("strategy") == "cross_encoder"
            assert "fused_score" in cal
            assert "threshold" in cal
            assert cal.get("gated") in {True, False}
            # With strict threshold, we expect gating to be true
            assert cal.get("gated") is True
            assert cal.get("decision") == "decline"

            gate = (res.metadata or {}).get("generation_gate") or {}
            assert gate.get("reason") == "low_relevance_probability"
            assert isinstance(res.generated_answer, str)
            assert "sufficient grounded evidence" in res.generated_answer or "Insufficient" in res.generated_answer
