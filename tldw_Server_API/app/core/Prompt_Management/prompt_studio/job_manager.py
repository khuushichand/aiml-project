# job_manager.py
# Job queue management for Prompt Studio

import json
import asyncio
import time
from typing import List, Dict, Any, Optional, Callable
from enum import Enum
from uuid import uuid4
from loguru import logger

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import (
    PromptStudioDatabase, DatabaseError
)
from tldw_Server_API.app.core.Prompt_Management.prompt_studio.monitoring import (
    prompt_studio_metrics,
)
import os

########################################################################################################################
# Job Types and Status

class JobType(str, Enum):
    EVALUATION = "evaluation"
    OPTIMIZATION = "optimization"
    GENERATION = "generation"

class JobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

########################################################################################################################
# Job Manager

class JobManager:
    """Manages job queue for Prompt Studio background operations."""

    def __init__(self, db: PromptStudioDatabase, *, worker_id: Optional[str] = None):
        """
        Initialize JobManager.

        Args:
            db: PromptStudioDatabase instance
        """
        self.db = db
        self.client_id = db.client_id
        self.worker_id = self._normalise_worker_id(worker_id)
        self._job_handlers: Dict[JobType, Callable] = {}
        self._is_processing = False
        self._processing_task = None
        self._metrics = prompt_studio_metrics

    def _normalise_worker_id(self, explicit: Optional[str]) -> str:
        """Derive a stable worker identifier for lease ownership."""
        try:
            candidate = (explicit or f"{self.client_id or 'prompt-studio'}-worker-{uuid4().hex[:8]}").strip()
        except Exception:
            candidate = f"{self.client_id or 'prompt-studio'}-worker"
        if not candidate:
            candidate = "prompt-studio-worker"
        return candidate[:128]

    ####################################################################################################################
    # Job Creation and Management

    def create_job(self, job_type: JobType, entity_id: int, payload: Dict[str, Any],
                  project_id: Optional[int] = None, priority: int = 5, max_retries: int = 3) -> Dict[str, Any]:
        """
        Create a new job in the queue.

        Args:
            job_type: Type of job
            entity_id: ID of related entity (evaluation, optimization, etc.)
            payload: Job-specific data
            project_id: Optional project ID
            priority: Job priority (1-10, higher = more priority)
            max_retries: Maximum retry attempts

        Returns:
            Created job record
        """
        try:
            job = self.db.create_job(
                job_type.value,
                entity_id,
                payload,
                project_id=project_id,
                priority=priority,
                status=JobStatus.QUEUED.value,
                max_retries=max_retries,
                client_id=self.client_id,
            )
            logger.info(f"Created {job_type} job {job.get('id')} for entity {entity_id}")
            try:
                self._metrics.metrics_manager.increment(
                    "jobs.scheduled_total", labels={"job_type": job_type.value}
                )
            except Exception as m_err:
                logger.debug(f"metrics increment failed (jobs.scheduled_total): error={m_err}")
            try:
                self._refresh_gauges_for_type(job_type.value)
            except Exception as g_err:
                logger.debug(f"refresh gauges failed for job_type={job_type.value}: error={g_err}")
            return self._normalize_job(job)
        except DatabaseError:
            raise
        except Exception as e:  # pragma: no cover - safeguard
            logger.error(f"Failed to create job: {e}")
            raise DatabaseError(f"Failed to create job: {e}")

    def get_job(self, job_id: int) -> Optional[Dict[str, Any]]:
        """
        Get a job by ID.

        Args:
            job_id: Job ID

        Returns:
            Job record or None
        """
        job = self.db.get_job(job_id)
        return self._normalize_job(job)

    def get_job_by_uuid(self, job_uuid: str) -> Optional[Dict[str, Any]]:
        """
        Get a job by UUID.

        Args:
            job_uuid: Job UUID

        Returns:
            Job record or None
        """
        job = self.db.get_job_by_uuid(job_uuid)
        return self._normalize_job(job)

    def list_jobs(self, status: Optional[JobStatus] = None,
                 job_type: Optional[JobType] = None,
                 limit: int = 100) -> List[Dict[str, Any]]:
        """
        List jobs with optional filtering.

        Args:
            status: Filter by status
            job_type: Filter by job type
            limit: Maximum results

        Returns:
            List of jobs
        """
        jobs = self.db.list_jobs(
            status=status.value if isinstance(status, JobStatus) else status,
            job_type=job_type.value if isinstance(job_type, JobType) else job_type,
            limit=limit,
        )
        normalized: List[Dict[str, Any]] = []
        for job in jobs:
            job_dict = self._normalize_job(job)
            if job_dict is not None:
                normalized.append(job_dict)
        return normalized

    def update_job_status(self, job_id: int, status: JobStatus,
                         error_message: Optional[str] = None,
                         result: Optional[Dict[str, Any]] = None) -> bool:
        """
        Update job status.

        Args:
            job_id: Job ID
            status: New status
            error_message: Error message if failed
            result: Result data if completed

        Returns:
            True if updated
        """
        job = self.db.update_job_status(
            job_id,
            status.value,
            error_message=error_message,
            result=result,
        )
        if job:
            logger.info(f"Updated job {job_id} status to {status.value}")
        return job is not None

    def cancel_job(self, job_id: int, reason: Optional[str] = None) -> bool:
        """
        Cancel a job.

        Args:
            job_id: Job ID
            reason: Cancellation reason

        Returns:
            True if cancelled
        """
        job = self.get_job(job_id)
        if not job:
            return False

        if job["status"] in [JobStatus.COMPLETED.value, JobStatus.FAILED.value]:
            logger.warning(f"Cannot cancel job {job_id} with status {job['status']}")
            return False

        return self.update_job_status(
            job_id,
            JobStatus.CANCELLED,
            error_message=reason or "Job cancelled by user"
        )

    ####################################################################################################################
    # Job Processing

    def get_next_job(self) -> Optional[Dict[str, Any]]:
        """
        Get the next job to process from the queue.

        Returns:
            Next job or None
        """
        job = self.db.acquire_next_job(worker_id=self.worker_id)
        normalized = self._normalize_job(job)
        if normalized:
            try:
                jt = str(normalized.get("job_type"))
                self._refresh_gauges_for_type(jt)
            except Exception as g_err:
                logger.debug(
                    f"refresh gauges failed in get_next_job: job_type={jt if 'jt' in locals() else '?'} error={g_err}"
                )
        return normalized

    def retry_job(self, job_id: int) -> bool:
        """
        Retry a failed job.

        Args:
            job_id: Job ID

        Returns:
            True if retry scheduled
        """
        job = self.get_job(job_id)
        if not job:
            return False

        # Allow at most (max_retries - 1) retries after the initial attempt
        if job["retry_count"] >= max(0, job["max_retries"] - 1):
            logger.warning(f"Job {job_id} has reached max retries")
            return False

        success = self.db.retry_job_record(job_id)
        if success:
            logger.info(
                f"Scheduled retry for job {job_id} (attempt {job['retry_count'] + 1})"
            )
            try:
                # Derive job type for metrics if possible
                j = self.get_job(job_id)
                jt = str(j.get("job_type")) if j else ""
                self._metrics.metrics_manager.increment(
                    "jobs.retries_total",
                    labels={"job_type": jt},
                )
            except Exception as m_err:
                logger.debug(f"metrics increment failed (jobs.retries_total): error={m_err}")
        return success

    def register_handler(self, job_type: JobType, handler: Optional[Callable] = None):
        """
        Register a handler function for a job type.

        Supports decorator usage:
            @jm.register_handler(JobType.OPTIMIZATION)
            async def handle(payload, entity_id): ...

        Or direct call:
            jm.register_handler(JobType.OPTIMIZATION, handle)
        """
        if handler is None:
            def _decorator(fn: Callable):
                self._job_handlers[job_type] = fn
                logger.info(f"Registered handler for {job_type.value} jobs")
                return fn
            return _decorator
        self._job_handlers[job_type] = handler
        logger.info(f"Registered handler for {job_type.value} jobs")

    async def process_job(self, job: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a single job.

        Args:
            job: Job record

        Returns:
            Job result
        """
        job_type = JobType(job["job_type"])
        handler = self._job_handlers.get(job_type)

        if not handler:
            raise ValueError(f"No handler registered for job type {job_type.value}")

        # Heartbeat: periodically renew the job lease while processing
        lease_task = None
        started_at = time.time()
        try:
            logger.info(f"Processing {job_type.value} job {job['id']}")

            # Parse payload to dict if stored as string
            payload = job.get("payload")
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception as hb_err:
                    logger.debug(f"lease renewal metrics increment failed: error={hb_err}")

            # Start lease heartbeat
            lease_secs = 60
            try:
                lease_secs = max(5, min(3600, int(os.getenv("TLDW_PS_JOB_LEASE_SECONDS", "60"))))
            except Exception:
                lease_secs = 60
            try:
                hb = int(os.getenv("TLDW_PS_HEARTBEAT_SECONDS", "0") or "0")
            except Exception:
                hb = 0
            interval = hb if hb > 0 else max(2, min(lease_secs // 2, 30))

            async def _lease_heartbeat():
                try:
                    while True:
                        await asyncio.sleep(interval)
                        try:
                            ok = self.db.renew_job_lease(int(job["id"]), seconds=lease_secs, worker_id=self.worker_id)
                            if ok:
                                try:
                                    self._metrics.metrics_manager.increment(
                                        "jobs.lease_renewals_total",
                                        labels={"job_type": job_type.value},
                                    )
                                except Exception as m_err:
                                    logger.debug(f"metrics increment failed (jobs.lease_renewals_total): error={m_err}")
                        except Exception as rn_err:
                            # Best-effort; ignore renewal failures here
                            logger.debug(f"lease renewal failed (best-effort ignored): error={rn_err}")
                except asyncio.CancelledError:  # graceful shutdown
                    return

            lease_task = asyncio.create_task(_lease_heartbeat())

            # Execute handler
            result = await handler(payload, job["entity_id"])  # type: ignore[arg-type]

            # Update job as completed
            self.update_job_status(job["id"], JobStatus.COMPLETED, result=result)
            try:
                self._refresh_gauges_for_type(job_type.value)
            except Exception as g_err:
                logger.debug(f"refresh gauges failed after completion: job_type={job_type.value}, error={g_err}")

            logger.info(f"Completed {job_type.value} job {job['id']}")
            return result

        except Exception as e:
            logger.error(f"Job {job['id']} failed: {e}")

            # Delegate retry decision to retry_job() to keep semantics consistent
            try:
                scheduled = self.retry_job(job["id"])  # returns True if re-queued
            except Exception as r_err:
                logger.debug(f"retry_job failed: job_id={job['id']}, error={r_err}")
                scheduled = False

            if not scheduled:
                self.update_job_status(
                    job["id"],
                    JobStatus.FAILED,
                    error_message=str(e),
                )
                try:
                    self._metrics.metrics_manager.increment(
                        "jobs.failures_total",
                        labels={"job_type": job_type.value, "reason": type(e).__name__},
                    )
                except Exception as m_err:
                    logger.debug(f"metrics increment failed (jobs.failures_total): error={m_err}")
            try:
                self._refresh_gauges_for_type(job_type.value)
            except Exception as g_err:
                logger.debug(f"refresh gauges failed after failure: job_type={job_type.value}, error={g_err}")

            raise
        finally:
            if lease_task is not None:
                try:
                    lease_task.cancel()
                except Exception as c_err:
                    logger.debug(f"lease_task.cancel() failed in finally: error={c_err}")
            # Record duration histogram
            try:
                duration = max(0.0, time.time() - started_at)
                self._metrics.metrics_manager.observe(
                    "jobs.duration_seconds",
                    duration,
                    labels={"job_type": job_type.value},
                )
            except Exception as m_err:
                logger.debug(f"observe jobs.duration_seconds failed in finally: error={m_err}")

    def _refresh_gauges_for_type(self, job_type: str) -> None:
        """Refresh queued and processing gauges for a given job type."""
        try:
            queued = int(self.db.count_jobs(status=JobStatus.QUEUED.value, job_type=job_type))
        except Exception as e:
            logger.debug(f"count_jobs queued failed: job_type={job_type}, error={e}")
            queued = 0
        try:
            processing = int(self.db.count_jobs(status=JobStatus.PROCESSING.value, job_type=job_type))
        except Exception as e:
            logger.debug(f"count_jobs processing failed: job_type={job_type}, error={e}")
            processing = 0
        # Update gauges
        try:
            self._metrics.update_job_queue_size(job_type, queued)
        except Exception as m_err:
            logger.debug(f"update_job_queue_size failed: job_type={job_type}, error={m_err}")
        try:
            self._metrics.metrics_manager.set_gauge(
                "jobs.processing",
                float(processing),
                labels={"job_type": job_type},
            )
        except Exception as m_err:
            logger.debug(f"set_gauge jobs.processing failed: job_type={job_type}, error={m_err}")
        # Backlog gauge
        try:
            backlog = max(0, int(queued) - int(processing))
            self._metrics.metrics_manager.set_gauge(
                "jobs.backlog",
                float(backlog),
                labels={"job_type": job_type},
            )
        except Exception as m_err:
            logger.debug(f"set_gauge jobs.backlog failed: job_type={job_type}, error={m_err}")
        # Stale processing (aggregate)
        try:
            lease_stats = self.db.get_lease_stats()
            self._metrics.metrics_manager.set_gauge(
                "jobs.stale_processing",
                float(lease_stats.get("stale_processing", 0)),
            )
        except Exception as m_err:
            logger.debug(f"set_gauge jobs.stale_processing failed: error={m_err}")

    async def start_processing(self, max_concurrent: int = 3):
        """
        Start processing jobs from the queue.

        Args:
            max_concurrent: Maximum concurrent jobs
        """
        if self._is_processing:
            logger.warning("Job processing already running")
            return

        self._is_processing = True
        logger.info(f"Starting job processor with max {max_concurrent} concurrent jobs")

        try:
            while self._is_processing:
                # Get next jobs up to max_concurrent
                jobs = []
                for _ in range(max_concurrent):
                    job = self.get_next_job()
                    if job:
                        jobs.append(job)

                if not jobs:
                    # No jobs to process, wait
                    await asyncio.sleep(5)
                    continue

                # Process jobs concurrently
                tasks = [self.process_job(job) for job in jobs]
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log results
                for job, result in zip(jobs, results):
                    if isinstance(result, Exception):
                        logger.error(f"Job {job['id']} failed with exception: {result}")
                    else:
                        logger.debug(f"Job {job['id']} completed successfully")

                # Small delay before next batch
                await asyncio.sleep(1)

        except Exception as e:
            logger.error(f"Job processor error: {e}")
        finally:
            self._is_processing = False
            logger.info("Job processor stopped")

    def stop_processing(self):
        """Stop processing jobs."""
        self._is_processing = False
        logger.info("Stopping job processor")

    ####################################################################################################################
    # Job Statistics

    def get_job_stats(self) -> Dict[str, Any]:
        """
        Get job queue statistics.

        Returns:
            Statistics dictionary
        """
        stats = self.db.get_job_stats()
        # Ensure status keys exist for convenience
        stats.setdefault("by_status", {})
        stats["queue_depth"] = stats["by_status"].get(JobStatus.QUEUED.value, 0)
        stats["processing"] = stats["by_status"].get(JobStatus.PROCESSING.value, 0)
        return stats

    def cleanup_old_jobs(self, days: int = 30) -> int:
        """
        Clean up old completed/failed jobs.

        Args:
            days: Delete jobs older than this many days

        Returns:
            Number of jobs deleted
        """
        deleted = self.db.cleanup_jobs(days)
        if deleted:
            logger.info(f"Cleaned up {deleted} old jobs")
        return deleted

    ####################################################################################################################
    # Helpers

    def _normalize_job(self, job: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if job is None:
            return None
        normalized = dict(job)
        if isinstance(normalized.get("payload"), (dict, list)):
            normalized["payload"] = json.dumps(normalized["payload"])  # type: ignore[index]
        if isinstance(normalized.get("result"), (dict, list)):
            normalized["result"] = json.dumps(normalized["result"])  # type: ignore[index]
        return normalized
