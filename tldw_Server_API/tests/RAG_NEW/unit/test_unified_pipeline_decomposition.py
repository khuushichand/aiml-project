"""
Unit tests for unified_rag_pipeline query decomposition behaviour.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_pipeline_query_decomposition_adds_metadata_and_docs():
    """
    When enable_query_decomposition is true and the query has multiple parts,
    the pipeline should attempt per-subquery retrieval and populate
    metadata.decomposition.
    """

    # Base documents returned for the primary query
    base_docs = [
        Document(
            id="base-1",
            content="Explain residual connections in deep networks.",
            metadata={},
            source=DataSource.MEDIA_DB,
            score=0.9,
        )
    ]
    # Documents returned for secondary subqueries
    sub_docs = [
        Document(
            id="sub-1",
            content="Dropout is a regularization technique.",
            metadata={},
            source=DataSource.MEDIA_DB,
            score=0.8,
        )
    ]

    async def _primary_retrieve(*args, **kwargs):
        return base_docs

    async def _sub_retrieve(*args, **kwargs):
        return sub_docs

    with patch(
        "tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever"
    ) as mock_retriever:
        mock_instance = MagicMock()
        # First call: base query, second call: decomposed subquery
        mock_instance.retrieve = AsyncMock(side_effect=[base_docs, sub_docs])
        mock_retriever.return_value = mock_instance

        result = await unified_rag_pipeline(
            query="Explain residual connections and dropout",
            sources=["media_db"],
            top_k=3,
            enable_query_decomposition=True,
            max_subqueries=2,
            subquery_time_budget_sec=1.0,
            subquery_doc_budget=4,
            enable_cache=False,
            enable_reranking=False,
            enable_generation=False,
        )

        assert isinstance(result, UnifiedRAGResponse)
        # Should contain both base and subquery docs (deduped, capped to top_k)
        doc_ids = {
            (d.get("id") if isinstance(d, dict) else d.id)
            for d in result.documents
        }
        assert "base-1" in doc_ids
        assert "sub-1" in doc_ids

        decomp = (result.metadata or {}).get("decomposition") or {}
        assert decomp.get("enabled") is True
        # At least one subquery entry should be present
        subs = decomp.get("subqueries") or []
        assert isinstance(subs, list)
        assert subs, "expected at least one decomposed subquery"
        assert isinstance(decomp.get("total_added"), int)
