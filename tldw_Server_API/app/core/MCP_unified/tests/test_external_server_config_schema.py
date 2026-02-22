from __future__ import annotations

import pytest

from tldw_Server_API.app.core.MCP_unified.external_servers.config_schema import (
    ExternalAuthMode,
    parse_external_server_registry,
)


def test_parse_registry_accepts_websocket_and_stdio() -> None:
    cfg = parse_external_server_registry(
        {
            "servers": [
                {
                    "id": "docs",
                    "name": "Docs",
                    "transport": "websocket",
                    "websocket": {"url": "wss://example.test/ws"},
                    "auth": {"mode": "bearer_env", "token_env": "DOCS_TOKEN"},
                },
                {
                    "id": "local_ci",
                    "name": "Local CI",
                    "transport": "stdio",
                    "stdio": {"command": "node", "args": ["ci.js"]},
                },
            ]
        }
    )

    assert len(cfg.servers) == 2
    assert cfg.servers[0].id == "docs"
    assert cfg.servers[0].auth.mode == ExternalAuthMode.BEARER_ENV
    assert cfg.servers[1].id == "local_ci"
    assert cfg.servers[1].stdio is not None


def test_parse_registry_requires_transport_specific_config() -> None:
    with pytest.raises(ValueError, match="requires websocket config"):
        parse_external_server_registry(
            {
                "servers": [
                    {
                        "id": "docs",
                        "name": "Docs",
                        "transport": "websocket",
                    }
                ]
            }
        )

    with pytest.raises(ValueError, match="requires stdio config"):
        parse_external_server_registry(
            {
                "servers": [
                    {
                        "id": "local",
                        "name": "Local",
                        "transport": "stdio",
                    }
                ]
            }
        )


def test_parse_registry_rejects_duplicate_ids() -> None:
    with pytest.raises(ValueError, match="Duplicate external server id"):
        parse_external_server_registry(
            {
                "servers": [
                    {
                        "id": "dup",
                        "name": "First",
                        "transport": "websocket",
                        "websocket": {"url": "wss://a.example/ws"},
                    },
                    {
                        "id": "dup",
                        "name": "Second",
                        "transport": "stdio",
                        "stdio": {"command": "echo"},
                    },
                ]
            }
        )


def test_policy_allow_and_deny_patterns() -> None:
    cfg = parse_external_server_registry(
        {
            "servers": [
                {
                    "id": "policy",
                    "name": "Policy",
                    "transport": "websocket",
                    "websocket": {"url": "wss://policy.example/ws"},
                    "policy": {
                        "allow_tool_patterns": ["docs.*"],
                        "deny_tool_patterns": ["docs.delete"],
                    },
                }
            ]
        }
    )

    policy = cfg.servers[0].policy
    assert policy.allows_tool("docs.search") is True
    assert policy.allows_tool("docs.delete") is False
    assert policy.allows_tool("ci.run") is False
