import os
import base64
import numpy as np
import pytest
from fastapi.testclient import TestClient
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
def test_single_token_array_input(client):
    async def override_user():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=False)

    app.dependency_overrides[get_request_user] = override_user

    payload = {
        "model": "text-embedding-3-small",
        "input": [101, 102, 103, 104]
    }
    r = client.post("/api/v1/embeddings", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) == 1
    emb = data["data"][0]["embedding"]
    assert isinstance(emb, list) and len(emb) > 0


@pytest.mark.unit
def test_batch_token_arrays_input_base64(client):
    async def override_user():
        from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User
        return User(id=1, username="u", email="u@x", is_active=True, is_admin=False)

    app.dependency_overrides[get_request_user] = override_user

    payload = {
        "model": "text-embedding-3-small",
        "input": [[101, 102], [103, 104, 105]],
        "encoding_format": "base64",
        "dimensions": 128
    }
    r = client.post("/api/v1/embeddings", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["data"]) == 2
    for item in data["data"]:
        b64 = item["embedding"]
        raw = np.frombuffer(base64.b64decode(b64), dtype=np.float32)
        # Should match requested dimensions
        assert len(raw) == 128
