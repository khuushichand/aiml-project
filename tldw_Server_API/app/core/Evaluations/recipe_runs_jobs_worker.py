"""Worker entrypoints for queued evaluation recipe runs."""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.evaluation_schemas_unified import RunStatus
from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    ABTestArm,
    ABTestChunking,
    ABTestQuery,
    ABTestRetrieval,
    EmbeddingsABTestConfig,
)
from tldw_Server_API.app.core.DB_Management.DB_Manager import get_content_backend_instance
from tldw_Server_API.app.core.DB_Management.Evaluations_DB import EvaluationsDatabase
from tldw_Server_API.app.core.DB_Management.db_path_utils import (
    DatabasePaths,
    get_user_media_db_path,
)
from tldw_Server_API.app.core.DB_Management.media_db.api import create_media_database
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import run_abtest_full
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


def _build_media_db(user_id: str) -> Any:
    backend = get_content_backend_instance()
    db_path = get_user_media_db_path(user_id)
    return create_media_database(
        client_id=f"recipe_runs_jobs_worker:{user_id}",
        db_path=db_path,
        backend=backend,
    )


def _parse_json_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return list(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, list):
            return list(parsed)
    return []


def _resolve_embeddings_dataset(record: Any, db: EvaluationsDatabase, user_id: str | None) -> list[dict[str, Any]]:
    inline_dataset = record.metadata.get("inline_dataset")
    if isinstance(inline_dataset, list):
        return [dict(sample) for sample in inline_dataset]

    dataset_id = record.metadata.get("dataset_id")
    if not dataset_id:
        raise ValueError("Embeddings recipe run requires inline_dataset or dataset_id metadata.")
    dataset_row = db.get_dataset(str(dataset_id), created_by=user_id or None)
    if not dataset_row:
        raise ValueError(f"Dataset '{dataset_id}' was not found for embeddings recipe execution.")
    samples = dataset_row.get("samples") or []
    return [dict(sample) for sample in samples]


def _resolve_candidate_provider_model(candidate: dict[str, Any]) -> tuple[str, str]:
    provider = str(candidate.get("provider") or "").strip()
    model = str(candidate.get("model") or "").strip()
    if provider and model:
        return provider, model
    if ":" in model:
        inferred_provider, inferred_model = model.split(":", 1)
        return inferred_provider.strip(), inferred_model.strip()
    raise ValueError("Embeddings recipe candidates must include provider and model.")


def _coerce_media_ids(run_config: dict[str, Any], dataset: list[dict[str, Any]]) -> list[int]:
    explicit_media_ids = run_config.get("media_ids")
    if isinstance(explicit_media_ids, list) and explicit_media_ids:
        return [int(media_id) for media_id in explicit_media_ids]

    derived_media_ids: set[int] = set()
    for sample in dataset:
        for expected_id in sample.get("expected_ids") or []:
            try:
                derived_media_ids.add(int(expected_id))
            except (TypeError, ValueError):
                continue
    if derived_media_ids:
        return sorted(derived_media_ids)
    raise ValueError(
        "Embeddings recipe execution requires run_config.media_ids or labeled expected_ids to derive the corpus."
    )


def _build_embeddings_abtest_config(record: Any, dataset: list[dict[str, Any]]) -> EmbeddingsABTestConfig:
    run_config = dict(record.metadata.get("run_config") or {})
    candidates = run_config.get("candidates") or []
    if not isinstance(candidates, list) or not candidates:
        raise ValueError("Embeddings recipe run_config.candidates must be populated before execution.")

    comparison_mode = str(run_config.get("comparison_mode") or "embedding_only").strip()
    search_mode = "hybrid" if comparison_mode == "retrieval_stack" else "vector"
    top_k = int(run_config.get("top_k") or 10)
    hybrid_alpha = run_config.get("hybrid_alpha")
    media_ids = _coerce_media_ids(run_config, dataset)

    arms = []
    for candidate in candidates:
        provider, model = _resolve_candidate_provider_model(dict(candidate))
        arms.append(
            ABTestArm(
                provider=provider,
                model=model,
                dimensions=candidate.get("dimensions"),
            )
        )

    queries = []
    for sample in dataset:
        queries.append(
            ABTestQuery(
                text=str(sample.get("input") or ""),
                expected_ids=[
                    int(expected_id)
                    for expected_id in (sample.get("expected_ids") or [])
                ] or None,
                metadata={
                    "query_id": str(sample.get("query_id") or ""),
                },
            )
        )

    return EmbeddingsABTestConfig(
        arms=arms,
        media_ids=media_ids,
        chunking=ABTestChunking(method="sentences", size=200, overlap=20, language=None),
        retrieval=ABTestRetrieval(
            k=top_k,
            search_mode=search_mode,
            hybrid_alpha=float(hybrid_alpha) if hybrid_alpha is not None else None,
        ),
        queries=queries,
        metric_level="media",
        reuse_existing=True,
    )


def _collect_embeddings_candidate_results(
    *,
    db: EvaluationsDatabase,
    test_id: str,
    user_id: str | None,
    record: Any,
) -> list[dict[str, Any]]:
    arms = db.get_abtest_arms(test_id, created_by=user_id or None)
    query_rows = db.get_abtest_queries(test_id, created_by=user_id or None)
    results_rows, _ = db.list_abtest_results(test_id, limit=1000, offset=0, created_by=user_id or None)
    abtest_row = db.get_abtest(test_id, created_by=user_id or None) or {}

    stats_payload = abtest_row.get("stats_json")
    if isinstance(stats_payload, str):
        try:
            stats_payload = json.loads(stats_payload)
        except json.JSONDecodeError:
            stats_payload = {}
    if not isinstance(stats_payload, dict):
        stats_payload = {}
    aggregates = stats_payload.get("aggregates") or {}

    query_lookup: dict[str, dict[str, Any]] = {}
    for row in query_rows:
        metadata_payload = row.get("metadata_json")
        if isinstance(metadata_payload, str):
            try:
                metadata_payload = json.loads(metadata_payload)
            except json.JSONDecodeError:
                metadata_payload = {}
        if not isinstance(metadata_payload, dict):
            metadata_payload = {}
        query_lookup[str(row.get("query_id") or "")] = {
            "expected_ids": [str(value) for value in _parse_json_list(row.get("ground_truth_ids"))],
            "query_id": str(metadata_payload.get("query_id") or row.get("query_id") or ""),
        }

    candidate_configs = list((record.metadata.get("run_config") or {}).get("candidates") or [])
    results_by_arm: dict[str, list[dict[str, Any]]] = {}
    for row in results_rows:
        results_by_arm.setdefault(str(row.get("arm_id") or ""), []).append(dict(row))

    candidate_results: list[dict[str, Any]] = []
    for index, arm in enumerate(arms):
        arm_id = str(arm.get("arm_id") or "")
        candidate_cfg = dict(candidate_configs[index]) if index < len(candidate_configs) else {}
        query_results = []
        for row in results_by_arm.get(arm_id, []):
            metrics_payload = row.get("metrics_json")
            if isinstance(metrics_payload, str):
                try:
                    metrics_payload = json.loads(metrics_payload)
                except json.JSONDecodeError:
                    metrics_payload = {}
            query_id = str(row.get("query_id") or "")
            query_results.append(
                {
                    "query_id": query_lookup.get(query_id, {}).get("query_id") or query_id,
                    "ranked_ids": [str(value) for value in _parse_json_list(row.get("ranked_ids"))],
                    "expected_ids": query_lookup.get(query_id, {}).get("expected_ids") or [],
                    "metrics": metrics_payload or {},
                    "latency_ms": row.get("latency_ms"),
                }
            )
        candidate_results.append(
            {
                "candidate_id": arm_id,
                "candidate_run_id": arm_id,
                "model": arm.get("model_id"),
                "provider": arm.get("provider"),
                "is_local": candidate_cfg.get("is_local"),
                "cost_usd": candidate_cfg.get("cost_usd"),
                "metrics": aggregates.get(arm_id) or {},
                "query_results": query_results,
            }
        )
    return candidate_results


def _execute_embeddings_recipe_run(
    *,
    record: Any,
    db: EvaluationsDatabase,
    user_id: str | None,
    service: RecipeRunsService | Any,
) -> dict[str, Any]:
    del service
    resolved_user_id = str(user_id or "")
    dataset = _resolve_embeddings_dataset(record, db, user_id)
    config = _build_embeddings_abtest_config(record, dataset)
    test_id = db.create_abtest(
        name=f"recipe-{record.run_id}",
        config=config.model_dump(),
        created_by=resolved_user_id or None,
    )
    for idx, arm in enumerate(config.arms):
        db.upsert_abtest_arm(
            test_id=test_id,
            arm_index=idx,
            provider=arm.provider,
            model_id=arm.model,
            dimensions=arm.dimensions,
            status="pending",
        )
    db.insert_abtest_queries(test_id, [query.model_dump() for query in config.queries])

    media_db = _build_media_db(resolved_user_id)
    asyncio.run(run_abtest_full(db, config, test_id, resolved_user_id, media_db))
    candidate_results = _collect_embeddings_candidate_results(
        db=db,
        test_id=test_id,
        user_id=resolved_user_id or None,
        record=record,
    )
    child_run_ids = [
        str(candidate_result.get("candidate_run_id") or candidate_result.get("candidate_id") or "")
        for candidate_result in candidate_results
        if str(candidate_result.get("candidate_run_id") or candidate_result.get("candidate_id") or "").strip()
    ]
    recipe_report_inputs = {
        "dataset_mode": record.metadata.get("dataset_mode"),
        "review_sample": record.metadata.get("review_sample") or {
            "required": False,
            "sample_size": 0,
            "sample_query_ids": [],
        },
        "candidate_results": candidate_results,
    }
    return {
        "child_run_ids": child_run_ids,
        "metadata": {
            "abtest": {"test_id": test_id},
            "candidate_results": candidate_results,
            "recipe_report_inputs": recipe_report_inputs,
        },
    }


def _execute_recipe_run(
    *,
    record: Any,
    db: EvaluationsDatabase,
    user_id: str | None,
    service: RecipeRunsService | Any,
) -> dict[str, Any] | None:
    if record.recipe_id == "embeddings_model_selection" and not record.metadata.get("candidate_results"):
        return _execute_embeddings_recipe_run(
            record=record,
            db=db,
            user_id=user_id,
            service=service,
        )
    return None


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
        execution_artifacts = _execute_recipe_run(
            record=record,
            db=db,
            user_id=resolved_user_id,
            service=service,
        )
        if execution_artifacts:
            merged_metadata = dict(service.get_run(run_id).metadata)
            merged_metadata.update(execution_artifacts.get("metadata") or {})
            db.update_recipe_run(
                run_id,
                metadata=merged_metadata,
            )
            child_run_ids = execution_artifacts.get("child_run_ids") or []
            if child_run_ids:
                db.set_recipe_run_children(run_id, list(child_run_ids))
        report = service.get_report(run_id)
        completed_metadata = dict(report.run.metadata)
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
        failed_metadata = dict(service.get_run(run_id).metadata)
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
