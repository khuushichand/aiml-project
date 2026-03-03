from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool

_VALID_SCOPE_TYPES = {"global", "org", "team", "user"}


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
                "mcp_external_servers",
                "mcp_external_server_secrets",
            }
            rows = await self.db_pool.fetchall(
                "SELECT name FROM sqlite_master WHERE type='table' AND name IN (?, ?, ?)",
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
    def _normalize_datetime_for_postgres(dt: datetime) -> datetime:
        return dt.replace(tzinfo=None) if getattr(dt, "tzinfo", None) else dt

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
        ts = (
            self._normalize_datetime_for_postgres(now)
            if getattr(self.db_pool, "pool", None) is not None
            else now.isoformat()
        )
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
        ts = (
            self._normalize_datetime_for_postgres(now)
            if getattr(self.db_pool, "pool", None) is not None
            else now.isoformat()
        )
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
        ts = (
            self._normalize_datetime_for_postgres(now)
            if getattr(self.db_pool, "pool", None) is not None
            else now.isoformat()
        )
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
        ts = (
            self._normalize_datetime_for_postgres(now)
            if getattr(self.db_pool, "pool", None) is not None
            else now.isoformat()
        )
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
