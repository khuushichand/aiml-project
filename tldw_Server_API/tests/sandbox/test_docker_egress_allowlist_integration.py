from __future__ import annotations

import os
import time
import pytest
from fastapi.testclient import TestClient
from tldw_Server_API.app.core.config import clear_config_cache
from tldw_Server_API.app.main import app


pytestmark = pytest.mark.integration


def _docker_present() -> bool:


     try:
        import shutil
        return shutil.which("docker") is not None
    except Exception:
        return False


def _client(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    # Use pytest monkeypatch to avoid leaking env between tests
    monkeypatch.setenv("TEST_MODE", "1")
    # Enable real execution and granular egress enforcement
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "true")
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "false")
    monkeypatch.setenv("TLDW_SANDBOX_DOCKER_FAKE_EXEC", "0")
    monkeypatch.setenv("SANDBOX_EGRESS_ENFORCEMENT", "true")
    monkeypatch.setenv("SANDBOX_EGRESS_GRANULAR_ENFORCEMENT", "true")
    # Use CIDR allowlist for Cloudflare Anycast (HTTP 1.1.1.1)
    monkeypatch.setenv("SANDBOX_EGRESS_ALLOWLIST", "1.1.1.1/32")
    clear_config_cache()
    return TestClient(app)


@pytest.mark.skipif(
    not bool(os.environ.get("TLDW_SANDBOX_DOCKER_EGRESS_IT")),
    reason="Explicitly enable with TLDW_SANDBOX_DOCKER_EGRESS_IT=1; requires Docker + iptables",
)
def test_docker_egress_allowlist_allows_allowed_and_blocks_others(monkeypatch: pytest.MonkeyPatch) -> None:
    if not _docker_present():
        pytest.skip("docker not available on PATH")

    with _client(monkeypatch) as client:
        # Allowed: 1.1.1.1
        body_allow = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "alpine:3",
            "command": [
                "sh",
                "-lc",
                "wget -T 2 -O - http://1.1.1.1 >/dev/null",
            ],
            "timeout_sec": 30,
            "network_policy": "allowlist",
        }
        r1 = client.post("/api/v1/sandbox/runs", json=body_allow, timeout=60)
        assert r1.status_code == 200, r1.text
        s1 = r1.json()
        assert s1.get("phase") in {"completed", "failed"}
        assert s1.get("exit_code") == 0

        # Blocked: 8.8.8.8 (not in allowlist)
        body_block = {
            "spec_version": "1.0",
            "runtime": "docker",
            "base_image": "alpine:3",
            "command": [
                "sh",
                "-lc",
                "wget -T 2 -O - http://8.8.8.8 >/dev/null",
            ],
            "timeout_sec": 30,
            "network_policy": "allowlist",
        }
        r2 = client.post("/api/v1/sandbox/runs", json=body_block, timeout=60)
        assert r2.status_code == 200, r2.text
        s2 = r2.json()
        # Expect non-zero exit due to DROP
        assert s2.get("phase") in {"failed", "completed"}
        assert (s2.get("exit_code") or 1) != 0
