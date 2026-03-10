from __future__ import annotations

import base64

import pytest


def _b64_key(byte_char: bytes) -> str:
    return base64.b64encode(byte_char * 32).decode("ascii")


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_hydrates_bearer_token(monkeypatch) -> None:
    monkeypatch.setenv("BYOK_ENCRYPTION_KEY", _b64_key(b"k"))

    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()
    auth = await bridge.hydrate_runtime_auth(
        server_config={
            "transport": "websocket",
            "config": {
                "websocket": {"url": "wss://docs.example/ws"},
                "auth": {"mode": "bearer_token"},
            },
        },
        secret_payload={"secret": "super-secret-token"},
    )

    assert auth["headers"]["Authorization"] == "Bearer super-secret-token"


@pytest.mark.asyncio
async def test_managed_external_auth_bridge_rejects_unsupported_auth_mode() -> None:
    from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
        ManagedExternalAuthBridge,
    )

    bridge = ManagedExternalAuthBridge()

    with pytest.raises(ValueError):
        await bridge.hydrate_runtime_auth(
            server_config={
                "transport": "stdio",
                "config": {
                    "auth": {"mode": "sigv4_env"},
                },
            },
            secret_payload={"secret": "super-secret-token"},
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
                    "token_readonly": "super-secret-token",
                }
            },
        )

        assert auth["headers"]["Authorization"] == "Bearer super-secret-token"
    finally:
        monkeypatch.undo()


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
