"""
Reading import Jobs worker.

Consumes core Jobs entries for reading list imports and delegates to
`handle_reading_import_job`.
"""

from __future__ import annotations

import asyncio
import os

from loguru import logger

from tldw_Server_API.app.core.Collections.reading_import_jobs import (
    READING_IMPORT_DOMAIN,
    reading_import_queue,
    handle_reading_import_job,
)
from tldw_Server_API.app.core.Jobs.manager import JobManager
from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK


async def main() -> None:
    worker_id = (os.getenv("READING_IMPORT_JOBS_WORKER_ID") or f"reading-import-{os.getpid()}").strip()
    queue = reading_import_queue()
    cfg = WorkerConfig(
        domain=READING_IMPORT_DOMAIN,
        queue=queue,
        worker_id=worker_id,
    )
    jm = JobManager()
    sdk = WorkerSDK(jm, cfg)
    logger.info(f"Reading import worker starting: queue={queue} worker_id={worker_id}")
    try:
        await sdk.run(handler=handle_reading_import_job)
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(f"Reading import worker crashed: queue={queue} worker_id={worker_id}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
