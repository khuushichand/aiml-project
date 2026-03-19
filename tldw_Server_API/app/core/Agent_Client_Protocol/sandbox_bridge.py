"""SandboxBridge for provisioning and managing sandboxed agent environments.

Delegates to an injected sandbox_service for actual container/VM lifecycle.
The bridge translates between ACP session concepts and the Sandbox module's
``SandboxService`` / ``SandboxOrchestrator`` API (``create_session``,
``start_run_scaffold``, ``destroy_session``).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from loguru import logger


@dataclass
class SandboxProvisionRequest:
    """Request to provision a sandbox for an agent."""
    user_id: int
    agent_command: list[str]
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
    """Bridge between ACP agent harness and sandbox service.

    The injected *sandbox_service* is expected to expose the same contract as
    ``tldw_Server_API.app.core.Sandbox.service.SandboxService``:

    - ``create_session(user_id, spec, spec_version, idem_key, raw_body) -> Session``
    - ``start_run_scaffold(run_id, spec, ...) -> RunStatus``
    - ``destroy_session(session_id) -> bool``

    Where ``Session.id`` and ``RunStatus.run_id`` are the identifiers.
    """

    def __init__(self, sandbox_service: Any) -> None:
        self._service = sandbox_service

    async def provision(self, request: SandboxProvisionRequest) -> SandboxHandle:
        """Provision a sandbox session and start a run inside it."""
        # 1. Create the sandbox session (environment only, no process yet)
        session = await self._service.create_session(
            user_id=request.user_id,
            spec={
                "runtime": request.runtime,
                "timeout_sec": request.ttl_sec,
            },
            spec_version="1",
            idem_key=None,
            raw_body={
                "trust_level": request.trust_level,
                "network_policy": request.network_policy,
            },
        )
        session_id = getattr(session, "id", None) or session.get("id", "")

        # 2. Start the agent process inside the session
        run = await self._service.start_run_scaffold(
            run_id=None,
            spec={
                "session_id": session_id,
                "command": request.agent_command,
                "env": request.agent_env,
            },
        )
        run_id = getattr(run, "run_id", None) or getattr(run, "id", None) or run.get("run_id", "")

        return SandboxHandle(
            sandbox_session_id=session_id,
            run_id=run_id,
            process_stdin=getattr(run, "stdin", None),
            process_stdout=getattr(run, "stdout", None),
            endpoint=getattr(session, "endpoint", None),
            ssh_endpoint=getattr(session, "ssh_endpoint", None),
        )

    async def teardown(self, handle: SandboxHandle) -> None:
        """Tear down a sandbox: destroy the session (which cleans up runs)."""
        try:
            await self._service.destroy_session(handle.sandbox_session_id)
        except Exception:
            logger.warning(
                "SandboxBridge: destroy_session failed for {}",
                handle.sandbox_session_id,
            )

    async def snapshot(self, handle: SandboxHandle) -> str:
        """Create a snapshot of the sandbox state. Returns snapshot ID."""
        return await self._service.snapshot(handle.sandbox_session_id)

    async def restore(self, handle: SandboxHandle, snapshot_id: str) -> None:
        """Restore a sandbox from a snapshot."""
        await self._service.restore(handle.sandbox_session_id, snapshot_id)
