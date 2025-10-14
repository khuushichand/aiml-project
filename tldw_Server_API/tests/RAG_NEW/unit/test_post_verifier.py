"""
Unit tests for the post-generation verification interface.

Verifies that unsupported claims trigger adaptive retry metrics and that
central metrics registry counters/histograms are updated.
"""

import asyncio
import pytest

from tldw_Server_API.app.core.RAG.rag_service.post_generation_verifier import PostGenerationVerifier
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.unit
@pytest.mark.asyncio
async def test_post_verifier_metrics_increment_on_unsupported(monkeypatch):
    # Stub claims runner returning unsupported ratio above threshold
    async def _fake_runner(**kwargs):
        return {
            "claims": [{"id": "c1"}, {"id": "c2"}, {"id": "c3"}, {"id": "c4"}],
            "summary": {
                "supported": 1,
                "refuted": 2,
                "nei": 1,
                "precision": 0.25,
                "coverage": 0.75,
                "claim_faithfulness": 0.25,
            },
        }

    verifier = PostGenerationVerifier(
        claims_runner=_fake_runner,
        max_retries=1,
        unsupported_threshold=0.10,  # low threshold to trigger repair
        max_claims=10,
        time_budget_sec=0.25,
    )

    # Minimal docs
    docs = [
        Document(id="1", content="A", metadata={"source": DataSource.MEDIA_DB}),
        Document(id="2", content="B", metadata={"source": DataSource.MEDIA_DB}),
    ]

    out = await verifier.verify_and_maybe_fix(
        query="What is RAG?",
        answer="RAG is X.",
        base_documents=docs,
        user_id="u1",
        media_db_path=None,  # no retrieval in this test
        generation_model=None,
        top_k=5,
    )

    # Unsupported ratio should reflect fake summary (3/4)
    assert out.unsupported_ratio > 0.5
    assert out.total_claims == 4
    assert out.unsupported_count == 3

    # Verify central metrics registry recorded increments
    registry = get_metrics_registry()

    def _sum_values(name: str) -> float:
        vals = registry.values.get(name)
        return sum(v.value for v in (vals or []))

    # Unsupported claims total should be incremented by 3
    assert _sum_values("rag_unsupported_claims_total") >= 3
    # One adaptive retry attempted
    assert _sum_values("rag_adaptive_retries_total") >= 1
    # Postcheck duration histogram should have recorded at least one observation
    assert registry.values.get("rag_postcheck_duration_seconds") is not None
