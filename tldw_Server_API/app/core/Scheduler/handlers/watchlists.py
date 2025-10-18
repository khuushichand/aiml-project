"""
Scheduler task handler for Watchlists runs.

Task name: 'watchlist_run'
Inputs expected in payload:
  payload = {
    'inputs': { 'watchlist_job_id': <int> },
    'user_id': '<user id>',
    'tenant_id': 'default' | str
  }

The handler creates a scrape_run row, performs a minimal fetch→ingest stub
and then updates run status and job history (last_run_at/next_run_at). When the
real scraping is implemented, this stub can be replaced with the actual pipeline.
"""

from __future__ import annotations

from typing import Any, Dict
from datetime import datetime, timezone
from loguru import logger

from tldw_Server_API.app.core.Scheduler.base.registry import task
from tldw_Server_API.app.core.DB_Management.Watchlists_DB import WatchlistsDatabase


def _utcnow_iso() -> str:
    return datetime.utcnow().replace(tzinfo=timezone.utc).isoformat()


def _compute_next_run(cron: str | None, timezone_str: str | None) -> str | None:
    if not cron:
        return None
    try:
        from apscheduler.triggers.cron import CronTrigger
        tz = (timezone_str or "UTC")
        trigger = CronTrigger.from_crontab(cron, timezone=tz)
        now = datetime.now(trigger.timezone)
        nxt = trigger.get_next_fire_time(None, now)
        return nxt.isoformat() if nxt else None
    except Exception:
        return None


@task(name="watchlist_run", max_retries=0, timeout=3600, queue="watchlists")
async def watchlist_run(payload: Dict[str, Any]) -> Dict[str, Any]:
    inputs = payload.get("inputs") or {}
    if not isinstance(inputs, dict):
        raise ValueError("watchlist_run: inputs must be a dict")
    job_id = inputs.get("watchlist_job_id")
    if not job_id:
        raise ValueError("watchlist_run: missing watchlist_job_id")
    user_id = payload.get("user_id")
    if user_id is None:
        raise ValueError("watchlist_run: missing user_id")
    try:
        uid_int = int(user_id)
    except Exception:
        raise ValueError("watchlist_run: user_id must be int-like")

    db = WatchlistsDatabase.for_user(uid_int)
    # Ensure job exists
    job = db.get_job(int(job_id))

    # Create run and set running
    run = db.create_run(job_id=int(job_id), status="running")

    # Minimal stub: no network; simulate zero items processed
    items_found = 0
    items_ingested = 0
    stats = {"items_found": items_found, "items_ingested": items_ingested}

    # Mark run complete
    db.update_run(
        run.id,
        status="succeeded",
        finished_at=_utcnow_iso(),
        stats_json=__import__("json").dumps(stats),
    )

    # Update job history
    next_run = _compute_next_run(job.schedule_expr, job.schedule_timezone)
    db.set_job_history(job_id=int(job_id), last_run_at=_utcnow_iso(), next_run_at=next_run)

    return {"run_id": run.id, "status": "succeeded", "items_ingested": items_ingested}

