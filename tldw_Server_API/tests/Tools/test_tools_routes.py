from __future__ import annotations

import os
import pytest


@pytest.mark.unit
def test_tools_list(client_user_only):
    # Ensure tools route is enabled (config.txt sets enable = tools; env can override)
    os.environ.setdefault("ROUTES_ENABLE", "tools")

    r = client_user_only.get("/api/v1/tools")
    assert r.status_code == 200, r.text
    data = r.json()
    assert isinstance(data, dict)
    assert "tools" in data and isinstance(data["tools"], list)


@pytest.mark.unit
def test_tools_execute_dry_run_when_available(client_user_only):
    os.environ.setdefault("ROUTES_ENABLE", "tools")
    # Promote deterministic module autoload in startup (Media module)
    os.environ.setdefault("TEST_MODE", "1")

    # List to pick a tool name if present
    r = client_user_only.get("/api/v1/tools")
    assert r.status_code == 200, r.text
    tools = r.json().get("tools", [])

    # If no tools registered, just assert the shape (environment-dependent)
    if not tools:
        assert isinstance(tools, list)
        return

    picked = None
    for t in tools:
        if isinstance(t, dict) and t.get("name"):
            picked = t["name"]
            break

    if picked:
        resp = client_user_only.post(
            "/api/v1/tools/execute",
            json={"tool_name": picked, "arguments": {}, "dry_run": True},
        )
        assert resp.status_code == 200, resp.text
        payload = resp.json()
        assert payload.get("ok") is True
        assert isinstance(payload.get("result"), dict)
        assert payload["result"].get("validated") is True
