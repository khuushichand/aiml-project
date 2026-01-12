from __future__ import annotations

import os
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


ABTEST_JOBS_DOMAIN = "evaluations"
ABTEST_JOBS_JOB_TYPE = "embeddings_abtest_run"


def abtest_jobs_queue() -> str:
    queue = (
        os.getenv("EVALUATIONS_JOBS_QUEUE")
        or os.getenv("EVALS_JOBS_QUEUE")
        or "default"
    ).strip()
    return queue or "default"


def abtest_jobs_manager() -> JobManager:
    db_url = (os.getenv("JOBS_DB_URL") or "").strip()
    if not db_url:
        return JobManager()
    backend = "postgres" if db_url.startswith("postgres") else None
    return JobManager(backend=backend, db_url=db_url)


def abtest_jobs_idempotency_key(test_id: str, idempotency_key: Optional[str]) -> Optional[str]:
    if not idempotency_key:
        return None
    base = str(idempotency_key).strip()
    if not base:
        return None
    return f"{test_id}:{base}"
