"""
Backfill missing or invalid user UUIDs in the AuthNZ users table.

This helper is intended as a one-off maintenance script to ensure that all
rows in the ``users`` table have a valid UUID before tightening schema or
API contracts that assume UUID presence.

Usage:
  # Use existing AUTH_MODE / DATABASE_URL env vars
  python -m Helper_Scripts.AuthNZ.backfill_user_uuids

  # Dry-run (show what would change, without writing)
  python -m Helper_Scripts.AuthNZ.backfill_user_uuids --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
from typing import Any, Dict, Iterable, Tuple
from uuid import UUID, uuid4

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


_ROW_EXTRACTION_ERROR = "Unable to extract id/uuid from row: {row!r}"


def _extract_row(row: Any) -> Tuple[int, Any]:
    """Return (id, uuid_value) from a db row (dict or Row)."""
    try:
        if isinstance(row, dict):
            return int(row.get("id")), row.get("uuid")
        # aiosqlite.Row supports both index and key access
        return int(row["id"]), row["uuid"]
    except Exception as exc:  # pragma: no cover - defensive
        raise RuntimeError(_ROW_EXTRACTION_ERROR.format(row=row)) from exc


def _normalize_existing_uuids(rows: Iterable[Any]) -> Tuple[Dict[int, str | None], set[str]]:
    """Normalize existing uuid cells and return (by_id, valid_uuid_set)."""
    by_id: Dict[int, str | None] = {}
    seen: set[str] = set()

    for row in rows:
        user_id, raw = _extract_row(row)
        value: str | None
        if raw is None:
            value = None
        else:
            try:
                value = str(raw).strip() or None
            except Exception as exc:
                logger.warning(
                    "Unable to normalize existing UUID value for user_id=%s: raw=%r (error=%r)",
                    user_id,
                    raw,
                    exc,
                )
                value = None
        by_id[user_id] = value
        if value:
            try:
                # Only treat parseable UUIDs as valid
                parsed = str(UUID(value))
                seen.add(parsed)
                by_id[user_id] = parsed
            except Exception as exc:
                logger.debug(
                    "Existing UUID value for user_id=%s is not a valid UUID and will be backfilled: value=%r (error=%r)",
                    user_id,
                    value,
                    exc,
                )
                # Leave as-is; will be backfilled
                continue

    return by_id, seen


async def backfill_user_uuids(*, dry_run: bool = False) -> int:
    """
    Backfill missing/invalid UUIDs on the users table.

    Returns the number of rows that would be (or were) updated.
    """
    settings = get_settings()
    pool = await get_db_pool()
    logger.info(
        "AuthNZ UUID backfill: AUTH_MODE=%s DATABASE_URL=%s (dry_run=%s)",
        settings.AUTH_MODE,
        settings.DATABASE_URL,
        dry_run,
    )

    rows = await pool.fetchall("SELECT id, uuid FROM users")
    if not rows:
        logger.info("No users found; nothing to backfill.")
        return 0

    by_id, seen = _normalize_existing_uuids(rows)

    updates: Dict[int, str] = {}
    for user_id, current in by_id.items():
        if current is None:
            # Missing UUID entirely
            new_uuid = str(uuid4())
            while new_uuid in seen:
                new_uuid = str(uuid4())
            seen.add(new_uuid)
            updates[user_id] = new_uuid
        else:
            # Present but may have been invalid; normalize step above already
            # skipped invalid values, so treat them as missing.
            try:
                UUID(current)
            except Exception as exc:
                logger.debug(
                    "Existing UUID for user_id=%s is invalid and will be replaced: value=%r (error=%r)",
                    user_id,
                    current,
                    exc,
                )
                new_uuid = str(uuid4())
                while new_uuid in seen:
                    new_uuid = str(uuid4())
                seen.add(new_uuid)
                updates[user_id] = new_uuid

    if not updates:
        logger.info("All users already have valid UUIDs; nothing to do.")
        return 0

    logger.info("Prepared UUID backfill for %d user(s)", len(updates))

    for user_id, new_uuid in updates.items():
        if dry_run:
            logger.info("DRY-RUN: would set users.id=%s uuid=%s", user_id, new_uuid)
            continue
        await pool.execute(
            "UPDATE users SET uuid = ? WHERE id = ?",
            new_uuid,
            user_id,
        )

    if not dry_run:
        remaining = await pool.fetchval(
            "SELECT COUNT(1) FROM users WHERE uuid IS NULL OR TRIM(uuid) = ''"
        )
        logger.info("UUID backfill complete; remaining rows without UUID: %s", int(remaining or 0))

    return len(updates)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backfill missing/invalid AuthNZ user UUIDs.")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned updates without writing to the database.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    try:
        updated = asyncio.run(backfill_user_uuids(dry_run=bool(args.dry_run)))
    except KeyboardInterrupt:
        logger.warning("UUID backfill interrupted by user.")
        return 1
    except Exception as exc:  # pragma: no cover - CLI surface
        logger.error(f"UUID backfill failed: {exc}")
        return 2

    logger.info("UUID backfill finished (planned/updated rows=%d)", updated)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
