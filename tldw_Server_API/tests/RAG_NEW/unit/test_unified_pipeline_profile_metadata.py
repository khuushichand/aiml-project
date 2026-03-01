import types

import pytest

from tldw_Server_API.app.core.RAG.rag_service.types import DataSource, Document
import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up


pytestmark = pytest.mark.unit


class FakeRetriever:
    def __init__(self, *args, **kwargs):
        self.retrievers = {}

    async def retrieve(self, query: str, sources=None, config=None, index_namespace=None, **kwargs):
        return [
            Document(
                id="m1",
                content="first doc",
                source=DataSource.MEDIA_DB,
                metadata={"title": "Doc 1"},
                score=0.8,
            ),
            Document(
                id="m2",
                content="second doc",
                source=DataSource.MEDIA_DB,
                metadata={"title": "Doc 2"},
                score=0.6,
            ),
        ]


class FakeHybridReranker:
    async def rerank(self, query, documents, original_scores=None):
        return [types.SimpleNamespace(document=d, rerank_score=getattr(d, "score", 0.0)) for d in documents]



def _metadata(result):
    if isinstance(result, dict):
        return result.get("metadata", {})
    return getattr(result, "metadata", {}) or {}


@pytest.mark.asyncio
async def test_pipeline_records_profile_resolution_metadata(monkeypatch):
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)

    result = await up.unified_rag_pipeline(
        query="q",
        sources=["media_db"],
        enable_cache=False,
        enable_generation=False,
        enable_reranking=False,
        rag_profile="balanced",
    )

    md = _metadata(result)
    profile = md.get("profile_resolution", {})
    assert profile.get("requested_profile") == "balanced"
    assert profile.get("applied_profile") == "balanced"


@pytest.mark.asyncio
async def test_two_tier_unavailable_degrades_to_hybrid(monkeypatch):
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)

    def _fake_create_reranker(strategy, *args, **kwargs):
        strategy_name = str(getattr(strategy, "name", strategy)).lower()
        if "two_tier" in strategy_name:
            raise RuntimeError("reranker unavailable")
        return FakeHybridReranker()

    monkeypatch.setattr(up, "create_reranker", _fake_create_reranker)

    result = await up.unified_rag_pipeline(
        query="q",
        sources=["media_db"],
        enable_cache=False,
        enable_generation=False,
        enable_reranking=True,
        reranking_strategy="two_tier",
        rag_profile="accuracy",
        top_k=2,
    )

    md = _metadata(result)
    degraded = md.get("profile_resolution", {}).get("degraded_features", [])
    assert any(
        item.get("from") == "two_tier" and item.get("to") == "hybrid"
        for item in degraded
    )
