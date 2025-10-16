import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _set_test_mode_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")


def test_rag_capabilities_agentic_features():
    # Basic smoke: capabilities exposes agentic feature block
    with TestClient(fastapi_app) as client:
        resp = client.get("/api/v1/rag/capabilities")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        features = data.get("features", {})
        assert "agentic_chunking" in features, "agentic_chunking not advertised in capabilities"
        agentic = features["agentic_chunking"]
        assert agentic.get("supported") is True
        assert "strategy" in agentic.get("parameters", []), "strategy parameter missing for agentic"
        # Defaults sanity
        defaults = agentic.get("defaults", {})
        assert defaults.get("strategy") == "standard"
        assert defaults.get("agentic_top_k_docs") == 3
        assert defaults.get("agentic_window_chars") == 1200
        assert defaults.get("agentic_max_tokens_read") == 6000
        assert defaults.get("agentic_max_tool_calls") == 8
        assert defaults.get("agentic_enable_tools") is False
        assert defaults.get("agentic_use_llm_planner") is False
        assert defaults.get("agentic_cache_ttl_sec") == 600
        # Quick start examples present
        qs = data.get("quick_start", {})
        assert "agentic_search" in qs and "ablate" in qs
        assert qs["agentic_search"]["body"]["strategy"] == "agentic"


@pytest.fixture()
def client_with_agentic_overrides(monkeypatch):
    # Override auth dependencies: accept any test user; disable rate limits
    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    async def _noop():
        return None

    # Monkeypatch RBAC enforcer to a no-op to avoid DB access
    import tldw_Server_API.app.api.v1.API_Deps.auth_deps as auth_deps
    async def _no_rbac(*args, **kwargs):  # noqa: ARG001
        return None
    monkeypatch.setattr(auth_deps, "enforce_rbac_rate_limit", _no_rbac)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[check_rate_limit] = _noop

    try:
        with TestClient(fastapi_app) as client:
            yield client
    finally:
        fastapi_app.dependency_overrides.clear()


def test_rag_agentic_search_smoke_api(client_with_agentic_overrides, monkeypatch):
    client = client_with_agentic_overrides

    # Patch retriever used inside agentic pipeline to return a single simple doc
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

    class FakeRetriever:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            pass

        async def retrieve(self, *args, **kwargs):  # noqa: ARG002
            return [
                Document(
                    id="m1",
                    content=(
                        "ResNet uses residual connections. Residual links help gradient flow and enable deeper networks."
                    ),
                    metadata={"title": "ResNet", "source": "media_db", "ingestion_date": "2024-01-01"},
                    source=DataSource.MEDIA_DB,
                    score=0.9,
                )
            ]

    import tldw_Server_API.app.core.RAG.rag_service.agentic_chunker as ac
    monkeypatch.setattr(ac, "MultiDatabaseRetriever", FakeRetriever)

    # Issue agentic search request (no generation to avoid LLM calls)
    payload = {
        "query": "How do residual connections help training?",
        "strategy": "agentic",
        "search_mode": "fts",
        "top_k": 5,
        "enable_generation": False,
        "agentic_enable_tools": True,
        "agentic_max_tool_calls": 3,
    }
    resp = client.post("/api/v1/rag/search", json=payload)
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert isinstance(out.get("documents"), list) and len(out["documents"]) >= 1
    # First document should be the synthetic agentic chunk
    first = out["documents"][0]
    meta = first.get("metadata", {})
    assert meta.get("source") == "agentic"
    # Top-level metadata should advertise agentic strategy
    assert out.get("metadata", {}).get("strategy") == "agentic"
