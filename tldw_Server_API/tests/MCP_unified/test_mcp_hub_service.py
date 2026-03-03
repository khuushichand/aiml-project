from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo

pytest_plugins = ("tldw_Server_API.tests.AuthNZ.conftest",)


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


@pytest.mark.asyncio
async def test_set_external_secret_encrypts_and_never_returns_plaintext(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.services.mcp_hub_service import McpHubService

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    svc = McpHubService(repo=repo)

    await svc.create_external_server(
        server_id="docs",
        name="Docs",
        transport="stdio",
        config={"cmd": "npx"},
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        actor_id=1,
    )
    out = await svc.set_external_server_secret(
        server_id="docs",
        secret_value="super-secret-token",
        actor_id=1,
    )

    assert out["secret_configured"] is True
    assert "super-secret-token" not in json.dumps(out)

    secret = await repo.get_external_secret("docs")
    assert secret is not None
    assert "super-secret-token" not in json.dumps(secret)


@pytest.mark.asyncio
async def test_service_emits_audit_event_on_external_server_update(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.services.mcp_hub_service import McpHubService

    db_path = tmp_path / "users.db"
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))

    reset_settings()
    await reset_db_pool()

    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    calls: list[dict[str, object]] = []

    def _capture(**kwargs):
        calls.append(kwargs)
        return None

    monkeypatch.setattr(
        "tldw_Server_API.app.services.mcp_hub_service.emit_mcp_hub_audit",
        _capture,
    )

    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    svc = McpHubService(repo=repo)

    await svc.create_external_server(
        server_id="docs",
        name="Docs",
        transport="stdio",
        config={"cmd": "npx"},
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        actor_id=1,
    )

    assert calls
    assert calls[0]["action"] == "mcp_hub.external_server.create"
