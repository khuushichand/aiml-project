"""StdioAdapter -- wraps ACPStdioClient as a ProtocolAdapter."""
from __future__ import annotations

from typing import Any

from loguru import logger

from .base import AdapterConfig, PromptOptions, ProtocolAdapter
from ..events import AgentEvent, AgentEventKind
from ..permission_tiers import determine_permission_tier
from ..stdio_client import ACPMessage, ACPStdioClient


class StdioAdapter(ProtocolAdapter):
    """Protocol adapter that communicates with an agent over stdio JSON-RPC.

    Expects ``config.protocol_config["client"]`` to be an :class:`ACPStdioClient`
    instance (already started or ready to use).
    """

    protocol_name = "stdio"

    def __init__(self) -> None:
        self._client: ACPStdioClient | None = None
        self._config: AdapterConfig | None = None
        self._connected: bool = False

    # -- ProtocolAdapter interface ------------------------------------------

    async def connect(self, config: AdapterConfig) -> None:
        client: ACPStdioClient = config.protocol_config["client"]
        self._client = client
        self._config = config
        self._connected = True

        # Wire up notification translation
        client.set_notification_handler(self._handle_notification)

    async def disconnect(self) -> None:
        if self._client is not None:
            await self._client.close()
        self._connected = False
        self._client = None

    async def send_prompt(
        self,
        messages: list[dict],
        options: PromptOptions | None = None,
    ) -> None:
        if self._client is None:
            raise RuntimeError("Not connected")
        await self._client.call("prompt", {"messages": messages})

    async def send_tool_result(
        self,
        tool_id: str,
        output: str,
        is_error: bool = False,
    ) -> None:
        if self._client is None:
            raise RuntimeError("Not connected")
        await self._client.call(
            "tool_result",
            {"tool_id": tool_id, "output": output, "is_error": is_error},
        )

    async def cancel(self) -> None:
        if self._client is None:
            raise RuntimeError("Not connected")
        await self._client.notify("cancel", {})

    @property
    def is_connected(self) -> bool:
        return self._connected

    @property
    def supports_streaming(self) -> bool:
        return True

    # -- Internal -----------------------------------------------------------

    async def _handle_notification(self, msg: ACPMessage) -> None:
        """Translate a JSON-RPC notification from the agent into an AgentEvent."""
        if self._config is None:
            return
        params: dict[str, Any] = msg.params if isinstance(msg.params, dict) else {}
        method = msg.method or ""
        msg_type = params.get("type", "")

        kind: AgentEventKind | None = None
        payload: dict[str, Any] = {}

        if method == "result":
            if msg_type == "text":
                kind = AgentEventKind.COMPLETION
                payload = {
                    "text": params.get("text", ""),
                    "stop_reason": params.get("stop_reason"),
                }
            elif msg_type == "tool_result":
                kind = AgentEventKind.TOOL_RESULT
                payload = {
                    "tool_id": params.get("tool_id", ""),
                    "tool_name": params.get("tool_name", ""),
                    "output": params.get("output", ""),
                    "is_error": params.get("is_error", False),
                    "duration_ms": params.get("duration_ms", 0),
                }
        elif method == "update":
            if msg_type == "tool_use":
                tool_name = params.get("tool_name", "")
                kind = AgentEventKind.TOOL_CALL
                payload = {
                    "tool_id": params.get("tool_id", ""),
                    "tool_name": tool_name,
                    "arguments": params.get("arguments", {}),
                    "permission_tier": determine_permission_tier(tool_name),
                }
            elif msg_type == "tool_result":
                kind = AgentEventKind.TOOL_RESULT
                payload = {
                    "tool_id": params.get("tool_id", ""),
                    "tool_name": params.get("tool_name", ""),
                    "output": params.get("output", ""),
                    "is_error": params.get("is_error", False),
                    "duration_ms": params.get("duration_ms", 0),
                }
            elif msg_type == "thinking":
                kind = AgentEventKind.THINKING
                payload = {
                    "text": params.get("text", ""),
                    "is_partial": params.get("is_partial", False),
                }
            elif msg_type == "permission_request":
                kind = AgentEventKind.PERMISSION_REQUEST
                payload = {
                    "request_id": params.get("request_id", ""),
                    "tool_name": params.get("tool_name", ""),
                    "arguments": params.get("arguments", {}),
                    "tier": params.get("tier", "batch"),
                    "timeout_sec": params.get("timeout_sec", 300),
                }
        elif method == "error":
            kind = AgentEventKind.ERROR
            payload = {
                "code": params.get("code", "agent_error"),
                "message": params.get("message", "Unknown error"),
                "recoverable": params.get("recoverable", False),
            }

        if kind is None:
            logger.warning(
                "StdioAdapter: unhandled notification method={} type={}",
                method,
                msg_type,
            )
            return

        event = AgentEvent(
            session_id=self._config.session_id,
            kind=kind,
            payload=payload,
        )
        await self._config.event_callback(event)
