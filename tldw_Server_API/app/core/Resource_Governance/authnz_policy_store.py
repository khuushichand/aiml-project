from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from sqlite3 import Error as SQLiteError
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import DatabasePool, get_db_pool

_STORE_NONCRITICAL_EXCEPTIONS = (
    ConnectionError,
    OSError,
    RuntimeError,
    SQLiteError,
    TimeoutError,
    TypeError,
    ValueError,
)
_ROW_PARSE_EXCEPTIONS = (
    AttributeError,
    IndexError,
    KeyError,
    TypeError,
    UnicodeError,
    ValueError,
)


class AuthNZPolicyStore:
    """
    Read-only PolicyStore backed by the AuthNZ database.

    Expects a table `rg_policies(id TEXT PRIMARY KEY, payload JSON/JSONB or TEXT, version INT, updated_at TIMESTAMP)`
    as documented in the PRD. If the table is missing, returns an empty policy set.
    """

    def __init__(self, pool: DatabasePool | None = None):
        """Initialize the policy store.

        Args:
            pool: Optional DatabasePool to use (for testing/DI). If not provided,
                  the global `get_db_pool()` is used on each call.
        """
        self._pool: DatabasePool | None = pool

    async def get_latest_policy(self) -> tuple[int, dict[str, Any], dict[str, Any], float] | tuple[int, dict[str, Any], dict[str, Any], dict[str, Any], float]:
        try:
            pool = self._pool or await get_db_pool()
        except _STORE_NONCRITICAL_EXCEPTIONS as e:
            logger.warning("AuthNZPolicyStore: failed to get DB pool: {}", e)
            # Fallback to empty snapshot with current time
            return 1, {}, {}, time.time()

        try:
            rows = await pool.fetchall(
                "SELECT id, payload, version, updated_at FROM rg_policies ORDER BY updated_at DESC"
            )
        except _STORE_NONCRITICAL_EXCEPTIONS as e:
            # Table may not exist yet; return empty
            logger.debug("AuthNZPolicyStore: rg_policies fetch failed (likely missing table): {}", e)
            return 1, {}, {}, time.time()

        policies: dict[str, Any] = {}
        tenant: dict[str, Any] = {}
        route_map: dict[str, Any] = {}
        max_version = 1
        latest_updated: float = 0.0

        for r in rows:
            try:
                rid = r["id"] if isinstance(r, dict) else r[0]
                raw_payload = r["payload"] if isinstance(r, dict) else r[1]
                ver = int(r["version"] if isinstance(r, dict) else r[2] or 1)
                updated = r["updated_at"] if isinstance(r, dict) else r[3]

                if isinstance(raw_payload, (bytes, bytearray)):
                    raw_payload = raw_payload.decode("utf-8", errors="ignore")
                if isinstance(raw_payload, str):
                    try:
                        payload = json.loads(raw_payload)
                    except (TypeError, ValueError, json.JSONDecodeError):
                        payload = {}
                else:
                    payload = dict(raw_payload) if isinstance(raw_payload, dict) else {}

                # Update max version
                if ver > max_version:
                    max_version = ver

                # Track latest updated time (epoch seconds)
                try:
                    if isinstance(updated, (int, float)):
                        ts = float(updated)
                    elif isinstance(updated, datetime):
                        ts = updated.replace(tzinfo=timezone.utc).timestamp()
                    elif isinstance(updated, str):
                        # Try ISO8601
                        ts = datetime.fromisoformat(updated.replace("Z", "+00:00")).timestamp()
                    else:
                        ts = time.time()
                except (OverflowError, TypeError, ValueError):
                    ts = time.time()
                latest_updated = max(latest_updated, ts)

                # Recognize tenant config rows by id
                rid_str = str(rid or "").strip().lower()
                if rid_str in {"tenant", "rg.tenant", "__tenant__"}:
                    if isinstance(payload, dict):
                        tenant = payload
                    continue
                # Recognize route_map row when present
                if rid_str in {"route_map", "rg.route_map", "__route_map__"}:
                    if isinstance(payload, dict):
                        route_map = payload
                    continue

                # Otherwise, treat as policy payload keyed by id
                if rid:
                    policies[str(rid)] = payload or {}
            except _ROW_PARSE_EXCEPTIONS as row_err:
                logger.debug("AuthNZPolicyStore: skipping row due to error: {}", row_err)
                continue

        if not latest_updated:
            latest_updated = time.time()
        # Backwards-compatible return: include route_map only when present
        if route_map:
            return max_version, policies, tenant, route_map, latest_updated
        return max_version, policies, tenant, latest_updated
