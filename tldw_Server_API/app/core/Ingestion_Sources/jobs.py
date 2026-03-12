from __future__ import annotations

import os
from typing import Any

from tldw_Server_API.app.core.Jobs.manager import JobManager

DOMAIN = "ingestion_sources"
JOB_TYPE_SYNC = "sync"


def ingestion_sources_queue() -> str:
    queue = (os.getenv("INGESTION_SOURCES_JOBS_QUEUE") or "default").strip()
    return queue or "default"


def enqueue_ingestion_source_job(
    *,
    user_id: int | str,
    source_id: int,
    job_type: str = JOB_TYPE_SYNC,
    idempotency_key: str | None = None,
    payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    jm = JobManager()
    base_payload = {
        "source_id": int(source_id),
        "user_id": str(user_id),
    }
    if payload:
        base_payload.update(payload)
    return jm.create_job(
        domain=DOMAIN,
        queue=ingestion_sources_queue(),
        job_type=str(job_type or JOB_TYPE_SYNC),
        payload=base_payload,
        owner_user_id=str(user_id),
        idempotency_key=idempotency_key,
        max_retries=0,
    )
