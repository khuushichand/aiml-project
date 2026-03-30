from __future__ import annotations

import asyncio
import contextlib
import json
import os
from typing import Any

from loguru import logger

from tldw_Server_API.app.core.Evaluations.recipe_runs_service import (
    RECIPE_ID,
    get_recipe_runs_service_for_user,
)
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK


RECIPE_RUN_JOB_DOMAIN = "evaluations"
RECIPE_RUN_JOB_TYPE = "rag_retrieval_tuning_run"


class RecipeRunJobError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, backoff_seconds: int | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        if backoff_seconds is not None:
            self.backoff_seconds = backoff_seconds


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_payload(raw: Any) -> dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


async def handle_recipe_run_job(job: dict[str, Any]) -> dict[str, Any]:
    job_type = str(job.get("job_type") or "").strip().lower()
    if job_type not in {RECIPE_RUN_JOB_TYPE, "recipe_run"}:
        raise RecipeRunJobError(f"Unsupported recipe run job type: {job.get('job_type')}", retryable=False)

    payload = _normalize_payload(job.get("payload"))
    run_id = payload.get("run_id") or payload.get("recipe_run_id")
    if not run_id:
        raise RecipeRunJobError("Missing run_id in job payload", retryable=False)
    recipe_id = payload.get("recipe_id") or RECIPE_ID
    if recipe_id != RECIPE_ID:
        raise RecipeRunJobError(f"Unsupported recipe_id: {recipe_id}", retryable=False)

    job_id = job.get("uuid") or job.get("id")
    owner = job.get("owner_user_id") or payload.get("user_id")
    user_id = str(owner) if owner is not None else "1"
    service = get_recipe_runs_service_for_user(user_id)
    job_logger = logger.bind(run_id=str(run_id), job_id=str(job_id) if job_id is not None else None, user_id=user_id)
    job_logger.info("Recipe run job starting")

    run_config = payload.get("run_config") or {}
    service.db.update_run_status(str(run_id), "running")
    try:
        report = await service.execute_recipe_run(
            run_id=str(run_id),
            recipe_id=str(recipe_id),
            run_config=run_config,
            created_by=user_id,
        )
        child_run_ids = list(report.get("child_run_ids") or [])
        service.db.update_run_progress(
            str(run_id),
            {
                "child_run_ids": child_run_ids,
                "review_state": report.get("review_state"),
                "confidence": report.get("confidence"),
            },
        )
        service.db.store_run_results(
            str(run_id),
            report,
            usage={"child_run_ids": child_run_ids, "recipe_id": recipe_id},
        )
        job_logger.info("Recipe run job completed")
        return {"run_id": str(run_id), "recipe_id": recipe_id, "status": "completed", "report": report}
    except Exception as exc:
        retryable = bool(getattr(exc, "retryable", True))
        backoff_seconds = getattr(exc, "backoff_seconds", None)
        with contextlib.suppress(Exception):
            service.db.update_run_status(str(run_id), "failed", str(exc))
        job_logger.warning(f"Recipe run job failed: {exc} (retryable={retryable})")
        raise RecipeRunJobError(str(exc), retryable=retryable, backoff_seconds=backoff_seconds) from exc


async def run_recipe_runs_jobs_worker(stop_event: asyncio.Event | None = None) -> None:
    worker_id = (os.getenv("EVALUATIONS_JOBS_WORKER_ID") or f"evals-recipe-jobs-{os.getpid()}").strip()
    queue = (os.getenv("EVALUATIONS_JOBS_QUEUE") or os.getenv("EVALS_JOBS_QUEUE") or "default").strip() or "default"

    cfg = WorkerConfig(
        domain=RECIPE_RUN_JOB_DOMAIN,
        queue=queue,
        worker_id=worker_id,
        lease_seconds=_coerce_int(os.getenv("EVALUATIONS_JOBS_LEASE_SECONDS"), 60),
        renew_jitter_seconds=_coerce_int(os.getenv("EVALUATIONS_JOBS_RENEW_JITTER_SECONDS"), 5),
        renew_threshold_seconds=_coerce_int(os.getenv("EVALUATIONS_JOBS_RENEW_THRESHOLD_SECONDS"), 10),
        backoff_base_seconds=_coerce_int(os.getenv("EVALUATIONS_JOBS_BACKOFF_BASE_SECONDS"), 2),
        backoff_max_seconds=_coerce_int(os.getenv("EVALUATIONS_JOBS_BACKOFF_MAX_SECONDS"), 30),
        retry_on_exception=True,
        retry_backoff_seconds=_coerce_int(os.getenv("EVALUATIONS_JOBS_RETRY_BACKOFF_SECONDS"), 10),
    )

    from tldw_Server_API.app.core.Jobs.manager import JobManager

    jm = JobManager()
    sdk = WorkerSDK(jm, cfg)
    logger.info(f"Recipe run Jobs worker starting (queue={queue}, worker_id={worker_id})")
    watcher = None
    if stop_event is not None:

        async def _watch_stop() -> None:
            await stop_event.wait()
            sdk.stop()

        watcher = asyncio.create_task(_watch_stop())

    try:
        await sdk.run(handler=handle_recipe_run_job)
    finally:
        if watcher is not None:
            watcher.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await watcher


if __name__ == "__main__":  # pragma: no cover - manual worker entry point
    asyncio.run(run_recipe_runs_jobs_worker())
