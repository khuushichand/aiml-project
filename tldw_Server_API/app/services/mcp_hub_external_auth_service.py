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
        slot_values = secret_payload.get("slots")
        if isinstance(slot_values, dict):
            slot_values = {
                str(name).strip().lower(): str(value or "").strip()
                for name, value in slot_values.items()
                if str(name or "").strip()
            }
        else:
            slot_values = {}
        required_slots = [
            str(slot).strip().lower()
            for slot in (auth.get("required_slots") or [])
            if str(slot or "").strip()
        ]
        slot_bindings = dict(auth.get("slot_bindings") or {})
        secret = str(secret_payload.get("secret") or secret_payload.get("api_key") or "").strip()

        if mode in {"", "none"}:
            return {"headers": {}}
        if required_slots:
            headers: dict[str, str] = {}
            for slot_name in required_slots:
                slot_secret = str(slot_values.get(slot_name) or "").strip()
                if not slot_secret:
                    raise ValueError(f"Managed auth requires configured slot secret: {slot_name}")
                binding = dict(slot_bindings.get(slot_name) or {})
                inject = str(binding.get("inject") or "").strip().lower()
                if inject != "header":
                    raise ValueError(f"Unsupported managed slot injection for {slot_name}: {inject or 'missing'}")
                header_name = str(binding.get("header_name") or "").strip()
                if not header_name:
                    raise ValueError(f"Managed auth slot binding requires header_name: {slot_name}")
                prefix = str(binding.get("prefix") or "")
                headers[header_name] = f"{prefix}{slot_secret}"
            return {"headers": headers}
        if mode == "bearer_token":
            if not secret:
                raise ValueError("Managed bearer token auth requires a configured secret")
            return {"headers": {"Authorization": f"Bearer {secret}"}}
        if mode == "api_key_header":
            header_name = str(auth.get("api_key_header") or "X-API-KEY")
            if not secret:
                raise ValueError("Managed API key header auth requires a configured secret")
            return {"headers": {header_name: secret}}

        raise ValueError(f"Unsupported managed auth mode: {mode}")
