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


def test_egress_allowlist_supported_when_enforced(monkeypatch) -> None:
    # Ensure app is in test mode and config cache is fresh
    os.environ.setdefault("TEST_MODE", "1")
    os.environ["SANDBOX_STORE_BACKEND"] = "memory"
    clear_config_cache()
    # Flip enforcement on the live service instance to avoid re-importing app
    import tldw_Server_API.app.api.v1.endpoints.sandbox as sandbox_ep
    sandbox_ep._service.policy.cfg.egress_enforcement = True  # type: ignore[attr-defined]
    with TestClient(app) as client:
        r = client.get("/api/v1/sandbox/runtimes")
        assert r.status_code == 200
        data = r.json()
        # Find docker entry and assert flag is true
        docker = next((rt for rt in data.get("runtimes", []) if rt.get("name") == "docker"), None)
        assert docker is not None
        assert docker.get("egress_allowlist_supported") is True


def test_runtimes_notes_reflect_granular_allowlist() -> None:
    os.environ.setdefault("TEST_MODE", "1")
    os.environ["SANDBOX_STORE_BACKEND"] = "memory"
    os.environ["SANDBOX_EGRESS_ENFORCEMENT"] = "true"
    os.environ["SANDBOX_EGRESS_GRANULAR_ENFORCEMENT"] = "true"
    clear_config_cache()
    with TestClient(app) as client:
        r = client.get("/api/v1/sandbox/runtimes")
        assert r.status_code == 200
        data = r.json()
        docker = next((rt for rt in data.get("runtimes", []) if rt.get("name") == "docker"), None)
        assert docker is not None
        assert isinstance(docker.get("notes"), str) and "Granular egress allowlist" in docker["notes"]
