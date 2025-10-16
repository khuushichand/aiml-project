import asyncio
import time

import pytest

from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.RAG.rag_service.agentic_chunker import (
    _assemble_ephemeral_chunk,
    AgenticConfig,
    agentic_rag_pipeline,
)


def make_doc(doc_id: str, content: str, title: str = "Doc") -> Document:
    return Document(
        id=doc_id,
        content=content,
        metadata={"title": title, "source": "media_db", "ingestion_date": "2024-01-01"},
        source=DataSource.MEDIA_DB,
        score=0.9,
    )


def test_assemble_ephemeral_chunk_basic():
    query = "dropout prevents overfitting"
    content = (
        "Deep learning models often overfit. One method is dropout, which randomly removes units during training. "
        "Dropout helps prevent overfitting by reducing co-adaptation of neurons."
    )
    docs = [make_doc("d1", content, title="DL")]

    cfg = AgenticConfig(top_k_docs=1, window_chars=400, max_tokens_read=500)
    chunk, prov = _assemble_ephemeral_chunk(docs, query, cfg)

    assert "dropout" in chunk.lower()
    assert prov and prov[0]["document_id"] == "d1"
    assert prov[0]["start"] >= 0 and prov[0]["end"] > prov[0]["start"]


@pytest.mark.asyncio
async def test_agentic_pipeline_cache_hit(monkeypatch):
    # Prepare fake docs returned by retriever
    query = "batch normalization effect"
    content = (
        "Batch Normalization reduces internal covariate shift and can speed up training. "
        "It also allows for higher learning rates."
    )
    docs = [make_doc("m1", content, title="BN")]

    calls = {"count": 0}

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass

        async def retrieve(self, *args, **kwargs):
            calls["count"] += 1
            return docs

    # Patch the retriever used inside agentic_chunker
    import tldw_Server_API.app.core.RAG.rag_service.agentic_chunker as ac
    monkeypatch.setattr(ac, "MultiDatabaseRetriever", FakeRetriever)

    # First call (miss -> assemble -> cache)
    res1 = await agentic_rag_pipeline(
        query=query,
        sources=["media_db"],
        media_db_path=None,
        notes_db_path=None,
        character_db_path=None,
        search_mode="fts",
        agentic=AgenticConfig(top_k_docs=1, cache_ttl_sec=60),
        enable_generation=False,
        enable_citations=False,
    )
    assert res1.documents and res1.documents[0].content
    assert res1.cache_hit is False
    assert calls["count"] == 1

    # Second call with same query/docs (hit)
    res2 = await agentic_rag_pipeline(
        query=query,
        sources=["media_db"],
        media_db_path=None,
        notes_db_path=None,
        character_db_path=None,
        search_mode="fts",
        agentic=AgenticConfig(top_k_docs=1, cache_ttl_sec=60),
        enable_generation=False,
        enable_citations=False,
    )
    assert res2.cache_hit is True
    assert calls["count"] == 2  # retriever still called, but assemble path uses cache
    assert res2.documents[0].content == res1.documents[0].content


@pytest.mark.asyncio
async def test_agentic_tool_loop_heuristic(monkeypatch):
    # Ensure tool loop can run and returns non-empty chunk around hits
    query = "transformer attention"
    content = (
        "Introduction. The Transformer architecture relies on attention mechanisms.\n"
        "Methods. Multi-head attention allows the model to jointly attend to information."
    )
    docs = [make_doc("t1", content, title="Transformer")]

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass
        async def retrieve(self, *args, **kwargs):
            return docs

    import tldw_Server_API.app.core.RAG.rag_service.agentic_chunker as ac
    monkeypatch.setattr(ac, "MultiDatabaseRetriever", FakeRetriever)

    res = await agentic_rag_pipeline(
        query=query,
        sources=["media_db"],
        search_mode="hybrid",
        agentic=AgenticConfig(top_k_docs=1, enable_tools=True, max_tool_calls=4, time_budget_sec=2.0),
        enable_generation=False,
        enable_citations=False,
    )
    assert res.documents and len(res.documents[0].content) > 0

