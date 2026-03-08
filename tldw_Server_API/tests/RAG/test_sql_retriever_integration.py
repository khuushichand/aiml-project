import pytest

from tldw_Server_API.app.core.RAG.rag_service.types import DataSource, Document


class _StubRetrievalConfig:
    def __init__(self, **kwargs):
        self.max_results = kwargs.get("max_results", 10)
        self.min_score = kwargs.get("min_score", 0.0)
        self.use_fts = kwargs.get("use_fts", True)
        self.use_vector = kwargs.get("use_vector", False)
        self.include_metadata = kwargs.get("include_metadata", True)
        self.fts_level = kwargs.get("fts_level", "media")


class _CapturingRetriever:
    captured_sources = None

    def __init__(self, *args, **kwargs):
        _ = args
        _ = kwargs

    async def retrieve(self, query: str, *, sources=None, config=None, **kwargs):
        _ = query
        _ = config
        _ = kwargs
        _CapturingRetriever.captured_sources = list(sources or [])
        return [
            Document(
                id="sql-doc-1",
                content='{"id": 1}',
                source=DataSource.SQL,
                metadata={"source": "sql"},
                score=1.0,
            )
        ]


@pytest.mark.asyncio
async def test_unified_rag_accepts_sql_source(monkeypatch):
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up

    monkeypatch.setattr(up, "MultiDatabaseRetriever", _CapturingRetriever, raising=False)
    monkeypatch.setattr(up, "RetrievalConfig", _StubRetrievalConfig, raising=False)

    result = await up.unified_rag_pipeline(
        query="sql question",
        sources=["sql"],
        enable_generation=False,
        search_mode="fts",
        top_k=5,
    )

    assert result is not None
    assert _CapturingRetriever.captured_sources == [DataSource.SQL]


@pytest.mark.asyncio
async def test_unified_rag_rejects_unknown_source(monkeypatch):
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up

    monkeypatch.setattr(up, "MultiDatabaseRetriever", _CapturingRetriever, raising=False)
    monkeypatch.setattr(up, "RetrievalConfig", _StubRetrievalConfig, raising=False)

    result = await up.unified_rag_pipeline(
        query="unknown source question",
        sources=["bogus_source"],
        enable_generation=False,
        search_mode="fts",
        top_k=5,
    )

    assert result.errors
    assert any("invalid_source" in err.lower() for err in result.errors)
