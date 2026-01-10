import pytest


def test_vlm_backends_endpoint():
    try:
        from fastapi.testclient import TestClient
        from tldw_Server_API.app.main import app
    except Exception as e:
        pytest.skip(f"FastAPI or app not importable: {e}")

    client = TestClient(app)
    resp = client.get("/api/v1/vlm/backends")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, dict)
