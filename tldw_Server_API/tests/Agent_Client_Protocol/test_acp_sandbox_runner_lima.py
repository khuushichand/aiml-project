from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.config import ACPSandboxConfig
from tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_runner_client import ACPSandboxRunnerManager
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPResponseError


@pytest.mark.unit
@pytest.mark.asyncio
async def test_acp_lima_runtime_fails_closed_when_strict_not_supported(monkeypatch) -> None:
    manager = ACPSandboxRunnerManager(
        ACPSandboxConfig(
            enabled=True,
            runtime="lima",
            network_policy="deny_all",
            agent_command="/usr/local/bin/codex",
        )
    )
    monkeypatch.setenv("SANDBOX_BACKGROUND_EXECUTION", "1")
    monkeypatch.setenv("SANDBOX_ENABLE_EXECUTION", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_AVAILABLE", "1")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_DENY_ALL_READY", "0")
    monkeypatch.setenv("TLDW_SANDBOX_LIMA_ENFORCER_ALLOWLIST_READY", "0")

    with pytest.raises(ACPResponseError, match="strict"):
        await manager.create_session(cwd="/workspace", user_id=7)

