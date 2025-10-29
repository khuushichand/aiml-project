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
        # Allow test overrides without monkeypatching global asyncio.sleep
        # (keeps event loop behavior stable under tests)
        self._sleep = asyncio.sleep
        # Detect test mode for more responsive sleeps and optional iteration caps
        try:
            self._test_mode = any(
                str(os.getenv(k, "")).strip().lower() in {"1", "true", "yes", "on"}
                for k in ("TEST_MODE", "TLDW_TEST_MODE")
            )
        except Exception:
            self._test_mode = False
        try:
            self._max_iters = int(os.getenv("JOBS_WORKER_MAX_ITERATIONS", "0") or "0")
        except Exception:
            self._max_iters = 0

    async def _sleep_chunked(self, total_seconds: float) -> None:
        """Sleep in small chunks to react quickly to stop() in tests.

        Uses shorter steps in test mode to avoid long blocking sleeps that can
        cause hangs when the event loop is under heavy load.
        """
        remaining = max(0.0, float(total_seconds))
        # Step size: short in tests, modest otherwise
        step = 0.05 if self._test_mode else 0.2
        while remaining > 0 and not self._stop.is_set():
            await self._sleep(min(step, remaining))
            remaining -= step

    def stop(self) -> None:
        self._stop.set()

    async def _auto_renew(self, job: Dict[str, Any], progress_cb: Optional[Callable[[], Dict[str, Any]]] = None) -> None:
        lease = int(max(1, self.cfg.lease_seconds))
        jitter = max(0, int(self.cfg.renew_jitter_seconds))
        threshold = max(1, int(self.cfg.renew_threshold_seconds))
        job_id = int(job.get('id'))
        lease_id = job.get('lease_id')
        iters = 0
        while not self._stop.is_set():
            # Sleep for lease - threshold, plus small jitter
            sleep_for = max(1, lease - threshold) + (random.randint(0, jitter) if jitter else 0)
            await self._sleep_chunked(float(sleep_for))
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
            iters += 1
            if self._max_iters and iters >= self._max_iters:
                logger.debug("Auto-renew reached max iterations; exiting loop")
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
        enforce = self.jm.should_enforce_leases()
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
                # Sleep with backoff in chunks for responsive stop()
                await self._sleep_chunked(float(min(backoff, backoff_max)))
                backoff = min(backoff * 2, backoff_max)
                continue
            backoff = max(1, int(self.cfg.backoff_base_seconds))

            job_id = int(job.get('id'))
            lease_id = job.get('lease_id')
            lease_id_str = str(lease_id) if lease_id is not None else None
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
                    worker_id=self.cfg.worker_id,
                    lease_id=lease_id_str,
                    completion_token=(lease_id_str if os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "").lower() in {"1","true","yes","y","on"} else None),
                    enforce=enforce,
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
                        worker_id=self.cfg.worker_id,
                        lease_id=lease_id_str,
                        completion_token=(lease_id_str if os.getenv("JOBS_REQUIRE_COMPLETION_TOKEN", "").lower() in {"1","true","yes","y","on"} else None),
                        enforce=enforce,
                        error_code="worker_exception",
                    )
                except Exception:
                    logger.debug(f"Fail finalize error for job {job_id}")
            finally:
                try:
                    renew_task.cancel()
                except Exception:
                    pass
