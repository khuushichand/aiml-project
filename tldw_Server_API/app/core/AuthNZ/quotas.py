from __future__ import annotations

from datetime import datetime
from typing import Optional, Tuple

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool


async def _ensure_tables(conn) -> None:
    """Ensure counters tables exist (idempotent). Used defensively from enforcement paths."""
    try:
        # Detect dialect by method availability
        if hasattr(conn, "execute") and not hasattr(conn, "fetchval"):
            # SQLite shim (aiosqlite connection via DatabasePool.transaction())
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vk_jwt_counters (
                    jti TEXT NOT NULL,
                    counter_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (jti, counter_type)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vk_api_key_counters (
                    api_key_id INTEGER NOT NULL,
                    counter_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (api_key_id, counter_type)
                )
                """
            )
        else:
            # Postgres/asyncpg
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vk_jwt_counters (
                    jti TEXT NOT NULL,
                    counter_type TEXT NOT NULL,
                    count BIGINT DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (jti, counter_type)
                )
                """
            )
            await conn.execute(
                """
                CREATE TABLE IF NOT EXISTS vk_api_key_counters (
                    api_key_id INTEGER NOT NULL REFERENCES api_keys(id) ON DELETE CASCADE,
                    counter_type TEXT NOT NULL,
                    count BIGINT DEFAULT 0,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    PRIMARY KEY (api_key_id, counter_type)
                )
                """
            )
    except Exception as e:
        # Never fail caller if ensure-tables trips; enforcement will fall back to process-local counters
        logger.debug(f"Quota ensure-tables skipped/failed: {e}")


async def increment_and_check_jwt_quota(
    db_pool: DatabasePool,
    jti: str,
    counter_type: str,
    limit: Optional[int],
    bucket: Optional[str] = None,
) -> Tuple[bool, int]:
    """
    Atomically increment JWT (by jti) quota counter and compare to limit.
    Returns (allowed, new_count). If limit is None, returns (True, current+1).
    """
    if not jti or limit is None:
        # Caller either cannot identify token or no limit is set; do nothing
        return True, -1
    try:
        ctype = f"{counter_type}@{bucket}" if bucket else str(counter_type)
        async with db_pool.transaction() as conn:
            await _ensure_tables(conn)
            if hasattr(conn, "fetchval"):
                # Postgres
                new_count = await conn.fetchval(
                    """
                    INSERT INTO vk_jwt_counters (jti, counter_type, count, updated_at)
                    VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (jti, counter_type)
                    DO UPDATE SET count = vk_jwt_counters.count + 1, updated_at = CURRENT_TIMESTAMP
                    RETURNING count
                    """,
                    jti, ctype,
                )
            else:
                # SQLite
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO vk_jwt_counters (jti, counter_type, count, updated_at)
                    VALUES (?, ?, 0, ?)
                    """,
                    (jti, ctype, datetime.utcnow().isoformat()),
                )
                await conn.execute(
                    """
                    UPDATE vk_jwt_counters
                    SET count = count + 1, updated_at = ?
                    WHERE jti = ? AND counter_type = ?
                    """,
                    (datetime.utcnow().isoformat(), jti, ctype),
                )
                # Read back new count
                cur = await conn.execute(
                    "SELECT count FROM vk_jwt_counters WHERE jti = ? AND counter_type = ?",
                    (jti, ctype),
                )
                row = await cur.fetchone()
                new_count = int(row[0]) if row else 0
        return (new_count <= int(limit)), int(new_count)
    except Exception as e:
        logger.debug(f"DB-backed JWT quota increment failed (falling back to process-local): {e}")
        # Signal to caller to fall back; treat as allowed here
        return True, -1


async def increment_and_check_api_key_quota(
    db_pool: DatabasePool,
    api_key_id: int,
    counter_type: str,
    limit: Optional[int],
    bucket: Optional[str] = None,
) -> Tuple[bool, int]:
    """
    Atomically increment API Key quota counter and compare to limit.
    Returns (allowed, new_count). If limit is None, returns (True, current+1).
    """
    if api_key_id is None or limit is None:
        return True, -1
    try:
        ctype = f"{counter_type}@{bucket}" if bucket else str(counter_type)
        async with db_pool.transaction() as conn:
            await _ensure_tables(conn)
            if hasattr(conn, "fetchval"):
                # Postgres
                new_count = await conn.fetchval(
                    """
                    INSERT INTO vk_api_key_counters (api_key_id, counter_type, count, updated_at)
                    VALUES ($1, $2, 1, CURRENT_TIMESTAMP)
                    ON CONFLICT (api_key_id, counter_type)
                    DO UPDATE SET count = vk_api_key_counters.count + 1, updated_at = CURRENT_TIMESTAMP
                    RETURNING count
                    """,
                    int(api_key_id), ctype,
                )
            else:
                # SQLite
                await conn.execute(
                    """
                    INSERT OR IGNORE INTO vk_api_key_counters (api_key_id, counter_type, count, updated_at)
                    VALUES (?, ?, 0, ?)
                    """,
                    (int(api_key_id), ctype, datetime.utcnow().isoformat()),
                )
                await conn.execute(
                    """
                    UPDATE vk_api_key_counters
                    SET count = count + 1, updated_at = ?
                    WHERE api_key_id = ? AND counter_type = ?
                    """,
                    (datetime.utcnow().isoformat(), int(api_key_id), ctype),
                )
                cur = await conn.execute(
                    "SELECT count FROM vk_api_key_counters WHERE api_key_id = ? AND counter_type = ?",
                    (int(api_key_id), ctype),
                )
                row = await cur.fetchone()
                new_count = int(row[0]) if row else 0
        return (new_count <= int(limit)), int(new_count)
    except Exception as e:
        logger.debug(f"DB-backed API key quota increment failed (falling back to process-local): {e}")
        return True, -1
