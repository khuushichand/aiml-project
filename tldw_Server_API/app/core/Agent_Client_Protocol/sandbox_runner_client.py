from __future__ import annotations

import asyncio
import base64
import json
import os
import socket
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.config import ACPSandboxConfig, load_acp_sandbox_config
from tldw_Server_API.app.core.Agent_Client_Protocol.runner_client import (
    PERMISSION_TIMEOUT_SECONDS,
    PendingPermission,
    SessionWebSocketRegistry,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.stream_client import ACPStreamClient
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import ACPMessage, ACPResponseError
from tldw_Server_API.app.core.config import settings as app_settings
from tldw_Server_API.app.core.Sandbox.models import RunSpec, RuntimeType, SessionSpec
from tldw_Server_API.app.core.Sandbox.streams import get_hub

from tldw_Server_API.app.api.v1.endpoints import sandbox as sandbox_ep


@dataclass
class SandboxSessionHandle:
    session_id: str
    user_id: int
    sandbox_session_id: str
    run_id: str
    client: ACPStreamClient
    reader_task: asyncio.Task
    ssh_user: str | None = None
    ssh_host: str | None = None
    ssh_port: int | None = None
    ssh_private_key: str | None = None
    agent_capabilities: dict[str, Any] | None = None


class ACPSandboxRunnerManager:
    def __init__(self, config: ACPSandboxConfig | None = None) -> None:
        self.config = config or load_acp_sandbox_config()
        self._sessions: dict[str, SandboxSessionHandle] = {}
        self._sessions_lock = asyncio.Lock()
        self._updates: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        self._agent_capabilities: dict[str, Any] = {}
        self._ws_registry: dict[str, SessionWebSocketRegistry] = {}
        self._ws_registry_lock = asyncio.Lock()
        self._ssh_ports_in_use: set[int] = set()
        self._ssh_ports_lock = asyncio.Lock()

    @property
    def agent_capabilities(self) -> dict[str, Any]:
        return self._agent_capabilities

    @property
    def is_running(self) -> bool:
        return True

    async def start(self) -> None:
        return

    async def shutdown(self) -> None:
        async with self._sessions_lock:
            sessions = list(self._sessions.values())
        for sess in sessions:
            await self.close_session(sess.session_id)

    # -------------------------------------------------------------------------
    # Session lifecycle
    # -------------------------------------------------------------------------

    async def create_session(
        self,
        cwd: str,
        mcp_servers: list[dict[str, Any]] | None = None,
        agent_type: str | None = None,
        user_id: int | None = None,
    ) -> str:
        if not self.config.enabled:
            raise ACPResponseError("ACP sandbox mode is not enabled")
        if not self.config.agent_command:
            raise ACPResponseError("ACP_SANDBOX_AGENT_COMMAND is required for sandbox mode")
        if cwd and cwd != "/workspace":
            logger.warning("ACP sandbox ignores host cwd '{}' (using /workspace inside container)", cwd)
        try:
            env_bg = os.getenv("SANDBOX_BACKGROUND_EXECUTION")
            if env_bg is not None:
                background = str(env_bg).strip().lower() in {"1", "true", "yes", "on", "y"}
            else:
                background = bool(getattr(app_settings, "SANDBOX_BACKGROUND_EXECUTION", False))
        except Exception:
            background = False
        if not background:
            raise ACPResponseError("SANDBOX_BACKGROUND_EXECUTION must be enabled for ACP sandbox sessions")
        try:
            env_exec = os.getenv("SANDBOX_ENABLE_EXECUTION")
            if env_exec is not None:
                execute_enabled = str(env_exec).strip().lower() in {"1", "true", "yes", "on", "y"}
            else:
                execute_enabled = bool(getattr(app_settings, "SANDBOX_ENABLE_EXECUTION", False))
        except Exception:
            execute_enabled = False
        if not execute_enabled:
            raise ACPResponseError("SANDBOX_ENABLE_EXECUTION must be enabled for ACP sandbox sessions")

        sandbox_service = sandbox_ep._service  # type: ignore[attr-defined]

        sandbox_session = None
        status = None
        ssh_port: int | None = None
        ssh_key_priv: str | None = None
        ssh_key_pub: str | None = None

        try:
            # Create sandbox session
            sess_spec = SessionSpec(
                runtime=RuntimeType(self.config.runtime),
                base_image=self.config.base_image,
                network_policy=self.config.network_policy or "allow_all",
            )
            sandbox_session = sandbox_service.create_session(
                user_id=user_id or 0,
                spec=sess_spec,
                spec_version="1.0",
                idem_key=None,
                raw_body={"runtime": self.config.runtime, "base_image": self.config.base_image},
            )

            if self.config.ssh_enabled:
                ssh_key_priv, ssh_key_pub = self._generate_ssh_keypair()
                ssh_port = await self._allocate_ssh_port()

            env = {
                "ACP_SSH_USER": self.config.ssh_user,
                "ACP_AGENT_COMMAND": self.config.agent_command,
                "ACP_AGENT_ARGS_JSON": json.dumps(self.config.agent_args),
                "ACP_AGENT_ENV_JSON": json.dumps(self.config.agent_env),
                "ACP_WORKSPACE_ROOT": "/workspace",
            }
            if self.config.ssh_enabled and ssh_key_pub:
                env["ACP_SSH_AUTHORIZED_KEY"] = ssh_key_pub

            port_mappings: list[dict[str, str | int]] = []
            if self.config.ssh_enabled and ssh_port is not None:
                port_mappings = [{
                    "host_ip": self.config.ssh_host,
                    "host_port": ssh_port,
                    "container_port": 22,
                }]

            run_spec = RunSpec(
                session_id=sandbox_session.id,
                runtime=RuntimeType(self.config.runtime),
                base_image=self.config.base_image,
                command=["/usr/local/bin/tldw-acp-entrypoint"],
                env=env,
                interactive=True,
                run_as_root=True,
                read_only_root=False,
                network_policy=self.config.network_policy or "allow_all",
                port_mappings=port_mappings,
            )

            status = sandbox_service.start_run_scaffold(
                user_id=user_id or 0,
                spec=run_spec,
                spec_version="1.0",
                idem_key=None,
                raw_body={"runtime": self.config.runtime, "base_image": self.config.base_image},
            )
        except Exception:
            if status is not None:
                try:
                    sandbox_service.cancel_run(status.id)
                except Exception:
                    pass
            if sandbox_session is not None:
                try:
                    sandbox_service.destroy_session(sandbox_session.id)
                except Exception:
                    pass
            if ssh_port is not None:
                await self._release_ssh_port(ssh_port)
            raise

        hub = get_hub()
        q = hub.subscribe_with_buffer(status.id)

        async def _send_bytes(data: bytes) -> None:
            try:
                hub.push_stdin(status.id, data)
            except Exception as e:
                logger.debug(f"ACP sandbox stdin push failed: {e}")

        client = ACPStreamClient(send_bytes=_send_bytes)
        client.set_notification_handler(self._handle_notification)
        client.set_request_handler(self._handle_request)

        reader_task = asyncio.create_task(self._reader_loop(status.id, q, client))

        try:
            await client.start()
            init_result = await client.call(
                "initialize",
                {
                    "protocolVersion": 1,
                    "clientCapabilities": {
                        "fs": {"readTextFile": True, "writeTextFile": True},
                        "terminal": True,
                    },
                    "clientInfo": {
                        "name": "tldw-server",
                        "title": "TLDW Server",
                        "version": "0.1.0",
                    },
                },
            )
            self._agent_capabilities = init_result.result.get("agentCapabilities", {}) if init_result.result else {}

            # Always use container workspace root for ACP sessions
            session_new = await client.call(
                "session/new",
                {
                    "cwd": "/workspace",
                    "mcpServers": mcp_servers or [],
                    "agentType": agent_type,
                },
            )
            session_id = (session_new.result or {}).get("sessionId")
            if not session_id:
                raise ACPResponseError("Missing sessionId in ACP sandbox response")

            handle = SandboxSessionHandle(
                session_id=session_id,
                user_id=user_id or 0,
                sandbox_session_id=sandbox_session.id,
                run_id=status.id,
                client=client,
                reader_task=reader_task,
                ssh_user=self.config.ssh_user if self.config.ssh_enabled else None,
                ssh_host=self.config.ssh_host if self.config.ssh_enabled else None,
                ssh_port=ssh_port if self.config.ssh_enabled else None,
                ssh_private_key=ssh_key_priv if self.config.ssh_enabled else None,
                agent_capabilities=self._agent_capabilities,
            )

            async with self._sessions_lock:
                self._sessions[session_id] = handle

            return session_id
        except Exception:
            try:
                reader_task.cancel()
            except Exception:
                pass
            try:
                await client.close()
            except Exception:
                pass
            try:
                sandbox_service.cancel_run(status.id)
            except Exception:
                pass
            try:
                sandbox_service.destroy_session(sandbox_session.id)
            except Exception:
                pass
            if ssh_port is not None:
                await self._release_ssh_port(ssh_port)
            raise

    async def prompt(self, session_id: str, prompt: list[dict[str, Any]]) -> dict[str, Any]:
        sess = await self._get_session(session_id)
        response = await sess.client.call(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": prompt,
            },
        )
        return response.result or {}

    async def cancel(self, session_id: str) -> None:
        sess = await self._get_session(session_id)
        await sess.client.notify("session/cancel", {"sessionId": session_id})

    async def close_session(self, session_id: str) -> None:
        sess = await self._get_session(session_id, required=False)
        if not sess:
            return
        try:
            await sess.client.call("_tldw/session/close", {"sessionId": session_id})
        except Exception:
            pass
        try:
            if sess.reader_task:
                sess.reader_task.cancel()
        except Exception:
            pass
        try:
            await sess.client.close()
        except Exception:
            pass
        try:
            sandbox_ep._service.cancel_run(sess.run_id)  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            sandbox_ep._service.destroy_session(sess.sandbox_session_id)  # type: ignore[attr-defined]
        except Exception:
            pass
        if sess.ssh_port:
            await self._release_ssh_port(sess.ssh_port)
        async with self._sessions_lock:
            self._sessions.pop(session_id, None)
        self._updates.pop(session_id, None)

    def pop_updates(self, session_id: str, limit: int = 100) -> list[dict[str, Any]]:
        updates = []
        queue = self._updates.get(session_id)
        if not queue:
            return updates
        for _ in range(min(limit, len(queue))):
            updates.append(queue.popleft())
        return updates

    # -------------------------------------------------------------------------
    # SSH metadata
    # -------------------------------------------------------------------------
    async def get_ssh_info(self, session_id: str, user_id: int | None = None) -> tuple[str, int, str, str] | None:
        sess = await self._get_session(session_id, required=False)
        if sess and user_id is not None and sess.user_id != user_id:
            return None
        if not sess or not sess.ssh_host or not sess.ssh_port or not sess.ssh_user or not sess.ssh_private_key:
            return None
        return sess.ssh_host, sess.ssh_port, sess.ssh_user, sess.ssh_private_key

    async def get_session_metadata(self, session_id: str, user_id: int | None = None) -> dict[str, Any] | None:
        sess = await self._get_session(session_id, required=False)
        if sess and user_id is not None and sess.user_id != user_id:
            return None
        if not sess:
            return None
        return {
            "sandbox_session_id": sess.sandbox_session_id,
            "sandbox_run_id": sess.run_id,
            "ssh_ws_url": f"/api/v1/acp/sessions/{session_id}/ssh" if sess.ssh_user else None,
            "ssh_user": sess.ssh_user,
        }

    # -------------------------------------------------------------------------
    # WebSocket registry / permissions (adapted from ACPRunnerClient)
    # -------------------------------------------------------------------------

    async def register_websocket(
        self,
        session_id: str,
        send_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        async with self._ws_registry_lock:
            if session_id not in self._ws_registry:
                self._ws_registry[session_id] = SessionWebSocketRegistry(session_id=session_id)
            self._ws_registry[session_id].websockets.add(send_callback)
            logger.debug("Registered WebSocket for session {}", session_id)

    async def unregister_websocket(
        self,
        session_id: str,
        send_callback: Callable[[dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        async with self._ws_registry_lock:
            if session_id in self._ws_registry:
                self._ws_registry[session_id].websockets.discard(send_callback)
                logger.debug("Unregistered WebSocket for session {}", session_id)

    def has_websocket_connections(self, session_id: str) -> bool:
        registry = self._ws_registry.get(session_id)
        return registry is not None and len(registry.websockets) > 0

    async def _broadcast_to_session(self, session_id: str, message: dict[str, Any]) -> None:
        registry = self._ws_registry.get(session_id)
        if not registry:
            return

        failed_callbacks = []
        for callback in list(registry.websockets):
            try:
                await callback(message)
            except Exception as e:
                logger.warning("Failed to send to WebSocket for session {}: {}", session_id, e)
                failed_callbacks.append(callback)

        for callback in failed_callbacks:
            registry.websockets.discard(callback)

    async def respond_to_permission(
        self,
        session_id: str,
        request_id: str,
        approved: bool,
        batch_approve_tier: str | None = None,
    ) -> bool:
        registry = self._ws_registry.get(session_id)
        if not registry:
            logger.warning("No registry for session {} when responding to permission", session_id)
            return False

        pending = registry.pending_permissions.pop(request_id, None)
        if not pending:
            logger.warning("Permission request {} not found for session {}", request_id, session_id)
            return False

        if approved and batch_approve_tier:
            registry.batch_approved_tiers.add(batch_approve_tier)
            logger.info("Batch-approved tier {} for session {}", batch_approve_tier, session_id)

        outcome = "approved" if approved else "denied"
        if not pending.future.done():
            pending.future.set_result({"outcome": outcome})

        return True

    def _determine_permission_tier(self, tool_name: str) -> str:
        tool_lower = tool_name.lower()
        auto_patterns = ["read", "get", "list", "search", "find", "view", "show", "glob", "grep", "status"]
        if any(p in tool_lower for p in auto_patterns):
            return "auto"
        individual_patterns = ["delete", "remove", "exec", "run", "shell", "bash", "terminal", "push", "force"]
        if any(p in tool_lower for p in individual_patterns):
            return "individual"
        return "batch"

    async def _handle_notification(self, msg: ACPMessage) -> None:
        if msg.method != "session/update":
            return
        params = msg.params or {}
        session_id = params.get("sessionId")
        if not session_id:
            return

        self._updates[session_id].append(params)

        update_message = {
            "type": "update",
            "session_id": session_id,
            "update_type": params.get("type", "unknown"),
            "data": params,
        }
        await self._broadcast_to_session(session_id, update_message)

    async def _handle_request(self, msg: ACPMessage) -> ACPMessage:
        if msg.method != "session/request_permission":
            return ACPMessage(jsonrpc="2.0", id=msg.id, error={"code": -32601, "message": "method not found"})

        params = msg.params or {}
        session_id = params.get("sessionId", "")
        tool_name = params.get("tool", {}).get("name", "unknown")
        tool_arguments = params.get("tool", {}).get("input", {})

        tier = self._determine_permission_tier(tool_name)

        registry = self._ws_registry.get(session_id)
        if registry and tier in registry.batch_approved_tiers:
            logger.info("Auto-approving {} (tier {} is batch-approved)", tool_name, tier)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "approved"}},
            )

        if tier == "auto":
            logger.debug("Auto-approving {} (auto tier)", tool_name)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "approved"}},
            )

        if not self.has_websocket_connections(session_id):
            logger.warning("ACP permission request auto-cancelled (no WebSocket connections)")
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "cancelled"}},
            )

        request_id = str(uuid.uuid4())
        pending = PendingPermission(
            request_id=request_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            acp_message_id=msg.id,
            future=asyncio.get_running_loop().create_future(),
        )

        async with self._ws_registry_lock:
            if session_id not in self._ws_registry:
                self._ws_registry[session_id] = SessionWebSocketRegistry(session_id=session_id)
            self._ws_registry[session_id].pending_permissions[request_id] = pending

        permission_message = {
            "type": "permission_request",
            "request_id": request_id,
            "session_id": session_id,
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "tier": tier,
            "timeout_seconds": PERMISSION_TIMEOUT_SECONDS,
        }
        await self._broadcast_to_session(session_id, permission_message)

        if not self.has_websocket_connections(session_id):
            logger.warning("ACP permission request auto-cancelled (all WebSocket connections failed during broadcast)")
            async with self._ws_registry_lock:
                if session_id in self._ws_registry:
                    self._ws_registry[session_id].pending_permissions.pop(request_id, None)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "cancelled"}},
            )

        try:
            result = await asyncio.wait_for(
                pending.future,
                timeout=PERMISSION_TIMEOUT_SECONDS,
            )
            logger.info("Permission {} for tool {} result: {}", request_id, tool_name, result)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": result},
            )
        except asyncio.TimeoutError:
            logger.warning("Permission request {} timed out for tool {}", request_id, tool_name)
            async with self._ws_registry_lock:
                if session_id in self._ws_registry:
                    self._ws_registry[session_id].pending_permissions.pop(request_id, None)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "cancelled"}},
            )

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    async def _reader_loop(self, run_id: str, q: asyncio.Queue, client: ACPStreamClient) -> None:
        try:
            while True:
                frame = await q.get()
                if not isinstance(frame, dict):
                    continue
                ftype = frame.get("type")
                if ftype in {"stdout", "stderr"}:
                    enc = frame.get("encoding") or "utf8"
                    data_field = frame.get("data")
                    if not isinstance(data_field, str):
                        continue
                    try:
                        if enc == "base64":
                            raw = base64.b64decode(data_field)
                        else:
                            raw = data_field.encode("utf-8")
                    except Exception:
                        raw = b""
                    if not raw:
                        continue
                    if ftype == "stdout":
                        await client.feed_bytes(raw)
                    else:
                        logger.debug(f"ACP sandbox stderr: {data_field}")
                elif ftype == "event" and frame.get("event") == "end":
                    await client.close()
                    return
        except asyncio.CancelledError:
            return
        except Exception as e:
            logger.debug(f"ACP sandbox reader loop error: {e}")

    async def _get_session(self, session_id: str, required: bool = True) -> SandboxSessionHandle | None:
        async with self._sessions_lock:
            sess = self._sessions.get(session_id)
        if not sess and required:
            raise ACPResponseError("Unknown session")
        return sess

    def _generate_ssh_keypair(self) -> tuple[str, str]:
        try:
            import asyncssh  # type: ignore

            key = asyncssh.generate_private_key("ssh-ed25519")
            priv = key.export_private_key().decode("utf-8")
            pub = key.export_public_key().decode("utf-8")
            return priv, pub
        except Exception as e:
            raise ACPResponseError(f"Failed to generate SSH key: {e}")

    async def _allocate_ssh_port(self) -> int:
        async with self._ssh_ports_lock:
            for port in range(self.config.ssh_port_min, self.config.ssh_port_max + 1):
                if port in self._ssh_ports_in_use:
                    continue
                if not self._port_available(self.config.ssh_host, port):
                    continue
                self._ssh_ports_in_use.add(port)
                return port
        raise ACPResponseError("No available SSH ports")

    async def _release_ssh_port(self, port: int) -> None:
        async with self._ssh_ports_lock:
            self._ssh_ports_in_use.discard(port)

    def _port_available(self, host: str, port: int) -> bool:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind((host, port))
                return True
        except Exception:
            return False
