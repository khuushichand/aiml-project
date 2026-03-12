import pytest

from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGRequest


def test_rag_sources_accept_sql() -> None:
    req = UnifiedRAGRequest(query="q", sources=["sql"])
    assert req.sources == ["sql"]


def test_rag_sources_reject_unknown() -> None:
    with pytest.raises(ValueError):
        UnifiedRAGRequest(query="q", sources=["bogus"])
