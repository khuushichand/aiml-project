from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import uuid4

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.PrivilegeMaps import (
    PrivilegeMapService,
    PrivilegeSnapshotStore,
    get_privilege_map_service,
    get_privilege_snapshot_store,
)
from tldw_Server_API.app.api.v1.schemas.privileges import PrivilegeSnapshotSummary


async def process_snapshot_job(
    *,
    payload: Dict[str, Any],
    service: Optional[PrivilegeMapService] = None,
    store: Optional[PrivilegeSnapshotStore] = None,
) -> str:
    """Generate and persist a privilege snapshot based on job payload."""
    service = service or get_privilege_map_service()
    store = store or get_privilege_snapshot_store()

    snapshot_id = payload.get("snapshot_id") or f"snap-{uuid4()}"
    target_scope = payload.get("target_scope")
    if target_scope not in {"org", "team", "user"}:
        raise ValueError(f"Unsupported snapshot scope: {target_scope}")

    org_id = payload.get("org_id")
    team_id = payload.get("team_id")
    user_ids = payload.get("user_ids") or []
    catalog_version = payload.get("catalog_version") or service.catalog.version
    requested_by = str(payload.get("requested_by") or "system")

    if target_scope == "team" and not team_id:
        raise ValueError("team_id required for team scope snapshot job")
    if target_scope == "org" and not org_id:
        logger.debug("Privilege snapshot job missing org_id; proceeding with global org scope.")
    if target_scope == "user" and not user_ids:
        raise ValueError("user scope snapshot job requires at least one user_id")

    summary_data, snapshot_users = await service.build_snapshot_summary(
        target_scope=target_scope,
        org_id=org_id,
        team_id=team_id,
        user_ids=user_ids,
    )
    detail_items = service.build_snapshot_detail(
        snapshot_users,
        restrict_to_team=team_id if target_scope == "team" else None,
    )
    summary_model = PrivilegeSnapshotSummary(**summary_data)
    generated_at = datetime.now(timezone.utc)

    await store.add_snapshot(
        {
            "snapshot_id": snapshot_id,
            "generated_at": generated_at,
            "generated_by": requested_by,
            "target_scope": target_scope,
            "org_id": org_id,
            "team_id": team_id,
            "catalog_version": catalog_version,
            "summary": summary_model.dict(),
        },
        detail_items=detail_items,
    )
    return snapshot_id


async def run_privilege_snapshot_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """Continuously process queued privilege snapshot jobs."""
    logger.info("Starting privilege snapshot worker loop")
    poll_interval = float(os.getenv("PRIVILEGE_SNAPSHOT_POLL_SECONDS", "1.0") or "1.0")
    lease_seconds = int(os.getenv("PRIVILEGE_SNAPSHOT_LEASE_SECONDS", "60") or "60")
    worker_id = f"priv-snap-worker-{uuid4()}"
    job_manager = JobManager()

    while True:
        if stop_event and stop_event.is_set():
            logger.info("Privilege snapshot worker shutting down on stop signal")
            return
        try:
            job = job_manager.acquire_next_job(
                domain="privilege_maps",
                queue="default",
                lease_seconds=lease_seconds,
                worker_id=worker_id,
            )
        except Exception as exc:
            logger.error("Failed to acquire privilege snapshot job: %s", exc)
            await asyncio.sleep(poll_interval)
            continue

        if not job:
            await asyncio.sleep(poll_interval)
            continue

        job_id = int(job.get("id"))
        lease_id = str(job.get("lease_id"))
        payload = job.get("payload") or {}
        try:
            snapshot_id = await process_snapshot_job(payload=payload)
            job_manager.complete_job(
                job_id,
                result={"snapshot_id": snapshot_id},
                worker_id=worker_id,
                lease_id=lease_id,
                completion_token=lease_id,
            )
            logger.info("Completed privilege snapshot job %s -> %s", job_id, snapshot_id)
        except Exception as exc:
            logger.exception("Privilege snapshot job %s failed: %s", job_id, exc)
            job_manager.fail_job(
                job_id,
                error=str(exc),
                retryable=False,
                worker_id=worker_id,
                lease_id=lease_id,
                completion_token=lease_id,
            )
