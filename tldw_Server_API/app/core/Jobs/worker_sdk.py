from __future__ import annotations

import asyncio
import os
import random
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Dict, Optional

from loguru import logger

from .manager import JobManager


CancelCheck = Callable[[Dict[str, Any]], Awaitable[bool]]
JobHandler = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any] | None]]


@dataclass
class WorkerConfig:
    domain: str
    queue: str
    worker_id: str
    lease_seconds: int = 30
    renew_jitter_seconds: int = 5
    renew_threshold_seconds: int = 10
    backoff_base_seconds: int = 2
    backoff_max_seconds: int = 30
    # Retry on handler exception
    retry_on_exception: bool = True
    retry_backoff_seconds: int = 10


class WorkerSDK:
    """Lightweight worker helper: acquisition, auto-renew, progress heartbeats, and cancellation checks.

    Example:
        sdk = WorkerSDK(JobManager(), WorkerConfig(domain='prompt_studio', queue='default', worker_id='w1'))
        await sdk.run(handler=my_handler)
    """

    def __init__(self, jm: JobManager, cfg: WorkerConfig):
        self.jm = jm
        self.cfg = cfg
        self._stop = asyncio.Event()

    def stop(self) -> None:
        self._stop.set()

    async def _auto_renew(self, job: Dict[str, Any], progress_cb: Optional[Callable[[], Dict[str, Any]]] = None) -> None:
        lease = int(max(1, self.cfg.lease_seconds))
        jitter = max(0, int(self.cfg.renew_jitter_seconds))
        threshold = max(1, int(self.cfg.renew_threshold_seconds))
        job_id = int(job.get('id'))
        lease_id = job.get('lease_id')
        while not self._stop.is_set():
            # Sleep for lease - threshold, plus small jitter
            sleep_for = max(1, lease - threshold) + (random.randint(0, jitter) if jitter else 0)
            await asyncio.sleep(sleep_for)
            if self._stop.is_set():
                return
            kwargs = {"job_id": job_id, "seconds": lease, "worker_id": self.cfg.worker_id, "lease_id": lease_id}
            if progress_cb:
                try:
                    upd = progress_cb() or {}
                    if 'progress_percent' in upd:
                        kwargs['progress_percent'] = float(upd['progress_percent'])
                    if 'progress_message' in upd:
                        kwargs['progress_message'] = str(upd['progress_message'])
                except Exception:
                    pass
            try:
                ok = self.jm.renew_job_lease(**kwargs)
                if not ok:
                    logger.debug(f"Auto-renew failed for job {job_id}; stopping renew loop")
                    return
            except Exception as e:
                logger.debug(f"Auto-renew error for job {job_id}: {e}")
                return

    async def run(
        self,
        *,
        handler: JobHandler,
        cancel_check: Optional[CancelCheck] = None,
        progress_cb: Optional[Callable[[], Dict[str, Any]]] = None,
        owner_user_id: Optional[str] = None,
    ) -> None:
        """Run the worker loop until stop() is called.

        handler should accept a job dict and return a result dict (or None) to finalize.
        """
        backoff = max(1, int(self.cfg.backoff_base_seconds))
        backoff_max = max(backoff, int(self.cfg.backoff_max_seconds))
        enforce = os.getenv("JOBS_ENFORCE_LEASE_ACK", "").lower() in {"1","true","yes","y","on"}
        while not self._stop.is_set():
            try:
                job = self.jm.acquire_next_job(
                    domain=self.cfg.domain,
                    queue=self.cfg.queue,
                    lease_seconds=self.cfg.lease_seconds,
                    worker_id=self.cfg.worker_id,
                    owner_user_id=owner_user_id,
                )
            except Exception as e:
                logger.debug(f"Acquire error: {e}")
                job = None
            if not job:
                await asyncio.sleep(min(backoff, backoff_max))
                backoff = min(backoff * 2, backoff_max)
                continue
            backoff = max(1, int(self.cfg.backoff_base_seconds))

            job_id = int(job.get('id'))
            lease_id = job.get('lease_id')
            # Start auto-renew task
            renew_task = asyncio.create_task(self._auto_renew(job, progress_cb=progress_cb))
            try:
                # Cancellation check (optional)
                if cancel_check is not None:
                    try:
                        if await cancel_check(job):
                            self.jm.cancel_job(job_id, reason="requested")
                            continue
                    except Exception:
                        pass
                # Handle job
                result = await handler(job)
                if result is None:
                    # No result; treat as success with empty result
                    result = {}
                ok = self.jm.complete_job(
                    job_id,
                    result=result,
                    worker_id=(self.cfg.worker_id if enforce else None),
                    lease_id=(lease_id if enforce else None),
                    completion_token=(lease_id if os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "").lower() in {"1","true","yes","y","on"} else None),
                )
                if not ok:
                    logger.debug(f"Complete returned False for job {job_id}")
            except Exception as e:
                # Retryable failure by default; allow exception to override via .retryable attribute
                retryable = self.cfg.retry_on_exception and bool(getattr(e, "retryable", True))
                backoff_s = int(getattr(e, "backoff_seconds", self.cfg.retry_backoff_seconds))
                try:
                    self.jm.fail_job(
                        job_id,
                        error=str(e),
                        retryable=retryable,
                        backoff_seconds=backoff_s,
                        worker_id=(self.cfg.worker_id if enforce else None),
                        lease_id=(lease_id if enforce else None),
                        completion_token=(lease_id if os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "").lower() in {"1","true","yes","y","on"} else None),
                        error_code="worker_exception",
                    )
                except Exception:
                    logger.debug(f"Fail finalize error for job {job_id}")
            finally:
                try:
                    renew_task.cancel()
                except Exception:
                    pass
