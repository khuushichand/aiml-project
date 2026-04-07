"""Unified Sharing audit writer and compatibility projection helpers."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from tldw_Server_API.app.core.Audit.unified_audit_service import (
    AuditContext,
    UnifiedAuditService,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

_SHARE_EVENT_FILTER_SQL = "(event_type LIKE 'share.%' OR event_type LIKE 'token.%')"
_SHARE_AUDIT_STATE_TABLE = "share_audit_state"
_SHARE_AUDIT_SEQUENCE_KEY = "compatibility_id_seq"
_RESERVED_METADATA_KEYS = {
    "compatibility_id",
    "legacy_share_audit_id",
    "owner_user_id",
    "actor_user_id",
    "share_id",
    "token_id",
}


def _coerce_int(value: Any) -> int | None:
    if value is None:
        return None
    try:
        if isinstance(value, bool):
            raise TypeError("bool is not a valid integer")
        return int(str(value).strip())
    except (TypeError, ValueError):
        return None


def _load_metadata(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if raw is None:
        return {}
    if isinstance(raw, str):
        try:
            loaded = json.loads(raw)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}
        return dict(loaded) if isinstance(loaded, dict) else {}
    return {}


def _visible_metadata(metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        key: value
        for key, value in metadata.items()
        if key not in _RESERVED_METADATA_KEYS and value is not None
    }


class UnifiedShareAuditWriter:
    """Write Sharing events into unified audit and project them back compatibly."""

    def __init__(self, db_path: str | None = None) -> None:
        resolved = Path(db_path) if db_path else DatabasePaths.get_shared_audit_db_path()
        self.db_path = str(resolved)
        self._service = UnifiedAuditService(db_path=self.db_path, storage_mode="shared")
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        await self._service.initialize(start_background_tasks=False)
        await self._ensure_compatibility_state()
        await self._sync_compatibility_floor()
        self._initialized = True

    async def stop(self) -> None:
        if not self._initialized:
            return
        await self._service.stop()
        self._initialized = False

    async def _ensure_compatibility_state(self) -> None:
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                f"""
                CREATE TABLE IF NOT EXISTS {_SHARE_AUDIT_STATE_TABLE} (
                    key TEXT PRIMARY KEY,
                    int_value INTEGER NOT NULL
                )
                """
            )
            await db.execute(
                f"""
                INSERT OR IGNORE INTO {_SHARE_AUDIT_STATE_TABLE} (key, int_value)
                VALUES (?, 0)
                """,
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            )
            await db.commit()

    async def _current_sequence_value(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT int_value FROM {_SHARE_AUDIT_STATE_TABLE} WHERE key = ?",
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            ) as cur:
                row = await cur.fetchone()
        return int(row["int_value"]) if row is not None else 0

    async def _max_existing_compatibility_id(self) -> int:
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(
                f"SELECT metadata FROM audit_events WHERE {_SHARE_EVENT_FILTER_SQL}"
            ) as cur:
                rows = await cur.fetchall()

        max_id = 0
        for row in rows:
            metadata = _load_metadata(row["metadata"])
            compatibility_id = _coerce_int(
                metadata.get("compatibility_id")
                or metadata.get("legacy_share_audit_id")
            )
            if compatibility_id is not None:
                max_id = max(max_id, compatibility_id)
        return max_id

    async def _sync_compatibility_floor(self) -> None:
        floor = max(
            await self._current_sequence_value(),
            await self._max_existing_compatibility_id(),
        )
        await self.bump_compatibility_floor(floor)

    async def bump_compatibility_floor(self, floor: int) -> None:
        await self._ensure_compatibility_state()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                f"""
                INSERT OR IGNORE INTO {_SHARE_AUDIT_STATE_TABLE} (key, int_value)
                VALUES (?, 0)
                """,
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            )
            async with db.execute(
                f"SELECT int_value FROM {_SHARE_AUDIT_STATE_TABLE} WHERE key = ?",
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            ) as cur:
                row = await cur.fetchone()
            current = int(row["int_value"]) if row is not None else 0
            if floor > current:
                await db.execute(
                    f"UPDATE {_SHARE_AUDIT_STATE_TABLE} SET int_value = ? WHERE key = ?",
                    (floor, _SHARE_AUDIT_SEQUENCE_KEY),
                )
            await db.commit()

    async def _allocate_compatibility_id(self) -> int:
        await self._ensure_compatibility_state()
        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            await db.execute("BEGIN IMMEDIATE")
            await db.execute(
                f"""
                INSERT OR IGNORE INTO {_SHARE_AUDIT_STATE_TABLE} (key, int_value)
                VALUES (?, 0)
                """,
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            )
            await db.execute(
                f"UPDATE {_SHARE_AUDIT_STATE_TABLE} SET int_value = int_value + 1 WHERE key = ?",
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            )
            async with db.execute(
                f"SELECT int_value FROM {_SHARE_AUDIT_STATE_TABLE} WHERE key = ?",
                (_SHARE_AUDIT_SEQUENCE_KEY,),
            ) as cur:
                row = await cur.fetchone()
            await db.commit()
        if row is None:
            raise RuntimeError("Failed to allocate Sharing audit compatibility id")
        return int(row["int_value"])

    async def log_event(
        self,
        *,
        event_type: str,
        resource_type: str,
        resource_id: str,
        owner_user_id: int,
        actor_user_id: int | None = None,
        share_id: int | None = None,
        token_id: int | None = None,
        metadata: dict[str, Any] | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        result: str = "success",
    ) -> int:
        await self.initialize()
        compatibility_id = await self._allocate_compatibility_id()
        payload = dict(metadata or {})
        payload.update(
            {
                "compatibility_id": compatibility_id,
                "owner_user_id": owner_user_id,
                "actor_user_id": actor_user_id,
                "share_id": share_id,
                "token_id": token_id,
            }
        )
        context = AuditContext(
            user_id=str(actor_user_id) if actor_user_id is not None else None,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        await self._service.log_event(
            event_type=event_type,
            context=context,
            tenant_user_id_override=str(owner_user_id),
            resource_type=resource_type,
            resource_id=resource_id,
            action=event_type,
            result=result,
            metadata=payload,
        )
        await self._service.flush(raise_on_failure=True)
        return compatibility_id

    async def query_events(
        self,
        *,
        owner_user_id: int | None = None,
        resource_type: str | None = None,
        resource_id: str | None = None,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        await self.initialize()
        conditions = [_SHARE_EVENT_FILTER_SQL]
        params: list[Any] = []
        if owner_user_id is not None:
            conditions.append("tenant_user_id = ?")
            params.append(str(owner_user_id))
        if resource_type is not None:
            conditions.append("resource_type = ?")
            params.append(resource_type)
        if resource_id is not None:
            conditions.append("resource_id = ?")
            params.append(resource_id)
        params.extend([limit, offset])

        query = f"""
            SELECT
                timestamp,
                event_type,
                tenant_user_id,
                context_user_id,
                context_ip_address,
                context_user_agent,
                resource_type,
                resource_id,
                metadata
            FROM audit_events
            WHERE {' AND '.join(conditions)}
            ORDER BY timestamp DESC, event_id DESC
            LIMIT ? OFFSET ?
        """

        async with aiosqlite.connect(self.db_path) as db:
            db.row_factory = aiosqlite.Row
            async with db.execute(query, tuple(params)) as cur:
                rows = await cur.fetchall()

        return [self._project_row(dict(row)) for row in rows]

    def _project_row(self, row: dict[str, Any]) -> dict[str, Any]:
        metadata = _load_metadata(row.get("metadata"))
        compatibility_id = _coerce_int(
            metadata.get("compatibility_id")
            or metadata.get("legacy_share_audit_id")
        )
        if compatibility_id is None:
            raise ValueError("Sharing audit row is missing a compatibility id")

        owner_user_id = _coerce_int(row.get("tenant_user_id"))
        if owner_user_id is None:
            owner_user_id = _coerce_int(metadata.get("owner_user_id"))
        if owner_user_id is None:
            raise ValueError("Sharing audit row is missing an owner_user_id")

        actor_user_id = _coerce_int(metadata.get("actor_user_id"))
        if actor_user_id is None:
            actor_user_id = _coerce_int(row.get("context_user_id"))

        return {
            "id": compatibility_id,
            "event_type": str(row.get("event_type") or ""),
            "actor_user_id": actor_user_id,
            "resource_type": row.get("resource_type"),
            "resource_id": row.get("resource_id"),
            "owner_user_id": owner_user_id,
            "share_id": _coerce_int(metadata.get("share_id")),
            "token_id": _coerce_int(metadata.get("token_id")),
            "metadata": _visible_metadata(metadata),
            "ip_address": row.get("context_ip_address"),
            "user_agent": row.get("context_user_agent"),
            "created_at": row.get("timestamp"),
        }
