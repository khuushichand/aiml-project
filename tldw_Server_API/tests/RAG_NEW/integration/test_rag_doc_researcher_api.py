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
def client_with_overrides(monkeypatch, auth_headers):
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
            with TestClient(fastapi_app, headers=auth_headers, raise_server_exceptions=False, lifespan='off') as client:
                yield client
        else:
            with TestClient(fastapi_app, headers=auth_headers, raise_server_exceptions=False) as client:
                yield client
    finally:
        fastapi_app.dependency_overrides.clear()


def test_rag_search_doc_researcher_flags(client_with_overrides, monkeypatch):
    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
    import tldw_Server_API.app.api.v1.endpoints.rag_unified as rag_ep
    import tldw_Server_API.app.core.RAG.rag_service.unified_pipeline as up

    class FakeRetriever:
        def __init__(self, *args, **kwargs):  # noqa: ARG002
            pass

        async def retrieve(
            self,
            query,
            sources=None,
            config=None,  # noqa: ARG002
            index_namespace=None,  # noqa: ARG002
            allowed_media_ids=None,  # noqa: ARG002
            allowed_note_ids=None,  # noqa: ARG002
        ):
            # Ensure follow-up retrievals reuse original sources (notes included)
            if sources is not None:
                assert DataSource.NOTES in sources
            return [
                Document(
                    id="doc1",
                    content="Unrelated content for testing evidence accumulation.",
                    metadata={"title": "Doc1", "source": "media_db", "ingestion_date": "2024-01-01"},
                    source=DataSource.MEDIA_DB,
                    score=0.2,
                )
            ]

    monkeypatch.setattr(rag_ep, "MultiDatabaseRetriever", FakeRetriever)
    monkeypatch.setattr(up, "MultiDatabaseRetriever", FakeRetriever)

    payload = {
        "query": "alpha beta gamma",
        "sources": ["media_db", "notes"],
        "search_mode": "fts",
        "enable_dynamic_granularity": True,
        "enable_evidence_accumulation": True,
        "accumulation_max_rounds": 2,
        "accumulation_time_budget_sec": 1.0,
        "enable_evidence_chains": True,
        "enable_cache": False,
        "enable_generation": False,
        "enable_reranking": False,
    }

    resp = client_with_overrides.post("/api/v1/rag/search", json=payload)
    assert resp.status_code == 200, resp.text
    data = resp.json()
    metadata = data.get("metadata", {})
    assert "granularity_routing" in metadata
    assert "evidence_accumulation" in metadata
    assert "evidence_chains" in metadata
