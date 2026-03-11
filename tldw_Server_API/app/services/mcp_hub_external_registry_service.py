from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.repos.mcp_hub_repo import McpHubRepo
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    decrypt_byok_payload,
    loads_envelope,
)
from tldw_Server_API.app.core.MCP_unified.external_servers.config_schema import (
    ExternalMCPServerConfig,
    parse_external_server_registry,
)
from tldw_Server_API.app.services.mcp_hub_external_auth_service import (
    ManagedExternalAuthBridge,
)


@dataclass
class McpHubExternalRegistryService:
    """Build executable external server configs from managed MCP Hub state."""

    repo: McpHubRepo
    auth_bridge: ManagedExternalAuthBridge | None = None

    def __post_init__(self) -> None:
        if self.auth_bridge is None:
            self.auth_bridge = ManagedExternalAuthBridge()

    async def list_runtime_servers(self) -> list[ExternalMCPServerConfig]:
        rows = await self.repo.list_external_servers()
        runtime_servers: list[ExternalMCPServerConfig] = []
        for row in rows:
            try:
                payload = await self._build_runtime_payload(row)
                if payload is None:
                    continue
                registry = parse_external_server_registry({"servers": [payload]})
                runtime_servers.extend(registry.servers)
            except Exception as exc:
                logger.warning(
                    "Skipping managed external server '{}' during runtime registry load: {}",
                    row.get("id"),
                    exc,
                )
        return runtime_servers

    @staticmethod
    def _extract_secret_value(secret_payload: dict[str, Any]) -> str:
        return str(
            secret_payload.get("secret")
            or secret_payload.get("api_key")
            or ""
        ).strip()

    async def _build_runtime_payload(self, row: dict[str, Any]) -> dict[str, Any] | None:
        if str(row.get("server_source") or "managed") != "managed":
            return None
        if row.get("superseded_by_server_id"):
            return None
        if not bool(row.get("enabled")):
            return None

        config = dict(row.get("config") or {})
        auth = dict(config.get("auth") or {})
        mode = str(auth.get("mode") or "none").strip().lower()

        if mode not in {"", "none"}:
            server_id = str(row.get("id") or "")
            required_slots = self.auth_bridge.get_required_slot_names(server_config=row)
            if required_slots:
                slot_payloads: dict[str, str] = {}
                default_slot = await self.repo.get_external_server_default_slot(server_id=server_id)
                default_slot_name = str(default_slot.get("slot_name") or "") if default_slot else ""
                for slot_name in required_slots:
                    secret_row = await self.repo.get_external_server_slot_secret(
                        server_id=server_id,
                        slot_name=slot_name,
                    )
                    if secret_row and str(secret_row.get("encrypted_blob") or "").strip():
                        decrypted = decrypt_byok_payload(loads_envelope(str(secret_row.get("encrypted_blob") or "")))
                        slot_secret = self._extract_secret_value(decrypted)
                    elif slot_name == default_slot_name:
                        legacy_secret = await self.repo.get_external_secret(server_id)
                        if not legacy_secret or not str(legacy_secret.get("encrypted_blob") or "").strip():
                            raise ValueError(f"managed external server requires a configured slot secret: {slot_name}")
                        decrypted = decrypt_byok_payload(loads_envelope(str(legacy_secret.get("encrypted_blob") or "")))
                        slot_secret = self._extract_secret_value(decrypted)
                    else:
                        raise ValueError(f"managed external server requires a configured slot secret: {slot_name}")
                    if not slot_secret:
                        raise ValueError(f"managed external server requires a configured slot secret: {slot_name}")
                    slot_payloads[slot_name] = slot_secret
                secret_payload = {"slots": slot_payloads}
            else:
                secret_row = await self.repo.get_external_secret(server_id)
                if not secret_row or not str(secret_row.get("encrypted_blob") or "").strip():
                    raise ValueError("managed external server requires a configured secret")
                secret_payload = decrypt_byok_payload(loads_envelope(str(secret_row.get("encrypted_blob") or "")))
            runtime_auth = await self.auth_bridge.hydrate_runtime_auth(
                server_config=row,
                secret_payload=secret_payload,
            )
            headers = dict(runtime_auth.get("headers") or {})
            env = dict(runtime_auth.get("env") or {})
            if headers:
                if str(row.get("transport") or "").strip().lower() != "websocket":
                    raise ValueError("managed header auth is currently supported only for websocket transport")
                websocket_cfg = dict(config.get("websocket") or {})
                merged_headers = dict(websocket_cfg.get("headers") or {})
                merged_headers.update(headers)
                websocket_cfg["headers"] = merged_headers
                config["websocket"] = websocket_cfg
            if env:
                if str(row.get("transport") or "").strip().lower() != "stdio":
                    raise ValueError("managed env auth is currently supported only for stdio transport")
                stdio_cfg = dict(config.get("stdio") or {})
                merged_env = dict(stdio_cfg.get("env") or {})
                merged_env.update(env)
                stdio_cfg["env"] = merged_env
                config["stdio"] = stdio_cfg
            config["auth"] = {"mode": "none"}

        payload = {
            "id": str(row.get("id") or ""),
            "name": str(row.get("name") or ""),
            "enabled": bool(row.get("enabled")),
            "transport": str(row.get("transport") or ""),
            **config,
        }
        return payload


async def get_mcp_hub_external_registry_service() -> McpHubExternalRegistryService:
    """Resolve the managed external runtime registry service from the active AuthNZ DB."""
    pool = await get_db_pool()
    repo = McpHubRepo(pool)
    await repo.ensure_tables()
    return McpHubExternalRegistryService(repo=repo)
