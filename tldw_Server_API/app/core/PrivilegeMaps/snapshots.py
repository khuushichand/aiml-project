from __future__ import annotations

import json
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool


class PrivilegeSnapshotStore:
    """Database-backed snapshot store for privilege maps."""

    def __init__(self, pool: Optional[DatabasePool] = None) -> None:
        self._pool = pool
        self._initialized = False

    async def list_snapshots(
        self,
        *,
        page: int,
        page_size: int,
        date_from: Optional[datetime],
        date_to: Optional[datetime],
        generated_by: Optional[str],
        org_id: Optional[str],
        team_id: Optional[str],
        catalog_version: Optional[str],
        scope: Optional[str],
        include_counts: bool,
    ) -> Dict[str, Any]:
        pool = await self._get_pool()
        await self._ensure_schema(pool)

        filters: List[str] = []
        params: List[Any] = []

        if org_id:
            filters.append("org_id = ?")
            params.append(org_id)
        if team_id:
            filters.append("team_id = ?")
            params.append(team_id)
        if generated_by:
            filters.append("generated_by = ?")
            params.append(generated_by)
        if catalog_version:
            filters.append("catalog_version = ?")
            params.append(catalog_version)
        if date_from:
            filters.append("generated_at >= ?")
            params.append(self._to_iso(date_from))
        if date_to:
            filters.append("generated_at <= ?")
            params.append(self._to_iso(date_to))
        if scope:
            filters.append("scope_index LIKE ?")
            params.append(f"%|{scope}|%")

        where_clause = f"WHERE {' AND '.join(filters)}" if filters else ""
        count_row = await pool.fetchone(
            f"SELECT COUNT(*) AS total FROM privilege_snapshots {where_clause}",
            tuple(params),
        )
        if not count_row:
            total_items = 0
        elif isinstance(count_row, dict):
            total_items = int(count_row.get("total", 0))
        elif hasattr(count_row, "keys"):
            total_items = int(count_row["total"])
        else:
            total_items = int(count_row[0])

        page = max(page, 1)
        page_size = max(min(page_size, 200), 1)
        offset = (page - 1) * page_size
        data_params = list(params) + [page_size, offset]

        rows = await pool.fetchall(
            f"""
            SELECT snapshot_id, generated_at, generated_by, target_scope, org_id, team_id,
                   catalog_version, summary_json
            FROM privilege_snapshots
            {where_clause}
            ORDER BY generated_at DESC
            LIMIT ? OFFSET ?
            """,
            tuple(data_params),
        )

        items: List[Dict[str, Any]] = []
        for row in rows:
            record = self._row_to_dict(row)
            if not record:
                continue
            summary_obj = None
            if include_counts and record.get("summary_json"):
                try:
                    summary_obj = json.loads(record["summary_json"])
                except Exception as exc:
                    logger.warning("Failed to parse snapshot summary JSON: %s", exc)
                    summary_obj = None

            generated_at_dt = self._parse_datetime(record.get("generated_at"))

            items.append(
                {
                    "snapshot_id": record.get("snapshot_id"),
                    "generated_at": generated_at_dt,
                    "generated_by": record.get("generated_by"),
                    "target_scope": record.get("target_scope"),
                    "org_id": record.get("org_id"),
                    "team_id": record.get("team_id"),
                    "catalog_version": record.get("catalog_version"),
                    "summary": summary_obj,
                }
            )

        return {
            "page": page,
            "page_size": page_size,
            "total_items": total_items,
            "items": items,
            "filters": {
                "date_from": date_from.isoformat() if date_from else None,
                "date_to": date_to.isoformat() if date_to else None,
                "generated_by": generated_by,
                "org_id": org_id,
                "team_id": team_id,
                "catalog_version": catalog_version,
                "scope": scope,
                "include_counts": include_counts,
            },
        }

    async def add_snapshot(self, snapshot: Dict[str, Any]) -> None:
        snapshot_id = snapshot.get("snapshot_id")
        if not snapshot_id:
            raise ValueError("snapshot must include snapshot_id")

        pool = await self._get_pool()
        await self._ensure_schema(pool)

        generated_at = snapshot.get("generated_at")
        generated_at_iso = self._to_iso(generated_at)
        generated_by = snapshot.get("generated_by")
        target_scope = snapshot.get("target_scope")
        org_id = snapshot.get("org_id")
        team_id = snapshot.get("team_id")
        catalog_version = snapshot.get("catalog_version")
        summary = snapshot.get("summary")
        summary_json = json.dumps(summary) if summary is not None else None
        scope_index = self._build_scope_index(summary)
        now_iso = self._to_iso(datetime.now(timezone.utc))

        async with pool.transaction() as conn:
            await conn.execute(
                """
                INSERT INTO privilege_snapshots (
                    snapshot_id,
                    generated_at,
                    generated_by,
                    target_scope,
                    org_id,
                    team_id,
                    catalog_version,
                    summary_json,
                    scope_index,
                    created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(snapshot_id) DO UPDATE SET
                    generated_at = excluded.generated_at,
                    generated_by = excluded.generated_by,
                    target_scope = excluded.target_scope,
                    org_id = excluded.org_id,
                    team_id = excluded.team_id,
                    catalog_version = excluded.catalog_version,
                    summary_json = excluded.summary_json,
                    scope_index = excluded.scope_index,
                    updated_at = excluded.updated_at
                """,
                (
                    snapshot_id,
                    generated_at_iso,
                    generated_by,
                    target_scope,
                    org_id,
                    team_id,
                    catalog_version,
                    summary_json,
                    scope_index,
                    now_iso,
                    now_iso,
                ),
            )

    async def clear(self) -> None:
        pool = await self._get_pool()
        await self._ensure_schema(pool)
        async with pool.transaction() as conn:
            await conn.execute("DELETE FROM privilege_snapshots")

    async def get_snapshot(
        self,
        *,
        snapshot_id: str,
        page: int,
        page_size: int,
    ) -> Optional[Dict[str, Any]]:
        pool = await self._get_pool()
        await self._ensure_schema(pool)
        row = await pool.fetchone(
            """
            SELECT snapshot_id,
                   generated_at,
                   generated_by,
                   target_scope,
                   org_id,
                   team_id,
                   catalog_version,
                   summary_json
            FROM privilege_snapshots
            WHERE snapshot_id = ?
            """,
            (snapshot_id,),
        )
        record = self._row_to_dict(row)
        if not record:
            return None

        summary_obj = None
        if record.get("summary_json"):
            try:
                summary_obj = json.loads(record["summary_json"])
            except Exception as exc:
                logger.warning("Failed to parse snapshot summary JSON: %s", exc)
                summary_obj = None

        detail = {
            "page": page,
            "page_size": page_size,
            "total_items": 0,
            "items": [],
        }

        return {
            "snapshot_id": record.get("snapshot_id"),
            "catalog_version": record.get("catalog_version"),
            "generated_at": self._parse_datetime(record.get("generated_at")),
            "generated_by": record.get("generated_by"),
            "target_scope": record.get("target_scope"),
            "org_id": record.get("org_id"),
            "team_id": record.get("team_id"),
            "summary": summary_obj,
            "detail": detail,
            "etag": f'W/"{record.get("snapshot_id")}-v1"',
        }

    # ------------------------------------------------------------------ #
    # Internal helpers
    # ------------------------------------------------------------------ #

    async def _get_pool(self) -> DatabasePool:
        if self._pool is None:
            self._pool = await get_db_pool()
        return self._pool

    async def _ensure_schema(self, pool: DatabasePool) -> None:
        if self._initialized:
            return
        async with pool.transaction() as conn:
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS privilege_snapshots (
                    snapshot_id TEXT PRIMARY KEY,
                    generated_at TEXT NOT NULL,
                    generated_by TEXT NOT NULL,
                    target_scope TEXT,
                    org_id TEXT,
                    team_id TEXT,
                    catalog_version TEXT NOT NULL,
                    summary_json TEXT,
                    scope_index TEXT,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

        # Ensure legacy deployments add scope_index column
        try:
            async with pool.transaction() as conn:
                await conn.execute(
                    "ALTER TABLE privilege_snapshots ADD COLUMN scope_index TEXT"
                )
        except Exception:
            pass

        try:
            async with pool.transaction() as conn:
                await conn.execute(
                    "ALTER TABLE privilege_snapshots ADD COLUMN target_scope TEXT"
                )
        except Exception:
            pass

        try:
            async with pool.transaction() as conn:
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_generated_at ON privilege_snapshots(generated_at)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_org ON privilege_snapshots(org_id)"
                )
                await conn.execute(
                    "CREATE INDEX IF NOT EXISTS idx_priv_snapshots_team ON privilege_snapshots(team_id)"
                )
        except Exception as exc:
            logger.debug("Privilege snapshot index creation skipped: %s", exc)

        self._initialized = True

    @staticmethod
    def _row_to_dict(row: Any) -> Optional[Dict[str, Any]]:
        if row is None:
            return None
        if isinstance(row, dict):
            return row
        if hasattr(row, "keys"):
            return {key: row[key] for key in row.keys()}
        if hasattr(row, "_mapping"):
            return dict(row._mapping)  # type: ignore[attr-defined]
        return None

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if value is None:
            return None
        if isinstance(value, datetime):
            return value
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        except Exception:
            return None

    @staticmethod
    def _to_iso(value: Any) -> str:
        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(tzinfo=timezone.utc)
            return value.astimezone(timezone.utc).isoformat()
        if isinstance(value, str):
            return value
        return datetime.now(timezone.utc).isoformat()

    @staticmethod
    def _build_scope_index(summary: Optional[Dict[str, Any]]) -> Optional[str]:
        if not summary:
            return None
        scope_ids = summary.get("scope_ids")
        if not scope_ids:
            return None
        ordered = sorted(set(scope_ids))
        return "|" + "|".join(ordered) + "|"


@lru_cache
def get_privilege_snapshot_store() -> PrivilegeSnapshotStore:
    return PrivilegeSnapshotStore()
