"""MCPSSETransport — SSE-based MCP transport."""
from __future__ import annotations

import asyncio
import json
from typing import Any
from urllib.parse import urljoin

import httpx
from loguru import logger

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_transport import (
    MCPTransport,
)


class MCPSSETransport(MCPTransport):
    """MCP transport over Server-Sent Events.

    Uses two channels:
    - **Server -> Client:** SSE stream at ``sse_url`` for JSON-RPC responses/notifications
    - **Client -> Server:** HTTP POST to ``post_url`` for JSON-RPC requests

    Connection flow:
    1. Open SSE stream to ``sse_url``
    2. If ``post_url`` is not provided, discover it from the first SSE ``endpoint`` event
    3. Start background reader task for SSE stream
    4. Perform MCP ``initialize`` / ``initialized`` handshake
    """

    def __init__(
        self,
        sse_url: str,
        post_url: str | None = None,
        headers: dict[str, str] | None = None,
        timeout_sec: int = 30,
    ) -> None:
        self._sse_url = sse_url
        self._post_url = post_url
        self._headers = headers
        self._timeout_sec = timeout_sec
        self._http_client: httpx.AsyncClient | None = None
        self._pending: dict[str, asyncio.Future] = {}
        self._next_id = 1
        self._reader_task: asyncio.Task | None = None
        self._connected = False
        # SSE line parser state
        self._sse_event_type: str | None = None
        self._sse_data: str | None = None

    # ------------------------------------------------------------------
    # MCPTransport interface
    # ------------------------------------------------------------------

    @property
    def is_connected(self) -> bool:
        return self._connected

    async def connect(self) -> None:
        """Open the SSE stream, discover post_url if needed, and perform MCP handshake."""
        self._http_client = self._create_http_client()

        if not self._post_url:
            self._post_url = await self._discover_post_url()
            logger.info("SSE transport discovered post_url: {}", self._post_url)

        self._reader_task = asyncio.create_task(self._sse_reader_loop())

        init_result = await self._json_rpc_call("initialize", {
            "protocolVersion": "2024-11-05",
            "clientInfo": {"name": "tldw_acp_harness", "version": "0.1.0"},
            "capabilities": {},
        })
        logger.debug("MCP initialize response: {}", init_result)

        await self._json_rpc_notify("initialized", {})
        self._connected = True
        logger.info("SSE transport connected to {}", self._sse_url)

    async def close(self) -> None:
        """Cancel reader task, close HTTP client, mark disconnected."""
        if self._reader_task is not None:
            self._reader_task.cancel()
            self._reader_task = None
        if self._http_client is not None:
            await self._http_client.aclose()
            self._http_client = None
        # Cancel any pending futures
        for future in self._pending.values():
            if not future.done():
                future.cancel()
        self._pending.clear()
        self._connected = False

    async def list_tools(self) -> list[dict[str, Any]]:
        """Request the tool list from the MCP server."""
        if not self._connected:
            raise RuntimeError("Not connected")
        result = await self._json_rpc_call("tools/list", {})
        return result.get("tools", [])

    async def call_tool(
        self, tool_name: str, arguments: dict[str, Any],
    ) -> dict[str, Any]:
        """Invoke a tool on the MCP server and return the result."""
        if not self._connected:
            raise RuntimeError("Not connected")
        return await self._json_rpc_call(
            "tools/call", {"name": tool_name, "arguments": arguments},
        )

    async def health_check(self) -> bool:
        """Return True if the transport is connected."""
        return self._connected

    # ------------------------------------------------------------------
    # HTTP client factory (patchable in tests)
    # ------------------------------------------------------------------

    def _create_http_client(self) -> httpx.AsyncClient:
        """Create an httpx.AsyncClient. Extracted for test patching."""
        return httpx.AsyncClient(
            headers=self._headers or {},
            timeout=httpx.Timeout(self._timeout_sec),
        )

    # ------------------------------------------------------------------
    # SSE discovery
    # ------------------------------------------------------------------

    async def _discover_post_url(self) -> str:
        """Connect to the SSE stream and read the first ``endpoint`` event.

        The MCP spec says the first event has ``event: endpoint`` with
        ``data: <relative_url>``.  We resolve this against the ``sse_url``
        base to get the absolute POST URL.
        """
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        async with self._http_client.stream("GET", self._sse_url) as response:
            async for raw_line in response.aiter_lines():
                event = self._parse_sse_line(raw_line)
                if event is not None:
                    event_type, data = event
                    if event_type == "endpoint":
                        # Resolve relative URL against sse_url base
                        base = self._sse_url.rsplit("/", 1)[0] + "/"
                        return urljoin(base, data)

        raise RuntimeError(
            f"SSE stream at {self._sse_url} closed without sending an endpoint event"
        )

    # ------------------------------------------------------------------
    # SSE reader loop
    # ------------------------------------------------------------------

    async def _sse_reader_loop(self) -> None:
        """Long-running task: read SSE stream, parse events, route responses."""
        if self._http_client is None:
            return
        try:
            async with self._http_client.stream("GET", self._sse_url) as response:
                async for raw_line in response.aiter_lines():
                    event = self._parse_sse_line(raw_line)
                    if event is None:
                        continue
                    event_type, data = event
                    if event_type == "message":
                        self._route_sse_message(data)
        except asyncio.CancelledError:
            logger.debug("SSE reader loop cancelled")
        except Exception:
            logger.exception("SSE reader loop error")
            self._connected = False

    def _route_sse_message(self, data: str) -> None:
        """Parse a JSON-RPC message from SSE data and resolve the pending future."""
        try:
            msg = json.loads(data)
        except json.JSONDecodeError:
            logger.warning("SSE: ignoring non-JSON message: {}", data[:200])
            return

        msg_id = msg.get("id")
        if msg_id is not None:
            msg_id = str(msg_id)
            future = self._pending.pop(msg_id, None)
            if future is not None and not future.done():
                if "error" in msg:
                    future.set_exception(
                        RuntimeError(f"JSON-RPC error: {msg['error']}")
                    )
                else:
                    future.set_result(msg.get("result", {}))
            elif future is None:
                logger.warning("SSE: no pending future for id={}", msg_id)
        else:
            # Notification from server (no id) — log for now
            logger.debug("SSE server notification: {}", msg.get("method", "unknown"))

    # ------------------------------------------------------------------
    # SSE line parser
    # ------------------------------------------------------------------

    def _parse_sse_line(self, line: str) -> tuple[str, str] | None:
        """Parse a single SSE line and return a complete event when ready.

        SSE events are separated by blank lines. Each event consists of
        ``event:`` and ``data:`` fields.  Returns ``(event_type, data)``
        when a blank line (event boundary) is encountered and there is a
        complete event buffered.  Returns ``None`` otherwise.
        """
        line = line.rstrip("\r\n")

        if line.startswith("event:"):
            self._sse_event_type = line[len("event:"):].strip()
            return None
        elif line.startswith("data:"):
            self._sse_data = line[len("data:"):].strip()
            return None
        elif line == "":
            # Blank line = event boundary
            if self._sse_event_type is not None and self._sse_data is not None:
                event = (self._sse_event_type, self._sse_data)
                self._sse_event_type = None
                self._sse_data = None
                return event
            # Reset even if incomplete
            self._sse_event_type = None
            self._sse_data = None
            return None
        else:
            # Comment or unknown field — ignore
            return None

    # ------------------------------------------------------------------
    # JSON-RPC helpers
    # ------------------------------------------------------------------

    async def _json_rpc_call(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        """Send a JSON-RPC request and await the response via the SSE stream.

        Assigns an incrementing id, creates a Future in ``_pending``, POSTs
        the request, and waits for the SSE reader to resolve the Future.
        """
        req_id = str(self._next_id)
        self._next_id += 1

        loop = asyncio.get_running_loop()
        future: asyncio.Future[dict[str, Any]] = loop.create_future()
        self._pending[req_id] = future

        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        await self._http_client.post(
            self._post_url,  # type: ignore[arg-type]
            json={
                "jsonrpc": "2.0",
                "id": req_id,
                "method": method,
                "params": params,
            },
        )

        return await asyncio.wait_for(future, timeout=self._timeout_sec)

    async def _json_rpc_notify(self, method: str, params: dict[str, Any]) -> None:
        """Send a JSON-RPC notification (no id, no response expected)."""
        if self._http_client is None:
            raise RuntimeError("HTTP client not initialized")

        await self._http_client.post(
            self._post_url,  # type: ignore[arg-type]
            json={
                "jsonrpc": "2.0",
                "method": method,
                "params": params,
            },
        )
