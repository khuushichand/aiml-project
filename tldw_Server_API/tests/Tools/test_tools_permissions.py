from __future__ import annotations

import os
import importlib
from fastapi.testclient import TestClient
import pytest


@pytest.mark.unit
def test_tools_execute_forbidden_without_permission_multi_user():
    # Force multi-user mode and enable tools route
    os.environ["AUTH_MODE"] = "multi_user"
    os.environ["ROUTES_ENABLE"] = ",".join(filter(None, {os.getenv("ROUTES_ENABLE", ""), "tools"}))
    # Provide a valid JWT secret for multi-user settings initialization
    os.environ["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY", "test-secret-jwt-key-please-change-1234567890-EXTRA")
    os.environ.setdefault("OTEL_SDK_DISABLED", "true")

    # Reset AuthNZ settings singleton so env takes effect
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    reset_settings()

    # Reload app to rebuild with new settings
    if "tldw_Server_API.app.main" in importlib.sys.modules:
        importlib.reload(importlib.sys.modules["tldw_Server_API.app.main"])  # type: ignore[arg-type]
    main = importlib.import_module("tldw_Server_API.app.main")
    app = getattr(main, "app")

    # Override request user to a non-admin, no-permission user
    from tldw_Server_API.app.core.AuthNZ.User_DB_Handling import User, get_request_user

    async def _override_user() -> User:
        return User(id=123, username="nope", email=None, is_active=True, roles=[], permissions=[], is_admin=False)

    app.dependency_overrides[get_request_user] = _override_user

    try:
        with TestClient(app) as client:
            # Body can be arbitrary; PermissionChecker should block before execution
            resp = client.post(
                "/api/v1/tools/execute",
                json={"tool_name": "any.tool", "arguments": {}, "dry_run": False},
            )
            assert resp.status_code == 403, resp.text
            body = resp.json()
            assert "Permission" in (body.get("detail") or "") or body.get("detail") == "Forbidden"
    finally:
        # Clean up override for isolation across tests
        app.dependency_overrides.pop(get_request_user, None)
