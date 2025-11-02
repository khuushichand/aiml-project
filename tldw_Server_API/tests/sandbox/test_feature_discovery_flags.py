from __future__ import annotations

import os
from fastapi.testclient import TestClient
from tldw_Server_API.app.core.config import clear_config_cache
from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    # Advertise a specific store backend
    os.environ["SANDBOX_STORE_BACKEND"] = "memory"
    clear_config_cache()
    return TestClient(app)


def test_runtimes_include_capability_flags_and_store_mode() -> None:
    with _client() as client:
        r = client.get("/api/v1/sandbox/runtimes")
        assert r.status_code == 200
        data = r.json()
        assert isinstance(data.get("runtimes"), list) and data["runtimes"]
        for rt in data["runtimes"]:
            assert "interactive_supported" in rt
            assert "egress_allowlist_supported" in rt
            assert "store_mode" in rt
            assert rt["store_mode"] in {"memory", "sqlite", "cluster", "unknown"}
