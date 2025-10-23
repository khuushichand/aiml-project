import os
import pytest
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


@pytest.fixture(autouse=True)
def _testing_env():
    os.environ["TESTING"] = "true"
    os.environ["USE_REAL_OPENAI_IN_TESTS"] = "true"  # force async path
    # Allow fallback even when x-provider header is present for this mapping test suite
    os.environ["EMBEDDINGS_ALLOW_FALLBACK_WITH_HEADER"] = "true"
    yield
    os.environ.pop("TESTING", None)
    os.environ.pop("USE_REAL_OPENAI_IN_TESTS", None)
    os.environ.pop("EMBEDDINGS_ALLOW_FALLBACK_WITH_HEADER", None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.cookies.set("csrf_token", "x")
        c.headers["X-CSRF-Token"] = "x"
        c.headers["Authorization"] = "Bearer key"
        yield c


def _override_user():
    async def _f():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=False)
    return _f


@pytest.mark.unit
def test_fallback_model_mapping_openai_to_hf(client, monkeypatch):
    # Capture the model_id used for fallback call
    calls = {"args": None}

    async def fake_batch_async(texts, provider, model_id=None, dimensions=None, api_key=None, api_url=None, metadata=None):
        calls["args"] = {"provider": provider, "model_id": model_id}
        if provider == "openai":
            # simulate failure for openai to force fallback
            from fastapi import HTTPException
            raise HTTPException(status_code=503, detail="openai down")
        # for HF, return simple vectors
        return [[0.0] * 384 for _ in texts]

    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as mod
    monkeypatch.setattr(mod, "create_embeddings_batch_async", fake_batch_async, raising=True)

    app.dependency_overrides[get_request_user] = _override_user()
    r = client.post(
        "/api/v1/embeddings",
        headers={"x-provider": "openai"},
        json={"input": "fallback mapping", "model": "text-embedding-3-small"}
    )
    assert r.status_code == 200
    assert calls["args"]["provider"] == "huggingface"
    # Must map openai small to HF all-MiniLM-L6-v2 by default
    assert calls["args"]["model_id"] == "sentence-transformers/all-MiniLM-L6-v2"
