from __future__ import annotations

import os
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _client() -> TestClient:
    os.environ.setdefault("TEST_MODE", "1")
    return TestClient(app)


def test_runtimes_contains_queue_fields() -> None:
    with _client() as client:
        r = client.get("/api/v1/sandbox/runtimes")
        assert r.status_code == 200
        js = r.json()
        assert isinstance(js.get("runtimes"), list) and js["runtimes"], "No runtimes returned"
        for rt in js["runtimes"]:
            # These fields should be present per PRD
            assert "queue_max_length" in rt
            assert "queue_ttl_sec" in rt
