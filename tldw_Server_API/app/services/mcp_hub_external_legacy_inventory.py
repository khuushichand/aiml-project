from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tldw_Server_API.app.core.MCP_unified.external_servers.config_schema import (
    load_external_server_registry,
)


def _legacy_source_ref_for_path(config_path: str | None, server_id: str) -> str:
    path = Path(config_path or "")
    suffix = path.suffix.lower()
    if suffix in {".yaml", ".yml"}:
        source = "yaml"
    elif suffix == ".json":
        source = "json"
    else:
        source = "config"
    return f"{source}:{server_id}"


@dataclass
class McpHubExternalLegacyInventoryService:
    """Load file/env-defined external servers as read-only MCP Hub inventory."""

    config_path: str | None = None

    async def list_inventory(self) -> list[dict[str, Any]]:
        registry = await asyncio.to_thread(load_external_server_registry, self.config_path)
        rows: list[dict[str, Any]] = []
        for server in registry.servers:
            model_dump = server.model_dump if hasattr(server, "model_dump") else server.dict  # type: ignore[attr-defined]
            payload = model_dump()
            payload.pop("id", None)
            payload.pop("name", None)
            payload.pop("enabled", None)
            payload.pop("transport", None)
            rows.append(
                {
                    "id": server.id,
                    "name": server.name,
                    "enabled": bool(server.enabled),
                    "transport": str(server.transport.value),
                    "config": payload,
                    "legacy_source_ref": _legacy_source_ref_for_path(self.config_path, server.id),
                }
            )
        return rows

    async def get_inventory_item(self, server_id: str) -> dict[str, Any] | None:
        target = str(server_id or "").strip().lower()
        if not target:
            return None
        for item in await self.list_inventory():
            if str(item.get("id") or "").strip().lower() == target:
                return item
        return None
