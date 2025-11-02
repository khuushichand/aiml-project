"""
Personalization Consolidation Service (scaffold)

Periodic job to embed recent events, update topic profiles, and distill memories.
This is a placeholder; real implementation will integrate embeddings and DB.
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Optional

from loguru import logger
from collections import Counter
from pathlib import Path

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Personalization_DB import PersonalizationDB
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.Metrics import get_metrics_registry


@dataclass
class ConsolidationConfig:
    interval_seconds: int = 1800  # default 30 minutes


class PersonalizationConsolidationService:
    def __init__(self, config: Optional[ConsolidationConfig] = None):
        self.config = config or ConsolidationConfig()
        self._task: Optional[asyncio.Task] = None
        self._shutdown = asyncio.Event()
        # In-memory status map of last consolidation tick per user (ISO timestamp)
        self._last_tick: dict[str, str] = {}

    async def start(self) -> Optional[asyncio.Task]:
        if self._task and not self._task.done():
            return self._task
        self._task = asyncio.create_task(self._run_loop(), name="personalization_consolidation_loop")
        logger.info("Personalization consolidation service started (scaffold)")
        return self._task

    async def stop(self) -> None:
        self._shutdown.set()
        if self._task:
            try:
                await self._task
            except Exception as e:
                logger.debug(f"Personalization consolidation stop wait failed: {e}")
                try:
                    get_metrics_registry().increment(
                        "app_warning_events_total",
                        labels={"component": "personalization", "event": "stop_wait_failed"},
                    )
                except Exception:
                    logger.debug("metrics increment failed for personalization stop_wait_failed")
        logger.info("Personalization consolidation service stopped (scaffold)")

    async def trigger_consolidation(self, user_id: Optional[str] = None) -> bool:
        """One-off consolidation for a user (scaffold: logs only)."""
        try:
            if not user_id:
                user_id = str(settings.get("SINGLE_USER_FIXED_ID", "1"))
            self._consolidate_user(user_id)
            # record last tick
            try:
                from datetime import datetime, timezone
                self._last_tick[str(user_id)] = datetime.now(timezone.utc).isoformat()
            except Exception:
                pass
            return True
        except Exception as e:
            logger.debug(f"Consolidation trigger failed: {e}")
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "personalization", "event": "trigger_failed"},
                )
            except Exception:
                logger.debug("metrics increment failed for personalization trigger_failed")
            return False

    async def _run_loop(self):
        while not self._shutdown.is_set():
            try:
                logger.debug("Consolidation tick (scaffold)")
                # Single-user default; multi-user enumeration can be added later
                uid = str(settings.get("SINGLE_USER_FIXED_ID", "1"))
                self._consolidate_user(uid)
                # Update last tick map
                try:
                    from datetime import datetime, timezone
                    self._last_tick[uid] = datetime.now(timezone.utc).isoformat()
                except Exception:
                    pass
            except Exception as e:
                logger.warning(f"Consolidation loop error (scaffold): {e}")
                try:
                    get_metrics_registry().increment(
                        "app_exception_events_total",
                        labels={"component": "personalization", "event": "loop_error"},
                    )
                except Exception:
                    logger.debug("metrics increment failed for personalization loop_error")
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=self.config.interval_seconds)
            except asyncio.TimeoutError:
                continue


_singleton: Optional[PersonalizationConsolidationService] = None


def get_consolidation_service() -> PersonalizationConsolidationService:
    global _singleton
    if _singleton is None:
        _singleton = PersonalizationConsolidationService()
    return _singleton



def _iter_recent_events(db: PersonalizationDB, user_id: str, window: int = 500) -> list[dict]:
    """Return recent usage events (scaffold: last N by timestamp)."""
    # SQLite simple query
    conn = db._connect()
    try:
        cur = conn.execute(
            "SELECT id, timestamp, type, resource_id, tags FROM usage_events WHERE user_id = ? ORDER BY timestamp DESC LIMIT ?",
            (str(user_id), int(window)),
        )
        rows = cur.fetchall()
        out = []
        import json as _json
        for r in rows:
            tags = None
            try:
                tags = _json.loads(r["tags"]) if r["tags"] else None
            except Exception:
                tags = None
            out.append({
                "id": r["id"],
                "timestamp": r["timestamp"],
                "type": r["type"],
                "resource_id": r["resource_id"],
                "tags": tags or [],
            })
        return out
    finally:
        conn.close()


def _score_topics_from_events(events: list[dict]) -> dict[str, float]:
    tags = []
    for e in events:
        tags.extend([t for t in (e.get("tags") or []) if isinstance(t, str)])
    c = Counter(tags)
    if not c:
        return {}
    maxc = max(c.values()) or 1
    return {k: v / maxc for k, v in c.items()}


def _get_user_personalization_db(user_id: str) -> PersonalizationDB:
    path = DatabasePaths.get_personalization_db_path(int(user_id))
    return PersonalizationDB(str(path))


def PersonalizationConsolidationService__consolidate_user(self, user_id: str) -> None:  # type: ignore
    """Internal: consolidate per-user topics (scaffold)."""
    db = _get_user_personalization_db(user_id)
    events = _iter_recent_events(db, user_id)
    scores = _score_topics_from_events(events)
    for label, score in scores.items():
        try:
            db.upsert_topic(user_id, label, score)
        except Exception:
            try:
                get_metrics_registry().increment(
                    "app_warning_events_total",
                    labels={"component": "personalization", "event": "upsert_topic_failed"},
                )
            except Exception:
                logger.debug("metrics increment failed for personalization upsert_topic_failed")

    # Mark completion time for status
    try:
        from datetime import datetime, timezone
        self._last_tick[str(user_id)] = datetime.now(timezone.utc).isoformat()
    except Exception:
        pass


def _service_status(self) -> dict:
    """Return service status including last consolidation ticks (in-memory)."""
    running = bool(self._task and not self._task.done())
    # copy map to avoid mutation races
    last = dict(self._last_tick)
    return {"running": running, "last_ticks": last}

# Bind helper for status
setattr(PersonalizationConsolidationService, "get_status", _service_status)


# Bind method dynamically to avoid circular imports at top
setattr(PersonalizationConsolidationService, "_consolidate_user", PersonalizationConsolidationService__consolidate_user)
