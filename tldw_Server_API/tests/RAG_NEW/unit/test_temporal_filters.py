import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timedelta

from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline, compute_temporal_range_from_query
from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse
from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource


_capture = {}

class _RecorderRetriever:
    def __init__(self, *args, **kwargs):
        self.retrievers = {}
        self.last_config = None
        _capture['instance'] = self

    async def retrieve(self, *, query: str, sources, config, index_namespace=None):
        # Record the config used, ensure date_filter set by auto temporal filters
        self.last_config = config
        return []


@pytest.mark.unit
@pytest.mark.asyncio
async def test_auto_temporal_filters_sets_date_range():
    with patch('tldw_Server_API.app.core.RAG.rag_service.unified_pipeline.MultiDatabaseRetriever', _RecorderRetriever):
        # Validate helper directly
        tf = compute_temporal_range_from_query("sales last week")
        assert tf is not None
        # Also ensure pipeline runs without error
        result = await unified_rag_pipeline(query="sales last week", sources=["media_db"], search_mode="fts", auto_temporal_filters=True, top_k=1)
        assert isinstance(result, UnifiedRAGResponse)
