from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings
from tldw_Server_API.app.core.AuthNZ.user_provider_secrets import (
    decrypt_byok_payload,
    dumps_envelope,
    encrypt_byok_payload,
    loads_envelope,
)


@dataclass
class RotationStats:
    processed: int = 0
    updated: int = 0
    skipped: int = 0
    failed: int = 0

    def add(self, other: RotationStats) -> None:
        self.processed += other.processed
        self.updated += other.updated
        self.skipped += other.skipped
        self.failed += other.failed


@dataclass
class RotationSummary:
    tables: dict[str, RotationStats]
    total: RotationStats
    dry_run: bool = False


def _is_postgres_pool(pool: DatabasePool) -> bool:
    """Return backend type from DatabasePool state."""
    return getattr(pool, "pool", None) is not None


def _extract_row_fields(row: Any) -> tuple[int, str | None]:
    if isinstance(row, dict):
        return int(row.get("id")), row.get("encrypted_blob")
    return int(row["id"]), row["encrypted_blob"]


async def _fetch_rows(
    conn: Any,
    *,
    table: str,
    last_id: int,
    batch_size: int,
    is_postgres: bool,
) -> list[Any]:
    if is_postgres:
        query = f"""
            SELECT id, encrypted_blob
            FROM {table}
            WHERE id > $1
            ORDER BY id
            LIMIT $2
        """
        return await conn.fetch(query, last_id, batch_size)

    query = f"""
        SELECT id, encrypted_blob
        FROM {table}
        WHERE id > ?
        ORDER BY id
        LIMIT ?
    """
    cursor = await conn.execute(query, last_id, batch_size)
    return list(await cursor.fetchall())


async def _apply_updates(
    conn: Any,
    *,
    table: str,
    updates: Iterable[tuple[str, int]],
    is_postgres: bool,
) -> None:
    if is_postgres:
        query = f"UPDATE {table} SET encrypted_blob = $1 WHERE id = $2"
    else:
        query = f"UPDATE {table} SET encrypted_blob = ? WHERE id = ?"

    if hasattr(conn, "executemany"):
        await conn.executemany(query, list(updates))
        return

    for params in updates:
        await conn.execute(query, *params)


async def _rotate_table(
    *,
    pool: DatabasePool,
    table: str,
    batch_size: int,
    dry_run: bool,
    is_postgres: bool,
) -> RotationStats:
    stats = RotationStats()
    last_id = 0

    while True:
        async with pool.transaction() as conn:
            rows = await _fetch_rows(
                conn,
                table=table,
                last_id=last_id,
                batch_size=batch_size,
                is_postgres=is_postgres,
            )
            if not rows:
                break

            updates: list[tuple[str, int]] = []
            max_id = last_id
            for row in rows:
                row_id, encrypted_blob = _extract_row_fields(row)
                max_id = max(max_id, row_id)
                stats.processed += 1

                if not encrypted_blob:
                    stats.skipped += 1
                    continue

                try:
                    payload = decrypt_byok_payload(loads_envelope(encrypted_blob))
                    updated_blob = dumps_envelope(encrypt_byok_payload(payload))
                except Exception as exc:
                    stats.failed += 1
                    logger.warning(
                        "BYOK rotation failed for table={} id={}: {}",
                        table,
                        row_id,
                        exc,
                    )
                    continue

                updates.append((updated_blob, row_id))

            if updates:
                stats.updated += len(updates)
                if not dry_run:
                    await _apply_updates(
                        conn,
                        table=table,
                        updates=updates,
                        is_postgres=is_postgres,
                    )

            last_id = max_id

    return stats


async def rotate_byok_secrets(
    *,
    dry_run: bool = False,
    batch_size: int = 500,
    pool: DatabasePool | None = None,
) -> RotationSummary:
    settings = get_settings()
    if not settings.BYOK_ENCRYPTION_KEY:
        raise ValueError("BYOK_ENCRYPTION_KEY is not configured")
    if not settings.BYOK_SECONDARY_ENCRYPTION_KEY:
        logger.warning(
            "BYOK_SECONDARY_ENCRYPTION_KEY is not set; rotation will only succeed for rows "
            "already encrypted with the primary key"
        )

    db_pool = pool or await get_db_pool()
    is_postgres = _is_postgres_pool(db_pool)

    tables = {}
    total = RotationStats()
    for table in ("user_provider_secrets", "org_provider_secrets"):
        stats = await _rotate_table(
            pool=db_pool,
            table=table,
            batch_size=batch_size,
            dry_run=dry_run,
            is_postgres=is_postgres,
        )
        tables[table] = stats
        total.add(stats)

    return RotationSummary(tables=tables, total=total, dry_run=dry_run)
