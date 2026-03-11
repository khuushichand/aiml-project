from __future__ import annotations

import base64
import json
from pathlib import Path

import pytest

from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.external_federation_module import (
    ExternalFederationModule,
)


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


@pytest.mark.asyncio
async def test_managed_external_registry_service_hydrates_auth_and_skips_legacy(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
        build_secret_payload,
        dumps_envelope,
        encrypt_byok_payload,
    )
    from tldw_Server_API.app.services.mcp_hub_external_registry_service import (
        McpHubExternalRegistryService,
    )

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
    await repo.upsert_external_server(
        server_id="docs",
        name="Docs",
        transport="websocket",
        config_json=json.dumps(
            {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {"mode": "bearer_token"},
            }
        ),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        server_source="managed",
        actor_id=1,
    )
    await repo.upsert_external_secret(
        server_id="docs",
        encrypted_blob=dumps_envelope(encrypt_byok_payload(build_secret_payload("super-secret-token"))),
        key_hint="oken",
        actor_id=1,
    )
    await repo.upsert_external_server(
        server_id="legacy-docs",
        name="Legacy Docs",
        transport="websocket",
        config_json=json.dumps({"websocket": {"url": "wss://legacy.example/ws"}}),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        server_source="legacy",
        actor_id=1,
    )
    await repo.upsert_external_server(
        server_id="old-docs",
        name="Old Docs",
        transport="websocket",
        config_json=json.dumps({"websocket": {"url": "wss://old.example/ws"}}),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        server_source="managed",
        superseded_by_server_id="docs",
        actor_id=1,
    )

    service = McpHubExternalRegistryService(repo=repo)
    servers = await service.list_runtime_servers()

    assert [server.id for server in servers] == ["docs"]
    assert servers[0].websocket is not None
    assert servers[0].websocket.headers["Authorization"] == "Bearer super-secret-token"


@pytest.mark.asyncio
async def test_external_federation_module_ignores_legacy_file_config_for_runtime(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings

    db_path = tmp_path / "users.db"
    cfg_path = tmp_path / "external_servers.yaml"
    cfg_path.write_text(
        json.dumps(
            {
                "servers": [
                    {
                        "id": "legacy-docs",
                        "name": "Legacy Docs",
                        "transport": "websocket",
                        "websocket": {"url": "wss://legacy.example/ws"},
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path}")
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))

    reset_settings()
    await reset_db_pool()
    pool = await get_db_pool()
    ensure_authnz_tables(Path(str(db_path)))

    repo = McpHubRepo(pool)
    await repo.ensure_tables()

    module = ExternalFederationModule(
        ModuleConfig(
            name="external_federation",
            settings={"external_servers_config_path": str(cfg_path)},
        )
    )
    try:
        await module.initialize()
        tools = await module.get_tools()
    finally:
        await module.shutdown()

    tool_names = {
        str(tool.get("name") or "")
        for tool in tools
        if isinstance(tool, dict)
    }
    assert "external.servers.list" in tool_names
    assert "external.tools.refresh" in tool_names
    assert not any(name.startswith("ext.legacy-docs.") for name in tool_names)


@pytest.mark.asyncio
async def test_managed_external_registry_service_hydrates_named_slot_template(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
        build_secret_payload,
        dumps_envelope,
        encrypt_byok_payload,
    )
    from tldw_Server_API.app.services.mcp_hub_external_registry_service import (
        McpHubExternalRegistryService,
    )

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
    await repo.upsert_external_server(
        server_id="docs",
        name="Docs",
        transport="websocket",
        config_json=json.dumps(
            {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {
                    "mode": "bearer_token",
                    "required_slots": ["token_readonly"],
                    "slot_bindings": {
                        "token_readonly": {
                            "inject": "header",
                            "header_name": "Authorization",
                            "prefix": "Bearer ",
                        }
                    },
                },
            }
        ),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        server_source="managed",
        actor_id=1,
    )
    await repo.create_external_server_credential_slot(
        server_id="docs",
        slot_name="token_readonly",
        display_name="Read-only token",
        secret_kind="bearer_token",
        privilege_class="read",
        is_required=True,
        actor_id=1,
    )
    await repo.upsert_external_server_slot_secret(
        server_id="docs",
        slot_name="token_readonly",
        encrypted_blob=dumps_envelope(
            encrypt_byok_payload(build_secret_payload("super-secret-token"))
        ),
        key_hint="oken",
        actor_id=1,
    )

    service = McpHubExternalRegistryService(repo=repo)
    servers = await service.list_runtime_servers()

    assert [server.id for server in servers] == ["docs"]
    assert servers[0].websocket is not None
    assert servers[0].websocket.headers["Authorization"] == "Bearer super-secret-token"


@pytest.mark.asyncio
async def test_managed_external_registry_service_hydrates_template_env_for_stdio(tmp_path, monkeypatch) -> None:
    from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, reset_db_pool
    from tldw_Server_API.app.core.AuthNZ.migrations import ensure_authnz_tables
    from tldw_Server_API.app.core.AuthNZ.settings import reset_settings
    from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
        build_secret_payload,
        dumps_envelope,
        encrypt_byok_payload,
    )
    from tldw_Server_API.app.services.mcp_hub_external_registry_service import (
        McpHubExternalRegistryService,
    )

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
    await repo.upsert_external_server(
        server_id="docs-stdio",
        name="Docs Stdio",
        transport="stdio",
        config_json=json.dumps(
            {
                "stdio": {"command": "npx", "args": ["-y", "@docs/server"]},
                "auth": {
                    "mode": "template",
                    "mappings": [
                        {
                            "slot_name": "token_readonly",
                            "target_type": "env",
                            "target_name": "DOCS_TOKEN",
                            "prefix": "",
                            "suffix": "",
                            "required": True,
                        }
                    ],
                },
            }
        ),
        owner_scope_type="global",
        owner_scope_id=None,
        enabled=True,
        server_source="managed",
        actor_id=1,
    )
    await repo.create_external_server_credential_slot(
        server_id="docs-stdio",
        slot_name="token_readonly",
        display_name="Read-only token",
        secret_kind="bearer_token",
        privilege_class="read",
        is_required=True,
        actor_id=1,
    )
    await repo.upsert_external_server_slot_secret(
        server_id="docs-stdio",
        slot_name="token_readonly",
        encrypted_blob=dumps_envelope(
            encrypt_byok_payload(build_secret_payload("super-secret-token"))
        ),
        key_hint="oken",
        actor_id=1,
    )

    service = McpHubExternalRegistryService(repo=repo)
    servers = await service.list_runtime_servers()

    assert [server.id for server in servers] == ["docs-stdio"]
    assert servers[0].stdio is not None
    assert servers[0].stdio.env["DOCS_TOKEN"] == "super-secret-token"
    assert str(servers[0].auth.mode) == "none"
