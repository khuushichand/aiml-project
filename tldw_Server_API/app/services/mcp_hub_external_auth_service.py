from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ManagedExternalAuthBridge:
    """Hydrate managed MCP Hub external auth config into runtime auth material."""

    async def hydrate_runtime_auth(
        self,
        *,
        server_config: dict[str, Any],
        secret_payload: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(server_config.get("config") or {})
        auth = dict(config.get("auth") or {})
        mode = str(auth.get("mode") or "none").strip().lower()
        secret = str(secret_payload.get("secret") or "").strip()

        if mode in {"", "none"}:
            return {"headers": {}}
        if mode == "bearer_token":
            return {"headers": {"Authorization": f"Bearer {secret}"}}
        if mode == "api_key_header":
            header_name = str(auth.get("api_key_header") or "X-API-KEY")
            return {"headers": {header_name: secret}}

        raise ValueError(f"Unsupported managed auth mode: {mode}")
