import os
import sys
import importlib
from fastapi.testclient import TestClient


def _make_app():
    # Ensure predictable single-user auth and enable tools routes
    os.environ.setdefault("TEST_MODE", "1")
    os.environ.setdefault("ROUTES_ENABLE", "tools")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")
    os.environ.setdefault("SINGLE_USER_API_KEY", "test-api-key-12345")

    # Reload app module to pick up env in case prior imports exist
    if "tldw_Server_API.app.main" in sys.modules:
        importlib.reload(sys.modules["tldw_Server_API.app.main"])  # type: ignore[arg-type]
    m = importlib.import_module("tldw_Server_API.app.main")
    return getattr(m, "app")


def test_tools_list_and_execute_dry_run():
    app = _make_app()
    headers = {"X-API-KEY": "test-api-key-12345"}

    with TestClient(app) as client:
        # List tools
        resp = client.get("/api/v1/tools", headers=headers)
        assert resp.status_code == 200, resp.text
        data = resp.json()
        assert isinstance(data, dict)
        assert "tools" in data and isinstance(data["tools"], list)

        # Pick a tool if available and validate via dry_run
        picked = None
        for t in data["tools"]:
            if isinstance(t, dict) and t.get("name"):
                picked = t["name"]
                break

        if picked:
            exec_resp = client.post(
                "/api/v1/tools/execute",
                json={"tool_name": picked, "arguments": {}, "dry_run": True},
                headers=headers,
            )
            assert exec_resp.status_code == 200, exec_resp.text
            payload = exec_resp.json()
            assert payload.get("ok") is True
            assert isinstance(payload.get("result"), dict)
            assert payload["result"].get("validated") is True
        else:
            # If no tools are registered, the list should be empty
            assert data["tools"] == []

