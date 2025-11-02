"""
Chatbooks Prompt Studio JobManager Adapter (scaffold).

Feature-gated integration path for routing Chatbooks jobs through
Prompt Studio's JobManager. Enable with env var CHATBOOKS_JOBS_BACKEND=prompt_studio
or module default TLDW_JOBS_BACKEND=prompt_studio. Legacy flag TLDW_USE_PROMPT_STUDIO_QUEUE
is still recognized but deprecated.

This is an initial adapter with minimal surface for migration.
"""

from typing import Optional, Dict, Any
from loguru import logger

try:
    from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
    from tldw_Server_API.app.core.Prompt_Management.prompt_studio.job_manager import (
        JobManager,
        JobType,
        JobStatus as PSJobStatus,
    )
except Exception as e:  # pragma: no cover - optional import
    PromptStudioDatabase = None  # type: ignore
    JobManager = None  # type: ignore
    JobType = None  # type: ignore
    PSJobStatus = None  # type: ignore
    logger.debug(f"PS Job adapter imports unavailable: {e}")


class ChatbooksPSJobAdapter:
    """Lightweight adapter into Prompt Studio JobManager for Chatbooks jobs."""

    def __init__(self):
        if PromptStudioDatabase is None or JobManager is None:
            raise RuntimeError("Prompt Studio JobManager is not available")
        self._db = PromptStudioDatabase()
        self._jm = JobManager(self._db)

    def create_export_job(self, payload: Dict[str, Any], *, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Create a PS job representing a chatbook export."""
        try:
            if request_id:
                payload = {**payload, "request_id": request_id}
            job = self._jm.create_job(JobType.GENERATION, entity_id=0, payload=payload)
            return job
        except Exception as e:
            logger.warning(f"Failed to create PS export job: {e}")
            return None

    def create_import_job(self, payload: Dict[str, Any], *, request_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        try:
            if request_id:
                payload = {**payload, "request_id": request_id}
            job = self._jm.create_job(JobType.GENERATION, entity_id=0, payload=payload)
            return job
        except Exception as e:
            logger.warning(f"Failed to create PS import job: {e}")
            return None

    def cancel(self, job_id: int) -> bool:
        try:
            return self._jm.cancel_job(job_id)
        except Exception as e:
            logger.warning(f"Failed to cancel PS job {job_id}: {e}")
            return False

    def get(self, job_id: int) -> Optional[Dict[str, Any]]:
        """Fetch a PS job by id."""
        try:
            job = self._jm.get_job(job_id)
            return job
        except Exception as e:
            logger.warning(f"Failed to fetch PS job {job_id}: {e}")
            return None

    def update_status(
        self,
        job_id: int,
        status: str,
        error_message: Optional[str] = None,
        result: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Update the PS job status using Chatbooks status strings.

        Chatbooks statuses: pending|in_progress|completed|failed|cancelled|expired
        Map to Prompt Studio: queued|processing|completed|failed|cancelled
        """
        if self._jm is None or PSJobStatus is None:
            return False

        status_map = {
            "pending": PSJobStatus.QUEUED,
            "queued": PSJobStatus.QUEUED,
            "in_progress": PSJobStatus.PROCESSING,
            "processing": PSJobStatus.PROCESSING,
            "completed": PSJobStatus.COMPLETED,
            "failed": PSJobStatus.FAILED,
            "cancelled": PSJobStatus.CANCELLED,
            "expired": PSJobStatus.CANCELLED,  # closest terminal equivalent
        }
        ps_status = status_map.get(str(status).lower())
        if ps_status is None:
            logger.warning(f"Unknown status mapping for PS adapter: {status}")
            return False
        try:
            return bool(self._jm.update_job_status(int(job_id), ps_status, error_message=error_message, result=result))
        except Exception as e:
            logger.warning(f"Failed to update PS job {job_id} to {ps_status}: {e}")
            return False
