from __future__ import annotations

from typing import Any, Dict, List, Optional
from loguru import logger

try:
    from tldw_Server_API.app.core.MCP_unified import get_mcp_server
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPRequest, RequestContext
except Exception:  # pragma: no cover - optional import in minimal environments
    get_mcp_server = None  # type: ignore
    MCPRequest = None  # type: ignore
    RequestContext = None  # type: ignore


class ToolExecutionError(Exception):
    pass


class ToolExecutor:
    """Thin wrapper around MCP Unified protocol for server-side tool execution.

    This keeps Chat and API endpoints decoupled from MCP internals and provides
    a stable surface for argument/permission checks.
    """

    def __init__(self) -> None:
        if get_mcp_server is None:
            raise RuntimeError("MCP Unified module not available")
        self.server = get_mcp_server()

    def _make_context(
        self,
        *,
        user_id: Optional[str],
        client_id: Optional[str],
        request_id: Optional[str] = None,
        admin_override: bool = False,
    ) -> Any:
        if RequestContext is None:
            raise RuntimeError("MCP RequestContext unavailable")
        meta = {"admin_override": bool(admin_override)}
        return RequestContext(
            request_id=str(request_id or "tools"),
            user_id=str(user_id) if user_id else None,
            client_id=str(client_id or "api_client"),
            metadata=meta,
        )

    async def list_tools(self, *, user_id: Optional[str], client_id: Optional[str]) -> Dict[str, Any]:
        ctx = self._make_context(user_id=user_id, client_id=client_id)
        req = MCPRequest(method="tools/list", params={})
        resp = await self.server.protocol.process_request(req, ctx)
        if getattr(resp, "error", None):
            raise ToolExecutionError(str(resp.error))
        return getattr(resp, "result", {}) or {}

    async def execute(
        self,
        *,
        user_id: Optional[str],
        client_id: Optional[str],
        tool_name: str,
        arguments: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
        validate_only: bool = False,
    ) -> Dict[str, Any]:
        if validate_only:
            # Lightweight permission probe via tools/list; skips actual execution
            listing = await self.list_tools(user_id=user_id, client_id=client_id)
            can = False
            for t in listing.get("tools", []) or []:
                if isinstance(t, dict) and t.get("name") == tool_name:
                    can = bool(t.get("canExecute"))
                    break
            if not can:
                raise ToolExecutionError("Permission denied for tool or tool not found")
            return {"validated": True}

        ctx = self._make_context(user_id=user_id, client_id=client_id)
        req = MCPRequest(
            method="tools/call",
            params={
                "name": tool_name,
                "arguments": arguments or {},
                "idempotencyKey": idempotency_key,
            },
        )
        resp = await self.server.protocol.process_request(req, ctx)
        if getattr(resp, "error", None):
            err = getattr(resp.error, "message", str(resp.error))  # type: ignore[attr-defined]
            raise ToolExecutionError(err)
        return getattr(resp, "result", {}) or {}
