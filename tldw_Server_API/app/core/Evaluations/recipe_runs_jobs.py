"""Jobs helpers for evaluation recipe runs."""

from __future__ import annotations

import os
from typing import Any

from tldw_Server_API.app.api.v1.schemas.evaluation_recipe_schemas import RecipeRunRecord
from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.core.Jobs.manager import JobManager


RECIPE_RUN_JOB_DOMAIN = "evaluations"
RECIPE_RUN_JOB_TYPE = "recipe_run"


def recipe_run_queue() -> str:
    """Return the queue used for evaluation recipe run jobs."""
    return (os.getenv("EVALUATIONS_RECIPE_RUN_JOBS_QUEUE") or "default").strip() or "default"


def build_recipe_run_job_payload(
    *,
    run_id: str,
    recipe_id: str,
    owner_user_id: str | None = None,
) -> dict[str, Any]:
    """Build the queued Jobs payload for one recipe run."""
    return {
        "run_id": str(run_id).strip(),
        "recipe_id": str(recipe_id).strip(),
        "owner_user_id": str(owner_user_id).strip() if owner_user_id is not None else None,
    }


def parse_recipe_run_job_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a recipe-run Jobs payload."""
    run_id = str(payload.get("run_id") or "").strip()
    recipe_id = str(payload.get("recipe_id") or "").strip()
    owner_user_id = payload.get("owner_user_id")
    owner_user_id = str(owner_user_id).strip() if owner_user_id is not None else None
    if not run_id:
        raise ValueError("missing_run_id")
    if not recipe_id:
        raise ValueError("missing_recipe_id")
    return {
        "run_id": run_id,
        "recipe_id": recipe_id,
        "owner_user_id": owner_user_id or None,
    }


def build_recipe_run_idempotency_key(*, run_id: str) -> str:
    """Build the Jobs idempotency key for one recipe run."""
    return f"recipe-run:{str(run_id).strip()}"


def enqueue_recipe_run(
    run: RecipeRunRecord | dict[str, Any],
    *,
    owner_user_id: str | None = None,
    job_manager: JobManager | None = None,
) -> str:
    """Enqueue one recipe run into Jobs and return the job id."""
    jobs = job_manager or JobManager()
    if hasattr(run, "model_dump"):
        payload = run.model_dump(mode="json")
    else:
        payload = dict(run)
    resolved_owner_user_id = owner_user_id
    if resolved_owner_user_id is None:
        metadata = payload.get("metadata") or {}
        resolved_owner_user_id = metadata.get("owner_user_id")
    job = jobs.create_job(
        domain=RECIPE_RUN_JOB_DOMAIN,
        queue=recipe_run_queue(),
        job_type=RECIPE_RUN_JOB_TYPE,
        payload=build_recipe_run_job_payload(
            run_id=str(payload["run_id"]),
            recipe_id=str(payload["recipe_id"]),
            owner_user_id=resolved_owner_user_id,
        ),
        owner_user_id=str(resolved_owner_user_id) if resolved_owner_user_id else None,
        idempotency_key=build_recipe_run_idempotency_key(run_id=str(payload["run_id"])),
    )
    return str(job.get("id"))


def mark_recipe_run_enqueue_failure(
    service: Any,
    record: RecipeRunRecord | dict[str, Any],
    *,
    error: str,
) -> None:
    """Persist a terminal enqueue failure so runs do not remain stranded in pending."""
    db = getattr(service, "db", None)
    if db is None or not hasattr(db, "update_recipe_run"):
        return
    payload = record.model_dump(mode="json") if hasattr(record, "model_dump") else dict(record)
    metadata = dict(payload.get("metadata") or {})
    metadata["jobs"] = {
        "worker_state": "enqueue_failed",
        "error": str(error),
    }
    db.update_recipe_run(
        str(payload["run_id"]),
        status=RunStatus.FAILED,
        metadata=metadata,
    )


__all__ = [
    "RECIPE_RUN_JOB_DOMAIN",
    "RECIPE_RUN_JOB_TYPE",
    "build_recipe_run_idempotency_key",
    "build_recipe_run_job_payload",
    "enqueue_recipe_run",
    "mark_recipe_run_enqueue_failure",
    "parse_recipe_run_job_payload",
    "recipe_run_queue",
]
