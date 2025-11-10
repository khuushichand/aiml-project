from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from typing import Any, Dict, Tuple, Optional

from loguru import logger

from tldw_Server_API.app.core.AuthNZ.database import get_db_pool, DatabasePool


class AuthNZPolicyStore:
    """
    Read-only PolicyStore backed by the AuthNZ database.

    Expects a table `rg_policies(id TEXT PRIMARY KEY, payload JSON/JSONB or TEXT, version INT, updated_at TIMESTAMP)`
    as documented in the PRD. If the table is missing, returns an empty policy set.
    """

    def __init__(self, pool: Optional[DatabasePool] = None):
        """Initialize the policy store.

        Args:
            pool: Optional DatabasePool to use (for testing/DI). If not provided,
                  the global `get_db_pool()` is used on each call.
        """
        self._pool: Optional[DatabasePool] = pool

    async def get_latest_policy(self) -> Tuple[int, Dict[str, Any], Dict[str, Any], float]:
        try:
            pool = self._pool or await get_db_pool()
        except Exception as e:
            logger.warning("AuthNZPolicyStore: failed to get DB pool: {}", e)
            # Fallback to empty snapshot with current time
            return 1, {}, {}, time.time()

        try:
            rows = await pool.fetchall(
                "SELECT id, payload, version, updated_at FROM rg_policies ORDER BY updated_at DESC"
            )
        except Exception as e:
            # Table may not exist yet; return empty
            logger.debug("AuthNZPolicyStore: rg_policies fetch failed (likely missing table): {}", e)
            return 1, {}, {}, time.time()

        policies: Dict[str, Any] = {}
        tenant: Dict[str, Any] = {}
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
                    except Exception:
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
                except Exception:
                    ts = time.time()
                latest_updated = max(latest_updated, ts)

                # Recognize tenant config rows by id
                rid_str = str(rid or "").strip().lower()
                if rid_str in {"tenant", "rg.tenant", "__tenant__"}:
                    if isinstance(payload, dict):
                        tenant = payload
                    continue

                # Otherwise, treat as policy payload keyed by id
                if rid:
                    policies[str(rid)] = payload or {}
            except Exception as row_err:
                logger.debug("AuthNZPolicyStore: skipping row due to error: {}", row_err)
                continue

        if not latest_updated:
            latest_updated = time.time()
        return max_version, policies, tenant, latest_updated
