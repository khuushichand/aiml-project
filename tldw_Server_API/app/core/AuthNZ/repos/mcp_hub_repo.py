from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool

_VALID_SCOPE_TYPES = {"global", "org", "team", "user"}
_VALID_CAPABILITY_ADAPTER_SCOPE_TYPES = {"global", "org", "team"}
_VALID_TARGET_TYPES = {"default", "group", "persona"}
_VALID_PROFILE_MODES = {"preset", "custom"}
_VALID_APPROVAL_MODES = {
    "allow_silently",
    "ask_every_time",
    "ask_outside_profile",
    "ask_on_sensitive_actions",
    "temporary_elevation_allowed",
}
_VALID_CREDENTIAL_SLOT_PRIVILEGE_CLASSES = {"read", "write", "admin"}
_VALID_CREDENTIAL_BINDING_TARGET_TYPES = {"profile", "assignment"}
_VALID_CREDENTIAL_BINDING_MODES = {"grant", "disable"}
_UNSET = object()


def _normalize_scope_type(scope_type: str | None) -> str:
    value = (scope_type or "").strip().lower()
    if value in {"organization", "orgs"}:
        return "org"
    if value in {"teams"}:
        return "team"
    if value in _VALID_SCOPE_TYPES:
        return value
    raise ValueError(f"Invalid owner_scope_type: {scope_type}")


def _normalize_capability_adapter_scope_type(scope_type: str | None) -> str:
    value = _normalize_scope_type(scope_type)
    if value not in _VALID_CAPABILITY_ADAPTER_SCOPE_TYPES:
        raise ValueError(f"Invalid capability adapter owner_scope_type: {scope_type}")
    return value


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return bool(value)
    text = str(value).strip().lower()
    return text in {"1", "true", "t", "yes", "y"}


def _normalize_target_type(target_type: str | None) -> str:
    value = str(target_type or "").strip().lower()
    if value not in _VALID_TARGET_TYPES:
        raise ValueError(f"Invalid target_type: {target_type}")
    return value


def _normalize_profile_mode(mode: str | None) -> str:
    value = str(mode or "").strip().lower()
    if value not in _VALID_PROFILE_MODES:
        raise ValueError(f"Invalid profile mode: {mode}")
    return value


def _normalize_approval_mode(mode: str | None) -> str:
    value = str(mode or "").strip().lower()
    if value not in _VALID_APPROVAL_MODES:
        raise ValueError(f"Invalid approval mode: {mode}")
    return value


def _normalize_credential_binding_target_type(target_type: str | None) -> str:
    value = str(target_type or "").strip().lower()
    if value not in _VALID_CREDENTIAL_BINDING_TARGET_TYPES:
        raise ValueError(f"Invalid credential binding target type: {target_type}")
    return value


def _normalize_credential_binding_mode(mode: str | None) -> str:
    value = str(mode or "").strip().lower()
    if value not in _VALID_CREDENTIAL_BINDING_MODES:
        raise ValueError(f"Invalid credential binding mode: {mode}")
    return value


def _normalize_slot_name(slot_name: str | None, *, allow_blank: bool = False) -> str:
    value = str(slot_name or "").strip().lower()
    if not value:
        if allow_blank:
            return ""
        raise ValueError("slot_name is required")
    return value


def _normalize_credential_slot_privilege_class(privilege_class: str | None) -> str:
    value = str(privilege_class or "").strip().lower()
    if value not in _VALID_CREDENTIAL_SLOT_PRIVILEGE_CLASSES:
        raise ValueError(f"Invalid credential slot privilege_class: {privilege_class}")
    return value


def _load_json_dict(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if not raw:
        return {}
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(parsed) if isinstance(parsed, dict) else {}
    return {}


def _load_json_list(raw: Any) -> list[Any]:
    if isinstance(raw, list):
        return list(raw)
    if not raw:
        return []
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return []
        return list(parsed) if isinstance(parsed, list) else []
    return []


def _normalize_string_list(values: Any) -> list[str]:
    if values is None:
        return []
    if not isinstance(values, (list, tuple, set)):
        raise ValueError("supported_environment_requirements must be a list")
    normalized: list[str] = []
    seen: set[str] = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        normalized.append(text)
        seen.add(text)
    return normalized


@dataclass
class McpHubRepo:
    """Data access for MCP Hub ACP profiles and external server configuration."""

    db_pool: DatabasePool

    async def ensure_tables(self) -> None:
        """Ensure MCP Hub tables are available on the current backend."""
        try:
            if getattr(self.db_pool, "pool", None) is not None:
                from tldw_Server_API.app.core.AuthNZ.pg_migrations_extra import (
                    ensure_mcp_hub_tables_pg,
                )

                ok = await ensure_mcp_hub_tables_pg(self.db_pool)
                if not ok:
                    raise RuntimeError("PostgreSQL MCP Hub schema ensure failed")
                return

            required = {
                "mcp_acp_profiles",
                "mcp_approval_decisions",
                "mcp_approval_policies",
                "mcp_capability_adapter_mappings",
                "mcp_credential_bindings",
                "mcp_external_servers",
                "mcp_external_server_credential_slots",
                "mcp_external_server_secrets",
                "mcp_external_server_slot_secrets",
                "mcp_governance_pack_objects",
                "mcp_governance_packs",
                "mcp_path_scope_objects",
                "mcp_permission_profiles",
                "mcp_policy_assignments",
                "mcp_policy_audit_history",
                "mcp_policy_assignment_workspaces",
                "mcp_shared_workspaces",
                "mcp_workspace_set_object_members",
                "mcp_workspace_set_objects",
                "mcp_policy_overrides",
            }
            rows = await self.db_pool.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table'",
                (),
            )
            existing = {
                str(name)
                for row in rows
                if (name := self._row_to_dict(row).get("name")) and str(name) in required
            }
            missing = required - existing
            if missing:
                raise RuntimeError(
                    "SQLite MCP Hub tables are missing. "
                    "Run AuthNZ migrations/bootstrap. "
                    f"Missing: {sorted(missing)}"
                )
        except Exception as exc:
            logger.error(f"McpHubRepo.ensure_tables failed: {exc}")
            raise

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        if row is None:
            return {}
        if isinstance(row, dict):
            return dict(row)
        try:
            return dict(row)
        except Exception as exc:
            logger.debug(f"McpHubRepo._row_to_dict direct cast failed: {exc}")
        try:
            keys = row.keys()
            return {key: row[key] for key in keys}
        except Exception as exc:
            logger.debug(f"McpHubRepo._row_to_dict key extraction failed: {exc}")
            return {}

    @staticmethod
    def _normalize_acp_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        return out

    @staticmethod
    def _normalize_external_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["enabled"] = _to_bool(out.get("enabled"))
        out["secret_configured"] = _to_bool(out.get("secret_configured"))
        out["server_source"] = str(out.get("server_source") or "managed")
        out["legacy_source_ref"] = out.get("legacy_source_ref")
        out["superseded_by_server_id"] = out.get("superseded_by_server_id")
        out["binding_count"] = int(out.get("binding_count") or 0)
        out["runtime_executable"] = bool(
            out.get("runtime_executable")
            if out.get("runtime_executable") is not None
            else (out["server_source"] == "managed" and out["enabled"])
        )
        out["config"] = _load_json_dict(out.get("config_json"))
        return out

    @staticmethod
    def _normalize_external_slot_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["slot_name"] = _normalize_slot_name(out.get("slot_name"))
        out["display_name"] = str(out.get("display_name") or out["slot_name"])
        out["secret_kind"] = str(out.get("secret_kind") or "secret")
        out["privilege_class"] = str(out.get("privilege_class") or "default")
        out["is_required"] = _to_bool(out.get("is_required"))
        out["secret_configured"] = _to_bool(out.get("secret_configured"))
        return out

    @staticmethod
    def _normalize_permission_profile_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["is_immutable"] = _to_bool(out.get("is_immutable"))
        out["policy_document"] = _load_json_dict(out.pop("policy_document_json", None))
        return out

    @staticmethod
    def _normalize_path_scope_object_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["path_scope_document"] = _load_json_dict(out.pop("path_scope_document_json", None))
        return out

    @staticmethod
    def _normalize_policy_assignment_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["is_immutable"] = _to_bool(out.get("is_immutable"))
        out["workspace_source_mode"] = str(out.get("workspace_source_mode") or "").strip().lower() or None
        out["inline_policy_document"] = _load_json_dict(out.pop("inline_policy_document_json", None))
        out["has_override"] = _to_bool(out.get("has_override"))
        out["override_active"] = _to_bool(out.get("override_active"))
        if out.get("override_id") is None:
            out["override_active"] = False
        return out

    @staticmethod
    def _normalize_policy_assignment_workspace_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _normalize_workspace_set_object_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        return out

    @staticmethod
    def _normalize_workspace_set_member_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        return dict(row)

    @staticmethod
    def _normalize_shared_workspace_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["workspace_id"] = str(out.get("workspace_id") or "").strip()
        out["display_name"] = str(out.get("display_name") or "").strip()
        out["absolute_root"] = str(out.get("absolute_root") or "").strip()
        out["owner_scope_type"] = _normalize_scope_type(out.get("owner_scope_type"))
        return out

    @staticmethod
    def _normalize_policy_override_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["broadens_access"] = _to_bool(out.get("broadens_access"))
        out["override_policy_document"] = _load_json_dict(out.pop("override_document_json", None))
        out["grant_authority_snapshot"] = _load_json_dict(
            out.pop("grant_authority_snapshot_json", None)
        )
        return out

    @staticmethod
    def _normalize_approval_policy_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["is_immutable"] = _to_bool(out.get("is_immutable"))
        out["rules"] = _load_json_dict(out.pop("rules_json", None))
        return out

    @staticmethod
    def _normalize_capability_adapter_mapping_row(
        row: dict[str, Any] | None,
    ) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["owner_scope_type"] = _normalize_capability_adapter_scope_type(out.get("owner_scope_type"))
        out["mapping_id"] = str(out.get("mapping_id") or "").strip()
        out["title"] = str(out.get("title") or out["mapping_id"]).strip()
        out["capability_name"] = str(out.get("capability_name") or "").strip()
        out["resolved_policy_document"] = _load_json_dict(
            out.pop("resolved_policy_document_json", None)
        )
        out["supported_environment_requirements"] = _normalize_string_list(
            _load_json_list(out.pop("supported_environment_requirements_json", None))
        )
        return out

    @staticmethod
    def _normalize_governance_pack_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["manifest"] = _load_json_dict(out.pop("manifest_json", None))
        out["normalized_ir"] = _load_json_dict(out.pop("normalized_ir_json", None))
        return out

    @staticmethod
    def _normalize_governance_pack_object_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["object_type"] = str(out.get("object_type") or "").strip().lower()
        out["object_id"] = str(out.get("object_id") or "").strip()
        out["source_object_id"] = str(out.get("source_object_id") or "").strip()
        return out

    @staticmethod
    def _normalize_approval_decision_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["consume_on_match"] = _to_bool(out.get("consume_on_match"))
        return out

    @staticmethod
    def _normalize_credential_binding_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        usage_rules = _load_json_dict(out.pop("usage_rules_json", None))
        out["usage_rules"] = usage_rules
        out["slot_name"] = _normalize_slot_name(out.get("slot_name"), allow_blank=True) or None
        out["binding_mode"] = str(
            out.get("binding_mode") or usage_rules.get("binding_mode") or "grant"
        )
        return out

    @staticmethod
    def _command_touched_rows(result: Any) -> bool:
        if result is None:
            return False
        if isinstance(result, str):
            return result.upper().startswith(("UPDATE ", "DELETE ", "INSERT "))
        rowcount = getattr(result, "rowcount", None)
        if isinstance(rowcount, int):
            return rowcount > 0
        return False

    async def create_governance_pack(
        self,
        *,
        pack_id: str,
        pack_version: str,
        pack_schema_version: int,
        capability_taxonomy_version: int,
        adapter_contract_version: int,
        title: str,
        description: str | None,
        owner_scope_type: str,
        owner_scope_id: int | None,
        bundle_digest: str,
        manifest: dict[str, Any],
        normalized_ir: dict[str, Any],
        actor_id: int | None,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_governance_packs (
                pack_id, pack_version, pack_schema_version, capability_taxonomy_version,
                adapter_contract_version, title, description, owner_scope_type, owner_scope_id,
                bundle_digest, manifest_json, normalized_ir_json, created_by, updated_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                str(pack_id or "").strip(),
                str(pack_version or "").strip(),
                int(pack_schema_version),
                int(capability_taxonomy_version),
                int(adapter_contract_version),
                str(title or "").strip(),
                description,
                scope_type,
                owner_scope_id,
                str(bundle_digest or "").strip(),
                json.dumps(manifest or {}),
                json.dumps(normalized_ir or {}),
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_governance_packs
            WHERE pack_id = ?
              AND pack_version = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                str(pack_id or "").strip(),
                str(pack_version or "").strip(),
                scope_type,
                owner_scope_id,
                owner_scope_id,
            ),
        )
        if not row:
            return {}
        created = await self.get_governance_pack(int(row["id"]))
        return created or {}

    async def get_governance_pack(self, governance_pack_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, pack_id, pack_version, pack_schema_version, capability_taxonomy_version,
                   adapter_contract_version, title, description, owner_scope_type, owner_scope_id,
                   bundle_digest, manifest_json, normalized_ir_json, created_by, updated_by,
                   created_at, updated_at
            FROM mcp_governance_packs
            WHERE id = ?
            """,
            (int(governance_pack_id),),
        )
        return self._normalize_governance_pack_row(self._row_to_dict(row) if row else None)

    async def get_governance_pack_by_identity(
        self,
        *,
        pack_id: str,
        pack_version: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
    ) -> dict[str, Any] | None:
        scope_type = _normalize_scope_type(owner_scope_type)
        row = await self.db_pool.fetchone(
            """
            SELECT id, pack_id, pack_version, pack_schema_version, capability_taxonomy_version,
                   adapter_contract_version, title, description, owner_scope_type, owner_scope_id,
                   bundle_digest, manifest_json, normalized_ir_json, created_by, updated_by,
                   created_at, updated_at
            FROM mcp_governance_packs
            WHERE pack_id = ?
              AND pack_version = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                str(pack_id or "").strip(),
                str(pack_version or "").strip(),
                scope_type,
                owner_scope_id,
                owner_scope_id,
            ),
        )
        return self._normalize_governance_pack_row(self._row_to_dict(row) if row else None)

    async def list_governance_packs(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        rows = await self.db_pool.fetchall(
            """
            SELECT id, pack_id, pack_version, pack_schema_version, capability_taxonomy_version,
                   adapter_contract_version, title, description, owner_scope_type, owner_scope_id,
                   bundle_digest, manifest_json, normalized_ir_json, created_by, updated_by,
                   created_at, updated_at
            FROM mcp_governance_packs
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
            ORDER BY pack_id, pack_version, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_governance_pack_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def delete_governance_pack(self, governance_pack_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_governance_packs WHERE id = ?",
            (int(governance_pack_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_governance_pack_object(
        self,
        *,
        governance_pack_id: int,
        object_type: str,
        object_id: int | str,
        source_object_id: str,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        normalized_object_type = str(object_type or "").strip().lower()
        normalized_object_id = str(object_id).strip()
        normalized_source_object_id = str(source_object_id or "").strip()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_governance_pack_objects (
                governance_pack_id, object_type, object_id, source_object_id, created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (
                int(governance_pack_id),
                normalized_object_type,
                normalized_object_id,
                normalized_source_object_id,
                ts,
            ),
        )
        return (
            await self.get_governance_pack_object(
                object_type=normalized_object_type,
                object_id=normalized_object_id,
            )
            or {}
        )

    async def get_governance_pack_object(
        self,
        *,
        object_type: str,
        object_id: int | str,
    ) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, governance_pack_id, object_type, object_id, source_object_id, created_at
            FROM mcp_governance_pack_objects
            WHERE object_type = ?
              AND object_id = ?
            """,
            (str(object_type or "").strip().lower(), str(object_id).strip()),
        )
        return self._normalize_governance_pack_object_row(self._row_to_dict(row) if row else None)

    async def list_governance_pack_objects(self, governance_pack_id: int) -> list[dict[str, Any]]:
        rows = await self.db_pool.fetchall(
            """
            SELECT id, governance_pack_id, object_type, object_id, source_object_id, created_at
            FROM mcp_governance_pack_objects
            WHERE governance_pack_id = ?
            ORDER BY object_type, source_object_id, id
            """,
            (int(governance_pack_id),),
        )
        return [
            self._normalize_governance_pack_object_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def create_capability_adapter_mapping(
        self,
        *,
        mapping_id: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        capability_name: str,
        adapter_contract_version: int,
        resolved_policy_document: dict[str, Any],
        supported_environment_requirements: list[str],
        actor_id: int | None,
        title: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        scope_type = _normalize_capability_adapter_scope_type(owner_scope_type)
        normalized_scope_id = None if scope_type == "global" else (
            int(owner_scope_id) if owner_scope_id is not None else None
        )
        if scope_type != "global" and normalized_scope_id is None:
            raise ValueError("owner_scope_id is required for org and team capability mappings")
        normalized_mapping_id = str(mapping_id or "").strip()
        if not normalized_mapping_id:
            raise ValueError("mapping_id is required")
        normalized_title = str(title or normalized_mapping_id).strip()
        normalized_capability_name = str(capability_name or "").strip()
        if not normalized_capability_name:
            raise ValueError("capability_name is required")
        normalized_requirements = _normalize_string_list(supported_environment_requirements)
        normalized_is_active = _to_bool(is_active)
        if normalized_is_active:
            existing = await self.find_active_capability_mapping(
                owner_scope_type=scope_type,
                owner_scope_id=normalized_scope_id,
                capability_name=normalized_capability_name,
            )
            if existing is not None:
                raise ValueError("active capability adapter mapping already exists for scope/capability")

        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = (
            normalized_is_active if getattr(self.db_pool, "pool", None) is not None else int(normalized_is_active)
        )
        await self.db_pool.execute(
            """
            INSERT INTO mcp_capability_adapter_mappings (
                mapping_id, title, description, owner_scope_type, owner_scope_id,
                capability_name, adapter_contract_version, resolved_policy_document_json,
                supported_environment_requirements_json, is_active, created_by, updated_by,
                created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_mapping_id,
                normalized_title,
                description,
                scope_type,
                normalized_scope_id,
                normalized_capability_name,
                int(adapter_contract_version),
                json.dumps(dict(resolved_policy_document or {})),
                json.dumps(normalized_requirements),
                active_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_capability_adapter_mappings
            WHERE mapping_id = ?
            """,
            (normalized_mapping_id,),
        )
        if not row:
            return {}
        created = await self.get_capability_adapter_mapping(int(row["id"]))
        return created or {}

    async def get_capability_adapter_mapping(
        self,
        capability_adapter_mapping_id: int,
    ) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, mapping_id, title, description, owner_scope_type, owner_scope_id,
                   capability_name, adapter_contract_version, resolved_policy_document_json,
                   supported_environment_requirements_json, is_active, created_by, updated_by,
                   created_at, updated_at
            FROM mcp_capability_adapter_mappings
            WHERE id = ?
            """,
            (int(capability_adapter_mapping_id),),
        )
        return self._normalize_capability_adapter_mapping_row(self._row_to_dict(row) if row else None)

    async def list_capability_adapter_mappings(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        capability_name: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_capability_adapter_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        normalized_capability_name = (
            str(capability_name or "").strip() if capability_name is not None else None
        )
        rows = await self.db_pool.fetchall(
            """
            SELECT id, mapping_id, title, description, owner_scope_type, owner_scope_id,
                   capability_name, adapter_contract_version, resolved_policy_document_json,
                   supported_environment_requirements_json, is_active, created_by, updated_by,
                   created_at, updated_at
            FROM mcp_capability_adapter_mappings
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
              AND (? IS NULL OR capability_name = ?)
            ORDER BY capability_name, mapping_id, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
                normalized_capability_name,
                normalized_capability_name,
            ),
        )
        return [
            self._normalize_capability_adapter_mapping_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_capability_adapter_mapping(
        self,
        capability_adapter_mapping_id: int,
        *,
        mapping_id: str | object = _UNSET,
        title: str | None | object = _UNSET,
        description: str | None | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        capability_name: str | object = _UNSET,
        adapter_contract_version: int | object = _UNSET,
        resolved_policy_document: dict[str, Any] | None | object = _UNSET,
        supported_environment_requirements: list[str] | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_capability_adapter_mapping(capability_adapter_mapping_id)
        if not existing:
            return None

        next_scope = (
            _normalize_capability_adapter_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing["owner_scope_type"])
        )
        if owner_scope_id is _UNSET:
            next_scope_id = existing.get("owner_scope_id")
        elif next_scope == "global":
            next_scope_id = None
        elif owner_scope_id is None:
            raise ValueError("owner_scope_id is required for org and team capability mappings")
        else:
            next_scope_id = int(owner_scope_id)
        next_mapping_id = (
            str(existing["mapping_id"])
            if mapping_id is _UNSET
            else str(mapping_id or "").strip()
        )
        if not next_mapping_id:
            raise ValueError("mapping_id is required")
        next_title = (
            str(existing.get("title") or existing["mapping_id"]).strip()
            if title is _UNSET
            else str(title or next_mapping_id).strip()
        )
        next_description = existing.get("description") if description is _UNSET else description
        next_capability_name = (
            str(existing["capability_name"])
            if capability_name is _UNSET
            else str(capability_name or "").strip()
        )
        if not next_capability_name:
            raise ValueError("capability_name is required")
        next_adapter_contract_version = (
            int(existing["adapter_contract_version"])
            if adapter_contract_version is _UNSET
            else int(adapter_contract_version)
        )
        next_resolved_policy_document = (
            dict(existing.get("resolved_policy_document") or {})
            if resolved_policy_document is _UNSET
            else dict(resolved_policy_document or {})
        )
        next_supported_environment_requirements = (
            list(existing.get("supported_environment_requirements") or [])
            if supported_environment_requirements is _UNSET
            else _normalize_string_list(supported_environment_requirements)
        )
        next_is_active = (
            _to_bool(existing.get("is_active"))
            if is_active is _UNSET
            else _to_bool(is_active)
        )
        if next_scope == "global":
            next_scope_id = None
        elif next_scope_id is None:
            raise ValueError("owner_scope_id is required for org and team capability mappings")
        if next_is_active:
            current_active = await self.find_active_capability_mapping(
                owner_scope_type=next_scope,
                owner_scope_id=next_scope_id,
                capability_name=next_capability_name,
            )
            if current_active is not None and int(current_active["id"]) != int(capability_adapter_mapping_id):
                raise ValueError("active capability adapter mapping already exists for scope/capability")

        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_is_active if getattr(self.db_pool, "pool", None) is not None else int(next_is_active)
        await self.db_pool.execute(
            """
            UPDATE mcp_capability_adapter_mappings
            SET mapping_id = ?,
                title = ?,
                description = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                capability_name = ?,
                adapter_contract_version = ?,
                resolved_policy_document_json = ?,
                supported_environment_requirements_json = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_mapping_id,
                next_title,
                next_description,
                next_scope,
                next_scope_id,
                next_capability_name,
                next_adapter_contract_version,
                json.dumps(next_resolved_policy_document),
                json.dumps(next_supported_environment_requirements),
                active_value,
                actor_id,
                ts,
                int(capability_adapter_mapping_id),
            ),
        )
        return await self.get_capability_adapter_mapping(capability_adapter_mapping_id)

    async def delete_capability_adapter_mapping(self, capability_adapter_mapping_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_capability_adapter_mappings WHERE id = ?",
            (int(capability_adapter_mapping_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def find_active_capability_mapping(
        self,
        *,
        owner_scope_type: str,
        owner_scope_id: int | None,
        capability_name: str,
    ) -> dict[str, Any] | None:
        scope_type = _normalize_capability_adapter_scope_type(owner_scope_type)
        normalized_scope_id = None if scope_type == "global" else (
            int(owner_scope_id) if owner_scope_id is not None else None
        )
        if scope_type != "global" and normalized_scope_id is None:
            raise ValueError("owner_scope_id is required for org and team capability mappings")
        normalized_capability_name = str(capability_name or "").strip()
        if not normalized_capability_name:
            raise ValueError("capability_name is required")
        row = await self.db_pool.fetchone(
            """
            SELECT id, mapping_id, title, description, owner_scope_type, owner_scope_id,
                   capability_name, adapter_contract_version, resolved_policy_document_json,
                   supported_environment_requirements_json, is_active, created_by, updated_by,
                   created_at, updated_at
            FROM mcp_capability_adapter_mappings
            WHERE owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
              AND capability_name = ?
              AND is_active = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                scope_type,
                normalized_scope_id,
                normalized_scope_id,
                normalized_capability_name,
                True if getattr(self.db_pool, "pool", None) is not None else 1,
            ),
        )
        return self._normalize_capability_adapter_mapping_row(self._row_to_dict(row) if row else None)

    async def create_acp_profile(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        profile_json: str,
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_acp_profiles (
                name, description, owner_scope_type, owner_scope_id, profile_json, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                profile_json,
                active_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_acp_profiles
            WHERE name = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (name.strip(), scope_type, owner_scope_id, owner_scope_id),
        )
        if not row:
            return {}
        created = await self.get_acp_profile(int(row["id"]))
        return created or {}

    async def get_acp_profile(self, profile_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, profile_json, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_acp_profiles
            WHERE id = ?
            """,
            (int(profile_id),),
        )
        return self._normalize_acp_row(self._row_to_dict(row) if row else None)

    async def list_acp_profiles(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = (
            int(owner_scope_id) if owner_scope_id is not None else None
        )
        rows = await self.db_pool.fetchall(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, profile_json, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_acp_profiles
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
            ORDER BY name, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_acp_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_acp_profile(
        self,
        profile_id: int,
        *,
        name: str | None = None,
        description: str | None = None,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        profile_json: str | None = None,
        is_active: bool | None = None,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_acp_profile(profile_id)
        if not existing:
            return None

        next_name = name.strip() if name is not None else str(existing["name"])
        next_description = description if description is not None else existing.get("description")
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else str(existing["owner_scope_type"])
        )
        next_scope_id = owner_scope_id if owner_scope_id is not None else existing.get("owner_scope_id")
        next_profile_json = profile_json if profile_json is not None else str(existing["profile_json"])
        next_active = _to_bool(is_active) if is_active is not None else _to_bool(existing.get("is_active"))
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_acp_profiles
            SET name = ?,
                description = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                profile_json = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_description,
                next_scope,
                next_scope_id,
                next_profile_json,
                active_value,
                actor_id,
                ts,
                int(profile_id),
            ),
        )
        return await self.get_acp_profile(profile_id)

    async def delete_acp_profile(self, profile_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_acp_profiles WHERE id = ?",
            (int(profile_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_permission_profile(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        mode: str,
        path_scope_object_id: int | None = None,
        policy_document: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
        is_immutable: bool = False,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        profile_mode = _normalize_profile_mode(mode)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        immutable_value: bool | int = (
            is_immutable if getattr(self.db_pool, "pool", None) is not None else int(is_immutable)
        )
        await self.db_pool.execute(
            """
            INSERT INTO mcp_permission_profiles (
                name, description, owner_scope_type, owner_scope_id, mode, path_scope_object_id,
                policy_document_json, is_active, is_immutable, created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                profile_mode,
                path_scope_object_id,
                json.dumps(policy_document or {}),
                active_value,
                immutable_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_permission_profiles
            WHERE name = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (name.strip(), scope_type, owner_scope_id, owner_scope_id),
        )
        if not row:
            return {}
        created = await self.get_permission_profile(int(row["id"]))
        return created or {}

    async def get_permission_profile(self, profile_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, mode, path_scope_object_id,
                   policy_document_json, is_active, is_immutable,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_permission_profiles
            WHERE id = ?
            """,
            (int(profile_id),),
        )
        return self._normalize_permission_profile_row(self._row_to_dict(row) if row else None)

    async def list_permission_profiles(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        rows = await self.db_pool.fetchall(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, mode, path_scope_object_id,
                   policy_document_json, is_active, is_immutable,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_permission_profiles
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
            ORDER BY name, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_permission_profile_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_permission_profile(
        self,
        profile_id: int,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        mode: str | object = _UNSET,
        path_scope_object_id: int | None | object = _UNSET,
        policy_document: dict[str, Any] | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_permission_profile(profile_id)
        if not existing:
            return None

        next_name = str(existing["name"]) if name is _UNSET else str(name).strip()
        next_description = existing.get("description") if description is _UNSET else description
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing["owner_scope_type"])
        )
        next_scope_id = existing.get("owner_scope_id") if owner_scope_id is _UNSET else owner_scope_id
        next_mode = _normalize_profile_mode(mode) if mode is not _UNSET else str(existing["mode"])
        next_path_scope_object_id = (
            existing.get("path_scope_object_id")
            if path_scope_object_id is _UNSET
            else path_scope_object_id
        )
        next_policy_document = (
            dict(existing.get("policy_document") or {})
            if policy_document is _UNSET
            else dict(policy_document or {})
        )
        next_active = _to_bool(existing.get("is_active")) if is_active is _UNSET else _to_bool(is_active)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_permission_profiles
            SET name = ?,
                description = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                mode = ?,
                path_scope_object_id = ?,
                policy_document_json = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_description,
                next_scope,
                next_scope_id,
                next_mode,
                next_path_scope_object_id,
                json.dumps(next_policy_document or {}),
                active_value,
                actor_id,
                ts,
                int(profile_id),
            ),
        )
        return await self.get_permission_profile(profile_id)

    async def delete_permission_profile(self, profile_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_permission_profiles WHERE id = ?",
            (int(profile_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_path_scope_object(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        path_scope_document: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_path_scope_objects (
                name, description, owner_scope_type, owner_scope_id, path_scope_document_json, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                json.dumps(path_scope_document or {}),
                active_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_path_scope_objects
            WHERE name = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (name.strip(), scope_type, owner_scope_id, owner_scope_id),
        )
        if not row:
            return {}
        created = await self.get_path_scope_object(int(row["id"]))
        return created or {}

    async def get_path_scope_object(self, path_scope_object_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, path_scope_document_json, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_path_scope_objects
            WHERE id = ?
            """,
            (int(path_scope_object_id),),
        )
        return self._normalize_path_scope_object_row(self._row_to_dict(row) if row else None)

    async def list_path_scope_objects(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        rows = await self.db_pool.fetchall(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, path_scope_document_json, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_path_scope_objects
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
            ORDER BY name, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_path_scope_object_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_path_scope_object(
        self,
        path_scope_object_id: int,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        path_scope_document: dict[str, Any] | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_path_scope_object(path_scope_object_id)
        if not existing:
            return None

        next_name = str(existing["name"]) if name is _UNSET else str(name).strip()
        next_description = existing.get("description") if description is _UNSET else description
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing["owner_scope_type"])
        )
        next_scope_id = existing.get("owner_scope_id") if owner_scope_id is _UNSET else owner_scope_id
        next_path_scope_document = (
            dict(existing.get("path_scope_document") or {})
            if path_scope_document is _UNSET
            else dict(path_scope_document or {})
        )
        next_active = _to_bool(existing.get("is_active")) if is_active is _UNSET else _to_bool(is_active)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_path_scope_objects
            SET name = ?,
                description = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                path_scope_document_json = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_description,
                next_scope,
                next_scope_id,
                json.dumps(next_path_scope_document or {}),
                active_value,
                actor_id,
                ts,
                int(path_scope_object_id),
            ),
        )
        return await self.get_path_scope_object(path_scope_object_id)

    async def delete_path_scope_object(self, path_scope_object_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_path_scope_objects WHERE id = ?",
            (int(path_scope_object_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_workspace_set_object(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_workspace_set_objects (
                name, description, owner_scope_type, owner_scope_id, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                active_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_workspace_set_objects
            WHERE name = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (name.strip(), scope_type, owner_scope_id, owner_scope_id),
        )
        if not row:
            return {}
        created = await self.get_workspace_set_object(int(row["id"]))
        return created or {}

    async def get_workspace_set_object(self, workspace_set_object_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_workspace_set_objects
            WHERE id = ?
            """,
            (int(workspace_set_object_id),),
        )
        return self._normalize_workspace_set_object_row(self._row_to_dict(row) if row else None)

    async def list_workspace_set_objects(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        rows = await self.db_pool.fetchall(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_workspace_set_objects
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
            ORDER BY name, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_workspace_set_object_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_workspace_set_object(
        self,
        workspace_set_object_id: int,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_workspace_set_object(workspace_set_object_id)
        if not existing:
            return None

        next_name = str(existing["name"]) if name is _UNSET else str(name).strip()
        next_description = existing.get("description") if description is _UNSET else description
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing["owner_scope_type"])
        )
        next_scope_id = existing.get("owner_scope_id") if owner_scope_id is _UNSET else owner_scope_id
        next_active = _to_bool(existing.get("is_active")) if is_active is _UNSET else _to_bool(is_active)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_workspace_set_objects
            SET name = ?,
                description = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_description,
                next_scope,
                next_scope_id,
                active_value,
                actor_id,
                ts,
                int(workspace_set_object_id),
            ),
        )
        return await self.get_workspace_set_object(workspace_set_object_id)

    async def delete_workspace_set_object(self, workspace_set_object_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_workspace_set_objects WHERE id = ?",
            (int(workspace_set_object_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_shared_workspace_entry(
        self,
        *,
        workspace_id: str,
        display_name: str,
        absolute_root: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        actor_id: int | None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        workspace_value = str(workspace_id or "").strip()
        display_value = str(display_name or "").strip()
        root_value = str(absolute_root or "").strip()
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_shared_workspaces (
                workspace_id, display_name, absolute_root, owner_scope_type, owner_scope_id, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                workspace_value,
                display_value,
                root_value,
                scope_type,
                owner_scope_id,
                active_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_shared_workspaces
            WHERE workspace_id = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (workspace_value, scope_type, owner_scope_id, owner_scope_id),
        )
        if not row:
            return {}
        created = await self.get_shared_workspace_entry(int(row["id"]))
        return created or {}

    async def get_shared_workspace_entry(self, shared_workspace_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, workspace_id, display_name, absolute_root, owner_scope_type, owner_scope_id, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_shared_workspaces
            WHERE id = ?
            """,
            (int(shared_workspace_id),),
        )
        return self._normalize_shared_workspace_row(self._row_to_dict(row) if row else None)

    async def list_shared_workspace_entries(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        workspace_id: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        normalized_workspace_id = str(workspace_id or "").strip() or None
        rows = await self.db_pool.fetchall(
            """
            SELECT id, workspace_id, display_name, absolute_root, owner_scope_type, owner_scope_id, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_shared_workspaces
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
              AND (? IS NULL OR workspace_id = ?)
            ORDER BY owner_scope_type, owner_scope_id, workspace_id, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
                normalized_workspace_id,
                normalized_workspace_id,
            ),
        )
        return [
            self._normalize_shared_workspace_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_shared_workspace_entry(
        self,
        shared_workspace_id: int,
        *,
        workspace_id: str | object = _UNSET,
        display_name: str | object = _UNSET,
        absolute_root: str | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_shared_workspace_entry(shared_workspace_id)
        if not existing:
            return None

        next_workspace_id = (
            str(existing.get("workspace_id") or "")
            if workspace_id is _UNSET
            else str(workspace_id or "").strip()
        )
        next_display_name = (
            str(existing.get("display_name") or "")
            if display_name is _UNSET
            else str(display_name or "").strip()
        )
        next_absolute_root = (
            str(existing.get("absolute_root") or "")
            if absolute_root is _UNSET
            else str(absolute_root or "").strip()
        )
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing.get("owner_scope_type") or "global")
        )
        next_scope_id = existing.get("owner_scope_id") if owner_scope_id is _UNSET else owner_scope_id
        next_active = _to_bool(existing.get("is_active")) if is_active is _UNSET else _to_bool(is_active)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_shared_workspaces
            SET workspace_id = ?,
                display_name = ?,
                absolute_root = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_workspace_id,
                next_display_name,
                next_absolute_root,
                next_scope,
                next_scope_id,
                active_value,
                actor_id,
                ts,
                int(shared_workspace_id),
            ),
        )
        return await self.get_shared_workspace_entry(shared_workspace_id)

    async def delete_shared_workspace_entry(self, shared_workspace_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_shared_workspaces WHERE id = ?",
            (int(shared_workspace_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def list_workspace_set_members(self, workspace_set_object_id: int) -> list[dict[str, Any]]:
        rows = await self.db_pool.fetchall(
            """
            SELECT workspace_set_object_id, workspace_id, created_by, created_at
            FROM mcp_workspace_set_object_members
            WHERE workspace_set_object_id = ?
            ORDER BY workspace_id
            """,
            (int(workspace_set_object_id),),
        )
        return [
            self._normalize_workspace_set_member_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def add_workspace_set_member(
        self,
        workspace_set_object_id: int,
        *,
        workspace_id: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        workspace_value = str(workspace_id or "").strip()
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_workspace_set_object_members (
                workspace_set_object_id, workspace_id, created_by, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (int(workspace_set_object_id), workspace_value, actor_id, ts),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT workspace_set_object_id, workspace_id, created_by, created_at
            FROM mcp_workspace_set_object_members
            WHERE workspace_set_object_id = ?
              AND workspace_id = ?
            """,
            (int(workspace_set_object_id), workspace_value),
        )
        return self._normalize_workspace_set_member_row(self._row_to_dict(row) if row else None) or {}

    async def delete_workspace_set_member(self, workspace_set_object_id: int, workspace_id: str) -> bool:
        cursor = await self.db_pool.execute(
            """
            DELETE FROM mcp_workspace_set_object_members
            WHERE workspace_set_object_id = ?
              AND workspace_id = ?
            """,
            (int(workspace_set_object_id), str(workspace_id or "").strip()),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_policy_assignment(
        self,
        *,
        target_type: str,
        target_id: str | None,
        owner_scope_type: str,
        owner_scope_id: int | None,
        profile_id: int | None,
        path_scope_object_id: int | None = None,
        workspace_source_mode: str | None = None,
        workspace_set_object_id: int | None = None,
        inline_policy_document: dict[str, Any],
        approval_policy_id: int | None,
        actor_id: int | None,
        is_active: bool = True,
        is_immutable: bool = False,
    ) -> dict[str, Any]:
        normalized_target_type = _normalize_target_type(target_type)
        normalized_target_id = str(target_id).strip() if target_id is not None else None
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        immutable_value: bool | int = (
            is_immutable if getattr(self.db_pool, "pool", None) is not None else int(is_immutable)
        )
        await self.db_pool.execute(
            """
            INSERT INTO mcp_policy_assignments (
                target_type, target_id, owner_scope_type, owner_scope_id, profile_id,
                path_scope_object_id, workspace_source_mode, workspace_set_object_id,
                inline_policy_document_json, approval_policy_id, is_active, is_immutable,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_target_type,
                normalized_target_id,
                scope_type,
                owner_scope_id,
                profile_id,
                path_scope_object_id,
                str(workspace_source_mode or "").strip().lower() or None,
                workspace_set_object_id,
                json.dumps(inline_policy_document or {}),
                approval_policy_id,
                active_value,
                immutable_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_policy_assignments
            WHERE target_type = ?
              AND (
                (target_id IS NULL AND ? IS NULL)
                OR target_id = ?
              )
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                normalized_target_type,
                normalized_target_id,
                normalized_target_id,
                scope_type,
                owner_scope_id,
                owner_scope_id,
            ),
        )
        if not row:
            return {}
        created = await self.get_policy_assignment(int(row["id"]))
        return created or {}

    async def get_policy_assignment(self, assignment_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT a.id, a.target_type, a.target_id, a.owner_scope_type, a.owner_scope_id, a.profile_id,
                   a.path_scope_object_id, a.workspace_source_mode, a.workspace_set_object_id,
                   a.inline_policy_document_json, a.approval_policy_id, a.is_active, a.is_immutable,
                   a.created_by, a.updated_by, a.created_at, a.updated_at,
                   o.id AS override_id,
                   CASE WHEN o.id IS NULL THEN 0 ELSE 1 END AS has_override,
                   COALESCE(o.is_active, 0) AS override_active,
                   o.updated_at AS override_updated_at
            FROM mcp_policy_assignments AS a
            LEFT JOIN mcp_policy_overrides AS o ON o.assignment_id = a.id
            WHERE a.id = ?
            """,
            (int(assignment_id),),
        )
        return self._normalize_policy_assignment_row(self._row_to_dict(row) if row else None)

    async def list_policy_assignments(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
        target_type: str | None = None,
        target_id: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        normalized_target_type = (
            _normalize_target_type(target_type)
            if target_type is not None
            else None
        )
        normalized_target_id = str(target_id).strip() if target_id is not None else None
        rows = await self.db_pool.fetchall(
            """
            SELECT a.id, a.target_type, a.target_id, a.owner_scope_type, a.owner_scope_id, a.profile_id,
                   a.path_scope_object_id, a.workspace_source_mode, a.workspace_set_object_id,
                   a.inline_policy_document_json, a.approval_policy_id, a.is_active, a.is_immutable,
                   a.created_by, a.updated_by, a.created_at, a.updated_at,
                   o.id AS override_id,
                   CASE WHEN o.id IS NULL THEN 0 ELSE 1 END AS has_override,
                   COALESCE(o.is_active, 0) AS override_active,
                   o.updated_at AS override_updated_at
            FROM mcp_policy_assignments AS a
            LEFT JOIN mcp_policy_overrides AS o ON o.assignment_id = a.id
            WHERE (? IS NULL OR a.owner_scope_type = ?)
              AND (? IS NULL OR a.owner_scope_id = ?)
              AND (? IS NULL OR a.target_type = ?)
              AND (? IS NULL OR a.target_id = ?)
            ORDER BY a.target_type, a.target_id, a.id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
                normalized_target_type,
                normalized_target_type,
                normalized_target_id,
                normalized_target_id,
            ),
        )
        return [
            self._normalize_policy_assignment_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_policy_assignment(
        self,
        assignment_id: int,
        *,
        target_type: str | object = _UNSET,
        target_id: str | None | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        profile_id: int | None | object = _UNSET,
        path_scope_object_id: int | None | object = _UNSET,
        workspace_source_mode: str | None | object = _UNSET,
        workspace_set_object_id: int | None | object = _UNSET,
        inline_policy_document: dict[str, Any] | None | object = _UNSET,
        approval_policy_id: int | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_policy_assignment(assignment_id)
        if not existing:
            return None

        next_target_type = (
            _normalize_target_type(target_type)
            if target_type is not _UNSET
            else str(existing["target_type"])
        )
        if target_id is _UNSET:
            next_target_id = existing.get("target_id")
        elif target_id is None:
            next_target_id = None
        else:
            next_target_id = str(target_id).strip()
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing["owner_scope_type"])
        )
        next_scope_id = existing.get("owner_scope_id") if owner_scope_id is _UNSET else owner_scope_id
        next_profile_id = existing.get("profile_id") if profile_id is _UNSET else profile_id
        next_path_scope_object_id = (
            existing.get("path_scope_object_id")
            if path_scope_object_id is _UNSET
            else path_scope_object_id
        )
        next_workspace_source_mode = (
            existing.get("workspace_source_mode")
            if workspace_source_mode is _UNSET
            else (str(workspace_source_mode or "").strip().lower() or None)
        )
        next_workspace_set_object_id = (
            existing.get("workspace_set_object_id")
            if workspace_set_object_id is _UNSET
            else workspace_set_object_id
        )
        next_inline_policy_document = (
            dict(existing.get("inline_policy_document") or {})
            if inline_policy_document is _UNSET
            else dict(inline_policy_document or {})
        )
        next_approval_policy_id = (
            existing.get("approval_policy_id")
            if approval_policy_id is _UNSET
            else approval_policy_id
        )
        next_active = _to_bool(existing.get("is_active")) if is_active is _UNSET else _to_bool(is_active)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_policy_assignments
            SET target_type = ?,
                target_id = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                profile_id = ?,
                path_scope_object_id = ?,
                workspace_source_mode = ?,
                workspace_set_object_id = ?,
                inline_policy_document_json = ?,
                approval_policy_id = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_target_type,
                next_target_id,
                next_scope,
                next_scope_id,
                next_profile_id,
                next_path_scope_object_id,
                next_workspace_source_mode,
                next_workspace_set_object_id,
                json.dumps(next_inline_policy_document or {}),
                next_approval_policy_id,
                active_value,
                actor_id,
                ts,
                int(assignment_id),
            ),
        )
        return await self.get_policy_assignment(assignment_id)

    async def delete_policy_assignment(self, assignment_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_policy_assignments WHERE id = ?",
            (int(assignment_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def list_policy_assignment_workspaces(self, assignment_id: int) -> list[dict[str, Any]]:
        rows = await self.db_pool.fetchall(
            """
            SELECT assignment_id, workspace_id, created_by, created_at
            FROM mcp_policy_assignment_workspaces
            WHERE assignment_id = ?
            ORDER BY workspace_id
            """,
            (int(assignment_id),),
        )
        return [
            self._normalize_policy_assignment_workspace_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def add_policy_assignment_workspace(
        self,
        assignment_id: int,
        *,
        workspace_id: str,
        actor_id: int | None,
    ) -> dict[str, Any]:
        workspace_value = str(workspace_id or "").strip()
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_policy_assignment_workspaces (
                assignment_id, workspace_id, created_by, created_at
            ) VALUES (?, ?, ?, ?)
            """,
            (int(assignment_id), workspace_value, actor_id, ts),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT assignment_id, workspace_id, created_by, created_at
            FROM mcp_policy_assignment_workspaces
            WHERE assignment_id = ?
              AND workspace_id = ?
            """,
            (int(assignment_id), workspace_value),
        )
        return self._normalize_policy_assignment_workspace_row(self._row_to_dict(row) if row else None) or {}

    async def delete_policy_assignment_workspace(self, assignment_id: int, workspace_id: str) -> bool:
        cursor = await self.db_pool.execute(
            """
            DELETE FROM mcp_policy_assignment_workspaces
            WHERE assignment_id = ?
              AND workspace_id = ?
            """,
            (int(assignment_id), str(workspace_id or "").strip()),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def get_policy_override_by_assignment(self, assignment_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, assignment_id, override_document_json, is_active, broadens_access,
                   grant_authority_snapshot_json, created_by, updated_by, created_at, updated_at
            FROM mcp_policy_overrides
            WHERE assignment_id = ?
            """,
            (int(assignment_id),),
        )
        return self._normalize_policy_override_row(self._row_to_dict(row) if row else None)

    async def upsert_policy_override(
        self,
        assignment_id: int,
        *,
        override_policy_document: dict[str, Any],
        broadens_access: bool,
        grant_authority_snapshot: dict[str, Any],
        actor_id: int | None,
        is_active: bool = True,
    ) -> dict[str, Any] | None:
        assignment = await self.get_policy_assignment(int(assignment_id))
        if assignment is None:
            return None

        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        broadens_value: bool | int = (
            broadens_access if getattr(self.db_pool, "pool", None) is not None else int(broadens_access)
        )

        await self.db_pool.execute(
            """
            INSERT INTO mcp_policy_overrides (
                assignment_id, override_document_json, is_active, broadens_access,
                grant_authority_snapshot_json, created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(assignment_id) DO UPDATE SET
                override_document_json = excluded.override_document_json,
                is_active = excluded.is_active,
                broadens_access = excluded.broadens_access,
                grant_authority_snapshot_json = excluded.grant_authority_snapshot_json,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                int(assignment_id),
                json.dumps(override_policy_document or {}),
                active_value,
                broadens_value,
                json.dumps(grant_authority_snapshot or {}),
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        return await self.get_policy_override_by_assignment(int(assignment_id))

    async def delete_policy_override_by_assignment(self, assignment_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_policy_overrides WHERE assignment_id = ?",
            (int(assignment_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_approval_policy(
        self,
        *,
        name: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        mode: str,
        rules: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
        is_immutable: bool = False,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        approval_mode = _normalize_approval_mode(mode)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        immutable_value: bool | int = (
            is_immutable if getattr(self.db_pool, "pool", None) is not None else int(is_immutable)
        )
        await self.db_pool.execute(
            """
            INSERT INTO mcp_approval_policies (
                name, description, owner_scope_type, owner_scope_id, mode, rules_json, is_active,
                is_immutable, created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                approval_mode,
                json.dumps(rules or {}),
                active_value,
                immutable_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_approval_policies
            WHERE name = ?
              AND owner_scope_type = ?
              AND (
                (owner_scope_id IS NULL AND ? IS NULL)
                OR owner_scope_id = ?
              )
            ORDER BY id DESC
            LIMIT 1
            """,
            (name.strip(), scope_type, owner_scope_id, owner_scope_id),
        )
        if not row:
            return {}
        created = await self.get_approval_policy(int(row["id"]))
        return created or {}

    async def get_approval_policy(self, approval_policy_id: int) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, mode, rules_json, is_active,
                   is_immutable,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_approval_policies
            WHERE id = ?
            """,
            (int(approval_policy_id),),
        )
        return self._normalize_approval_policy_row(self._row_to_dict(row) if row else None)

    async def list_approval_policies(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = int(owner_scope_id) if owner_scope_id is not None else None
        rows = await self.db_pool.fetchall(
            """
            SELECT id, name, description, owner_scope_type, owner_scope_id, mode, rules_json, is_active,
                   is_immutable,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_approval_policies
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
            ORDER BY name, id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_approval_policy_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_approval_policy(
        self,
        approval_policy_id: int,
        *,
        name: str | object = _UNSET,
        description: str | None | object = _UNSET,
        owner_scope_type: str | object = _UNSET,
        owner_scope_id: int | None | object = _UNSET,
        mode: str | object = _UNSET,
        rules: dict[str, Any] | None | object = _UNSET,
        is_active: bool | object = _UNSET,
        actor_id: int | None = None,
    ) -> dict[str, Any] | None:
        existing = await self.get_approval_policy(approval_policy_id)
        if not existing:
            return None

        next_name = str(existing["name"]) if name is _UNSET else str(name).strip()
        next_description = existing.get("description") if description is _UNSET else description
        next_scope = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not _UNSET
            else str(existing["owner_scope_type"])
        )
        next_scope_id = existing.get("owner_scope_id") if owner_scope_id is _UNSET else owner_scope_id
        next_mode = (
            _normalize_approval_mode(mode)
            if mode is not _UNSET
            else str(existing["mode"])
        )
        next_rules = (
            dict(existing.get("rules") or {})
            if rules is _UNSET
            else dict(rules or {})
        )
        next_active = _to_bool(existing.get("is_active")) if is_active is _UNSET else _to_bool(is_active)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = next_active if getattr(self.db_pool, "pool", None) is not None else int(next_active)

        await self.db_pool.execute(
            """
            UPDATE mcp_approval_policies
            SET name = ?,
                description = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                mode = ?,
                rules_json = ?,
                is_active = ?,
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                next_name,
                next_description,
                next_scope,
                next_scope_id,
                next_mode,
                json.dumps(next_rules or {}),
                active_value,
                actor_id,
                ts,
                int(approval_policy_id),
            ),
        )
        return await self.get_approval_policy(approval_policy_id)

    async def delete_approval_policy(self, approval_policy_id: int) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_approval_policies WHERE id = ?",
            (int(approval_policy_id),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_approval_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        decision: str,
        consume_on_match: bool = False,
        expires_at: datetime | str | None = None,
        actor_id: int | None = None,
    ) -> dict[str, Any]:
        normalized_decision = str(decision or "").strip().lower()
        if normalized_decision not in {"approved", "denied"}:
            raise ValueError(f"Invalid approval decision: {decision}")
        normalized_expires_at = expires_at
        if isinstance(expires_at, datetime) and getattr(self.db_pool, "pool", None) is None:
            normalized_expires_at = expires_at.isoformat()
        consume_value: bool | int = (
            bool(consume_on_match)
            if getattr(self.db_pool, "pool", None) is not None
            else int(bool(consume_on_match))
        )
        now = datetime.now(timezone.utc)
        created_at = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_approval_decisions (
                approval_policy_id, context_key, conversation_id, tool_name, scope_key,
                decision, consume_on_match, expires_at, consumed_at, created_by, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                approval_policy_id,
                str(context_key).strip(),
                str(conversation_id).strip() if conversation_id is not None else None,
                str(tool_name).strip(),
                str(scope_key).strip(),
                normalized_decision,
                consume_value,
                normalized_expires_at,
                None,
                actor_id,
                created_at,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id, approval_policy_id, context_key, conversation_id, tool_name, scope_key,
                   decision, consume_on_match, expires_at, consumed_at, created_by, created_at
            FROM mcp_approval_decisions
            WHERE context_key = ?
              AND (
                (conversation_id IS NULL AND ? IS NULL)
                OR conversation_id = ?
              )
              AND tool_name = ?
              AND scope_key = ?
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                str(context_key).strip(),
                str(conversation_id).strip() if conversation_id is not None else None,
                str(conversation_id).strip() if conversation_id is not None else None,
                str(tool_name).strip(),
                str(scope_key).strip(),
            ),
        )
        return self._normalize_approval_decision_row(self._row_to_dict(row) if row else None) or {}

    async def find_active_approval_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        decision: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        rows = await self.db_pool.fetchall(
            """
            SELECT id, approval_policy_id, context_key, conversation_id, tool_name, scope_key,
                   decision, consume_on_match, expires_at, consumed_at, created_by, created_at
            FROM mcp_approval_decisions
            WHERE (? IS NULL OR approval_policy_id = ?)
              AND context_key = ?
              AND (
                (? IS NULL AND conversation_id IS NULL)
                OR conversation_id = ?
              )
              AND tool_name = ?
              AND scope_key = ?
              AND (? IS NULL OR decision = ?)
            ORDER BY id DESC
            """,
            (
                approval_policy_id,
                approval_policy_id,
                str(context_key).strip(),
                str(conversation_id).strip() if conversation_id is not None else None,
                str(conversation_id).strip() if conversation_id is not None else None,
                str(tool_name).strip(),
                str(scope_key).strip(),
                str(decision).strip().lower() if decision is not None else None,
                str(decision).strip().lower() if decision is not None else None,
            ),
        )
        current = now or datetime.now(timezone.utc)
        for row in rows:
            normalized = self._normalize_approval_decision_row(self._row_to_dict(row)) or {}
            if normalized.get("consumed_at") is not None:
                continue
            expires_at = normalized.get("expires_at")
            if expires_at:
                try:
                    expiry_dt = (
                        expires_at
                        if isinstance(expires_at, datetime)
                        else datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                    )
                    if expiry_dt <= current:
                        continue
                except (TypeError, ValueError):
                    continue
            return normalized
        return None

    async def consume_active_approval_decision(
        self,
        *,
        approval_policy_id: int | None,
        context_key: str,
        conversation_id: str | None,
        tool_name: str,
        scope_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any] | None:
        consume_time = now or datetime.now(timezone.utc)
        conversation_value = str(conversation_id).strip() if conversation_id is not None else None
        if getattr(self.db_pool, "pool", None) is not None:
            async with self.db_pool.transaction() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, approval_policy_id, context_key, conversation_id, tool_name, scope_key,
                           decision, consume_on_match, expires_at, consumed_at, created_by, created_at
                    FROM mcp_approval_decisions
                    WHERE ($1::INTEGER IS NULL OR approval_policy_id = $1)
                      AND context_key = $2
                      AND (
                        ($3::TEXT IS NULL AND conversation_id IS NULL)
                        OR conversation_id = $3
                      )
                      AND tool_name = $4
                      AND scope_key = $5
                      AND decision = 'approved'
                      AND consume_on_match = TRUE
                      AND consumed_at IS NULL
                      AND (expires_at IS NULL OR expires_at > $6)
                    ORDER BY id DESC
                    LIMIT 1
                    FOR UPDATE
                    """,
                    approval_policy_id,
                    str(context_key).strip(),
                    conversation_value,
                    str(tool_name).strip(),
                    str(scope_key).strip(),
                    consume_time,
                )
                if not row:
                    return None

                result = await conn.execute(
                    """
                    UPDATE mcp_approval_decisions
                    SET consumed_at = $1
                    WHERE id = $2
                      AND decision = 'approved'
                      AND consume_on_match = TRUE
                      AND consumed_at IS NULL
                    """,
                    consume_time,
                    int(row["id"]),
                )
                if not self._command_touched_rows(result):
                    return None

                item = self._normalize_approval_decision_row(self._row_to_dict(row)) or {}
                item["consumed_at"] = consume_time
                return item

        async with self.db_pool.transaction() as conn:
            cursor = await conn.execute(
                """
                SELECT id, approval_policy_id, context_key, conversation_id, tool_name, scope_key,
                       decision, consume_on_match, expires_at, consumed_at, created_by, created_at
                FROM mcp_approval_decisions
                WHERE (? IS NULL OR approval_policy_id = ?)
                  AND context_key = ?
                  AND (
                    (? IS NULL AND conversation_id IS NULL)
                    OR conversation_id = ?
                  )
                  AND tool_name = ?
                  AND scope_key = ?
                  AND decision = 'approved'
                  AND consume_on_match = 1
                  AND consumed_at IS NULL
                  AND (expires_at IS NULL OR datetime(expires_at) > datetime(?))
                ORDER BY id DESC
                LIMIT 1
                """,
                (
                    approval_policy_id,
                    approval_policy_id,
                    str(context_key).strip(),
                    conversation_value,
                    conversation_value,
                    str(tool_name).strip(),
                    str(scope_key).strip(),
                    consume_time.isoformat(),
                ),
            )
            row = await cursor.fetchone()
            if not row:
                return None

            update_cursor = await conn.execute(
                """
                UPDATE mcp_approval_decisions
                SET consumed_at = ?
                WHERE id = ?
                  AND decision = 'approved'
                  AND consume_on_match = 1
                  AND consumed_at IS NULL
                """,
                (
                    consume_time.isoformat(),
                    int(row["id"]),
                ),
            )
            if not self._command_touched_rows(update_cursor):
                return None

            item = self._normalize_approval_decision_row(self._row_to_dict(row)) or {}
            item["consumed_at"] = consume_time.isoformat()
            return item

    async def expire_approval_decision(
        self,
        approval_decision_id: int,
        *,
        expires_at: datetime | str,
    ) -> dict[str, Any] | None:
        normalized_expires_at = expires_at
        if isinstance(expires_at, datetime) and getattr(self.db_pool, "pool", None) is None:
            normalized_expires_at = expires_at.isoformat()
        await self.db_pool.execute(
            """
            UPDATE mcp_approval_decisions
            SET expires_at = ?
            WHERE id = ?
            """,
            (
                normalized_expires_at,
                int(approval_decision_id),
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id, approval_policy_id, context_key, conversation_id, tool_name, scope_key,
                   decision, consume_on_match, expires_at, consumed_at, created_by, created_at
            FROM mcp_approval_decisions
            WHERE id = ?
            """,
            (int(approval_decision_id),),
        )
        return self._normalize_approval_decision_row(self._row_to_dict(row) if row else None)

    async def upsert_external_server(
        self,
        *,
        server_id: str,
        name: str,
        transport: str,
        config_json: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        enabled: bool,
        server_source: str = "managed",
        legacy_source_ref: str | None = None,
        superseded_by_server_id: str | None = None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        source_value = str(server_source or "managed").strip().lower() or "managed"
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        enabled_value: bool | int = enabled if getattr(self.db_pool, "pool", None) is not None else int(enabled)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_external_servers (
                id, name, enabled, owner_scope_type, owner_scope_id, transport, config_json,
                server_source, legacy_source_ref, superseded_by_server_id,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                enabled = excluded.enabled,
                owner_scope_type = excluded.owner_scope_type,
                owner_scope_id = excluded.owner_scope_id,
                transport = excluded.transport,
                config_json = excluded.config_json,
                server_source = excluded.server_source,
                legacy_source_ref = excluded.legacy_source_ref,
                superseded_by_server_id = excluded.superseded_by_server_id,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                server_id.strip(),
                name.strip(),
                enabled_value,
                scope_type,
                owner_scope_id,
                transport.strip(),
                config_json,
                source_value,
                str(legacy_source_ref).strip() if legacy_source_ref is not None else None,
                str(superseded_by_server_id).strip() if superseded_by_server_id is not None else None,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.get_external_server(server_id)
        return row or {}

    async def update_external_server(
        self,
        server_id: str,
        *,
        name: str,
        transport: str,
        config_json: str,
        owner_scope_type: str,
        owner_scope_id: int | None,
        enabled: bool,
        server_source: str | object = _UNSET,
        legacy_source_ref: str | None | object = _UNSET,
        superseded_by_server_id: str | None | object = _UNSET,
        actor_id: int | None,
    ) -> dict[str, Any] | None:
        """Update an existing external server row and return the normalized record."""
        scope_type = _normalize_scope_type(owner_scope_type)
        next_source = (
            str(server_source or "managed").strip().lower() or "managed"
            if server_source is not _UNSET
            else None
        )
        next_legacy_source_ref = (
            str(legacy_source_ref).strip() if legacy_source_ref is not _UNSET and legacy_source_ref is not None else None
        )
        next_superseded_by = (
            str(superseded_by_server_id).strip()
            if superseded_by_server_id is not _UNSET and superseded_by_server_id is not None
            else None
        )
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        enabled_value: bool | int = enabled if getattr(self.db_pool, "pool", None) is not None else int(enabled)
        cursor = await self.db_pool.execute(
            """
            UPDATE mcp_external_servers
            SET name = ?,
                enabled = ?,
                owner_scope_type = ?,
                owner_scope_id = ?,
                transport = ?,
                config_json = ?,
                server_source = COALESCE(?, server_source),
                legacy_source_ref = COALESCE(?, legacy_source_ref),
                superseded_by_server_id = COALESCE(?, superseded_by_server_id),
                updated_by = ?,
                updated_at = ?
            WHERE id = ?
            """,
            (
                name.strip(),
                enabled_value,
                scope_type,
                owner_scope_id,
                transport.strip(),
                config_json,
                next_source,
                next_legacy_source_ref,
                next_superseded_by,
                actor_id,
                ts,
                server_id.strip(),
            ),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        if not (rowcount and rowcount > 0):
            return None
        return await self.get_external_server(server_id)

    async def get_external_server(self, server_id: str) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT s.id,
                   s.name,
                   s.enabled,
                   s.owner_scope_type,
                   s.owner_scope_id,
                   s.transport,
                   s.server_source,
                   s.legacy_source_ref,
                   s.superseded_by_server_id,
                   s.config_json,
                   s.created_by,
                   s.updated_by,
                   s.created_at,
                   s.updated_at,
                   CASE
                     WHEN EXISTS (
                       SELECT 1 FROM mcp_external_server_secrets sec WHERE sec.server_id = s.id
                     ) THEN 1
                     WHEN EXISTS (
                       SELECT 1
                       FROM mcp_external_server_slot_secrets slot_sec
                       JOIN mcp_external_server_credential_slots slot ON slot.id = slot_sec.slot_id
                       WHERE slot.server_id = s.id
                     ) THEN 1
                     ELSE 0
                   END AS secret_configured,
                   (
                       SELECT COUNT(*)
                       FROM mcp_credential_bindings b
                       WHERE b.external_server_id = s.id
                   ) AS binding_count,
                   COALESCE(
                       (
                           SELECT sec.key_hint
                           FROM mcp_external_server_secrets sec
                           WHERE sec.server_id = s.id
                           LIMIT 1
                       ),
                       (
                           SELECT slot_sec.key_hint
                           FROM mcp_external_server_slot_secrets slot_sec
                           JOIN mcp_external_server_credential_slots slot ON slot.id = slot_sec.slot_id
                           WHERE slot.server_id = s.id
                           LIMIT 1
                       )
                   ) AS key_hint
            FROM mcp_external_servers s
            WHERE s.id = ?
            """,
            (server_id.strip(),),
        )
        return self._normalize_external_row(self._row_to_dict(row) if row else None)

    async def list_external_servers(
        self,
        *,
        owner_scope_type: str | None = None,
        owner_scope_id: int | None = None,
    ) -> list[dict[str, Any]]:
        normalized_scope_type = (
            _normalize_scope_type(owner_scope_type)
            if owner_scope_type is not None
            else None
        )
        normalized_scope_id = (
            int(owner_scope_id) if owner_scope_id is not None else None
        )
        rows = await self.db_pool.fetchall(
            """
            SELECT s.id,
                   s.name,
                   s.enabled,
                   s.owner_scope_type,
                   s.owner_scope_id,
                   s.transport,
                   s.server_source,
                   s.legacy_source_ref,
                   s.superseded_by_server_id,
                   s.config_json,
                   s.created_by,
                   s.updated_by,
                   s.created_at,
                   s.updated_at,
                   CASE
                     WHEN EXISTS (
                       SELECT 1 FROM mcp_external_server_secrets sec WHERE sec.server_id = s.id
                     ) THEN 1
                     WHEN EXISTS (
                       SELECT 1
                       FROM mcp_external_server_slot_secrets slot_sec
                       JOIN mcp_external_server_credential_slots slot ON slot.id = slot_sec.slot_id
                       WHERE slot.server_id = s.id
                     ) THEN 1
                     ELSE 0
                   END AS secret_configured,
                   (
                       SELECT COUNT(*)
                       FROM mcp_credential_bindings b
                       WHERE b.external_server_id = s.id
                   ) AS binding_count,
                   COALESCE(
                       (
                           SELECT sec.key_hint
                           FROM mcp_external_server_secrets sec
                           WHERE sec.server_id = s.id
                           LIMIT 1
                       ),
                       (
                           SELECT slot_sec.key_hint
                           FROM mcp_external_server_slot_secrets slot_sec
                           JOIN mcp_external_server_credential_slots slot ON slot.id = slot_sec.slot_id
                           WHERE slot.server_id = s.id
                           LIMIT 1
                       )
                   ) AS key_hint
            FROM mcp_external_servers s
            WHERE (? IS NULL OR s.owner_scope_type = ?)
              AND (? IS NULL OR s.owner_scope_id = ?)
            ORDER BY s.name, s.id
            """,
            (
                normalized_scope_type,
                normalized_scope_type,
                normalized_scope_id,
                normalized_scope_id,
            ),
        )
        return [
            self._normalize_external_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def delete_external_server(self, server_id: str) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_external_servers WHERE id = ?",
            (server_id.strip(),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def upsert_external_secret(
        self,
        server_id: str,
        *,
        encrypted_blob: str,
        key_hint: str | None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_external_server_secrets (
                server_id, encrypted_blob, key_hint, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(server_id) DO UPDATE SET
                encrypted_blob = excluded.encrypted_blob,
                key_hint = excluded.key_hint,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                server_id.strip(),
                encrypted_blob,
                key_hint,
                actor_id,
                ts,
            ),
        )
        row = await self.get_external_secret(server_id)
        return row or {}

    async def get_external_secret(self, server_id: str) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT server_id, encrypted_blob, key_hint, updated_by, updated_at
            FROM mcp_external_server_secrets
            WHERE server_id = ?
            """,
            (server_id.strip(),),
        )
        return self._row_to_dict(row) if row else None

    async def clear_external_secret(self, server_id: str) -> bool:
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_external_server_secrets WHERE server_id = ?",
            (server_id.strip(),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def create_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
        display_name: str,
        secret_kind: str,
        privilege_class: str,
        is_required: bool,
        actor_id: int | None,
    ) -> dict[str, Any]:
        server = await self.get_external_server(server_id)
        if not server:
            raise ValueError(f"Unknown external server: {server_id}")
        normalized_slot_name = _normalize_slot_name(slot_name)
        existing = await self.get_external_server_credential_slot(
            server_id=server_id,
            slot_name=normalized_slot_name,
        )
        if existing is not None:
            raise ValueError(f"External server slot already exists: {server_id}/{normalized_slot_name}")
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        required_value: bool | int = is_required if getattr(self.db_pool, "pool", None) is not None else int(is_required)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_external_server_credential_slots (
                server_id, slot_name, display_name, secret_kind, privilege_class, is_required,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                server_id.strip(),
                normalized_slot_name,
                str(display_name or normalized_slot_name).strip(),
                str(secret_kind or "secret").strip().lower(),
                _normalize_credential_slot_privilege_class(privilege_class),
                required_value,
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.get_external_server_credential_slot(
            server_id=server_id,
            slot_name=normalized_slot_name,
        )
        return row or {}

    async def get_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
    ) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT slot.id,
                   slot.server_id,
                   slot.slot_name,
                   slot.display_name,
                   slot.secret_kind,
                   slot.privilege_class,
                   slot.is_required,
                   slot.created_by,
                   slot.updated_by,
                   slot.created_at,
                   slot.updated_at,
                   CASE WHEN slot_sec.slot_id IS NULL THEN 0 ELSE 1 END AS secret_configured,
                   slot_sec.key_hint
            FROM mcp_external_server_credential_slots slot
            LEFT JOIN mcp_external_server_slot_secrets slot_sec ON slot_sec.slot_id = slot.id
            WHERE slot.server_id = ?
              AND slot.slot_name = ?
            """,
            (server_id.strip(), _normalize_slot_name(slot_name)),
        )
        return self._normalize_external_slot_row(self._row_to_dict(row) if row else None)

    async def list_external_server_credential_slots(
        self,
        *,
        server_id: str,
    ) -> list[dict[str, Any]]:
        rows = await self.db_pool.fetchall(
            """
            SELECT slot.id,
                   slot.server_id,
                   slot.slot_name,
                   slot.display_name,
                   slot.secret_kind,
                   slot.privilege_class,
                   slot.is_required,
                   slot.created_by,
                   slot.updated_by,
                   slot.created_at,
                   slot.updated_at,
                   CASE WHEN slot_sec.slot_id IS NULL THEN 0 ELSE 1 END AS secret_configured,
                   slot_sec.key_hint
            FROM mcp_external_server_credential_slots slot
            LEFT JOIN mcp_external_server_slot_secrets slot_sec ON slot_sec.slot_id = slot.id
            WHERE slot.server_id = ?
            ORDER BY slot.slot_name, slot.id
            """,
            (server_id.strip(),),
        )
        return [
            self._normalize_external_slot_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def update_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
        display_name: str | object = _UNSET,
        secret_kind: str | object = _UNSET,
        privilege_class: str | object = _UNSET,
        is_required: bool | object = _UNSET,
        actor_id: int | None,
    ) -> dict[str, Any] | None:
        existing = await self.get_external_server_credential_slot(server_id=server_id, slot_name=slot_name)
        if not existing:
            return None
        next_display_name = (
            str(existing.get("display_name") or existing.get("slot_name"))
            if display_name is _UNSET
            else str(display_name or existing.get("slot_name") or "").strip()
        )
        next_secret_kind = (
            str(existing.get("secret_kind") or "secret")
            if secret_kind is _UNSET
            else str(secret_kind or "secret").strip().lower()
        )
        next_privilege_class = (
            str(existing.get("privilege_class") or "read").strip().lower()
            if privilege_class is _UNSET
            else _normalize_credential_slot_privilege_class(privilege_class)
        )
        next_required = (
            _to_bool(existing.get("is_required"))
            if is_required is _UNSET
            else _to_bool(is_required)
        )
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        required_value: bool | int = next_required if getattr(self.db_pool, "pool", None) is not None else int(next_required)
        cursor = await self.db_pool.execute(
            """
            UPDATE mcp_external_server_credential_slots
            SET display_name = ?,
                secret_kind = ?,
                privilege_class = ?,
                is_required = ?,
                updated_by = ?,
                updated_at = ?
            WHERE server_id = ?
              AND slot_name = ?
            """,
            (
                next_display_name,
                next_secret_kind,
                next_privilege_class,
                required_value,
                actor_id,
                ts,
                server_id.strip(),
                _normalize_slot_name(slot_name),
            ),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        if not (rowcount and rowcount > 0):
            return None
        return await self.get_external_server_credential_slot(server_id=server_id, slot_name=slot_name)

    async def delete_external_server_credential_slot(
        self,
        *,
        server_id: str,
        slot_name: str,
    ) -> bool:
        cursor = await self.db_pool.execute(
            """
            DELETE FROM mcp_external_server_credential_slots
            WHERE server_id = ?
              AND slot_name = ?
            """,
            (server_id.strip(), _normalize_slot_name(slot_name)),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def get_external_server_default_slot(
        self,
        *,
        server_id: str,
    ) -> dict[str, Any] | None:
        slots = await self.list_external_server_credential_slots(server_id=server_id)
        if len(slots) != 1:
            return None
        slot = dict(slots[0])
        if str(slot.get("slot_name") or "") not in {"bearer_token", "api_key"}:
            return None
        return slot

    async def upsert_external_server_slot_secret(
        self,
        *,
        server_id: str,
        slot_name: str,
        encrypted_blob: str,
        key_hint: str | None,
        actor_id: int | None,
    ) -> dict[str, Any]:
        slot = await self.get_external_server_credential_slot(server_id=server_id, slot_name=slot_name)
        if not slot:
            raise ValueError(f"Unknown external server slot: {server_id}/{slot_name}")
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        await self.db_pool.execute(
            """
            INSERT INTO mcp_external_server_slot_secrets (
                slot_id, encrypted_blob, key_hint, updated_by, updated_at
            ) VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(slot_id) DO UPDATE SET
                encrypted_blob = excluded.encrypted_blob,
                key_hint = excluded.key_hint,
                updated_by = excluded.updated_by,
                updated_at = excluded.updated_at
            """,
            (
                int(slot["id"]),
                encrypted_blob,
                key_hint,
                actor_id,
                ts,
            ),
        )
        row = await self.get_external_server_slot_secret(server_id=server_id, slot_name=slot_name)
        return row or {}

    async def get_external_server_slot_secret(
        self,
        *,
        server_id: str,
        slot_name: str,
    ) -> dict[str, Any] | None:
        row = await self.db_pool.fetchone(
            """
            SELECT slot.server_id,
                   slot.slot_name,
                   slot_sec.slot_id,
                   slot_sec.encrypted_blob,
                   slot_sec.key_hint,
                   slot_sec.updated_by,
                   slot_sec.updated_at
            FROM mcp_external_server_credential_slots slot
            JOIN mcp_external_server_slot_secrets slot_sec ON slot_sec.slot_id = slot.id
            WHERE slot.server_id = ?
              AND slot.slot_name = ?
            """,
            (server_id.strip(), _normalize_slot_name(slot_name)),
        )
        out = self._row_to_dict(row) if row else None
        if out is None:
            return None
        out["slot_name"] = _normalize_slot_name(out.get("slot_name"))
        return out

    async def clear_external_server_slot_secret(
        self,
        *,
        server_id: str,
        slot_name: str,
    ) -> bool:
        slot = await self.get_external_server_credential_slot(server_id=server_id, slot_name=slot_name)
        if not slot:
            return False
        cursor = await self.db_pool.execute(
            "DELETE FROM mcp_external_server_slot_secrets WHERE slot_id = ?",
            (int(slot["id"]),),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)

    async def upsert_credential_binding(
        self,
        *,
        binding_target_type: str,
        binding_target_id: str,
        external_server_id: str,
        slot_name: str | None = None,
        credential_ref: str,
        binding_mode: str,
        usage_rules: dict[str, Any],
        actor_id: int | None,
    ) -> dict[str, Any]:
        normalized_target_type = _normalize_credential_binding_target_type(binding_target_type)
        normalized_binding_mode = _normalize_credential_binding_mode(binding_mode)
        target_id = str(binding_target_id or "").strip()
        if not target_id:
            raise ValueError("binding_target_id is required")
        if normalized_target_type == "profile" and normalized_binding_mode == "disable":
            raise ValueError("profile bindings may not use disable mode")

        server = await self.get_external_server(external_server_id)
        if not server:
            raise ValueError(f"Unknown external server: {external_server_id}")
        if str(server.get("server_source") or "managed") != "managed":
            raise ValueError("credential bindings require a managed external server")
        if server.get("superseded_by_server_id"):
            raise ValueError("credential bindings cannot target superseded external servers")
        normalized_slot_name = _normalize_slot_name(slot_name, allow_blank=True)
        if normalized_slot_name:
            slot = await self.get_external_server_credential_slot(
                server_id=external_server_id,
                slot_name=normalized_slot_name,
            )
            if not slot:
                raise ValueError(f"Unknown external server slot: {external_server_id}/{normalized_slot_name}")

        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        usage = dict(usage_rules or {})

        await self.db_pool.execute(
            """
            INSERT INTO mcp_credential_bindings (
                binding_target_type,
                binding_target_id,
                external_server_id,
                slot_name,
                credential_ref,
                binding_mode,
                usage_rules_json,
                created_by,
                updated_by,
                created_at,
                updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_target_type,
                target_id,
                external_server_id.strip(),
                normalized_slot_name,
                str(credential_ref or "server").strip(),
                normalized_binding_mode,
                json.dumps(usage),
                actor_id,
                actor_id,
                ts,
                ts,
            ),
        )
        row = await self.db_pool.fetchone(
            """
            SELECT id,
                   binding_target_type,
                   binding_target_id,
                   external_server_id,
                   slot_name,
                   credential_ref,
                   binding_mode,
                   usage_rules_json,
                   created_by,
                   updated_by,
                   created_at,
                   updated_at
            FROM mcp_credential_bindings
            WHERE binding_target_type = ?
              AND binding_target_id = ?
              AND external_server_id = ?
              AND slot_name = ?
            """,
            (normalized_target_type, target_id, external_server_id.strip(), normalized_slot_name),
        )
        return self._normalize_credential_binding_row(self._row_to_dict(row) if row else None) or {}

    async def create_credential_binding(
        self,
        *,
        binding_target_type: str,
        binding_target_id: str,
        external_server_id: str,
        slot_name: str | None = None,
        credential_ref: str,
        binding_mode: str,
        usage_rules: dict[str, Any],
        actor_id: int | None,
    ) -> dict[str, Any]:
        existing = await self.db_pool.fetchone(
            """
            SELECT id
            FROM mcp_credential_bindings
            WHERE binding_target_type = ?
              AND binding_target_id = ?
              AND external_server_id = ?
              AND slot_name = ?
            """,
            (
                _normalize_credential_binding_target_type(binding_target_type),
                str(binding_target_id or "").strip(),
                external_server_id.strip(),
                _normalize_slot_name(slot_name, allow_blank=True),
            ),
        )
        if existing is not None:
            raise ValueError("credential binding already exists for target, server, and slot")
        return await self.upsert_credential_binding(
            binding_target_type=binding_target_type,
            binding_target_id=binding_target_id,
            external_server_id=external_server_id,
            slot_name=slot_name,
            credential_ref=credential_ref,
            binding_mode=binding_mode,
            usage_rules=usage_rules,
            actor_id=actor_id,
        )

    async def list_credential_bindings(
        self,
        *,
        binding_target_type: str,
        binding_target_id: str,
    ) -> list[dict[str, Any]]:
        normalized_target_type = _normalize_credential_binding_target_type(binding_target_type)
        target_id = str(binding_target_id or "").strip()
        rows = await self.db_pool.fetchall(
            """
            SELECT id,
                   binding_target_type,
                   binding_target_id,
                   external_server_id,
                   slot_name,
                   credential_ref,
                   binding_mode,
                   usage_rules_json,
                   created_by,
                   updated_by,
                   created_at,
                   updated_at
            FROM mcp_credential_bindings
            WHERE binding_target_type = ?
              AND binding_target_id = ?
            ORDER BY external_server_id, slot_name, id
            """,
            (normalized_target_type, target_id),
        )
        return [
            self._normalize_credential_binding_row(self._row_to_dict(row)) or {}
            for row in rows
        ]

    async def delete_credential_binding(
        self,
        *,
        binding_target_type: str,
        binding_target_id: str,
        external_server_id: str,
        slot_name: str | None = None,
    ) -> bool:
        cursor = await self.db_pool.execute(
            """
            DELETE FROM mcp_credential_bindings
            WHERE binding_target_type = ?
              AND binding_target_id = ?
              AND external_server_id = ?
              AND slot_name = ?
            """,
            (
                _normalize_credential_binding_target_type(binding_target_type),
                str(binding_target_id or "").strip(),
                external_server_id.strip(),
                _normalize_slot_name(slot_name, allow_blank=True),
            ),
        )
        rowcount = getattr(cursor, "rowcount", 0)
        return bool(rowcount and rowcount > 0)
