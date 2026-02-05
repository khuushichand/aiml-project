"""
TTS history retention cleanup service.

Runs periodic cleanup based on:
  - TTS_HISTORY_RETENTION_DAYS
  - TTS_HISTORY_MAX_ROWS_PER_USER
  - TTS_HISTORY_PURGE_INTERVAL_HOURS
"""
from __future__ import annotations

import asyncio
import os
from collections.abc import Iterable

from loguru import logger

from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import MediaDatabase
from tldw_Server_API.app.core.Metrics import get_metrics_registry


def _enumerate_user_ids_from_fs() -> list[str]:
    try:
        base = DatabasePaths.get_user_db_base_dir()
    except Exception as exc:
        logger.debug(f"tts_history_cleanup: failed to resolve user db base dir: {exc}")
        return []
    uids: list[str] = []
    try:
        for p in base.iterdir():
            if p.is_dir():
                try:
                    int(p.name)
                    uids.append(p.name)
                except (TypeError, ValueError):
                    logger.debug(f"tts_history_cleanup: skipping non-int user dir {p.name}")
    except Exception as exc:
        logger.debug(f"tts_history_cleanup: failed to list user dirs: {exc}")
    if not uids:
        try:
            uids = [str(DatabasePaths.get_single_user_id())]
        except Exception as exc:
            logger.debug(f"tts_history_cleanup: single_user_id fallback failed: {exc}")
            uids = []
    return sorted(set(uids))


def _purge_with_db(db: MediaDatabase, user_ids: Iterable[str], retention_days: int, max_rows: int) -> int:
    removed_total = 0
    for uid in user_ids:
        try:
            removed = db.purge_tts_history_for_user(
                user_id=str(uid),
                retention_days=retention_days,
                max_rows=max_rows,
            )
            removed_total += removed
        except Exception as exc:
            logger.debug(f"tts_history_cleanup: purge failed for user {uid}: {exc}")
    return removed_total


async def run_tts_history_cleanup_loop(stop_event: asyncio.Event | None = None) -> None:
    interval_hours_raw = os.getenv("TTS_HISTORY_PURGE_INTERVAL_HOURS", "24")
    retention_days_raw = os.getenv("TTS_HISTORY_RETENTION_DAYS", "90")
    max_rows_raw = os.getenv("TTS_HISTORY_MAX_ROWS_PER_USER", "10000")

    try:
        interval_hours = int(str(interval_hours_raw).strip())
    except Exception:
        interval_hours = 24
    try:
        retention_days = int(str(retention_days_raw).strip())
    except Exception:
        retention_days = 90
    try:
        max_rows = int(str(max_rows_raw).strip())
    except Exception:
        max_rows = 10000

    if interval_hours <= 0 or (retention_days <= 0 and max_rows <= 0):
        logger.info("TTS history cleanup disabled by settings")
        return

    interval_sec = max(60, interval_hours * 3600)
    await asyncio.sleep(min(interval_sec, 60))

    while True:
        if stop_event is not None and stop_event.is_set():
            break
        removed_total = 0
        try:
            probe_db = MediaDatabase(
                db_path=str(DatabasePaths.get_media_db_path(DatabasePaths.get_single_user_id())),
                client_id="tts_history_cleanup",
            )
            if probe_db.backend_type.name.lower() == "postgresql":
                user_ids = probe_db.list_tts_history_user_ids()
                removed_total = _purge_with_db(probe_db, user_ids, retention_days, max_rows)
            else:
                probe_db.close_connection()
                user_ids = _enumerate_user_ids_from_fs()
                for uid in user_ids:
                    db_path = DatabasePaths.get_media_db_path(uid)
                    db = MediaDatabase(db_path=str(db_path), client_id="tts_history_cleanup")
                    try:
                        removed_total += db.purge_tts_history_for_user(
                            user_id=str(uid),
                            retention_days=retention_days,
                            max_rows=max_rows,
                        )
                    finally:
                        db.close_connection()
                probe_db = None
            if removed_total:
                logger.info(f"TTS history cleanup removed={removed_total}")
        except Exception as exc:
            logger.debug(f"TTS history cleanup loop failed: {exc}")
            try:
                get_metrics_registry().increment(
                    "app_exception_events_total",
                    labels={"component": "tts_history_cleanup", "event": "cleanup_failed"},
                )
            except Exception:
                logger.debug("metrics increment failed for tts_history_cleanup")
        finally:
            try:
                if "probe_db" in locals() and probe_db is not None:
                    probe_db.close_connection()
            except Exception:
                pass

        if stop_event is not None:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=interval_sec)
            except asyncio.TimeoutError:
                pass
        else:
            await asyncio.sleep(interval_sec)
