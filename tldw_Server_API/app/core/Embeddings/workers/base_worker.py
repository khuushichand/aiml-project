# base_worker.py
# Base worker class for all embedding pipeline workers

import asyncio
import json
import os
import signal
import time
from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, Dict, List, Optional, Type, TypeVar
import random

import redis.asyncio as redis
from loguru import logger
from pydantic import BaseModel, Field

from ..queue_schemas import EmbeddingJobMessage, JobInfo, JobStatus, WorkerMetrics
from ..messages import build_dedupe_key, classify_failure, validate_schema
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat


T = TypeVar('T', bound=EmbeddingJobMessage)


class WorkerConfig(BaseModel):
    """Base configuration for workers"""
    worker_id: str
    worker_type: str
    redis_url: str = Field(
        default_factory=lambda: os.getenv("REDIS_URL", "redis://localhost:6379"),
        description="Redis connection URL"
    )
    queue_name: str
    consumer_group: str
    batch_size: int = 1
    poll_interval_ms: int = 100
    max_retries: int = 3
    heartbeat_interval: int = 30
    shutdown_timeout: int = 30
    metrics_interval: int = 60


class BaseWorker(ABC):
    """Abstract base class for all pipeline workers"""
    
    def __init__(self, config: WorkerConfig):
        self.config = config
        self.redis_client: Optional[redis.Redis] = None
        self.running = False
        self.jobs_processed = 0
        self.jobs_failed = 0
        self.processing_times: List[float] = []
        self._tasks: List[asyncio.Task] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        
        # Setup signal handlers
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
        
        logger.info(f"Initialized {self.config.worker_type} worker: {self.config.worker_id}")
    
    def _log_signal_notice(self, signum: int):
        """Log signal notice outside of signal handler context."""
        try:
            logger.info(f"Received signal {signum}, initiating shutdown...")
        except Exception:
            # Avoid raising from logging paths
            pass

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals gracefully"""
        # IMPORTANT: Do not log from within a signal handler. Loguru (and many
        # loggers) are not re-entrant and can deadlock when used here.
        # Just flip the running flag; regular loops will exit and log during
        # normal control flow outside the signal context.
        self.running = False
        try:
            # Optionally emit a minimal, non-logger notice to stderr.
            # Avoid raising if stderr is unavailable.
            import sys
            sys.stderr.write(f"[worker:{self.config.worker_id}] Signal {signum} received, shutting down...\n")
            sys.stderr.flush()
        except Exception:
            pass
        # Queue a safe log call onto the event loop thread if available
        try:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._log_signal_notice, signum)
        except Exception:
            pass
    
    @asynccontextmanager
    async def _redis_connection(self):
        """Context manager for Redis connection"""
        try:
            self.redis_client = await redis.from_url(
                self.config.redis_url,
                decode_responses=True
            )
            yield self.redis_client
        finally:
            if self.redis_client:
                await self.redis_client.close()
    
    async def start(self):
        """Start the worker"""
        async with self._redis_connection():
            self.running = True
            # Capture the running event loop for safe cross-thread scheduling
            try:
                self._loop = asyncio.get_running_loop()
            except Exception:
                self._loop = None
            
            # Start background tasks
            self._tasks = [
                asyncio.create_task(self._process_messages()),
                asyncio.create_task(self._heartbeat_loop()),
                asyncio.create_task(self._metrics_loop()),
            ]
            
            logger.info(f"Worker {self.config.worker_id} started")
            
            try:
                await asyncio.gather(*self._tasks)
            except asyncio.CancelledError:
                logger.info("Worker tasks cancelled")
            finally:
                await self._cleanup()
    
    async def _process_messages(self):
        """Main message processing loop"""
        while self.running:
            try:
                # Respect per-stage pause/drain flag
                try:
                    if await self._is_stage_paused():
                        await asyncio.sleep(max(0.01, self.config.poll_interval_ms / 1000))
                        continue
                except Exception:
                    # Do not fail loop on control check
                    pass
                # Read messages from stream
                messages = await self.redis_client.xreadgroup(
                    self.config.consumer_group,
                    self.config.worker_id,
                    {self.config.queue_name: '>'},
                    count=self.config.batch_size,
                    block=self.config.poll_interval_ms
                )
                
                if messages:
                    for stream_name, stream_messages in messages:
                        await self._process_batch(stream_messages)
                        
            except Exception as e:
                logger.error(f"Error in message processing loop: {e}")
                await asyncio.sleep(1)
    
    async def _process_batch(self, messages: List[tuple]):
        """Process a batch of messages"""
        for message_id, data in messages:
            start_time = time.time()
            
            try:
                # Validate envelope early using JSON Schema bundle (best-effort)
                try:
                    validate_schema(self._stage_name(), data)
                except Exception as ve:
                    # Treat schema invalid as permanent failure
                    raise ValueError(str(ve))

                # Parse message
                message = self._parse_message(data)
                # Operation-level dedupe via operation_id if present
                try:
                    op_id = (data.get("operation_id") if isinstance(data, dict) else None) or getattr(message, "operation_id", None)
                    if op_id:
                        first = await self._dedupe_mark_operation_once(str(op_id))
                        if not first:
                            await self.redis_client.xack(
                                self.config.queue_name,
                                self.config.consumer_group,
                                message_id
                            )
                            continue
                except Exception:
                    pass
                # Operator skip registry: allow skipping known-poison jobs
                try:
                    if await self._is_job_skipped(message.job_id):
                        # Mark cancelled and acknowledge
                        await self._update_job_status(message.job_id, JobStatus.CANCELLED, error_message="Skipped by operator")
                        await self.redis_client.xack(
                            self.config.queue_name,
                            self.config.consumer_group,
                            message_id
                        )
                        continue
                except Exception:
                    # Non-fatal
                    pass
                # Deduplicate within a short window to guard against replays
                try:
                    dkey = build_dedupe_key(self._stage_name(), data)
                    if dkey:
                        should_process = await self._dedupe_mark_once(dkey)
                        if not should_process:
                            # Already seen recently; ack and skip
                            await self.redis_client.xack(
                                self.config.queue_name,
                                self.config.consumer_group,
                                message_id
                            )
                            continue
                except Exception:
                    # Non-fatal; proceed without dedupe
                    pass
                
                # Update job status
                await self._update_job_status(message.job_id, JobStatus.CHUNKING)
                
                # Process the message
                result = await self.process_message(message)
                
                # Send to next stage
                if result:
                    await self._send_to_next_stage(result)
                
                # Acknowledge message
                await self.redis_client.xack(
                    self.config.queue_name,
                    self.config.consumer_group,
                    message_id
                )
                
                # Update metrics
                self.jobs_processed += 1
                self.processing_times.append(time.time() - start_time)
                
            except Exception as e:
                logger.error(f"Error processing message {message_id}: {e}")
                await self._handle_failed_message(message_id, data, e)
                self.jobs_failed += 1
    
    @abstractmethod
    async def process_message(self, message: T) -> Optional[BaseModel]:
        """Process a single message. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    def _parse_message(self, data: Dict[str, Any]) -> T:
        """Parse raw message data into typed message. Must be implemented by subclasses."""
        pass
    
    @abstractmethod
    async def _send_to_next_stage(self, result: BaseModel):
        """Send processed result to next stage. Must be implemented by subclasses."""
        pass
    
    async def _handle_failed_message(self, message_id: str, data: Dict[str, Any], error: Exception):
        """Handle failed message processing"""
        try:
            message = self._parse_message(data)
            
            failure_type, error_code = classify_failure(error)

            should_retry = failure_type == "transient" and (message.retry_count < message.max_retries)

            if should_retry:
                # Increment retry count and requeue with exponential backoff + jitter
                message.retry_count += 1
                message.updated_at = datetime.utcnow()
                base = (2 ** message.retry_count) * 1000
                jitter = random.randint(0, 1000)
                delay_ms = base + jitter
                await self._schedule_retry(message, delay_ms)
                logger.warning(
                    f"Scheduled retry for {message.job_id} in ~{delay_ms}ms (retry {message.retry_count}, error_code={error_code})"
                )
            else:
                # Permanent failure or retries exhausted → DLQ
                await self._update_job_status(
                    message.job_id,
                    JobStatus.FAILED,
                    error_message=f"{error_code}: {str(error)}"
                )
                # Publish to DLQ stream for operator intervention
                try:
                    dlq_stream = f"{self.config.queue_name}:dlq"
                    payload = model_dump_compat(message)
                    safe_payload = json.dumps(payload, default=str)
                    await self.redis_client.xadd(
                        dlq_stream,
                        {
                            "original_queue": self.config.queue_name,
                            "consumer_group": self.config.consumer_group,
                            "worker_id": self.config.worker_id,
                            "job_id": getattr(message, "job_id", ""),
                            "job_type": self.config.worker_type,
                            "error": str(error),
                            "error_code": error_code,
                            "failure_type": failure_type,
                            "dlq_state": "quarantined",
                            "retry_count": str(getattr(message, "retry_count", 0)),
                            "max_retries": str(getattr(message, "max_retries", 0)),
                            "failed_at": datetime.utcnow().isoformat(),
                            "payload": safe_payload,
                        },
                    )
                except Exception as dlq_err:
                    logger.error(f"Failed to publish message {message.job_id} to DLQ: {dlq_err}")
                logger.error(
                    f"Message {message.job_id} sent to DLQ (retries={message.retry_count}/{message.max_retries}, type={failure_type}, code={error_code})"
                )
                
            # Always acknowledge to prevent reprocessing
            await self.redis_client.xack(
                self.config.queue_name,
                self.config.consumer_group,
                message_id
            )
            
        except Exception as e:
            logger.error(f"Error handling failed message: {e}")

    async def _is_job_skipped(self, job_id: str) -> bool:
        """Return True if the job_id is marked as skipped by operator."""
        if not self.redis_client:
            return False
        try:
            key = f"embeddings:skip:job:{job_id}"
            val = await self.redis_client.get(key)
            return str(val).lower() in ("1", "true", "yes")
        except Exception:
            return False
    
    async def _update_job_status(self, job_id: str, status: JobStatus, error_message: Optional[str] = None):
        """Update job status in Redis"""
        job_key = f"job:{job_id}"
        if not self.redis_client:
            # In unit tests or when Redis is not initialized, skip status updates
            return

        updates = {
            "status": status.value,
            "updated_at": datetime.utcnow().isoformat(),
            "current_stage": self.config.worker_type
        }
        
        if error_message:
            updates["error_message"] = error_message
        
        if status == JobStatus.COMPLETED:
            updates["completed_at"] = datetime.utcnow().isoformat()
        
        await self.redis_client.hset(job_key, mapping=updates)
        
        # Set TTL for completed/failed jobs
        if status in [JobStatus.COMPLETED, JobStatus.FAILED]:
            try:
                await self.redis_client.expire(job_key, 86400)  # 24 hours
            except Exception:
                # Some in-memory fakes used by tests may not implement expire
                pass
    
    async def _heartbeat_loop(self):
        """Send periodic heartbeats"""
        while self.running:
            try:
                await self._send_heartbeat()
                await asyncio.sleep(self.config.heartbeat_interval)
            except Exception as e:
                logger.error(f"Error sending heartbeat: {e}")
    
    async def _send_heartbeat(self):
        """Send worker heartbeat to Redis"""
        if not self.redis_client:
            return
        heartbeat_key = f"worker:heartbeat:{self.config.worker_id}"
        await self.redis_client.setex(
            heartbeat_key,
            self.config.heartbeat_interval * 2,  # TTL = 2x heartbeat interval
            datetime.utcnow().isoformat()
        )
    
    async def _metrics_loop(self):
        """Report metrics periodically"""
        while self.running:
            try:
                await self._report_metrics()
                await asyncio.sleep(self.config.metrics_interval)
            except Exception as e:
                logger.error(f"Error reporting metrics: {e}")
    
    async def _report_metrics(self):
        """Report worker metrics"""
        avg_processing_time = (
            sum(self.processing_times) / len(self.processing_times)
            if self.processing_times else 0
        )
        last_proc = self.processing_times[-1] if self.processing_times else 0.0
        
        metrics = WorkerMetrics(
            worker_id=self.config.worker_id,
            worker_type=self.config.worker_type,
            jobs_processed=self.jobs_processed,
            jobs_failed=self.jobs_failed,
            average_processing_time_ms=avg_processing_time * 1000,
            current_load=await self._calculate_load(),
            last_heartbeat=datetime.utcnow()
        )
        
        metrics_key = f"worker:metrics:{self.config.worker_id}"
        payload = json.loads(metrics.json())
        payload["last_processing_time_ms"] = last_proc * 1000.0
        await self.redis_client.setex(
            metrics_key,
            self.config.metrics_interval * 2,
            json.dumps(payload)
        )
        
        # Reset processing times to prevent unbounded growth
        if len(self.processing_times) > 1000:
            self.processing_times = self.processing_times[-100:]
    
    async def _calculate_load(self) -> float:
        """Calculate current worker load (0-1)"""
        # This is a simple implementation - can be overridden by subclasses
        queue_length = await self.redis_client.xlen(self.config.queue_name)
        return min(1.0, queue_length / 100)  # Normalize to 0-1
    
    async def _cleanup(self):
        """Cleanup resources before shutdown"""
        logger.info(f"Cleaning up worker {self.config.worker_id}")
        
        # Cancel all tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()
        
        # Wait for tasks to complete
        await asyncio.gather(*self._tasks, return_exceptions=True)
        
        logger.info(f"Worker {self.config.worker_id} shutdown complete")

    # ---------------------------
    # Control & dedupe helpers
    # ---------------------------
    def _stage_name(self) -> str:
        try:
            wt = (self.config.worker_type or "").lower()
            if wt in ("chunking", "embedding", "storage"):
                return wt
            # Fallback from queue name
            if ":" in self.config.queue_name:
                return self.config.queue_name.split(":", 1)[1]
        except Exception:
            pass
        return (self.config.worker_type or "").lower()

    async def _is_stage_paused(self) -> bool:
        key = f"embeddings:stage:{self._stage_name()}:paused"
        try:
            val = await self.redis_client.get(key)
            return str(val).lower() in ("1", "true", "yes")
        except Exception:
            return False

    async def _dedupe_mark_once(self, dkey: str) -> bool:
        ttl = int(os.getenv("EMBEDDINGS_DEDUPE_TTL_SECONDS", "3600") or 3600)
        key = f"embeddings:dedupe:{dkey}"
        try:
            # SET NX with TTL
            # redis-py asyncio supports: set(name, value, ex=seconds, nx=True)
            ok = await self.redis_client.set(key, "1", ex=ttl, nx=True)
            return bool(ok)
        except Exception:
            return True

    async def _dedupe_mark_operation_once(self, operation_id: str) -> bool:
        """Mark an operation_id once using RedisBloom (if available) or SET NX.

        Returns True if first time seen; False if duplicate.
        """
        if not self.redis_client:
            return True
        try:
            # Try RedisBloom first
            try:
                res = await self.redis_client.execute_command("BF.ADD", "embeddings:dedupe:opbf", operation_id)
                if res == 0:
                    return False
                return True
            except Exception:
                pass
            # Fallback to SET NX
            ttl = int(os.getenv("EMBEDDINGS_DEDUPE_TTL_SECONDS", "3600") or 3600)
            key = f"embeddings:dedupe:op:{operation_id}"
            ok = await self.redis_client.set(key, "1", ex=ttl, nx=True)
            return bool(ok)
        except Exception:
            return True

    async def _schedule_retry(self, message: EmbeddingJobMessage, delay_ms: int):
        """Push a message into the delayed ZSET for this stage/queue."""
        if not self.redis_client:
            return
        delayed_key = f"{self.config.queue_name}:delayed"
        score = int(time.time() * 1000) + int(max(0, delay_ms))
        payload = model_dump_compat(message)
        try:
            await self.redis_client.zadd(delayed_key, {json.dumps(payload, default=str): score})
        except Exception as e:
            # Fallback: best effort immediate requeue
            logger.warning(f"Delayed queue unavailable, immediate requeue: {e}")
            await self.redis_client.xadd(self.config.queue_name, payload)
