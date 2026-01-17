"""
Embeddings A/B test Jobs worker (Phase 2):

- Consumes core Jobs entries for embeddings A/B tests.
- Executes the A/B test pipeline via embeddings_abtest_service.
- Updates Jobs status/result via the core JobManager.

Job contract (domain/queue/job_type):
- domain = "evaluations"
- queue = os.getenv("EVALUATIONS_JOBS_QUEUE", "default")
- job_type = "embeddings_abtest_run" | "embeddings_abtest_cleanup"

Payload fields:
- test_id: str (required)
- config: dict (optional; falls back to stored config_json)
- user_id: str|int (optional; owner_user_id preferred)
- request_id, trace_id (optional)

Usage:
  python -m tldw_Server_API.app.core.Evaluations.embeddings_abtest_jobs_worker
"""

from __future__ import annotations

import asyncio
import json
import os
from typing import Any, Dict, Optional, Tuple

from loguru import logger

from tldw_Server_API.app.api.v1.schemas.embeddings_abtest_schemas import (
    ABTestChunking,
    EmbeddingsABTestConfig,
)
from tldw_Server_API.app.core.DB_Management.DB_Manager import (
    create_media_database,
    get_content_backend_instance,
)
from tldw_Server_API.app.core.DB_Management.db_path_utils import (
    DatabasePaths,
    get_user_media_db_path,
)
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_jobs import (
    ABTEST_JOBS_CLEANUP_TYPE,
    ABTEST_JOBS_DOMAIN,
    ABTEST_JOBS_JOB_TYPE,
    abtest_jobs_manager,
    abtest_jobs_queue,
)
from tldw_Server_API.app.core.Evaluations.embeddings_abtest_service import (
    cleanup_abtest_resources,
    run_abtest_full,
)
from tldw_Server_API.app.core.Evaluations.unified_evaluation_service import (
    get_unified_evaluation_service_for_user,
)
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerSDK, WorkerConfig


class EmbeddingsABTestJobError(RuntimeError):
    def __init__(self, message: str, *, retryable: bool = False, backoff_seconds: Optional[int] = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        if backoff_seconds is not None:
            self.backoff_seconds = backoff_seconds


def _coerce_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _normalize_user_id(value: Any) -> Tuple[str, int]:
    if value is None or str(value).strip() == "":
        uid = DatabasePaths.get_single_user_id()
        return str(uid), int(uid)
    try:
        uid_int = int(value)
    except (TypeError, ValueError):
        uid_int = int(DatabasePaths.get_single_user_id())
    return str(value), uid_int


def _normalize_payload(raw: Any) -> Dict[str, Any]:
    if isinstance(raw, dict):
        return dict(raw)
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _load_config_from_payload(payload: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    cfg = payload.get("config")
    if cfg is None:
        return None
    if isinstance(cfg, str):
        try:
            parsed = json.loads(cfg)
        except json.JSONDecodeError:
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(cfg, dict):
        return cfg
    return None


def _load_config_from_db(db, test_id: str) -> Dict[str, Any]:
    row = db.get_abtest(test_id)
    if not row:
        raise EmbeddingsABTestJobError(f"A/B test not found: {test_id}", retryable=False)
    raw = row.get("config_json")
    if raw is None:
        raise EmbeddingsABTestJobError(f"A/B test config missing for {test_id}", retryable=False)
    if isinstance(raw, dict):
        return raw
    try:
        parsed = json.loads(raw)
    except Exception as exc:
        raise EmbeddingsABTestJobError(f"Failed to parse A/B config for {test_id}: {exc}", retryable=False)
    if not isinstance(parsed, dict):
        raise EmbeddingsABTestJobError(f"A/B config is not a dict for {test_id}", retryable=False)
    return parsed


def _normalize_config(cfg: Dict[str, Any]) -> EmbeddingsABTestConfig:
    try:
        if hasattr(EmbeddingsABTestConfig, "model_validate"):
            config = EmbeddingsABTestConfig.model_validate(cfg)  # type: ignore[attr-defined]
        else:
            config = EmbeddingsABTestConfig.parse_obj(cfg)  # type: ignore[attr-defined]
    except Exception as exc:
        raise EmbeddingsABTestJobError(f"Invalid A/B config payload: {exc}", retryable=False)

    if getattr(config, "chunking", None) is None:
        config.chunking = ABTestChunking(method="sentences", size=200, overlap=20, language=None)
    return config


def _build_media_db(user_id: str) -> Any:
    backend = get_content_backend_instance()
    db_path = get_user_media_db_path(user_id)
    return create_media_database(
        client_id=f"emb_abtest_jobs_worker:{user_id}",
        db_path=db_path,
        backend=backend,
    )


async def handle_abtest_job(job: Dict[str, Any]) -> Dict[str, Any]:
    job_type = str(job.get("job_type") or "").strip().lower()
    if job_type not in {ABTEST_JOBS_JOB_TYPE, ABTEST_JOBS_CLEANUP_TYPE}:
        raise EmbeddingsABTestJobError(
            f"Unsupported embeddings A/B job type: {job.get('job_type')}",
            retryable=False,
        )

    payload = _normalize_payload(job.get("payload"))
    test_id = payload.get("test_id") or payload.get("abtest_id")
    if not test_id:
        raise EmbeddingsABTestJobError("Missing test_id in job payload", retryable=False)

    owner = job.get("owner_user_id") or payload.get("user_id")
    user_id_str, user_id_int = _normalize_user_id(owner)

    svc = get_unified_evaluation_service_for_user(user_id_int)
    if job_type == ABTEST_JOBS_CLEANUP_TYPE:
        cleanup_abtest_resources(
            svc.db,
            user_id_str,
            str(test_id),
            delete_db=True,
            delete_idempotency=True,
        )
        return {"test_id": str(test_id), "cleanup": True}

    config_payload = _load_config_from_payload(payload)
    if config_payload is None:
        config_payload = _load_config_from_db(svc.db, str(test_id))
    config = _normalize_config(config_payload)

    media_db = _build_media_db(user_id_str)
    await run_abtest_full(svc.db, config, str(test_id), user_id_str, media_db)
    return {"test_id": str(test_id), "cleanup": False}


async def run_embeddings_abtest_jobs_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    worker_id = (os.getenv("EVALUATIONS_JOBS_WORKER_ID") or f"evals-abtest-jobs-{os.getpid()}").strip()
    queue = abtest_jobs_queue()

    cfg = WorkerConfig(
        domain=ABTEST_JOBS_DOMAIN,
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

    jm = abtest_jobs_manager()
    sdk = WorkerSDK(jm, cfg)
    logger.info(f"Embeddings A/B Jobs worker starting (queue={queue}, worker_id={worker_id})")
    watcher = None
    if stop_event is not None:
        async def _watch_stop() -> None:
            await stop_event.wait()
            sdk.stop()
        watcher = asyncio.create_task(_watch_stop())
    try:
        await sdk.run(handler=handle_abtest_job)
    finally:
        if watcher is not None:
            try:
                watcher.cancel()
            except Exception:
                pass


if __name__ == "__main__":
    asyncio.run(run_embeddings_abtest_jobs_worker())
