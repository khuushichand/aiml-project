from __future__ import annotations

import base64

import pytest


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


def _slot_secret(label: str) -> str:
    return f"{label}-credential-value"


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_hydrates_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))

    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    secret_value = _slot_secret("primary")
    auth = await bridge.hydrate_runtime_auth(
        server_config={
            "transport": "websocket",
            "config": {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {"mode": "bearer_token"},
            },
        },
        secret_payload={"secret": secret_value},
    )

    assert auth["headers"]["Authorization"] == f"Bearer {secret_value}"


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_rejects_unsupported_auth_mode() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    secret_value = _slot_secret("unsupported-mode")

    with pytest.raises(ValueError):
        await bridge.hydrate_runtime_auth(
            server_config={
                "transport": "stdio",
                "config": {
                    "auth": {"mode": "sigv4_env"},
                },
            },
            secret_payload={"secret": secret_value},
        )


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_hydrates_named_required_slot() -> None:
    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))
    try:
        from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
            ManagedExternalAuthBridge,
        )

        bridge = ManagedExternalAuthBridge()
        secret_value = _slot_secret("readonly")
        auth = await bridge.hydrate_runtime_auth(
            server_config={
                "transport": "websocket",
                "config": {
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
                },
            },
            secret_payload={
                "slots": {
                    "token_readonly": secret_value,
                }
            },
        )

        assert auth["headers"]["Authorization"] == f"Bearer {secret_value}"
    finally:
        monkeypatch.undo()


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_hydrates_template_header_mapping() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    secret_value = _slot_secret("template-header")
    auth = await bridge.hydrate_runtime_auth(
        server_config={
            "transport": "websocket",
            "config": {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {
                    "mode": "template",
                    "mappings": [
                        {
                            "slot_name": "token_readonly",
                            "target_type": "header",
                            "target_name": "Authorization",
                            "prefix": "Bearer ",
                            "suffix": "",
                            "required": True,
                        }
                    ],
                },
            },
        },
        secret_payload={"slots": {"token_readonly": secret_value}},
    )

    assert auth["headers"]["Authorization"] == f"Bearer {secret_value}"


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_preserves_custom_template_header_name() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    secret_value = _slot_secret("custom-header")
    auth = await bridge.hydrate_runtime_auth(
        server_config={
            "transport": "websocket",
            "config": {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {
                    "mode": "template",
                    "mappings": [
                        {
                            "slot_name": "token_readonly",
                            "target_type": "header",
                            "target_name": "X-DOCS-TOKEN",
                            "prefix": "Token ",
                            "suffix": "",
                            "required": True,
                        }
                    ],
                },
            },
        },
        secret_payload={"slots": {"token_readonly": secret_value}},
    )

    assert auth["headers"] == {"X-DOCS-TOKEN": f"Token {secret_value}"}


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_hydrates_template_env_mapping() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    secret_value = _slot_secret("template-env")
    auth = await bridge.hydrate_runtime_auth(
        server_config={
            "transport": "stdio",
            "config": {
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
            },
        },
        secret_payload={"slots": {"token_readonly": secret_value}},
    )

    assert auth["env"]["DOCS_TOKEN"] == secret_value


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_rejects_duplicate_template_targets() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    readonly_secret = _slot_secret("readonly")
    write_secret = _slot_secret("write")

    with pytest.raises(ValueError, match="duplicate"):
        await bridge.hydrate_runtime_auth(
            server_config={
                "transport": "websocket",
                "config": {
                    "websocket": {"url": "wss://docs.example/ws"},
                    "auth": {
                        "mode": "template",
                        "mappings": [
                            {
                                "slot_name": "token_readonly",
                                "target_type": "header",
                                "target_name": "Authorization",
                                "prefix": "Bearer ",
                                "suffix": "",
                                "required": True,
                            },
                            {
                                "slot_name": "token_write",
                                "target_type": "header",
                                "target_name": "Authorization",
                                "prefix": "Bearer ",
                                "suffix": "",
                                "required": True,
                            },
                        ],
                    },
                },
            },
            secret_payload={
                "slots": {
                    "token_readonly": readonly_secret,
                    "token_write": write_secret,
                }
            },
        )


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_prefers_template_shape_over_legacy_slot_bindings() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    legacy_secret = _slot_secret("legacy")
    readonly_secret = _slot_secret("readonly")
    auth = await bridge.hydrate_runtime_auth(
        server_config={
            "transport": "websocket",
            "config": {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {
                    "mode": "template",
                    "required_slots": ["legacy_token"],
                    "slot_bindings": {
                        "legacy_token": {
                            "inject": "header",
                            "header_name": "X-API-KEY",
                            "prefix": "",
                        }
                    },
                    "mappings": [
                        {
                            "slot_name": "token_readonly",
                            "target_type": "header",
                            "target_name": "Authorization",
                            "prefix": "Bearer ",
                            "suffix": "",
                            "required": True,
                        }
                    ],
                },
            },
        },
        secret_payload={
            "slots": {
                "legacy_token": legacy_secret,
                "token_readonly": readonly_secret,
            }
        },
    )

    assert auth["headers"]["Authorization"] == f"Bearer {readonly_secret}"
    assert "X-API-KEY" not in auth["headers"]


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_rejects_missing_required_slot_secret() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()

    with pytest.raises(ValueError):
        await bridge.hydrate_runtime_auth(
            server_config={
                "transport": "websocket",
                "config": {
                    "auth": {
                        "mode": "api_key_header",
                        "required_slots": ["api_key"],
                        "slot_bindings": {
                            "api_key": {
                                "inject": "header",
                                "header_name": "X-API-KEY",
                            }
                        },
                    },
                },
            },
            secret_payload={"slots": {}},
        )
