from types import SimpleNamespace

import pytest

from tldw_Server_API.app.api.v1.schemas.rag_schemas_unified import UnifiedRAGResponse
from tldw_Server_API.app.core.RAG.rag_service import quick_wins as qw
from tldw_Server_API.app.core.RAG.rag_service import unified_pipeline as up
from tldw_Server_API.app.core.RAG.rag_service.quick_wins import QuerySpellChecker


class _FakeChecker:
    def check_query(self, query: str):
        corrected = query.replace("teh", "the")
        return {
            "original": query,
            "corrected": corrected,
            "has_errors": corrected != query,
            "corrections": {"teh": {"correction": "the", "suggestions": ["the"]}},
        }


class _NoopDebug:
    def log(self, *_args, **_kwargs):
        return None


@pytest.mark.unit
@pytest.mark.asyncio
async def test_spell_check_query_accepts_raw_string(monkeypatch):
    monkeypatch.setattr(qw, "get_spell_checker", lambda: _FakeChecker())

    corrected = await qw.spell_check_query("teh query")

    assert corrected == "the query"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_spell_check_query_context_still_supported(monkeypatch):
    monkeypatch.setattr(qw, "get_spell_checker", lambda: _FakeChecker())
    monkeypatch.setattr(qw, "get_debug_mode", lambda: _NoopDebug())

    context = SimpleNamespace(
        config={"spell_check": {"enabled": True, "auto_correct": True}},
        query="teh query",
        metadata={},
    )

    out = await qw.spell_check_query(context)

    assert out is context
    assert context.query == "the query"
    assert context.metadata.get("original_query_before_correction") == "teh query"


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_pipeline_spell_check_no_config_attr_error(monkeypatch):
    monkeypatch.setattr(qw, "get_spell_checker", lambda: _FakeChecker())

    class _FakeMultiRetriever:
        def __init__(self, *_args, **_kwargs):
            self.retrievers = {}

        async def retrieve(self, *_args, **_kwargs):
            return []

    monkeypatch.setattr(up, "MultiDatabaseRetriever", _FakeMultiRetriever)

    result = await up.unified_rag_pipeline(
        query="teh query",
        spell_check=True,
        enable_generation=False,
        enable_reranking=False,
        enable_cache=False,
        sources=["media_db"],
        fallback_on_error=False,
    )

    assert isinstance(result, UnifiedRAGResponse)
    assert not any("no attribute 'config'" in err for err in (result.errors or []))
    assert result.metadata.get("original_query") == "teh query"
    assert result.metadata.get("corrected_query") == "the query"


@pytest.mark.unit
def test_query_spell_checker_preserves_ambiguous_media_entity_names():
    checker = QuerySpellChecker()

    frieza_result = checker.check_query("frieza new form")
    goku_result = checker.check_query("goku one inch punch on frieza")

    assert frieza_result["corrected"] == "frieza new form"
    assert frieza_result["has_errors"] is False
    assert goku_result["corrected"] == "goku one inch punch on frieza"
    assert goku_result["has_errors"] is False
