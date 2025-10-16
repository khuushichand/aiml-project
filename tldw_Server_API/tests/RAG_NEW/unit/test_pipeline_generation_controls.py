import asyncio
import types
import pytest

from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up


class FakeRetriever:
    def __init__(self, *args, **kwargs):
        self.retrievers = {}

    async def retrieve(self, query: str, sources=None, config=None, index_namespace=None, **kwargs):
        return [
            Document(id="m1", content="First doc with content", source=DataSource.MEDIA_DB, metadata={}, score=0.6),
            Document(id="m2", content="Second doc with content", source=DataSource.MEDIA_DB, metadata={}, score=0.5),
        ]


class FakeTwoTierReranker:
    def __init__(self, *args, **kwargs):
        # Force gating
        self.last_metadata = {"gated": True, "top_doc_prob": 0.1}

    async def rerank(self, query, documents, original_scores=None):
        # return original as scored docs (simplified)
        return [types.SimpleNamespace(document=d, rerank_score=getattr(d, "score", 0.0)) for d in documents]


class FakeAnswerGenerator:
    def __init__(self, *args, **kwargs):
        pass

    async def generate(self, *, query: str, context: str, prompt_template=None, max_tokens=None, temperature=None):
        # Distinguish calls by prompt content to simulate draft/refine
        if "CRITIQUE:" in context:
            return {"answer": "refined answer"}
        return {"answer": "draft answer"}


@pytest.mark.asyncio
async def test_abstention_ask_behavior(monkeypatch):
    # Patch retriever and reranker
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)
    # create_reranker is imported symbol in unified_pipeline
    monkeypatch.setattr(up, "create_reranker", lambda *a, **k: FakeTwoTierReranker())

    res = await up.unified_rag_pipeline(
        query="What is the thing?",
        sources=["media_db"],
        enable_cache=False,
        search_mode="hybrid",
        enable_reranking=True,
        reranking_strategy="two_tier",
        enable_generation=True,
        enable_abstention=True,
        abstention_behavior="ask",
        top_k=3,
    )
    # Gated → abstention path should provide a clarifying answer
    ga = getattr(res, "generated_answer", None) or (res.get("generated_answer") if isinstance(res, dict) else None)
    assert ga and ("clarify" in ga.lower() or "clarification" in ga.lower())


@pytest.mark.asyncio
async def test_multi_turn_synthesis_happy_path(monkeypatch):
    # Patch retriever and generator; disable reranking
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)
    monkeypatch.setattr(up, "AnswerGenerator", FakeAnswerGenerator)

    res = await up.unified_rag_pipeline(
        query="Explain topic X",
        sources=["media_db"],
        enable_cache=False,
        enable_reranking=False,
        enable_generation=True,
        enable_multi_turn_synthesis=True,
        synthesis_time_budget_sec=5.0,
        synthesis_draft_tokens=64,
        synthesis_refine_tokens=64,
        top_k=3,
    )
    # Expect refined answer and synthesis metadata
    ga = getattr(res, "generated_answer", None) or (res.get("generated_answer") if isinstance(res, dict) else None)
    md = getattr(res, "metadata", None) or (res.get("metadata") if isinstance(res, dict) else {})
    assert ga == "refined answer"
    syn = md.get("synthesis") if isinstance(md, dict) else None
    assert isinstance(syn, dict) and syn.get("enabled") is True
    assert set((syn.get("durations") or {}).keys()) == {"draft", "critique", "refine"}
