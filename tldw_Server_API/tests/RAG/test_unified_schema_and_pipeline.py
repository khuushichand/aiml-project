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


def test_unified_schema_query_decomposition_fields():
    """UnifiedRAGRequest should accept query decomposition fields."""
    from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest

    payload = {
        "query": "Explain residual connections and dropout",
        "max_query_variations": 2,
        "enable_query_decomposition": True,
        "max_subqueries": 3,
        "subquery_time_budget_sec": 2.5,
        "subquery_doc_budget": 6,
        "subquery_max_concurrency": 2,
    }
    req = UnifiedRAGRequest(**payload)
    assert req.max_query_variations == 2
    assert req.enable_query_decomposition is True
    assert req.max_subqueries == 3
    assert req.subquery_time_budget_sec == pytest.approx(2.5)
    assert req.subquery_doc_budget == 6
    assert req.subquery_max_concurrency == 2


def test_unified_batch_schema_query_decomposition_fields():
    """UnifiedBatchRequest should accept query decomposition fields."""
    from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedBatchRequest

    payload = {
        "queries": ["q1", "q2"],
        "max_query_variations": 2,
        "enable_query_decomposition": True,
        "max_subqueries": 2,
        "subquery_time_budget_sec": 1.5,
        "subquery_doc_budget": 4,
        "subquery_max_concurrency": 2,
    }
    req = UnifiedBatchRequest(**payload)
    assert req.max_query_variations == 2
    assert req.enable_query_decomposition is True
    assert req.max_subqueries == 2
    assert req.subquery_time_budget_sec == pytest.approx(1.5)
    assert req.subquery_doc_budget == 4
    assert req.subquery_max_concurrency == 2


@pytest.mark.asyncio
async def test_unified_pipeline_invalid_query_returns_result():
    """Invalid/empty query should return a UnifiedSearchResult with an error, not raise or return other types."""
    from tldw_Server_API.app.core.RAG.rag_service.unified_pipeline import unified_rag_pipeline
    from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse

    result = await unified_rag_pipeline(query="")
    assert isinstance(result, UnifiedRAGResponse)
    assert result.generated_answer == "Invalid query"
    assert result.errors and any("Invalid query" in e for e in result.errors)
