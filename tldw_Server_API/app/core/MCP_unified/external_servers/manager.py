"""Manager scaffold for external MCP server federation."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional

from loguru import logger

from .config_schema import ExternalMCPServerConfig, load_external_server_registry
from .transports import ExternalMCPTransportAdapter, build_transport_adapter


@dataclass(slots=True)
class VirtualExternalTool:
    """External tool exposed through a namespaced virtual name."""

    virtual_name: str
    server_id: str
    upstream_tool_name: str
    description: str
    input_schema: dict[str, Any]
    metadata: dict[str, Any]
    is_write: bool = False


class ExternalServerManager:
    """Lifecycle and routing manager for external MCP federation.

    This manager is intentionally conservative: discovery failures are isolated to
    the impacted external server and do not crash MCP Unified startup.
    """

    def __init__(self, config_path: Optional[str] = None) -> None:
        self.config_path = config_path
        self._servers: dict[str, ExternalMCPServerConfig] = {}
        self._adapters: dict[str, ExternalMCPTransportAdapter] = {}
        self._virtual_tools: dict[str, VirtualExternalTool] = {}
        self._discovery_errors: dict[str, str] = {}
        self._initialized = False

    @property
    def initialized(self) -> bool:
        return self._initialized

    async def initialize(self) -> None:
        """Load config, construct adapters, and attempt initial discovery."""

        cfg = load_external_server_registry(self.config_path)
        self._servers = {s.id: s for s in cfg.servers if s.enabled}
        self._adapters = {}
        self._virtual_tools = {}
        self._discovery_errors = {}

        for server in self._servers.values():
            adapter = build_transport_adapter(server)
            self._adapters[server.id] = adapter
            try:
                await adapter.connect()
                await self._refresh_server_tools(server.id)
                self._discovery_errors.pop(server.id, None)
            except Exception as exc:
                self._discovery_errors[server.id] = str(exc)
                self._clear_server_tools(server.id)
                logger.warning(
                    "External MCP server '{}' failed initialization/discovery: {}",
                    server.id,
                    exc,
                )

        self._initialized = True

    async def shutdown(self) -> None:
        """Close all external transport adapters."""

        for server_id, adapter in list(self._adapters.items()):
            try:
                await adapter.close()
            except Exception as exc:
                logger.warning(f"External MCP adapter close failed for {server_id}: {exc}")
        self._adapters = {}
        self._virtual_tools = {}
        self._discovery_errors = {}
        self._initialized = False

    async def refresh_discovery(self, server_id: Optional[str] = None) -> dict[str, Any]:
        """Refresh virtual tool cache for one server or all configured servers."""

        target_ids = [server_id] if server_id else sorted(self._adapters.keys())
        refreshed = 0
        errors: dict[str, str] = {}

        for sid in target_ids:
            if sid not in self._adapters:
                errors[sid] = "unknown_server"
                continue
            try:
                await self._refresh_server_tools(sid)
                refreshed += 1
                self._discovery_errors.pop(sid, None)
            except Exception as exc:
                errors[sid] = str(exc)
                self._discovery_errors[sid] = str(exc)
                self._clear_server_tools(sid)

        return {
            "refreshed_servers": refreshed,
            "total_servers": len(target_ids),
            "virtual_tools": len(self._virtual_tools),
            "errors": errors,
        }

    async def list_servers(self) -> list[dict[str, Any]]:
        """Return summarized status for configured external servers."""

        rows: list[dict[str, Any]] = []
        for server_id in sorted(self._servers.keys()):
            server = self._servers[server_id]
            adapter = self._adapters.get(server_id)
            checks = {"configured": True, "connected": False}
            if adapter is not None:
                try:
                    checks = await adapter.health_check()
                except Exception as exc:
                    checks = {"configured": True, "connected": False, "error": True}
                    self._discovery_errors[server_id] = str(exc)

            connected = bool(checks.get("connected"))
            discovery_ok = server_id not in self._discovery_errors
            if connected and discovery_ok:
                status = "healthy"
            elif connected or discovery_ok:
                status = "degraded"
            else:
                status = "unhealthy"

            rows.append(
                {
                    "id": server.id,
                    "name": server.name,
                    "transport": server.transport.value,
                    "tool_count": self._count_tools_for_server(server.id),
                    "status": status,
                    "discovery_ok": discovery_ok,
                    "checks": checks,
                    "last_error": self._discovery_errors.get(server.id),
                }
            )
        return rows

    def list_virtual_tools(self) -> list[VirtualExternalTool]:
        """Return all currently discovered virtual tools."""

        return [self._virtual_tools[name] for name in sorted(self._virtual_tools.keys())]

    async def execute_virtual_tool(
        self,
        virtual_tool_name: str,
        arguments: dict[str, Any],
        context: Optional[Any] = None,
    ) -> dict[str, Any]:
        """Route a namespaced virtual tool execution to its external adapter."""

        virtual_tool = self._virtual_tools.get(virtual_tool_name)
        if virtual_tool is None:
            raise ValueError(f"Unknown external virtual tool '{virtual_tool_name}'")

        server_id = virtual_tool.server_id
        upstream_tool_name = virtual_tool.upstream_tool_name
        adapter = self._adapters.get(server_id)
        if adapter is None:
            raise ValueError(f"Unknown external server '{server_id}'")

        server_cfg = self._servers[server_id]
        if not server_cfg.policy.allows_tool(upstream_tool_name):
            raise PermissionError(
                f"External tool '{upstream_tool_name}' is blocked by local policy for server '{server_id}'"
            )

        call_args = dict(arguments or {})
        if virtual_tool.is_write:
            if not server_cfg.policy.allow_writes:
                raise PermissionError(
                    f"External write tool '{upstream_tool_name}' is disabled by local policy for server '{server_id}'"
                )
            if server_cfg.policy.require_write_confirmation and not bool(call_args.get("__confirm_write")):
                raise PermissionError(
                    "Write confirmation required. Re-run with '__confirm_write': true."
                )
            call_args.pop("__confirm_write", None)

        result = await adapter.call_tool(upstream_tool_name, call_args, context=context)
        return {
            "content": result.content,
            "is_error": result.is_error,
            "server_id": server_id,
            "upstream_tool": upstream_tool_name,
            "metadata": result.metadata,
        }

    @staticmethod
    def parse_virtual_tool_name(virtual_tool_name: str) -> tuple[str, str]:
        """Parse `ext.<server_id>.<tool_name>` into `(server_id, tool_name)` parts."""

        if not virtual_tool_name.startswith("ext."):
            raise ValueError("External tool names must start with 'ext.'")

        parts = virtual_tool_name.split(".", 2)
        if len(parts) != 3 or not parts[1] or not parts[2]:
            raise ValueError("External tool name must match 'ext.<server_id>.<tool_name>'")

        return parts[1], parts[2]

    async def _refresh_server_tools(self, server_id: str) -> None:
        """Refresh discovery cache for a single server."""

        adapter = self._adapters[server_id]
        tools = await adapter.list_tools()
        server_cfg = self._servers[server_id]

        server_tools: dict[str, VirtualExternalTool] = {}

        for tool in tools:
            if not server_cfg.policy.allows_tool(tool.name):
                continue
            virtual_name = self._virtual_tool_name(server_id, tool.name)
            tool_metadata = dict(tool.metadata or {})
            server_tools[virtual_name] = VirtualExternalTool(
                virtual_name=virtual_name,
                server_id=server_id,
                upstream_tool_name=tool.name,
                description=tool.description,
                input_schema=tool.input_schema,
                metadata=tool_metadata,
                is_write=self._is_write_tool(tool.name, tool_metadata),
            )

        # Replace only this server's tools while preserving other caches.
        self._clear_server_tools(server_id)
        self._virtual_tools.update(server_tools)

    @staticmethod
    def _virtual_tool_name(server_id: str, tool_name: str) -> str:
        return f"ext.{server_id}.{tool_name}"

    def _clear_server_tools(self, server_id: str) -> None:
        self._virtual_tools = {
            name: tool
            for name, tool in self._virtual_tools.items()
            if tool.server_id != server_id
        }

    def _count_tools_for_server(self, server_id: str) -> int:
        return sum(1 for tool in self._virtual_tools.values() if tool.server_id == server_id)

    @staticmethod
    def _is_write_tool(tool_name: str, metadata: dict[str, Any]) -> bool:
        """Best-effort write classification for external tools."""

        annotations = metadata.get("annotations")
        if isinstance(annotations, dict):
            read_only_hint = annotations.get("readOnlyHint")
            if isinstance(read_only_hint, bool):
                return not read_only_hint

        for key in ("read_only", "readOnly", "is_read_only"):
            value = metadata.get(key)
            if isinstance(value, bool):
                return not value

        category = str(metadata.get("category") or "").strip().lower()
        if category in {"read", "discovery", "search"}:
            return False
        if category in {"ingestion", "management", "write", "mutation", "admin"}:
            return True

        lowered = str(tool_name).lower()
        tokens = [token for token in re.split(r"[^a-z0-9]+", lowered) if token]
        write_tokens = {
            "create",
            "update",
            "delete",
            "remove",
            "write",
            "set",
            "insert",
            "upsert",
            "patch",
            "put",
            "post",
            "ingest",
            "import",
            "exec",
            "execute",
            "run",
        }
        return any(token in write_tokens for token in tokens)


__all__ = ["ExternalServerManager", "VirtualExternalTool"]
