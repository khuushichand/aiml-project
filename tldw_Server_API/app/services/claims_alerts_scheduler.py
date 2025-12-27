"""
Claims alerts scheduler.

Runs periodic evaluation of claims alert rules and dispatches notifications.
Enable via env:
  - CLAIMS_ALERTS_SCHEDULER_ENABLED=true
  - CLAIMS_ALERTS_EVAL_INTERVAL_SEC=300
  - CLAIMS_ALERTS_WINDOW_SEC=3600
  - CLAIMS_ALERTS_BASELINE_SEC=86400
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Callable, List, Optional

from loguru import logger

from tldw_Server_API.app.core.Claims_Extraction.claims_service import (
    evaluate_claims_alerts_for_scheduler,
    send_claims_alert_email_digest_for_scheduler,
)
from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_media_database,
    content_db_settings,
)
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths, get_user_media_db_path
from tldw_Server_API.app.core.Utils.Utils import get_project_root
from tldw_Server_API.app.core.config import settings


def _is_truthy(value: Optional[str]) -> bool:
    return str(value or "").lower() in {"1", "true", "yes", "on"}


def _resolve_user_db_base_dir() -> Path:
    user_db_base = os.getenv("USER_DB_BASE_DIR") or settings.get("USER_DB_BASE_DIR")
    project_root = Path(get_project_root())
    if not user_db_base:
        return project_root / "Databases" / "user_databases"
    base_path = Path(user_db_base).expanduser()
    if not base_path.is_absolute():
        return (project_root / base_path).resolve()
    return base_path.resolve()


def _enumerate_sqlite_user_ids() -> List[int]:
    base = _resolve_user_db_base_dir()
    if not base.exists():
        return []
    user_ids: List[int] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        try:
            user_id = int(entry.name)
        except (TypeError, ValueError):
            logger.debug(f"claims_alerts: skipping non-int user dir {entry.name}")
            continue
        db_path = entry / DatabasePaths.MEDIA_DB_NAME
        if db_path.exists():
            user_ids.append(user_id)
    if not user_ids:
        try:
            user_ids = [DatabasePaths.get_single_user_id()]
        except Exception as exc:
            logger.debug(f"claims_alerts: failed to derive single_user_id: {exc}")
            user_ids = []
    return sorted(set(user_ids))


async def run_claims_alerts_once(
    *,
    evaluator: Optional[Callable[..., dict]] = None,
    window_sec: Optional[int] = None,
    baseline_sec: Optional[int] = None,
) -> int:
    eval_fn = evaluator or evaluate_claims_alerts_for_scheduler
    window_val = int(window_sec or settings.get("CLAIMS_ALERTS_WINDOW_SEC", 3600))
    baseline_val = int(baseline_sec or settings.get("CLAIMS_ALERTS_BASELINE_SEC", 86400))
    processed = 0
    if content_db_settings.backend_type == BackendType.POSTGRESQL:
        try:
            db = create_media_database(client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")))
        except Exception as exc:
            logger.warning(f"claims_alerts: failed to create media db: {exc}")
            return 0
        try:
            try:
                db.initialize_db()
            except Exception:
                pass
            user_ids = db.list_claims_monitoring_user_ids()
            for user_id in user_ids:
                try:
                    await asyncio.to_thread(
                        eval_fn,
                        target_user_id=str(user_id),
                        window_sec=window_val,
                        baseline_sec=baseline_val,
                        db=db,
                    )
                    await send_claims_alert_email_digest_for_scheduler(
                        target_user_id=str(user_id),
                        db=db,
                    )
                    processed += 1
                except Exception as exc:
                    logger.warning(f"claims_alerts: evaluation failed for user {user_id}: {exc}")
        finally:
            try:
                db.close_connection()
            except Exception:
                pass
    else:
        user_ids = _enumerate_sqlite_user_ids()
        for user_id in user_ids:
            try:
                user_db = create_media_database(
                    client_id=str(settings.get("SERVER_CLIENT_ID", "SERVER_API_V1")),
                    db_path=get_user_media_db_path(int(user_id)),
                )
            except Exception as exc:
                logger.debug(f"claims_alerts: failed to open user db {user_id}: {exc}")
                continue
            try:
                try:
                    user_db.initialize_db()
                except Exception:
                    pass
                await asyncio.to_thread(
                    eval_fn,
                    target_user_id=str(user_id),
                    window_sec=window_val,
                    baseline_sec=baseline_val,
                    db=user_db,
                )
                await send_claims_alert_email_digest_for_scheduler(
                    target_user_id=str(user_id),
                    db=user_db,
                )
                processed += 1
            except Exception as exc:
                logger.warning(f"claims_alerts: evaluation failed for user {user_id}: {exc}")
            finally:
                try:
                    user_db.close_connection()
                except Exception:
                    pass
    return processed


async def start_claims_alerts_scheduler() -> Optional[asyncio.Task]:
    enabled = _is_truthy(os.getenv("CLAIMS_ALERTS_SCHEDULER_ENABLED")) or bool(
        settings.get("CLAIMS_ALERTS_SCHEDULER_ENABLED", False)
    )
    if not enabled:
        logger.info("Claims alerts scheduler disabled (CLAIMS_ALERTS_SCHEDULER_ENABLED != true)")
        return None
    try:
        interval = int(os.getenv("CLAIMS_ALERTS_EVAL_INTERVAL_SEC") or settings.get("CLAIMS_ALERTS_EVAL_INTERVAL_SEC", 300))
    except Exception:
        interval = 300

    async def _runner() -> None:
        await asyncio.sleep(min(5, interval))
        while True:
            try:
                await run_claims_alerts_once()
            except Exception as exc:
                logger.warning(f"Claims alerts scheduler loop error: {exc}")
            await asyncio.sleep(interval)

    task = asyncio.create_task(_runner(), name="claims_alerts_scheduler")
    logger.info(f"Claims alerts scheduler started (interval={interval}s)")
    return task
