import importlib
import os

from fastapi.testclient import TestClient


def test_sandbox_public_health_no_auth(monkeypatch):


     # Ensure sandbox routes are included in the test app
    monkeypatch.setenv("TEST_MODE", "1")

    if "tldw_Server_API.app.main" in importlib.sys.modules:
        importlib.reload(importlib.sys.modules["tldw_Server_API.app.main"])  # type: ignore[arg-type]
    main = importlib.import_module("tldw_Server_API.app.main")
    app = getattr(main, "app")

    with TestClient(app) as client:
        # No auth headers supplied
        r = client.get("/api/v1/sandbox/health/public")
        assert r.status_code == 200, r.text
        data = r.json()
        assert "ok" in data
        assert "store" in data and isinstance(data["store"], dict)
        assert "redis" in data and isinstance(data["redis"], dict)
