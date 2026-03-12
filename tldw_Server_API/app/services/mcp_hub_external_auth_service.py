from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class ManagedExternalAuthBridge:
    """Hydrate managed MCP Hub external auth config into runtime auth material."""

    @staticmethod
    def _normalize_slot_values(secret_payload: dict[str, Any]) -> dict[str, str]:
        slot_values = secret_payload.get("slots")
        if not isinstance(slot_values, dict):
            return {}
        return {
            str(name).strip().lower(): str(value or "").strip()
            for name, value in slot_values.items()
            if str(name or "").strip()
        }

    @staticmethod
    def _transport_target_for_server(server_config: dict[str, Any]) -> str | None:
        transport = str(server_config.get("transport") or "").strip().lower()
        if transport == "websocket":
            return "header"
        if transport == "stdio":
            return "env"
        return None

    @classmethod
    def _extract_template_mappings(cls, auth: dict[str, Any]) -> list[dict[str, Any]] | None:
        raw_mappings = auth.get("mappings")
        if isinstance(raw_mappings, list) and raw_mappings:
            mappings: list[dict[str, Any]] = []
            for raw_mapping in raw_mappings:
                if not isinstance(raw_mapping, dict):
                    raise ValueError("Managed auth template mappings must be objects")
                mappings.append(
                    {
                        "slot_name": str(raw_mapping.get("slot_name") or "").strip().lower(),
                        "target_type": str(raw_mapping.get("target_type") or "").strip().lower(),
                        "target_name": str(raw_mapping.get("target_name") or "").strip(),
                        "prefix": str(raw_mapping.get("prefix") or ""),
                        "suffix": str(raw_mapping.get("suffix") or ""),
                        "required": bool(raw_mapping.get("required", True)),
                    }
                )
            return mappings

        required_slots = [
            str(slot).strip().lower()
            for slot in (auth.get("required_slots") or [])
            if str(slot or "").strip()
        ]
        if not required_slots:
            return None

        slot_bindings = dict(auth.get("slot_bindings") or {})
        mappings = []
        for slot_name in required_slots:
            binding = dict(slot_bindings.get(slot_name) or {})
            inject = str(binding.get("inject") or "").strip().lower()
            if inject == "header":
                target_name = str(binding.get("header_name") or "").strip()
            elif inject == "env":
                target_name = str(binding.get("env_name") or "").strip()
            else:
                raise ValueError(f"Unsupported managed slot injection for {slot_name}: {inject or 'missing'}")
            mappings.append(
                {
                    "slot_name": slot_name,
                    "target_type": inject,
                    "target_name": target_name,
                    "prefix": str(binding.get("prefix") or ""),
                    "suffix": str(binding.get("suffix") or ""),
                    "required": True,
                }
            )
        return mappings

    @classmethod
    def get_required_slot_names(
        cls,
        *,
        server_config: dict[str, Any],
    ) -> list[str]:
        config = dict(server_config.get("config") or {})
        auth = dict(config.get("auth") or {})
        mappings = cls._extract_template_mappings(auth)
        if not mappings:
            return []
        required_slots: list[str] = []
        for mapping in mappings:
            slot_name = str(mapping.get("slot_name") or "").strip().lower()
            if not slot_name or not bool(mapping.get("required", True)):
                continue
            if slot_name not in required_slots:
                required_slots.append(slot_name)
        return required_slots

    async def hydrate_runtime_auth(
        self,
        *,
        server_config: dict[str, Any],
        secret_payload: dict[str, Any],
    ) -> dict[str, Any]:
        config = dict(server_config.get("config") or {})
        auth = dict(config.get("auth") or {})
        mode = str(auth.get("mode") or "none").strip().lower()
        slot_values = self._normalize_slot_values(secret_payload)
        secret = str(secret_payload.get("secret") or secret_payload.get("api_key") or "").strip()
        headers: dict[str, str] = {}
        env: dict[str, str] = {}

        if mode in {"", "none"}:
            return {"headers": headers, "env": env}

        template_mappings = self._extract_template_mappings(auth)
        if template_mappings:
            expected_target = self._transport_target_for_server(server_config)
            if expected_target is None:
                raise ValueError("Managed auth templates are supported only for websocket and stdio transport")
            seen_targets: set[tuple[str, str]] = set()
            for mapping in template_mappings:
                slot_name = str(mapping.get("slot_name") or "").strip().lower()
                target_type = str(mapping.get("target_type") or "").strip().lower()
                target_name = str(mapping.get("target_name") or "").strip()
                if not slot_name:
                    raise ValueError("Managed auth template mapping requires slot_name")
                if target_type not in {"header", "env"}:
                    raise ValueError(f"Unsupported auth template target_type: {target_type or 'missing'}")
                if target_type != expected_target:
                    raise ValueError(
                        f"Managed auth template target_type '{target_type}' is invalid for transport "
                        f"'{str(server_config.get('transport') or '').strip().lower() or 'missing'}'"
                    )
                if not target_name:
                    raise ValueError("Managed auth template mapping requires target_name")
                target_key = (target_type, target_name.lower())
                if target_key in seen_targets:
                    raise ValueError("Managed auth template contains duplicate target mappings")
                seen_targets.add(target_key)

                slot_secret = str(slot_values.get(slot_name) or "").strip()
                required = bool(mapping.get("required", True))
                if not slot_secret:
                    if required:
                        raise ValueError(f"Managed auth requires configured slot secret: {slot_name}")
                    continue
                formatted = f"{str(mapping.get('prefix') or '')}{slot_secret}{str(mapping.get('suffix') or '')}"
                if target_type == "header":
                    headers[target_name] = formatted
                else:
                    env[target_name] = formatted
            return {"headers": headers, "env": env}
        if mode == "bearer_token":
            if not secret:
                raise ValueError("Managed bearer token auth requires a configured secret")
            return {"headers": {"Authorization": f"Bearer {secret}"}, "env": env}
        if mode == "api_key_header":
            header_name = str(auth.get("api_key_header") or "X-API-KEY")
            if not secret:
                raise ValueError("Managed API key header auth requires a configured secret")
            return {"headers": {header_name: secret}, "env": env}

        raise ValueError(f"Unsupported managed auth mode: {mode}")
