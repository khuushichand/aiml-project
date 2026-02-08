import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user
from tldw_Server_API.app.api.v1.API_Deps.auth_deps import check_rate_limit


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _set_test_mode_env(monkeypatch):
    monkeypatch.setenv("TEST_MODE", "1")
    monkeypatch.setenv("RAG_DEFAULT_LLM_PROVIDER", "test-provider")
    monkeypatch.setenv("RAG_DEFAULT_LLM_MODEL", "default-model")


@pytest.fixture()
def client_with_stream_overrides(monkeypatch, auth_headers):
    async def override_user():
        return User(id=1, username="tester", email=None, is_active=True)

    async def _noop():
        return None

    fastapi_app.dependency_overrides[get_request_user] = override_user
    fastapi_app.dependency_overrides[check_rate_limit] = _noop

    try:
        from tldw_Server_API.app.api.v1.API_Deps.DB_Deps import get_media_db_for_user as _get_media_db
        from tldw_Server_API.app.api.v1.API_Deps.ChaCha_Notes_DB_Deps import get_chacha_db_for_user as _get_chacha_db

        class StubDB:
            def __init__(self, path: str):
                self.db_path = path

        async def _stub_media_db():
            return StubDB("stub_media.db")

        async def _stub_chacha_db():
            return StubDB("stub_chacha.db")

        fastapi_app.dependency_overrides[_get_media_db] = _stub_media_db
        fastapi_app.dependency_overrides[_get_chacha_db] = _stub_chacha_db
    except Exception:
        pass

    with TestClient(fastapi_app, headers=auth_headers) as client:
        yield client

    fastapi_app.dependency_overrides.clear()


def test_rag_streaming_parity_generation_and_hybrid_sources(monkeypatch, client_with_stream_overrides):


    from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource
    import tldw_Server_API.app.api.v1.endpoints.rag_unified as rag_ep

    captured = {"retrieve_kwargs": None, "generation_config": None}

    class StubRetriever:
        def __init__(self, *args, **kwargs):
            self.retrievers = {}

        async def retrieve(self, query, **kwargs):
            captured["retrieve_kwargs"] = {"query": query, **kwargs}
            return [
                Document(
                    id="doc-1",
                    content="Context content",
                    metadata={"title": "Doc"},
                    source=DataSource.MEDIA_DB,
                    score=0.9,
                )
            ]

    async def fake_generate_streaming_response(context, **kwargs):  # noqa: ANN001
        captured["generation_config"] = context.config.get("generation")

        async def _gen():
            yield "chunk"

        context.stream_generator = _gen()
        context.metadata = {"streaming": True}
        return context

    monkeypatch.setattr(rag_ep, "MultiDatabaseRetriever", StubRetriever)
    monkeypatch.setattr(rag_ep, "generate_streaming_response", fake_generate_streaming_response)

    payload = {
        "query": "Hybrid streaming parity",
        "search_mode": "hybrid",
        "sources": ["media_db", "notes"],
        "enable_generation": True,
        "top_k": 7,
        "min_score": 0.12,
        "generation_model": "explicit-model",
        "generation_prompt": "concise",
        "max_generation_tokens": 256,
    }

    with client_with_stream_overrides.stream("POST", "/api/v1/rag/search/stream", json=payload) as resp:
        assert resp.status_code == 200
        next(resp.iter_lines(), None)

    retrieve_kwargs = captured["retrieve_kwargs"]
    assert retrieve_kwargs is not None
    config = retrieve_kwargs.get("config")
    assert config.max_results == 7
    assert config.min_score == 0.12
    assert config.use_fts is True
    assert config.use_vector is True
    sources = retrieve_kwargs.get("sources")
    assert DataSource.MEDIA_DB in sources
    assert DataSource.NOTES in sources

    generation_config = captured["generation_config"]
    assert generation_config["provider"] == "test-provider"
    assert generation_config["model"] == "explicit-model"
    assert generation_config["max_tokens"] == 256
    assert generation_config["prompt_template"] == "concise"
    assert generation_config["streaming"] is True


def test_rag_streaming_generation_provider_override(monkeypatch, client_with_stream_overrides):
    import tldw_Server_API.app.api.v1.endpoints.rag_unified as rag_ep

    captured = {"generation_config": None}

    class StubRetriever:
        def __init__(self, *args, **kwargs):
            self.retrievers = {}

        async def retrieve(self, query, **kwargs):
            from tldw_Server_API.app.core.RAG.rag_service.types import Document, DataSource

            return [
                Document(
                    id="doc-1",
                    content="Context content",
                    metadata={"title": "Doc"},
                    source=DataSource.MEDIA_DB,
                    score=0.9,
                )
            ]

    async def fake_generate_streaming_response(context, **kwargs):  # noqa: ANN001
        captured["generation_config"] = context.config.get("generation")

        async def _gen():
            yield "chunk"

        context.stream_generator = _gen()
        context.metadata = {"streaming": True}
        return context

    monkeypatch.setattr(rag_ep, "MultiDatabaseRetriever", StubRetriever)
    monkeypatch.setattr(rag_ep, "generate_streaming_response", fake_generate_streaming_response)

    payload = {
        "query": "Provider override parity",
        "search_mode": "hybrid",
        "sources": ["media_db"],
        "enable_generation": True,
        "generation_provider": "groq",
        "generation_model": "llama-3.3-70b-versatile",
    }

    with client_with_stream_overrides.stream("POST", "/api/v1/rag/search/stream", json=payload) as resp:
        assert resp.status_code == 200
        next(resp.iter_lines(), None)

    generation_config = captured["generation_config"]
    assert generation_config is not None
    assert generation_config["provider"] == "groq"
    assert generation_config["model"] == "llama-3.3-70b-versatile"
