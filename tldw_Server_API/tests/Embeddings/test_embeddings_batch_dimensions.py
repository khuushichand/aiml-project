import pytest
from tldw_Server_API.app.main import app
from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import get_request_user, User


@pytest.fixture(autouse=True)
def _override_user():
    async def _user():
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=False)

    app.dependency_overrides[get_request_user] = _user
    try:
        yield
    finally:
        app.dependency_overrides.pop(get_request_user, None)


@pytest.mark.unit
def test_batch_dimensions_rejected_for_non_openai(test_client, monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as emb_mod

    monkeypatch.setattr(emb_mod, "_should_enforce_policy", lambda _user=None: False)

    resp = test_client.post(
        "/api/v1/embeddings/batch",
        json={
            "texts": ["hello"],
            "model": "sentence-transformers/all-MiniLM-L6-v2",
            "provider": "huggingface",
            "dimensions": 128,
        },
    )
    assert resp.status_code == 400
    assert "dimensions" in resp.json().get("detail", "").lower()


@pytest.mark.unit
def test_batch_dimensions_rejected_for_openai_non_3_models(test_client, monkeypatch):
    import tldw_Server_API.app.api.v1.endpoints.embeddings_v5_production_enhanced as emb_mod

    monkeypatch.setattr(emb_mod, "_should_enforce_policy", lambda _user=None: False)

    resp = test_client.post(
        "/api/v1/embeddings/batch",
        json={
            "texts": ["hello"],
            "model": "text-embedding-ada-002",
            "provider": "openai",
            "dimensions": 128,
        },
    )
    assert resp.status_code == 400
    assert "dimensions" in resp.json().get("detail", "").lower()
