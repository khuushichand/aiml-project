from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from typing import Any

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool


async def seed_rg_policies_sqlite(db_pool: DatabasePool, rows: Iterable[Mapping[str, Any]]) -> None:
    """
    Seed rg_policies table in SQLite (AuthNZ DB) for tests and local dev.

    Each row mapping expects keys: id (str), payload (dict or JSON string),
    version (int), updated_at (datetime or ISO8601 string).
    """
    # Ensure table
    await db_pool.execute(
        """
        CREATE TABLE IF NOT EXISTS rg_policies (
          id TEXT PRIMARY KEY,
          payload TEXT NOT NULL,
          version INTEGER NOT NULL DEFAULT 1,
          updated_at TEXT NOT NULL
        )
        """
    )
    # Insert rows
    for r in rows:
        pid = str(r.get("id"))
        payload_obj = r.get("payload") or {}
        payload = json.dumps(payload_obj) if not isinstance(payload_obj, (str, bytes, bytearray)) else payload_obj
        ver = int(r.get("version") or 1)
        upd = r.get("updated_at")
        if isinstance(upd, datetime):
            upd_s = upd.astimezone(timezone.utc).isoformat()
        else:
            upd_s = str(upd or datetime.now(timezone.utc).isoformat())
        await db_pool.execute(
            "INSERT OR REPLACE INTO rg_policies (id, payload, version, updated_at) VALUES (?, ?, ?, ?)",
            pid,
            payload,
            ver,
            upd_s,
        )


async def seed_rg_policies_postgres(db_pool: DatabasePool, rows: Iterable[Mapping[str, Any]]) -> None:
    """
    Seed rg_policies table in PostgreSQL (AuthNZ DB) for tests and local dev.

    Each row mapping expects keys: id (str), payload (dict or JSON string),
    version (int), updated_at (datetime or ISO8601 string).
    """
    # Ensure table (JSONB payload)
    await db_pool.execute(
        """
        CREATE TABLE IF NOT EXISTS rg_policies (
          id TEXT PRIMARY KEY,
          payload JSONB NOT NULL,
          version INTEGER NOT NULL DEFAULT 1,
          updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )

    upsert_sql = (
        "INSERT INTO rg_policies (id, payload, version, updated_at) "
        "VALUES ($1, $2::jsonb, $3, $4) "
        "ON CONFLICT (id) DO UPDATE SET payload=EXCLUDED.payload, version=EXCLUDED.version, updated_at=EXCLUDED.updated_at"
    )
    for r in rows:
        pid = str(r.get("id"))
        payload_obj = r.get("payload") or {}
        payload = json.dumps(payload_obj) if not isinstance(payload_obj, (str, bytes, bytearray)) else payload_obj
        ver = int(r.get("version") or 1)
        upd = r.get("updated_at")
        if isinstance(upd, datetime):
            upd_dt = upd.astimezone(timezone.utc)
        else:
            try:
                upd_dt = datetime.fromisoformat(str(upd).replace("Z", "+00:00")).astimezone(timezone.utc)
            except Exception:
                upd_dt = datetime.now(timezone.utc)
        await db_pool.execute(upsert_sql, pid, payload, ver, upd_dt)
