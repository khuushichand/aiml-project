from __future__ import annotations

from typing import Any, Dict, List

from fastapi.testclient import TestClient

from tldw_Server_API.app.main import app


def test_user_profile_update_emits_audit(auth_headers, monkeypatch) -> None:
    calls: List[Dict[str, Any]] = []

    async def _stub_emit(*_args, **kwargs):
        calls.append(kwargs)

    monkeypatch.setattr(
        "tldw_Server_API.app.api.v1.endpoints.users._emit_user_profile_audit_event",
        _stub_emit,
    )

    with TestClient(app) as client:
        resp = client.patch(
            "/api/v1/users/me/profile",
            headers=auth_headers,
            json={"updates": [{"key": "preferences.ui.theme", "value": "audit-test"}]},
        )
        assert resp.status_code == 200

    assert calls
    assert calls[0].get("dry_run") is False
