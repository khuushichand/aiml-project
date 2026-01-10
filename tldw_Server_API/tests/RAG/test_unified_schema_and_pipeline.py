import pytest


def test_unified_schema_alias_min_relevance_score():
    """UnifiedRAGRequest should accept legacy alias 'min_relevance_score' and map to 'min_score'."""
    from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest

    payload = {
        "query": "test",
        "min_relevance_score": 0.42,
    }
    req = UnifiedRAGRequest(**payload)
    assert hasattr(req, "min_score")
    assert req.min_score == pytest.approx(0.42)


@pytest.mark.asyncio
async def test_unified_pipeline_invalid_query_returns_result():
    """Invalid/empty query should return a UnifiedSearchResult with an error, not raise or return other types."""
    from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
    from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse

    result = await unified_rag_pipeline(query="")
    assert isinstance(result, UnifiedRAGResponse)
    assert result.generated_answer == "Invalid query"
    assert result.errors and any("Invalid query" in e for e in result.errors)
