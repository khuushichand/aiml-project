"""SandboxBridge for provisioning and managing sandboxed agent environments.

Delegates to an injected sandbox_service for actual container/VM lifecycle.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SandboxProvisionRequest:
    """Request to provision a sandbox for an agent."""
    user_id: int
    agent_command: str
    agent_args: list[str] = field(default_factory=list)
    agent_env: dict[str, str] = field(default_factory=dict)
    runtime: str | None = None
    trust_level: str = "standard"
    ttl_sec: int = 86400
    network_policy: str = "deny_all"
    workspace_files: list[str] | None = None


@dataclass
class SandboxHandle:
    """Handle to a running sandbox session."""
    sandbox_session_id: str
    run_id: str
    process_stdin: Any | None = None
    process_stdout: Any | None = None
    endpoint: str | None = None
    ssh_endpoint: str | None = None


class SandboxBridge:
    """Bridge between ACP agent harness and sandbox service."""

    def __init__(self, sandbox_service: Any) -> None:
        self._service = sandbox_service

    async def provision(self, request: SandboxProvisionRequest) -> SandboxHandle:
        """Provision a sandbox session and start a run."""
        session = await self._service.create_session(
            user_id=request.user_id,
            agent_command=request.agent_command,
            agent_args=request.agent_args,
            agent_env=request.agent_env,
            runtime=request.runtime,
            trust_level=request.trust_level,
            ttl_sec=request.ttl_sec,
            network_policy=request.network_policy,
            workspace_files=request.workspace_files,
        )
        run = await self._service.start_run(
            session_id=session["session_id"],
        )
        return SandboxHandle(
            sandbox_session_id=session["session_id"],
            run_id=run["run_id"],
            process_stdin=run.get("process_stdin"),
            process_stdout=run.get("process_stdout"),
            endpoint=session.get("endpoint"),
            ssh_endpoint=session.get("ssh_endpoint"),
        )

    async def teardown(self, handle: SandboxHandle) -> None:
        """Tear down a sandbox: cancel the run, then delete the session."""
        await self._service.cancel_run(handle.run_id)
        await self._service.delete_session(handle.sandbox_session_id)

    async def snapshot(self, handle: SandboxHandle) -> str:
        """Create a snapshot of the sandbox state. Returns snapshot ID."""
        return await self._service.snapshot(handle.sandbox_session_id)

    async def restore(self, handle: SandboxHandle, snapshot_id: str) -> None:
        """Restore a sandbox from a snapshot."""
        await self._service.restore(handle.sandbox_session_id, snapshot_id)
