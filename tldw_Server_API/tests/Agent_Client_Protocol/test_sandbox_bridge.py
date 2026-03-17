"""Tests for SandboxBridge (Task 10)."""
from __future__ import annotations

import pytest
from unittest.mock import AsyncMock, MagicMock

from tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_bridge import (
    SandboxBridge,
    SandboxHandle,
    SandboxProvisionRequest,
)


class TestSandboxBridgeProvisionReturnsHandle:
    """provision() should call create_session + start_run and return a SandboxHandle."""

    @pytest.mark.asyncio
    async def test_sandbox_bridge_provision_returns_handle(self) -> None:
        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value={
            "session_id": "sess-123",
            "endpoint": "http://localhost:9000",
            "ssh_endpoint": "ssh://localhost:2222",
        })
        mock_service.start_run = AsyncMock(return_value={
            "run_id": "run-456",
            "process_stdin": "stdin_mock",
            "process_stdout": "stdout_mock",
        })

        bridge = SandboxBridge(sandbox_service=mock_service)
        request = SandboxProvisionRequest(
            user_id=1,
            agent_command="python",
            agent_args=["-m", "agent"],
            trust_level="untrusted",
        )
        handle = await bridge.provision(request)

        assert isinstance(handle, SandboxHandle)
        assert handle.sandbox_session_id == "sess-123"
        assert handle.run_id == "run-456"
        assert handle.endpoint == "http://localhost:9000"
        assert handle.ssh_endpoint == "ssh://localhost:2222"
        assert handle.process_stdin == "stdin_mock"
        assert handle.process_stdout == "stdout_mock"

        mock_service.create_session.assert_awaited_once()
        mock_service.start_run.assert_awaited_once()


class TestSandboxBridgeTeardown:
    """teardown() should call cancel_run + delete_session."""

    @pytest.mark.asyncio
    async def test_sandbox_bridge_teardown(self) -> None:
        mock_service = MagicMock()
        mock_service.cancel_run = AsyncMock()
        mock_service.delete_session = AsyncMock()

        bridge = SandboxBridge(sandbox_service=mock_service)
        handle = SandboxHandle(
            sandbox_session_id="sess-123",
            run_id="run-456",
        )

        await bridge.teardown(handle)

        mock_service.cancel_run.assert_awaited_once_with("run-456")
        mock_service.delete_session.assert_awaited_once_with("sess-123")
