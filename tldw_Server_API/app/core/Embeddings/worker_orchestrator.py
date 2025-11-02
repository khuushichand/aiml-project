# worker_orchestrator.py
# Orchestrates and manages worker pools for the embedding pipeline

import asyncio
import json
import signal
import sys
from datetime import datetime
from typing import Dict, List, Optional
import os

from loguru import logger
from prometheus_client import start_http_server, Gauge, Counter, Histogram
from tldw_Server_API.app.core.Metrics import initialize_telemetry, OTEL_AVAILABLE

from .job_manager import EmbeddingJobManager, JobManagerConfig
from .worker_config import (
    OrchestrationConfig,
    WorkerPoolConfig,
    ChunkingWorkerPoolConfig,
    EmbeddingWorkerPoolConfig,
    StorageWorkerPoolConfig,
)
from .workers import (
    ChunkingWorker,
    EmbeddingWorker,
    EmbeddingWorkerConfig,
    StorageWorker,
    WorkerConfig,
)
from tldw_Server_API.app.core.Utils.pydantic_compat import model_dump_compat


# Prometheus metrics
WORKER_COUNT = Gauge("embedding_worker_count", "Number of active workers", ["worker_type"])
QUEUE_DEPTH = Gauge("embedding_queue_depth", "Current queue depth", ["queue_name"])
DLQ_QUEUE_DEPTH = Gauge("embedding_dlq_queue_depth", "Current DLQ queue depth", ["queue_name"])
DLQ_INGEST_RATE = Gauge("embedding_dlq_ingest_rate", "Estimated DLQ ingest rate per second", ["queue_name"])
STAGE_JOBS_PROCESSED = Counter("embedding_stage_jobs_processed_total", "Total jobs processed per stage", ["stage"])
STAGE_JOBS_FAILED = Counter("embedding_stage_jobs_failed_total", "Total jobs failed per stage", ["stage"])
JOBS_TOTAL = Counter("embedding_jobs_total", "Total jobs processed", ["status"])
QUEUE_AGE_SECONDS = Histogram("embedding_queue_age_seconds", "Age of oldest message in seconds", ["queue_name"])
STAGE_PROCESS_LATENCY_SECONDS = Histogram("embedding_stage_processing_latency_seconds", "Observed per-message processing latency", ["stage"])

# Worker liveness gauges
WORKERS_ACTIVE = Gauge("embedding_workers_active", "Workers with valid heartbeat TTL", ["worker_type"])
WORKERS_STALLED = Gauge("embedding_workers_stalled", "Workers missing/expired heartbeat", ["worker_type"])


class WorkerPool:
    """Manages a pool of workers of the same type"""

    def __init__(self, pool_config: WorkerPoolConfig):
        self.config = pool_config
        self.workers: List[asyncio.Task] = []
        self.running = False

    async def start(self, redis_url: str):
        """Start all workers in the pool"""
        self.running = True

        for i in range(self.config.num_workers):
            worker_id = f"{self.config.worker_type}-{i}"
            worker = await self._create_worker(worker_id, redis_url)

            # Start worker in background task
            task = asyncio.create_task(worker.start())
            self.workers.append(task)

            logger.info(f"Started worker {worker_id}")

        # Update metrics
        WORKER_COUNT.labels(worker_type=self.config.worker_type).set(len(self.workers))

    async def stop(self):
        """Stop all workers in the pool"""
        self.running = False

        # Cancel all worker tasks
        for task in self.workers:
            task.cancel()

        # Wait for all to complete
        await asyncio.gather(*self.workers, return_exceptions=True)

        self.workers.clear()
        WORKER_COUNT.labels(worker_type=self.config.worker_type).set(0)

        logger.info(f"Stopped all {self.config.worker_type} workers")

    async def scale(self, new_count: int, redis_url: str):
        """Scale the worker pool to new count"""
        current_count = len(self.workers)

        if new_count > current_count:
            # Scale up
            for i in range(current_count, new_count):
                worker_id = f"{self.config.worker_type}-{i}"
                worker = await self._create_worker(worker_id, redis_url)

                task = asyncio.create_task(worker.start())
                self.workers.append(task)

                logger.info(f"Scaled up: started worker {worker_id}")

        elif new_count < current_count:
            # Scale down
            workers_to_stop = self.workers[new_count:]
            self.workers = self.workers[:new_count]

            for task in workers_to_stop:
                task.cancel()

            await asyncio.gather(*workers_to_stop, return_exceptions=True)

            logger.info(f"Scaled down: stopped {len(workers_to_stop)} workers")

        WORKER_COUNT.labels(worker_type=self.config.worker_type).set(len(self.workers))

    async def _create_worker(self, worker_id: str, redis_url: str):
        """Create a worker instance based on type"""
        base_config = WorkerConfig(
            worker_id=worker_id,
            worker_type=self.config.worker_type,
            redis_url=redis_url,
            queue_name=self.config.queue_name,
            consumer_group=self.config.consumer_group,
            batch_size=self.config.batch_size,
            poll_interval_ms=self.config.poll_interval_ms,
            max_retries=self.config.max_retries,
            heartbeat_interval=self.config.heartbeat_interval,
            shutdown_timeout=self.config.shutdown_timeout,
            metrics_interval=self.config.metrics_interval,
        )

        if isinstance(self.config, ChunkingWorkerPoolConfig):
            return ChunkingWorker(base_config)

        elif isinstance(self.config, EmbeddingWorkerPoolConfig):
            # Assign GPU in round-robin fashion
            gpu_id = None
            if self.config.gpu_allocation:
                worker_index = int(worker_id.split('-')[-1])
                gpu_id = self.config.gpu_allocation[worker_index % len(self.config.gpu_allocation)]

            embedding_config = EmbeddingWorkerConfig(
                **model_dump_compat(base_config),
                default_model_provider=self.config.default_model_provider,
                default_model_name=self.config.default_model_name,
                max_batch_size=self.config.batch_size,
                gpu_id=gpu_id
            )
            return EmbeddingWorker(embedding_config)

        elif isinstance(self.config, StorageWorkerPoolConfig):
            return StorageWorker(base_config)

        else:
            raise ValueError(f"Unknown worker type: {self.config.worker_type}")


class WorkerOrchestrator:
    """Orchestrates all worker pools and manages the embedding pipeline"""

    def __init__(self, config: OrchestrationConfig):
        self.config = config
        self.pools: Dict[str, WorkerPool] = {}
        self.job_manager: Optional[EmbeddingJobManager] = None
        self.running = False
        self._tasks: List[asyncio.Task] = []
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._dlq_prev: Dict[str, tuple] = {}
        self._stage_prev: Dict[str, Dict[str, float]] = {}
        self._delayed_last_run: float = 0.0
        # Token bucket state per live queue to guard requeue storms
        self._requeue_buckets: Dict[str, Dict[str, float]] = {}
        self._requeue_rate = float(os.getenv("EMBEDDINGS_REQUEUE_RATE", "50"))  # tokens per second
        self._requeue_burst = float(os.getenv("EMBEDDINGS_REQUEUE_BURST", "200"))  # max tokens

        # Setup signal handlers only when running on the main thread.
        # In test contexts (or when embedded), installing signal handlers from
        # non-main threads raises ValueError and may cause teardown hangs.
        try:
            import threading as _thr
            if _thr.current_thread() is _thr.main_thread():
                signal.signal(signal.SIGINT, self._signal_handler)
                signal.signal(signal.SIGTERM, self._signal_handler)
        except Exception:
            # Best-effort; orchestrator works without direct signal handlers.
            pass

    def _log_signal_notice(self, signum: int):
        try:
            logger.info(f"Received signal {signum}, initiating shutdown...")
        except Exception:
            pass

    def _signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        # Avoid Loguru logging inside signal handlers to prevent re-entrant deadlocks.
        self.running = False
        try:
            import sys
            sys.stderr.write(f"[orchestrator] Signal {signum} received, shutting down...\n")
            sys.stderr.flush()
        except Exception:
            pass
        # Queue a safe log call on the loop thread if available
        try:
            if self._loop is not None:
                self._loop.call_soon_threadsafe(self._log_signal_notice, signum)
        except Exception:
            pass

    async def start(self):
        """Start the orchestrator and all worker pools"""
        logger.info("Starting Worker Orchestrator")

        # Configure logging
        logger.remove()
        logger.add(sys.stderr, level=self.config.log_level)
        # Capture running event loop for queued logging from signal handler
        try:
            self._loop = asyncio.get_running_loop()
        except Exception:
            self._loop = None

        # Initialize OpenTelemetry (optional; console exporter by default)
        try:
            initialize_telemetry()
            logger.info(f"Telemetry initialized (OTEL_AVAILABLE={OTEL_AVAILABLE})")
        except Exception as _otel_e:
            logger.debug(f"Telemetry initialization skipped: {_otel_e}")

        # Start monitoring if enabled
        if self.config.enable_monitoring:
            start_http_server(self.config.monitoring_port)
            logger.info(f"Monitoring dashboard available at http://localhost:{self.config.monitoring_port}")

        # Initialize job manager
        job_manager_config = JobManagerConfig(redis_url=self.config.redis.url)
        self.job_manager = EmbeddingJobManager(job_manager_config)
        await self.job_manager.initialize()

        # Start worker pools
        for pool_name, pool_config in self.config.worker_pools.items():
            pool = WorkerPool(pool_config)
            self.pools[pool_name] = pool
            await pool.start(self.config.redis.url)

        self.running = True

        # Start background tasks
        self._tasks = [
            asyncio.create_task(self._monitor_queues()),
            asyncio.create_task(self._drain_delayed_queues()),
        ]

        if self.config.enable_autoscaling:
            self._tasks.append(asyncio.create_task(self._autoscale_loop()))

        logger.info("Worker Orchestrator started successfully")

        try:
            # Wait for shutdown signal
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Orchestrator tasks cancelled")
        finally:
            await self.stop()

    async def stop(self):
        """Stop all worker pools and cleanup"""
        logger.info("Stopping Worker Orchestrator")

        # Cancel background tasks
        for task in self._tasks:
            if not task.done():
                task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Stop all worker pools
        stop_tasks = []
        for pool in self.pools.values():
            stop_tasks.append(pool.stop())

        await asyncio.gather(*stop_tasks)

        # Close job manager
        if self.job_manager:
            await self.job_manager.close()

        logger.info("Worker Orchestrator stopped")

    async def _monitor_queues(self):
        """Monitor queue depths and update metrics"""
        while self.running:
            try:
                if self.job_manager:
                    # Queue depths + DLQ rates
                    stats = await self.job_manager.get_queue_stats_with_dlq()
                    now = datetime.utcnow().timestamp()
                    for queue_name, depth in stats.items():
                        if queue_name.endswith(":dlq"):
                            DLQ_QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)
                            prev = self._dlq_prev.get(queue_name)
                            if prev is not None:
                                prev_ts, prev_depth = prev
                                dt = max(1e-3, now - prev_ts)
                                delta = depth - prev_depth
                                rate = max(0.0, delta / dt)
                                DLQ_INGEST_RATE.labels(queue_name=queue_name).set(rate)
                            self._dlq_prev[queue_name] = (now, depth)
                        else:
                            QUEUE_DEPTH.labels(queue_name=queue_name).set(depth)
                            # Observe age of oldest message via stream ID timestamp
                            try:
                                client = self.job_manager.redis_client
                                if client:
                                    rng = await client.xrange(queue_name, min='-', max='+', count=1)
                                    if rng:
                                        first_id, _ = rng[0]
                                        # Stream ID format: millis-seq
                                        ts_ms = int(str(first_id).split('-')[0])
                                        age_s = max(0.0, (now * 1000 - ts_ms) / 1000.0)
                                        QUEUE_AGE_SECONDS.labels(queue_name=queue_name).observe(age_s)
                            except Exception:
                                pass

                    # Aggregate worker metrics from Redis to update per-stage counters
                    try:
                        client = self.job_manager.redis_client
                        if client:
                            cursor = 0
                            totals: Dict[str, Dict[str, float]] = {}
                            # Stale detection window for worker metrics (seconds)
                            try:
                                _STALE_MAX_AGE = float(os.getenv("EMB_ORCH_METRICS_STALE_MAX_AGE", "120") or 120.0)
                            except Exception:
                                _STALE_MAX_AGE = 120.0
                            now_ts = datetime.utcnow().timestamp()
                            # We compute cumulative totals by stage from worker snapshots
                            while True:
                                cursor, keys = await client.scan(cursor, match="worker:metrics:*", count=100)
                                for k in keys:
                                    # Skip or prune stale snapshots
                                    try:
                                        ttl = await client.ttl(k)  # type: ignore[attr-defined]
                                    except Exception:
                                        ttl = None
                                    data = await client.get(k)
                                    if not data:
                                        continue
                                    try:
                                        m = json.loads(data)
                                        # Drop metrics that appear stale by last_heartbeat
                                        try:
                                            hb = m.get("last_heartbeat")
                                            if hb:
                                                # best-effort ISO parse
                                                ts = datetime.fromisoformat(str(hb)).timestamp()
                                                if (now_ts - ts) > _STALE_MAX_AGE:
                                                    # Best-effort prune if no TTL is set
                                                    try:
                                                        if ttl is not None and int(ttl) < 0:
                                                            await client.delete(k)  # type: ignore[attr-defined]
                                                    except Exception:
                                                        pass
                                                    continue
                                        except Exception:
                                            pass
                                        stage = str(m.get("worker_type", "unknown"))
                                        processed = float(m.get("jobs_processed", 0) or 0)
                                        failed = float(m.get("jobs_failed", 0) or 0)
                                        last_ms = float(m.get("last_processing_time_ms", 0) or 0)
                                        agg = totals.setdefault(stage, {"processed": 0.0, "failed": 0.0})
                                        agg["processed"] += processed
                                        agg["failed"] += failed
                                        if last_ms > 0:
                                            STAGE_PROCESS_LATENCY_SECONDS.labels(stage=stage).observe(last_ms / 1000.0)
                                    except Exception:
                                        continue
                                if cursor == 0:
                                    break
                            # Emit deltas as counter increments
                            prev = self._stage_prev
                            for stage, vals in totals.items():
                                prev_vals = prev.get(stage, {"processed": 0.0, "failed": 0.0})
                                d_proc = max(0.0, vals["processed"] - prev_vals.get("processed", 0.0))
                                d_fail = max(0.0, vals["failed"] - prev_vals.get("failed", 0.0))
                                if d_proc > 0:
                                    STAGE_JOBS_PROCESSED.labels(stage=stage).inc(d_proc)
                                if d_fail > 0:
                                    STAGE_JOBS_FAILED.labels(stage=stage).inc(d_fail)
                            self._stage_prev = totals
                    except Exception as agg_err:
                        logger.debug(f"Worker metrics aggregation error: {agg_err}")

                    # Worker liveness from heartbeats
                    try:
                        client = self.job_manager.redis_client
                        if client:
                            # Reset gauges each tick
                            for wt in ("chunking", "embedding", "storage"):
                                WORKERS_ACTIVE.labels(worker_type=wt).set(0)
                                WORKERS_STALLED.labels(worker_type=wt).set(0)
                            # Scan heartbeats with cap to prevent unbounded work per tick
                            cursor = 0
                            processed_hb = 0
                            try:
                                _HB_MAX = int(os.getenv("EMB_ORCH_HEARTBEATS_MAX_KEYS", "2000") or 2000)
                            except Exception:
                                _HB_MAX = 2000
                            counts: Dict[str, Dict[str, int]] = {"chunking": {"a": 0, "s": 0},
                                                                 "embedding": {"a": 0, "s": 0},
                                                                 "storage": {"a": 0, "s": 0}}
                            while True:
                                cursor, keys = await client.scan(cursor, match="worker:heartbeat:*", count=200)
                                for key in keys:
                                    if processed_hb >= _HB_MAX:
                                        cursor = 0
                                        break
                                    try:
                                        wid = str(key).split(":", 2)[-1]
                                        wtype = wid.split("-", 1)[0] if "-" in wid else "unknown"
                                        # Prefer PTTL if available
                                        ttl_ms = None
                                        try:
                                            ttl_ms = await client.pttl(key)  # type: ignore[attr-defined]
                                        except Exception:
                                            ttl_ms = None
                                        if ttl_ms is not None and ttl_ms > 0:
                                            counts.setdefault(wtype, {"a": 0, "s": 0})["a"] += 1
                                        else:
                                            # Fallback: if key exists but no TTL, treat as active; else stalled
                                            val = await client.get(key)
                                            if val:
                                                counts.setdefault(wtype, {"a": 0, "s": 0})["a"] += 1
                                            else:
                                                counts.setdefault(wtype, {"a": 0, "s": 0})["s"] += 1
                                    except Exception:
                                        continue
                                    finally:
                                        processed_hb += 1
                                if cursor == 0:
                                    break
                            for wt, cs in counts.items():
                                try:
                                    WORKERS_ACTIVE.labels(worker_type=wt).set(cs.get("a", 0))
                                    WORKERS_STALLED.labels(worker_type=wt).set(cs.get("s", 0))
                                except Exception:
                                    pass
                    except Exception as hb_err:
                        logger.debug(f"Heartbeat scan error: {hb_err}")

                await asyncio.sleep(30)  # Update every 30 seconds

            except Exception as e:
                logger.error(f"Error monitoring queues: {e}")
                await asyncio.sleep(30)

    async def _autoscale_loop(self):
        """Auto-scale worker pools based on queue depth"""
        while self.running:
            try:
                await self._check_scaling()
                await asyncio.sleep(self.config.scale_check_interval)

            except Exception as e:
                logger.error(f"Error in auto-scaling: {e}")
                await asyncio.sleep(self.config.scale_check_interval)

    async def _check_scaling(self):
        """Check if scaling is needed based on queue depths"""
        if not self.job_manager:
            return

        stats = await self.job_manager.get_queue_stats()

        for pool_name, pool in self.pools.items():
            queue_depth = stats.get(pool.config.queue_name, 0)
            current_workers = len(pool.workers)

            # Calculate load factor
            load_factor = queue_depth / (current_workers * 100) if current_workers > 0 else 1.0

            if load_factor > self.config.scale_up_threshold:
                # Scale up
                new_count = min(
                    current_workers + 1,
                    pool.config.num_workers * 2,  # Max 2x configured workers
                    self.config.max_total_workers - self._total_workers() + current_workers
                )

                if new_count > current_workers:
                    logger.info(f"Scaling up {pool_name} from {current_workers} to {new_count} workers")
                    await pool.scale(new_count, self.config.redis.url)

            elif load_factor < self.config.scale_down_threshold and current_workers > pool.config.num_workers:
                # Scale down
                new_count = max(pool.config.num_workers, current_workers - 1)

                if new_count < current_workers:
                    logger.info(f"Scaling down {pool_name} from {current_workers} to {new_count} workers")
                    await pool.scale(new_count, self.config.redis.url)

    def _total_workers(self) -> int:
        """Get total number of workers across all pools"""
        return sum(len(pool.workers) for pool in self.pools.values())

    async def _drain_delayed_queues(self):
        """Move due items from delayed ZSETs into their live streams."""
        while self.running:
            try:
                if not self.job_manager:
                    await asyncio.sleep(1)
                    continue
                client = self.job_manager.redis_client
                now_ms = int(datetime.utcnow().timestamp() * 1000)
                # derive queues from configured pools
                live_queues: List[str] = []
                for pool in self.pools.values():
                    q = getattr(pool.config, 'queue_name', None)
                    if q:
                        live_queues.append(q)
                for q in set(live_queues):
                    delayed_key = f"{q}:delayed"
                    try:
                        # Token bucket throttle per queue
                        bkt = self._requeue_buckets.get(q)
                        now_s = now_ms / 1000.0
                        if not bkt:
                            bkt = {"tokens": self._requeue_burst, "last": now_s}
                            self._requeue_buckets[q] = bkt
                        # Refill tokens
                        elapsed = max(0.0, now_s - float(bkt.get("last", now_s)))
                        tokens = float(bkt.get("tokens", 0.0)) + self._requeue_rate * elapsed
                        tokens = min(self._requeue_burst, tokens)
                        bkt["last"] = now_s
                        allow = int(min(100, max(0, int(tokens))))
                        if allow <= 0:
                            continue
                        # Take up to 'allow' due items at a time
                        due = await client.zrangebyscore(delayed_key, min='-inf', max=now_ms, start=0, num=allow)
                        for raw in due:
                            try:
                                payload = json.loads(raw)
                            except Exception:
                                payload = None
                            if payload:
                                try:
                                    fields = {k: (v if isinstance(v, str) else json.dumps(v)) for k, v in payload.items()}
                                except Exception:
                                    fields = {k: str(v) for k, v in (payload or {}).items()}
                                try:
                                    await client.xadd(q, fields)
                                except Exception:
                                    pass
                            # Remove regardless to avoid hot-looping on bad entries
                            await client.zrem(delayed_key, raw)
                        # Consume tokens used
                        try:
                            used = len(due)
                            bkt["tokens"] = max(0.0, tokens - used)
                        except Exception:
                            pass
                    except Exception:
                        continue
            except Exception:
                pass
            await asyncio.sleep(1)


async def main():
    """Main entry point for the orchestrator"""
    # Load configuration
    import argparse

    parser = argparse.ArgumentParser(description="Embedding Pipeline Worker Orchestrator")
    parser.add_argument(
        "--config",
        type=str,
        help="Path to configuration YAML file",
        default=None
    )
    parser.add_argument(
        "--workers",
        type=int,
        help="Number of workers per pool (overrides config)",
        default=None
    )

    args = parser.parse_args()

    # Load or create configuration
    if args.config:
        config = OrchestrationConfig.from_yaml(args.config)
    else:
        config = OrchestrationConfig.default_config()

    # Override worker counts if specified
    if args.workers:
        for pool_config in config.worker_pools.values():
            pool_config.num_workers = args.workers

    # Create and start orchestrator
    orchestrator = WorkerOrchestrator(config)
    await orchestrator.start()


if __name__ == "__main__":
    asyncio.run(main())
