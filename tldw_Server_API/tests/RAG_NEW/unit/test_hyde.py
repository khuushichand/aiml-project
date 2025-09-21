import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_pipeline_with_hyde_merges_results():
    """Ensure HyDE path runs and merged results are returned when enabled."""
    base_docs = [
        Document(id="base1", content="Base A", metadata={}, source=DataSource.MEDIA_DB, score=0.2),
        Document(id="base2", content="Base B", metadata={}, source=DataSource.MEDIA_DB, score=0.1),
    ]
    hyde_docs = [
        Document(id="hyde1", content="HyDE A", metadata={}, source=DataSource.MEDIA_DB, score=0.9),
        Document(id="hyde2", content="HyDE B", metadata={}, source=DataSource.MEDIA_DB, score=0.8),
    ]

    # Fake retriever that returns baseline docs and offers a MEDIA_DB retriever with retrieve_hybrid
    class _FakeMediaRetriever:
        async def retrieve_hybrid(self, *args, **kwargs):
            # Ensure HyDE vector was provided via kwargs for vector search
            assert "query_vector" in kwargs
            return hyde_docs

    class _FakeMultiRetriever:
        def __init__(self, *args, **kwargs):
            self.retrievers = {DataSource.MEDIA_DB: _FakeMediaRetriever()}
        async def retrieve(self, *args, **kwargs):
            return base_docs

    with patch("tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever", _FakeMultiRetriever), \
         patch("tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.generate_hypothetical_answer", return_value="Hypo answer"), \
         patch("tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.hyde_embed_text", new=AsyncMock(return_value=[0.1, 0.2, 0.3])):

        result = await unified_rag_pipeline(
            query="test hyde",
            sources=["media_db"],
            top_k=10,
            enable_hyde=True,
            adaptive_hybrid_weights=False,
        )

        # Response shape
        from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse
        assert isinstance(result, UnifiedRAGResponse)
        # HyDE metadata present
        assert result.metadata.get("hyde_applied") is True
        assert result.metadata.get("hyde_merged_count") == len(hyde_docs)
        # Documents include both baseline and hyde docs (dedup by id)
        ids = {d["id"] for d in result.documents}
        for d in base_docs + hyde_docs:
            assert d.id in ids
