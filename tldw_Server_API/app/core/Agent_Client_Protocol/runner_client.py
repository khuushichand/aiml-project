from __future__ import annotations

import asyncio
from collections import defaultdict, deque
from typing import Any, Deque, Dict, List, Optional

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

    async def create_session(self, cwd: str, mcp_servers: Optional[List[Dict[str, Any]]] = None) -> str:
        params: Dict[str, Any] = {"cwd": cwd}
        if mcp_servers:
            params["mcpServers"] = mcp_servers
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

    async def _handle_notification(self, msg: ACPMessage) -> None:
        if msg.method != "session/update":
            return
        params = msg.params or {}
        session_id = params.get("sessionId")
        if not session_id:
            return
        self._updates[session_id].append(params)

    async def _handle_request(self, msg: ACPMessage) -> ACPMessage:
        if msg.method != "session/request_permission":
            return ACPMessage(jsonrpc="2.0", id=msg.id, error={"code": -32601, "message": "method not found"})

        logger.warning("ACP permission request auto-cancelled")
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
