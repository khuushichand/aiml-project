"""Tests for SandboxBridge."""
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.sandbox_bridge import (
    SandboxBridge,
    SandboxHandle,
    SandboxProvisionRequest,
)

pytestmark = pytest.mark.unit


class TestSandboxBridgeProvisionReturnsHandle:
    """provision() should call create_session + start_run_scaffold and return a SandboxHandle."""

    @pytest.mark.asyncio
    async def test_sandbox_bridge_provision_returns_handle(self) -> None:
        mock_session = MagicMock()
        mock_session.id = "sess-123"
        mock_session.endpoint = "http://localhost:9000"
        mock_session.ssh_endpoint = "ssh://localhost:2222"

        mock_run = MagicMock()
        mock_run.run_id = "run-456"
        mock_run.stdin = "stdin_mock"
        mock_run.stdout = "stdout_mock"

        mock_service = MagicMock()
        mock_service.create_session = AsyncMock(return_value=mock_session)
        mock_service.start_run_scaffold = AsyncMock(return_value=mock_run)

        bridge = SandboxBridge(sandbox_service=mock_service)
        request = SandboxProvisionRequest(
            user_id=1,
            agent_command=["python", "-m", "agent"],
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
        mock_service.start_run_scaffold.assert_awaited_once()


class TestSandboxBridgeTeardown:
    """teardown() should call destroy_session."""

    @pytest.mark.asyncio
    async def test_sandbox_bridge_teardown(self) -> None:
        mock_service = MagicMock()
        mock_service.destroy_session = AsyncMock()

        bridge = SandboxBridge(sandbox_service=mock_service)
        handle = SandboxHandle(
            sandbox_session_id="sess-123",
            run_id="run-456",
        )

        await bridge.teardown(handle)

        mock_service.destroy_session.assert_awaited_once_with("sess-123")
