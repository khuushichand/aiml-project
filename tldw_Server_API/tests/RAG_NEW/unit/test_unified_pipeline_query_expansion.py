"""
Unit tests for unified_rag_pipeline query expansion retrieval behavior.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_pipeline_query_expansion_retrieves_variations():
    """Expanded queries should trigger additional retrieval and merge results."""

    base_docs = [
        Document(
            id="base-1",
            content="Base result.",
            metadata={},
            source=DataSource.MEDIA_DB,
            score=0.9,
        )
    ]
    expanded_docs = [
        Document(
            id="exp-1",
            content="Expanded result.",
            metadata={},
            source=DataSource.MEDIA_DB,
            score=0.8,
        )
    ]

    async def _expander(*args, **kwargs):
        return ["expanded query"]

    with patch(
        "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever"
    ) as mock_retriever, patch(
        "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.multi_strategy_expansion",
        new=_expander,
    ):
        mock_instance = MagicMock()
        mock_instance.retrieve = AsyncMock(side_effect=[base_docs, expanded_docs])
        mock_retriever.return_value = mock_instance

        result = await unified_rag_pipeline(
            query="Base query",
            sources=["media_db"],
            search_mode="fts",
            top_k=5,
            expand_query=True,
            expansion_strategies=["synonym"],
            max_query_variations=1,
            enable_cache=False,
            enable_reranking=False,
            enable_generation=False,
        )

        assert isinstance(result, UnifiedRAGResponse)
        doc_ids = {
            (d.get("id") if isinstance(d, dict) else d.id)
            for d in result.documents
        }
        assert "base-1" in doc_ids
        assert "exp-1" in doc_ids
        assert mock_instance.retrieve.call_count == 2
