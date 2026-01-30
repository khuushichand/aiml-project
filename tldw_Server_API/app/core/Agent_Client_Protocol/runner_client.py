from __future__ import annotations

import asyncio
import time
import uuid
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Callable, Coroutine, Deque, Dict, List, Optional, Set

from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.config import (
    ACPRunnerConfig,
    load_acp_runner_config,
)
from tldw_Server_API.app.core.Agent_Client_Protocol.stdio_client import (
    ACPMessage,
    ACPResponseError,
    ACPStdioClient,
)


# Permission timeout in seconds (5 minutes)
PERMISSION_TIMEOUT_SECONDS = 300


@dataclass
class PendingPermission:
    """Tracks a pending permission request."""
    request_id: str
    session_id: str
    tool_name: str
    tool_arguments: Dict[str, Any]
    acp_message_id: Any  # The original ACP message ID for responding
    created_at: float = field(default_factory=time.monotonic)
    # Future is created when permission request is processed, not at dataclass init
    # This avoids the deprecated asyncio.get_event_loop() call
    future: Optional[asyncio.Future] = field(default=None)


@dataclass
class SessionWebSocketRegistry:
    """Tracks WebSocket connections and state per session."""
    session_id: str
    websockets: Set[Callable[[Dict[str, Any]], Coroutine[Any, Any, None]]] = field(default_factory=set)
    pending_permissions: Dict[str, PendingPermission] = field(default_factory=dict)
    # Tiers that are batch-approved for this session
    batch_approved_tiers: Set[str] = field(default_factory=set)


class ACPRunnerClient:
    def __init__(self, config: ACPRunnerConfig) -> None:
        self.config = config
        self._client = ACPStdioClient(
            command=config.command,
            args=config.args,
            env=config.env,
            cwd=config.cwd,
        )
        self._client.set_notification_handler(self._handle_notification)
        self._client.set_request_handler(self._handle_request)
        self._updates: Dict[str, Deque[Dict[str, Any]]] = defaultdict(deque)
        self._agent_capabilities: Dict[str, Any] = {}
        # WebSocket registry per session
        self._ws_registry: Dict[str, SessionWebSocketRegistry] = {}
        self._ws_registry_lock = asyncio.Lock()

    @classmethod
    def from_config(cls) -> "ACPRunnerClient":
        return cls(load_acp_runner_config())

    @property
    def agent_capabilities(self) -> Dict[str, Any]:
        return self._agent_capabilities

    @property
    def is_running(self) -> bool:
        return self._client.is_running

    async def start(self) -> None:
        if not self._client.is_running:
            await self._client.start()
        if self.config.startup_timeout_sec > 0:
            await asyncio.wait_for(self.initialize(), timeout=self.config.startup_timeout_sec)
        else:
            await self.initialize()

    async def initialize(self) -> Dict[str, Any]:
        response = await self._client.call(
            "initialize",
            {
                "protocolVersion": 1,
                "clientCapabilities": {
                    "fs": {"readTextFile": False, "writeTextFile": False},
                    "terminal": False,
                },
                "clientInfo": {
                    "name": "tldw-server",
                    "title": "TLDW Server",
                    "version": "0.1.0",
                },
            },
        )
        result = response.result or {}
        self._agent_capabilities = result.get("agentCapabilities", {}) or {}
        return result

    async def create_session(
        self,
        cwd: str,
        mcp_servers: Optional[List[Dict[str, Any]]] = None,
        agent_type: Optional[str] = None,
    ) -> str:
        params: Dict[str, Any] = {"cwd": cwd}
        if mcp_servers:
            params["mcpServers"] = mcp_servers
        if agent_type:
            params["agentType"] = agent_type
        response = await self._client.call("session/new", params)
        result = response.result or {}
        session_id = result.get("sessionId")
        if not session_id:
            raise ACPResponseError("Missing sessionId in response")
        return session_id

    async def prompt(self, session_id: str, prompt: List[Dict[str, Any]]) -> Dict[str, Any]:
        response = await self._client.call(
            "session/prompt",
            {
                "sessionId": session_id,
                "prompt": prompt,
            },
        )
        return response.result or {}

    async def cancel(self, session_id: str) -> None:
        await self._client.notify("session/cancel", {"sessionId": session_id})

    async def close_session(self, session_id: str) -> None:
        await self._client.call("_tldw/session/close", {"sessionId": session_id})
        self._updates.pop(session_id, None)

    def pop_updates(self, session_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        updates = []
        queue = self._updates.get(session_id)
        if not queue:
            return updates
        for _ in range(min(limit, len(queue))):
            updates.append(queue.popleft())
        return updates

    async def shutdown(self) -> None:
        await self._client.close()

    # -------------------------------------------------------------------------
    # WebSocket Registry Management
    # -------------------------------------------------------------------------

    async def register_websocket(
        self,
        session_id: str,
        send_callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Register a WebSocket send callback for a session."""
        async with self._ws_registry_lock:
            if session_id not in self._ws_registry:
                self._ws_registry[session_id] = SessionWebSocketRegistry(session_id=session_id)
            self._ws_registry[session_id].websockets.add(send_callback)
            logger.debug("Registered WebSocket for session {}", session_id)

    async def unregister_websocket(
        self,
        session_id: str,
        send_callback: Callable[[Dict[str, Any]], Coroutine[Any, Any, None]],
    ) -> None:
        """Unregister a WebSocket send callback for a session."""
        async with self._ws_registry_lock:
            if session_id in self._ws_registry:
                self._ws_registry[session_id].websockets.discard(send_callback)
                logger.debug("Unregistered WebSocket for session {}", session_id)

    def has_websocket_connections(self, session_id: str) -> bool:
        """Check if a session has any active WebSocket connections."""
        registry = self._ws_registry.get(session_id)
        return registry is not None and len(registry.websockets) > 0

    async def _broadcast_to_session(self, session_id: str, message: Dict[str, Any]) -> None:
        """Broadcast a message to all WebSockets connected to a session."""
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

        # Remove failed callbacks
        for callback in failed_callbacks:
            registry.websockets.discard(callback)

    # -------------------------------------------------------------------------
    # Permission Management
    # -------------------------------------------------------------------------

    async def respond_to_permission(
        self,
        session_id: str,
        request_id: str,
        approved: bool,
        batch_approve_tier: Optional[str] = None,
    ) -> bool:
        """Respond to a pending permission request.

        Returns True if the permission was found and responded to.
        """
        registry = self._ws_registry.get(session_id)
        if not registry:
            logger.warning("No registry for session {} when responding to permission", session_id)
            return False

        pending = registry.pending_permissions.pop(request_id, None)
        if not pending:
            logger.warning("Permission request {} not found for session {}", request_id, session_id)
            return False

        # Handle batch approval tier
        if approved and batch_approve_tier:
            registry.batch_approved_tiers.add(batch_approve_tier)
            logger.info("Batch-approved tier {} for session {}", batch_approve_tier, session_id)

        # Resolve the permission future
        outcome = "approved" if approved else "denied"
        if not pending.future.done():
            pending.future.set_result({"outcome": outcome})

        return True

    def _determine_permission_tier(self, tool_name: str) -> str:
        """Determine the permission tier for a tool based on its name.

        This is a heuristic based on common patterns:
        - Read operations: auto
        - Write operations: batch
        - Execute/delete operations: individual
        """
        tool_lower = tool_name.lower()

        # Auto-approve tier (read-only)
        auto_patterns = ["read", "get", "list", "search", "find", "view", "show", "glob", "grep", "status"]
        if any(p in tool_lower for p in auto_patterns):
            return "auto"

        # Individual approval tier (destructive)
        individual_patterns = ["delete", "remove", "exec", "run", "shell", "bash", "terminal", "push", "force"]
        if any(p in tool_lower for p in individual_patterns):
            return "individual"

        # Default to batch tier (write operations)
        return "batch"

    # -------------------------------------------------------------------------
    # Notification and Request Handlers
    # -------------------------------------------------------------------------

    async def _handle_notification(self, msg: ACPMessage) -> None:
        if msg.method != "session/update":
            return
        params = msg.params or {}
        session_id = params.get("sessionId")
        if not session_id:
            return

        # Queue update for polling clients
        self._updates[session_id].append(params)

        # Broadcast to WebSocket clients
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

        # Determine permission tier
        tier = self._determine_permission_tier(tool_name)

        # Check if tier is batch-approved
        registry = self._ws_registry.get(session_id)
        if registry and tier in registry.batch_approved_tiers:
            logger.info("Auto-approving {} (tier {} is batch-approved)", tool_name, tier)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "approved"}},
            )

        # Check if tier is auto-approve
        if tier == "auto":
            logger.debug("Auto-approving {} (auto tier)", tool_name)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "approved"}},
            )

        # Check if we have WebSocket connections to ask for permission
        if not self.has_websocket_connections(session_id):
            logger.warning("ACP permission request auto-cancelled (no WebSocket connections)")
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "cancelled"}},
            )

        # Create pending permission with future for async response
        request_id = str(uuid.uuid4())
        pending = PendingPermission(
            request_id=request_id,
            session_id=session_id,
            tool_name=tool_name,
            tool_arguments=tool_arguments,
            acp_message_id=msg.id,
            future=asyncio.get_running_loop().create_future(),
        )

        # Register pending permission
        async with self._ws_registry_lock:
            if session_id not in self._ws_registry:
                self._ws_registry[session_id] = SessionWebSocketRegistry(session_id=session_id)
            self._ws_registry[session_id].pending_permissions[request_id] = pending

        # Broadcast permission request to WebSocket clients
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

        # Re-check connections after broadcast - all might have failed
        if not self.has_websocket_connections(session_id):
            logger.warning("ACP permission request auto-cancelled (all WebSocket connections failed during broadcast)")
            # Clean up pending permission
            async with self._ws_registry_lock:
                if session_id in self._ws_registry:
                    self._ws_registry[session_id].pending_permissions.pop(request_id, None)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "cancelled"}},
            )

        # Wait for permission response with timeout
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
            # Clean up pending permission
            async with self._ws_registry_lock:
                if session_id in self._ws_registry:
                    self._ws_registry[session_id].pending_permissions.pop(request_id, None)
            return ACPMessage(
                jsonrpc="2.0",
                id=msg.id,
                result={"outcome": {"outcome": "cancelled"}},
            )


_runner_client: Optional[ACPRunnerClient] = None
_runner_lock = asyncio.Lock()


async def get_runner_client() -> ACPRunnerClient:
    global _runner_client
    async with _runner_lock:
        if _runner_client is None or not _runner_client.is_running:
            _runner_client = ACPRunnerClient.from_config()
            await _runner_client.start()
        return _runner_client
