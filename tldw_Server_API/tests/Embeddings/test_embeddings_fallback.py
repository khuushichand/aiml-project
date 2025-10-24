import os
import asyncio
from typing import List, Optional
import pytest
from fastapi.testclient import TestClient
from fastapi import HTTPException

from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user


@pytest.fixture(autouse=True)
def _enable_testing_env():
    os.environ["TESTING"] = "true"
    yield
    os.environ.pop("TESTING", None)


@pytest.fixture
def client():
    with TestClient(app) as c:
        c.cookies.set("csrf_token", "test-csrf")
        c.headers["X-CSRF-Token"] = "test-csrf"
        c.headers["Authorization"] = "Bearer test-api-key"
        yield c


@pytest.mark.unit
def test_provider_fallback_to_hf(client, monkeypatch):
    async def override_user():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=False)

    app.dependency_overrides[get_request_user] = override_user

    # Patch the async batch creator to fail for openai and succeed for huggingface
    async def fake_batch_async(
        texts: List[str],
        provider: str,
        model_id: Optional[str] = None,
        dimensions: Optional[int] = None,
        api_key: Optional[str] = None,
        api_url: Optional[str] = None,
        metadata: Optional[dict] = None,
    ):
        if provider == "openai":
            raise HTTPException(status_code=503, detail="openai down")
        elif provider == "huggingface":
            # Return simple 384-dim zero vector to simulate HF
            return [[0.0] * 384 for _ in texts]
        raise HTTPException(status_code=400, detail="unknown provider")

    # Patch metrics to avoid registry issues
    class _MC:
        def labels(self, **kwargs):
            return self
        def inc(self, *args, **kwargs):
            return None

    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as mod
    monkeypatch.setattr(mod, "create_embeddings_batch_async", fake_batch_async, raising=True)
    monkeypatch.setattr(mod, "embedding_fallbacks_total", _MC(), raising=False)
    monkeypatch.setattr(mod, "embedding_provider_failures_total", _MC(), raising=False)

    # Disable synthetic OpenAI so the endpoint uses the async path we patched
    os.environ["USE_REAL_OPENAI_IN_TESTS"] = "true"

    # Request declares openai; should fallback to huggingface and still succeed
    payload = {
        "model": "text-embedding-3-small",
        "input": "fallback test"
    }
    r = client.post("/api/v1/embeddings", json=payload)
    assert r.status_code == 200
    data = r.json()
    # Expect model string to indicate the actual fallback model
    assert data["model"] == "huggingface:sentence-transformers/all-MiniLM-L6-v2"
    # Headers reflect fallback
    assert r.headers.get("X-Embeddings-Provider") == "huggingface"
    assert r.headers.get("X-Embeddings-Fallback-From") == "openai"
    emb = data["data"][0]["embedding"]
    assert isinstance(emb, list)
    assert len(emb) == 384


@pytest.mark.unit
def test_no_fallback_when_header_specified(client, monkeypatch):
    async def override_user():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=False)

    app.dependency_overrides[get_request_user] = override_user

    # Fail for openai, succeed for huggingface; header will disable fallback and keep failure
    async def fake_batch_async(
        texts,
        provider,
        model_id=None,
        dimensions=None,
        api_key=None,
        api_url=None,
        metadata=None,
    ):
        from fastapi import HTTPException
        if provider == "openai":
            raise HTTPException(status_code=503, detail="openai down")
        return [[0.0] * 384 for _ in texts]

    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as mod
    monkeypatch.setattr(mod, "create_embeddings_batch_async", fake_batch_async, raising=True)
    os.environ["USE_REAL_OPENAI_IN_TESTS"] = "true"

    payload = {"model": "text-embedding-3-small", "input": "no-fallback"}
    r = client.post("/api/v1/embeddings", json=payload, headers={"x-provider": "openai"})
    assert r.status_code == 503
    # No fallback headers expected
    assert r.headers.get("X-Embeddings-Provider") is None or r.headers.get("X-Embeddings-Provider") == "openai"
    assert r.headers.get("X-Embeddings-Fallback-From") is None
