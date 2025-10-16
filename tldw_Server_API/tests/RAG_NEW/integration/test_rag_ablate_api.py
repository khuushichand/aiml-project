import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _test_mode(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")


@pytest.fixture()
def client_with_overrides(monkeypatch):
    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    async def _noop():
        return None

    # Disable RBAC enforcement to avoid DB access
    import tldw_Server_API.app.api.v1.API_Deps.auth_deps as auth_deps
    async def _no_rbac(*args, **kwargs):  # noqa: ARG001
        return None
    monkeypatch.setattr(auth_deps, "enforce_rbac_rate_limit", _no_rbac)

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[check_rate_limit] = _noop
    # Avoid DB initialization by overriding DB deps to return None
    try:
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user as _get_media_db
        from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user as _get_chacha_db
        async def _none_media_db():
            return None
        async def _none_chacha_db():
            return None
        fastapi_app.dependency_overrides[_get_media_db] = _none_media_db
        fastapi_app.dependency_overrides[_get_chacha_db] = _none_chacha_db
    except Exception:
        pass

    try:
        # Prefer disabling lifespan to avoid DB/services startup in CI; skip if not supported
        import inspect as _inspect
        if 'lifespan' in _inspect.signature(TestClient.__init__).parameters:
            with TestClient(fastapi_app, raise_server_exceptions=False, lifespan='off') as client:
                yield client
        else:
            with TestClient(fastapi_app, raise_server_exceptions=False) as client:
                yield client
    finally:
        fastapi_app.dependency_overrides.clear()


def test_rag_ablate_smoke(client_with_overrides, monkeypatch):
    client = client_with_overrides

    # Patch retrievers for both unified_pipeline and agentic_chunker to return a simple doc
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

    class FakeRetriever:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            pass
        async def retrieve(self, *args, **kwargs):  # noqa: ARG002
            return [
                Document(
                    id="m1",
                    content="Residual connections enable gradient flow and stabilize deep networks.",
                    metadata={"title": "ResNet", "source": "media_db", "ingestion_date": "2024-01-01"},
                    source=DataSource.MEDIA_DB,
                    score=0.9,
                )
            ]

    import tldw_Server_API.app.core.RAG.rag_service.agentic_chunker as ac
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up
    monkeypatch.setattr(ac, "MultiDatabaseRetriever", FakeRetriever)
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)

    # Run ablations
    resp = client.post(
        "/api/v1/rag/ablate",
        json={
            "query": "What do residual connections do?",
            "top_k": 5,
            "search_mode": "fts",
            "with_answer": False,
            "reranking_strategy": "none"
        },
    )
    assert resp.status_code == 200, resp.text
    out = resp.json()
    assert isinstance(out.get("summary"), list) and len(out["summary"]) == 4
    runs = out.get("runs", [])
    assert len(runs) == 4
    labels = [r.get("label") for r in out["summary"]]
    assert set(labels) == {"baseline", "+rerank", "agentic", "agentic_strict"}

    # Verify agentic runs advertise strategy in metadata
    agentic_runs = [r for r in runs if r.get("label") in ("agentic", "agentic_strict")]
    for r in agentic_runs:
        md = r["result"].get("metadata", {})
        assert md.get("strategy") == "agentic"


def test_rag_ablate_capabilities_smoke():
    # Quick smoke to ensure capabilities advertises new agentic knobs
    with TestClient(fastapi_app) as client:
        resp = client.get("/api/v1/rag/capabilities")
        assert resp.status_code == 200, resp.text
        data = resp.json()
        agentic = data.get("features", {}).get("agentic_chunking", {})
        params = set(agentic.get("parameters", []))
        assert {"agentic_adaptive_budgets", "agentic_coverage_target", "agentic_min_corroborating_docs"}.issubset(params)
