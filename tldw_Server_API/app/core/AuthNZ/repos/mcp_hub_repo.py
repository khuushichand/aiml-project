from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool

_VALID_SCOPE_TYPES = {"global", "org", "team", "user"}
_VALID_TARGET_TYPES = {"default", "group", "persona"}
_VALID_PROFILE_MODES = {"preset", "custom"}
_VALID_APPROVAL_MODES = {
    "allow_silently",
    "ask_every_time",
    "ask_outside_profile",
    "ask_on_sensitive_actions",
    "temporary_elevation_allowed",
}
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
                "mcp_credential_bindings",
                "mcp_external_servers",
                "mcp_external_server_secrets",
                "mcp_permission_profiles",
                "mcp_policy_assignments",
                "mcp_policy_audit_history",
                "mcp_policy_overrides",
            }
            placeholders = ", ".join("?" for _ in required)
            rows = await self.db_pool.fetchall(
                f"SELECT name FROM sqlite_master WHERE type='table' AND name IN ({placeholders})",
                tuple(required),
            )
            existing = {str(row["name"]) for row in rows}
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
        return out

    @staticmethod
    def _normalize_permission_profile_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["policy_document"] = _load_json_dict(out.pop("policy_document_json", None))
        return out

    @staticmethod
    def _normalize_policy_assignment_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["inline_policy_document"] = _load_json_dict(out.pop("inline_policy_document_json", None))
        return out

    @staticmethod
    def _normalize_approval_policy_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["is_active"] = _to_bool(out.get("is_active"))
        out["rules"] = _load_json_dict(out.pop("rules_json", None))
        return out

    @staticmethod
    def _normalize_approval_decision_row(row: dict[str, Any] | None) -> dict[str, Any] | None:
        if row is None:
            return None
        out = dict(row)
        out["consume_on_match"] = _to_bool(out.get("consume_on_match"))
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
        policy_document: dict[str, Any],
        actor_id: int | None,
        description: str | None = None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        profile_mode = _normalize_profile_mode(mode)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_permission_profiles (
                name, description, owner_scope_type, owner_scope_id, mode, policy_document_json, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                profile_mode,
                json.dumps(policy_document or {}),
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
            SELECT id, name, description, owner_scope_type, owner_scope_id, mode, policy_document_json, is_active,
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
            SELECT id, name, description, owner_scope_type, owner_scope_id, mode, policy_document_json, is_active,
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

    async def create_policy_assignment(
        self,
        *,
        target_type: str,
        target_id: str | None,
        owner_scope_type: str,
        owner_scope_id: int | None,
        profile_id: int | None,
        inline_policy_document: dict[str, Any],
        approval_policy_id: int | None,
        actor_id: int | None,
        is_active: bool = True,
    ) -> dict[str, Any]:
        normalized_target_type = _normalize_target_type(target_type)
        normalized_target_id = str(target_id).strip() if target_id is not None else None
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_policy_assignments (
                target_type, target_id, owner_scope_type, owner_scope_id, profile_id,
                inline_policy_document_json, approval_policy_id, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                normalized_target_type,
                normalized_target_id,
                scope_type,
                owner_scope_id,
                profile_id,
                json.dumps(inline_policy_document or {}),
                approval_policy_id,
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
            SELECT id, target_type, target_id, owner_scope_type, owner_scope_id, profile_id,
                   inline_policy_document_json, approval_policy_id, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_policy_assignments
            WHERE id = ?
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
            SELECT id, target_type, target_id, owner_scope_type, owner_scope_id, profile_id,
                   inline_policy_document_json, approval_policy_id, is_active,
                   created_by, updated_by, created_at, updated_at
            FROM mcp_policy_assignments
            WHERE (? IS NULL OR owner_scope_type = ?)
              AND (? IS NULL OR owner_scope_id = ?)
              AND (? IS NULL OR target_type = ?)
              AND (? IS NULL OR target_id = ?)
            ORDER BY target_type, target_id, id
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
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        approval_mode = _normalize_approval_mode(mode)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        active_value: bool | int = is_active if getattr(self.db_pool, "pool", None) is not None else int(is_active)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_approval_policies (
                name, description, owner_scope_type, owner_scope_id, mode, rules_json, is_active,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                name.strip(),
                description,
                scope_type,
                owner_scope_id,
                approval_mode,
                json.dumps(rules or {}),
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
        actor_id: int | None,
    ) -> dict[str, Any]:
        scope_type = _normalize_scope_type(owner_scope_type)
        now = datetime.now(timezone.utc)
        ts = now if getattr(self.db_pool, "pool", None) is not None else now.isoformat()
        enabled_value: bool | int = enabled if getattr(self.db_pool, "pool", None) is not None else int(enabled)
        await self.db_pool.execute(
            """
            INSERT INTO mcp_external_servers (
                id, name, enabled, owner_scope_type, owner_scope_id, transport, config_json,
                created_by, updated_by, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                name = excluded.name,
                enabled = excluded.enabled,
                owner_scope_type = excluded.owner_scope_type,
                owner_scope_id = excluded.owner_scope_id,
                transport = excluded.transport,
                config_json = excluded.config_json,
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
        actor_id: int | None,
    ) -> dict[str, Any] | None:
        """Update an existing external server row and return the normalized record."""
        scope_type = _normalize_scope_type(owner_scope_type)
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
                   s.config_json,
                   s.created_by,
                   s.updated_by,
                   s.created_at,
                   s.updated_at,
                   CASE WHEN sec.server_id IS NULL THEN 0 ELSE 1 END AS secret_configured,
                   sec.key_hint
            FROM mcp_external_servers s
            LEFT JOIN mcp_external_server_secrets sec ON sec.server_id = s.id
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
                   s.config_json,
                   s.created_by,
                   s.updated_by,
                   s.created_at,
                   s.updated_at,
                   CASE WHEN sec.server_id IS NULL THEN 0 ELSE 1 END AS secret_configured,
                   sec.key_hint
            FROM mcp_external_servers s
            LEFT JOIN mcp_external_server_secrets sec ON sec.server_id = s.id
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
