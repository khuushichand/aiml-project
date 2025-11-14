from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool, is_postgres_backend


class AuthNZPolicyAdmin:
    """
    Admin DAL for Resource Governor policies in the AuthNZ DB (SoT).

    Provides upsert/list/get/delete and tenant config helpers.
    """

    def __init__(self, db_pool: Optional[DatabasePool] = None) -> None:
        self.db_pool = db_pool
        self._initialized = False

    async def initialize(self) -> None:
        if self._initialized:
            return
        if not self.db_pool:
            self.db_pool = await get_db_pool()
        is_pg = await is_postgres_backend()
        try:
            async with self.db_pool.transaction() as conn:
                if is_pg:
                    await conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS rg_policies (
                          id TEXT PRIMARY KEY,
                          payload JSONB NOT NULL,
                          version INTEGER NOT NULL DEFAULT 1,
                          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
                        )
                        """
                    )
                else:
                    await conn.execute(
                        """
                        CREATE TABLE IF NOT EXISTS rg_policies (
                          id TEXT PRIMARY KEY,
                          payload TEXT NOT NULL,
                          version INTEGER NOT NULL DEFAULT 1,
                          updated_at TEXT NOT NULL
                        )
                        """
                    )
            self._initialized = True
        except Exception as e:
            logger.error(f"AuthNZPolicyAdmin.initialize failed: {e}")
            raise

    async def upsert_policy(self, policy_id: str, payload: Dict[str, Any], version: Optional[int] = None) -> None:
        if not self._initialized:
            await self.initialize()
        is_pg = await is_postgres_backend()
        now = datetime.now(timezone.utc)
        try:
            if is_pg:
                upsert_sql = (
                    "INSERT INTO rg_policies (id, payload, version, updated_at) "
                    "VALUES ($1, $2::jsonb, $3, $4) "
                    "ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload, version=EXCLUDED.version, updated_at=EXCLUDED.updated_at"
                )
                ver = int(version) if version is not None else await self._next_version(policy_id)
                await self.db_pool.execute(upsert_sql, policy_id, json.dumps(payload), ver, now)
            else:
                # SQLite: store payload as TEXT (JSON string)
                ver = int(version) if version is not None else await self._next_version(policy_id)
                await self.db_pool.execute(
                    "INSERT OR REPLACE INTO rg_policies (id, payload, version, updated_at) VALUES (?, ?, ?, ?)",
                    policy_id,
                    json.dumps(payload),
                    ver,
                    now.isoformat(),
                )
        except Exception as e:
            logger.error(f"AuthNZPolicyAdmin.upsert_policy failed: {e}")
            raise

    async def _next_version(self, policy_id: str) -> int:
        try:
            row = await self.db_pool.fetchone("SELECT version FROM rg_policies WHERE id = ?", policy_id)
            if row is None:
                return 1
            cur = int(row["version"] if isinstance(row, dict) else row[0] or 0)
            return max(1, cur + 1)
        except Exception:
            return 1

    async def get_policy(self, policy_id: str) -> Optional[Dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        try:
            row = await self.db_pool.fetchone("SELECT payload FROM rg_policies WHERE id = ?", policy_id)
            if not row:
                return None
            payload = row["payload"] if isinstance(row, dict) else row[0]
            if isinstance(payload, (bytes, bytearray)):
                payload = payload.decode("utf-8", errors="ignore")
            if isinstance(payload, str):
                try:
                    return json.loads(payload)
                except Exception:
                    return {}
            if isinstance(payload, dict):
                return payload
            return {}
        except Exception as e:
            logger.error(f"AuthNZPolicyAdmin.get_policy failed: {e}")
            raise

    async def get_policy_record(self, policy_id: str) -> Optional[Dict[str, Any]]:
        """
        Return full record including id, version, updated_at, and payload.
        """
        if not self._initialized:
            await self.initialize()
        try:
            row = await self.db_pool.fetchone("SELECT id, version, updated_at, payload FROM rg_policies WHERE id = ?", policy_id)
            if not row:
                return None
            if isinstance(row, dict):
                payload = row.get("payload")
                if isinstance(payload, (bytes, bytearray)):
                    payload = payload.decode("utf-8", errors="ignore")
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except Exception:
                        payload = {}
                upd = row.get("updated_at")
                try:
                    # Normalize datetimes to ISO strings for JSON friendliness
                    if hasattr(upd, "isoformat"):
                        upd = upd.isoformat()
                except Exception:
                    pass
                return {
                    "id": row.get("id"),
                    "version": int(row.get("version") or 1),
                    "updated_at": upd,
                    "payload": payload if isinstance(payload, dict) else {},
                }
            # Row-like (SQLite)
            rid = row[0]
            ver = int(row[1] or 1)
            upd = row[2]
            try:
                if hasattr(upd, "isoformat"):
                    upd = upd.isoformat()
            except Exception:
                pass
            payload = row[3]
            if isinstance(payload, (bytes, bytearray)):
                payload = payload.decode("utf-8", errors="ignore")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {}
            return {"id": rid, "version": ver, "updated_at": upd, "payload": payload if isinstance(payload, dict) else {}}
        except Exception as e:
            logger.error(f"AuthNZPolicyAdmin.get_policy_record failed: {e}")
            raise

    async def list_policies(self) -> List[Dict[str, Any]]:
        if not self._initialized:
            await self.initialize()
        try:
            rows = await self.db_pool.fetchall("SELECT id, version, updated_at FROM rg_policies ORDER BY id")
            out: List[Dict[str, Any]] = []
            for r in rows:
                rid = r["id"] if isinstance(r, dict) else r[0]
                ver = int(r["version"] if isinstance(r, dict) else r[1] or 1)
                upd = r["updated_at"] if isinstance(r, dict) else r[2]
                try:
                    if hasattr(upd, "isoformat"):
                        upd = upd.isoformat()
                except Exception:
                    pass
                out.append({
                    "id": rid,
                    "version": ver,
                    "updated_at": upd,
                })
            return out
        except Exception as e:
            logger.error(f"AuthNZPolicyAdmin.list_policies failed: {e}")
            raise

    async def delete_policy(self, policy_id: str) -> int:
        if not self._initialized:
            await self.initialize()
        try:
            res = await self.db_pool.execute("DELETE FROM rg_policies WHERE id = ?", policy_id)
            # asyncpg returns 'DELETE <n>' string; SQLite returns cursor
            if isinstance(res, str) and res.startswith("DELETE"):
                try:
                    return int(res.split(" ")[1])
                except Exception:
                    return 0
            return 0
        except Exception as e:
            logger.error(f"AuthNZPolicyAdmin.delete_policy failed: {e}")
            raise

    async def set_tenant_config(self, tenant_payload: Dict[str, Any], version: Optional[int] = None) -> None:
        await self.upsert_policy("tenant", tenant_payload, version)

    async def get_tenant_config(self) -> Optional[Dict[str, Any]]:
        return await self.get_policy("tenant")
