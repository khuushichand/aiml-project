from __future__ import annotations

import os
from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def _setup_env():
    os.environ["AUTH_MODE"] = "single_user"
    os.environ["SINGLE_USER_API_KEY"] = "unit-test-api-key-pricing"


def test_admin_reload_pricing_catalog_smoke():
    _setup_env()

    headers = {"X-API-KEY": os.environ["SINGLE_USER_API_KEY"]}
    with TestClient(app, headers=headers) as client:
        r = client.post("/api/v1/admin/llm-usage/pricing/reload")
        assert r.status_code == 200, r.text
        data = r.json()
        assert isinstance(data, dict) and data.get("status") == "ok"
