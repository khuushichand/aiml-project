"""
Unit test: unified_rag_pipeline attaches post-verification metadata and
honors a patched verifier's repaired answer.
"""

import asyncio
import pytest

from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
from tldw_Server_API.app.core.RAG.rag_service import unified_pipeline as up


class _FakeVerifier:
    def __init__(self, *args, **kwargs):
        pass

    async def verify_and_maybe_fix(self, **kwargs):  # noqa: D401
        class _Out:
            unsupported_ratio = 0.3
            total_claims = 10
            unsupported_count = 3
            fixed = True
            reason = "fixed"
            new_answer = "repaired answer"
            claims = None
            summary = None

        return _Out()


class _FakeAnswerGen:
    def __init__(self, *args, **kwargs):
        pass

    async def generate(self, **kwargs):
        return {"answer": "draft answer"}


class _FakeRetriever:
    def __init__(self, *args, **kwargs):
        self.retrievers = {DataSource.MEDIA_DB: self}

    async def retrieve(self, **kwargs):
        return [
            Document(id="d1", content="alpha", metadata={"source": DataSource.MEDIA_DB}),
            Document(id="d2", content="beta", metadata={"source": DataSource.MEDIA_DB}),
        ]


@pytest.mark.unit
@pytest.mark.asyncio
async def test_unified_pipeline_post_verification_metadata(monkeypatch):
    # Patch verifier, generator, and retriever to fast fakes
    monkeypatch.setattr(up, "PostGenerationVerifier", _FakeVerifier, raising=True)
    monkeypatch.setattr(up, "AnswerGenerator", _FakeAnswerGen, raising=True)

    class _RetrievalConfig:  # minimal placeholder used by pipeline
        def __init__(self, *args, **kwargs):
            pass

    monkeypatch.setattr(up, "RetrievalConfig", _RetrievalConfig, raising=True)
    monkeypatch.setattr(up, "MultiDatabaseRetriever", _FakeRetriever, raising=True)

    res = await up.unified_rag_pipeline(
        query="what is rag?",
        sources=["media_db"],
        enable_generation=True,
        enable_post_verification=True,
        adaptive_max_retries=1,
        adaptive_unsupported_threshold=0.15,
        top_k=5,
    )

    # Metadata should include post_verification block
    pv = res.metadata.get("post_verification")
    assert isinstance(pv, dict)
    assert pv.get("unsupported_ratio") == 0.3
    assert pv.get("total_claims") == 10
    assert pv.get("unsupported_count") == 3
    assert pv.get("fixed") is True
    assert pv.get("reason") == "fixed"

    # Generated answer should be updated to repaired answer
    assert res.generated_answer == "repaired answer"
