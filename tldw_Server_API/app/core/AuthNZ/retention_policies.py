from __future__ import annotations

from typing import Any, Dict

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool
from tldw_Server_API.app.core.AuthNZ.settings import get_settings


RETENTION_POLICIES: Dict[str, Dict[str, Any]] = {
    "audit_logs": {
        "attr": "AUDIT_LOG_RETENTION_DAYS",
        "min": 30,
        "max": 3650,
        "description": "AuthNZ audit log retention",
    },
    "usage_logs": {
        "attr": "USAGE_LOG_RETENTION_DAYS",
        "min": 1,
        "max": 3650,
        "description": "Usage log retention",
    },
    "llm_usage_logs": {
        "attr": "LLM_USAGE_LOG_RETENTION_DAYS",
        "min": 1,
        "max": 3650,
        "description": "LLM usage log retention",
    },
    "usage_daily": {
        "attr": "USAGE_DAILY_RETENTION_DAYS",
        "min": 1,
        "max": 3650,
        "description": "Daily usage aggregates retention",
    },
    "llm_usage_daily": {
        "attr": "LLM_USAGE_DAILY_RETENTION_DAYS",
        "min": 1,
        "max": 3650,
        "description": "Daily LLM usage aggregates retention",
    },
    "sessions": {
        "attr": "SESSION_LOG_RETENTION_DAYS",
        "min": 7,
        "max": 3650,
        "description": "Session log retention",
    },
    "privilege_snapshots": {
        "attr": "PRIVILEGE_SNAPSHOT_RETENTION_DAYS",
        "min": 7,
        "max": 3650,
        "description": "Privilege snapshot retention",
    },
    "privilege_snapshots_weekly": {
        "attr": "PRIVILEGE_SNAPSHOT_WEEKLY_RETENTION_DAYS",
        "min": 30,
        "max": 3650,
        "description": "Weekly privilege snapshot retention",
    },
}


async def _fetch_retention_overrides(db_pool: DatabasePool) -> Dict[str, int]:
    rows = await db_pool.fetch(
        "SELECT policy_key, days FROM retention_policy_overrides"
    )
    overrides: Dict[str, int] = {}
    for row in rows:
        try:
            key = row["policy_key"]
            days = row["days"]
        except Exception:
            if isinstance(row, (list, tuple)) and len(row) >= 2:
                key, days = row[0], row[1]
            else:
                continue
        if key is None or days is None:
            continue
        overrides[str(key)] = int(days)
    return overrides


async def fetch_retention_overrides() -> Dict[str, int]:
    """Return persisted retention overrides keyed by policy_key."""
    try:
        db_pool = await get_db_pool()
        return await _fetch_retention_overrides(db_pool)
    except Exception as exc:
        logger.warning(f"Retention overrides load failed: {exc}")
        return {}


async def apply_retention_overrides(settings=None) -> Dict[str, int]:
    """Apply persisted retention overrides to the provided settings object."""
    overrides = await fetch_retention_overrides()
    if not overrides:
        return {}
    settings_obj = settings or get_settings()
    for key, value in overrides.items():
        meta = RETENTION_POLICIES.get(key)
        if not meta:
            logger.debug(f"Skipping unknown retention override key: {key}")
            continue
        setattr(settings_obj, meta["attr"], int(value))
    return overrides


async def upsert_retention_override(policy_key: str, days: int) -> None:
    """Persist a retention override for the given policy key."""
    db_pool = await get_db_pool()
    if getattr(db_pool, "pool", None) is not None:
        await db_pool.execute(
            """
            INSERT INTO retention_policy_overrides (policy_key, days, updated_at)
            VALUES ($1, $2, CURRENT_TIMESTAMP)
            ON CONFLICT (policy_key)
            DO UPDATE SET days = EXCLUDED.days, updated_at = CURRENT_TIMESTAMP
            """,
            policy_key,
            int(days),
        )
    else:
        await db_pool.execute(
            """
            INSERT INTO retention_policy_overrides (policy_key, days, updated_at)
            VALUES (?, ?, CURRENT_TIMESTAMP)
            ON CONFLICT(policy_key)
            DO UPDATE SET days = excluded.days, updated_at = CURRENT_TIMESTAMP
            """,
            policy_key,
            int(days),
        )
