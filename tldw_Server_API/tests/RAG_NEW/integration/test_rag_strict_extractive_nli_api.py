import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _enable_test_mode(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")


def test_unified_endpoint_strict_extractive_with_nli_gate(monkeypatch):
    # Patch retriever to return one document with the keyword and short sentences
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

    class FakeRetriever:
        def __init__(self, *args, **kwargs):
            pass
        async def retrieve(self, *args, **kwargs):
            return [
                Document(id="m1", content="RAG answers are grounded. It aims to be factual.", metadata={"source": "media_db"}, source=DataSource.MEDIA_DB, score=0.9)
            ]

    import tldw_Server_API.app.api.v1.endpoints.rag_unified as rag_ep
    monkeypatch.setattr(rag_ep, "MultiDatabaseRetriever", FakeRetriever)

    # Patch hard citations to claim incomplete coverage (to ensure that path still records metadata)
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up
    monkeypatch.setattr(up, "build_hard_citations", lambda *a, **k: {"coverage": 0.6, "sentences": []})

    # Patch PostGenerationVerifier to return low confidence per NLI
    class _FakeOutcome:
        unsupported_ratio = 0.7
        total_claims = 5
        unsupported_count = 3
        fixed = False
        reason = "low_confidence"
        new_answer = None
        claims = None
        summary = None

    class _FakeVerifier:
        def __init__(self, *_, **__):
            pass
        async def verify_and_maybe_fix(self, *_, **__):
            return _FakeOutcome()

    monkeypatch.setattr(up, "PostGenerationVerifier", _FakeVerifier)

    from tldw_Server_API.app.core.AuthNZ.settings import get_settings
    headers = {"X-API-KEY": get_settings().SINGLE_USER_API_KEY}
    with TestClient(fastapi_app) as client:
        # Request: strict extractive + NLI verification + decline on low confidence
        payload = {
            "query": "What is RAG?",
            "enable_generation": True,
            "strict_extractive": True,
            "enable_post_verification": True,
            "enable_claims": True,
            "adaptive_unsupported_threshold": 0.2,
            "low_confidence_behavior": "decline",
            "sources": ["media_db"],
        }
        resp = client.post("/api/v1/rag/search", json=payload, headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        # Basic shape checks to ensure endpoint runs with strict_extractive + post-verification enabled
        assert data.get("query") == payload["query"]
        assert isinstance(data.get("documents"), list)
