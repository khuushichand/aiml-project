"""Worker entrypoints for queued evaluation recipe runs."""

from __future__ import annotations

import asyncio
import os
from typing import Any

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.Evaluations.recipe_runs_jobs import (
    RECIPE_RUN_JOB_DOMAIN,
    parse_recipe_run_job_payload,
    recipe_run_queue,
)
from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RecipeRunsService,
    get_recipe_runs_service_for_user,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK
from tldw_Server_API.app.core.testing import env_flag_enabled


def _get_db(*, user_id: str | None) -> EvaluationsDatabase:
    db_path = os.getenv("EVALUATIONS_TEST_DB_PATH")
    if not db_path:
        db_path = str(DatabasePaths.get_evaluations_db_path(user_id))
    return EvaluationsDatabase(db_path)


def _get_service(*, user_id: str | None, db: EvaluationsDatabase | None = None) -> RecipeRunsService:
    if db is not None:
        return RecipeRunsService(db=db, user_id=user_id)
    return get_recipe_runs_service_for_user(user_id)


def handle_recipe_run_job(
    job: dict[str, Any],
    *,
    db: EvaluationsDatabase | None = None,
    user_id: str | None = None,
    service: RecipeRunsService | Any | None = None,
) -> dict[str, Any]:
    """Execute one queued recipe run and persist a normalized report shell."""
    payload = parse_recipe_run_job_payload(job.get("payload") or {})
    resolved_user_id = user_id or payload.get("owner_user_id")
    db = db or _get_db(user_id=resolved_user_id)
    service = service or _get_service(user_id=resolved_user_id, db=db)
    run_id = payload["run_id"]
    job_id = str(job.get("id")) if job.get("id") is not None else None

    record = service.get_run(run_id)
    if record.status is RunStatus.COMPLETED:
        return {
            "status": "completed",
            "run_id": run_id,
            "job_id": job_id,
            "recipe_id": record.recipe_id,
            "reused": True,
        }

    running_metadata = dict(record.metadata)
    running_metadata["jobs"] = {
        "job_id": job_id,
        "worker_state": "running",
    }
    db.update_recipe_run(
        run_id,
        status=RunStatus.RUNNING,
        metadata=running_metadata,
    )

    try:
        report = service.get_report(run_id)
        completed_metadata = dict(record.metadata)
        completed_metadata["jobs"] = {
            "job_id": job_id,
            "worker_state": "completed",
        }
        db.update_recipe_run(
            run_id,
            status=RunStatus.COMPLETED,
            confidence_summary=report.confidence_summary,
            recommendation_slots=report.recommendation_slots,
            metadata=completed_metadata,
        )
    except Exception as exc:
        failed_metadata = dict(record.metadata)
        failed_metadata["jobs"] = {
            "job_id": job_id,
            "worker_state": "failed",
            "error": str(exc),
        }
        db.update_recipe_run(
            run_id,
            status=RunStatus.FAILED,
            metadata=failed_metadata,
        )
        raise

    logger.info("Recipe run job completed: run_id={} job_id={}", run_id, job_id)
    return {
        "status": "completed",
        "run_id": run_id,
        "job_id": job_id,
        "recipe_id": payload["recipe_id"],
        "reused": False,
    }


async def handle_recipe_run_job_async(job: dict[str, Any]) -> dict[str, Any]:
    """Async WorkerSDK adapter for the synchronous recipe run handler."""
    return await asyncio.to_thread(handle_recipe_run_job, job)


async def run_recipe_run_jobs_worker() -> None:
    """Run the WorkerSDK loop for recipe-run Jobs."""
    worker_id = (os.getenv("EVALUATIONS_RECIPE_RUN_JOBS_WORKER_ID") or f"recipe-run-{os.getpid()}").strip()
    cfg = WorkerConfig(
        domain=RECIPE_RUN_JOB_DOMAIN,
        queue=recipe_run_queue(),
        worker_id=worker_id,
    )
    jm = JobManager()
    sdk = WorkerSDK(jm, cfg)
    logger.info("Recipe run Jobs worker starting: queue={} worker_id={}", cfg.queue, worker_id)
    await sdk.run(handler=handle_recipe_run_job_async)


def recipe_run_jobs_worker_enabled() -> bool:
    """Return True when the recipe-run Jobs worker is explicitly enabled."""
    return env_flag_enabled("EVALUATIONS_RECIPE_RUN_JOBS_WORKER_ENABLED") or env_flag_enabled(
        "EVALS_RECIPE_RUN_JOBS_WORKER_ENABLED"
    )


async def start_recipe_run_jobs_worker() -> asyncio.Task[None]:
    """Start the recipe-run worker as a background task."""
    if not recipe_run_jobs_worker_enabled():
        return None
    return asyncio.create_task(
        run_recipe_run_jobs_worker(),
        name="recipe_run_jobs_worker",
    )


__all__ = [
    "handle_recipe_run_job",
    "handle_recipe_run_job_async",
    "recipe_run_jobs_worker_enabled",
    "run_recipe_run_jobs_worker",
    "start_recipe_run_jobs_worker",
]
