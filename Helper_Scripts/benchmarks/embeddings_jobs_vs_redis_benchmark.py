#!/usr/bin/env python3
"""
embeddings_jobs_vs_redis_benchmark.py

Purpose:
- Compare embeddings pipeline throughput/latency between Redis streams (current)
  and Jobs-backed pipeline (candidate) using a fixed workload.
- Emit a JSON + Markdown report for baseline vs candidate comparison.

Notes:
- Redis mode expects the embeddings orchestrator + workers to be running.
- Jobs mode runs a lightweight, in-script 3-stage worker pipeline using Jobs.
- Jobs queues are namespaced and added to JOBS_ALLOWED_QUEUES_EMBEDDINGS for this process.

Example:
  # Redis-only baseline (requires orchestrator running)
  python Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py \
      --mode redis --job-count 200 --text-bytes 8000 --redis-url redis://localhost:6379 \
      --report-dir Docs/Performance

  # Jobs-only candidate (no external workers)
  python Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py \
      --mode jobs --job-count 200 --text-bytes 8000 --jobs-db-path ./Databases/jobs.db \
      --report-dir Docs/Performance

  # Compare (runs redis then jobs)
  python Helper_Scripts/benchmarks/embeddings_jobs_vs_redis_benchmark.py \
      --mode compare --job-count 200 --text-bytes 8000 --report-dir Docs/Performance
"""

from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

from loguru import logger
import redis.asyncio as redis

def _now_s() -> float:
    """Return a monotonic wall-clock timestamp in seconds.

    Returns:
        float: Current time from time.perf_counter(), in seconds.
    """
    return time.perf_counter()


def _percentile(values: List[float], pct: float) -> float:
    """Return the pct-th percentile from a list of floats.

    Args:
        values (List[float]): Numeric samples to evaluate.
        pct (float): Percentile to compute; clamped to [0, 100].

    Returns:
        float: Percentile value from the sorted list; returns 0.0 when values is empty.

    Notes:
        Selection uses round((pct/100) * (len(values) - 1)) on the sorted list.
    """
    if not values:
        return 0.0
    pct = max(0.0, min(100.0, pct))
    idx = round((pct / 100.0) * (len(values) - 1))
    return sorted(values)[idx]


def _estimate_chunks(text_len: int, chunk_size: int) -> int:
    """Estimate the number of chunks for a given text length and chunk size.

    Args:
        text_len (int): Length of the text in bytes/characters.
        chunk_size (int): Requested chunk size; values < 1 are treated as 1.

    Returns:
        int: Estimated chunk count (>= 1), computed via ceiling division.
    """
    size = max(1, int(chunk_size))
    return max(1, math.ceil(text_len / size))


def _as_int(value: Any, default: int = 0) -> int:
    """Best-effort int conversion for Redis payloads."""
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


async def _ensure_redis_groups(redis_url: str, queues: List[Tuple[str, str]]) -> None:
    """Ensure Redis stream consumer groups exist for the provided queues.

    Args:
        redis_url (str): Redis connection URL.
        queues (List[Tuple[str, str]]): Queue name + group name pairs to create.

    Returns:
        None

    Notes:
        BUSYGROUP errors are ignored when the group already exists.
    """
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        for queue_name, group_name in queues:
            try:
                await client.xgroup_create(queue_name, group_name, id="0", mkstream=True)
            except redis.ResponseError as exc:
                if "BUSYGROUP" in str(exc):
                    continue
                raise
    finally:
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning(f"_ensure_redis_groups: failed to close client for {redis_url}: {exc}")


async def _reset_redis_user_keys(redis_url: str, user_id: str) -> None:
    """Delete Redis bookkeeping keys for a benchmark user.

    Args:
        redis_url (str): Redis connection URL.
        user_id (str): User identifier whose active/recent job keys are reset.

    Returns:
        None
    """
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        keys = [
            f"user:active_jobs:{user_id}",
            f"user:recent_jobs:{user_id}",
        ]
        if keys:
            await client.delete(*keys)
    finally:
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning(
                f"_reset_redis_user_keys: failed to close client for {redis_url} user_id={user_id}: {exc}"
            )


async def _dump_redis_debug(
    redis_url: str,
    *,
    base_queues: List[Tuple[str, str]],
    priority_enabled: bool,
) -> None:
    """Emit Redis debug state for embeddings queues and workers.

    Args:
        redis_url (str): Redis connection URL to inspect.
        base_queues (List[Tuple[str, str]]): Base queue + group name pairs.
        priority_enabled (bool): Whether priority queues are enabled.

    Returns:
        None
    """
    client = redis.from_url(redis_url, decode_responses=True)
    try:
        paused = {}
        for stage in ("chunking", "embedding", "storage"):
            key = f"embeddings:stage:{stage}:paused"
            try:
                val = await client.get(key)
            except Exception as exc:
                logger.warning(f"_dump_redis_debug: failed to read {key} from {redis_url}: {exc}")
                val = None
            paused[stage] = str(val).lower() in ("1", "true", "yes")

        queues_to_check: List[str] = []
        for base, _group in base_queues:
            if priority_enabled:
                for suf in ("high", "normal", "low"):
                    queues_to_check.append(f"{base}:{suf}")
            queues_to_check.append(base)

        queue_lengths: Dict[str, int] = {}
        for q in queues_to_check:
            try:
                queue_lengths[q] = int(await client.xlen(q))
            except Exception as exc:
                logger.warning(f"_dump_redis_debug: failed to read xlen for {q} from {redis_url}: {exc}")
                queue_lengths[q] = -1

        group_info: Dict[str, List[Dict[str, Any]]] = {}
        for base, _group in base_queues:
            try:
                group_info[base] = await client.xinfo_groups(base)
            except Exception as exc:
                logger.warning(f"_dump_redis_debug: failed to read groups for {base} from {redis_url}: {exc}")
                group_info[base] = []

        worker_entries: List[str] = []
        cursor = 0
        while True:
            cursor, keys = await client.scan(cursor, match="worker:metrics:*", count=100)
            worker_entries.extend(keys)
            if cursor == 0 or len(worker_entries) >= 200:
                break

        logger.info(f"redis debug: redis_url={redis_url} priority_enabled={priority_enabled}")
        logger.info(f"  stage_paused={paused}")
        logger.info(f"  queue_lengths={queue_lengths}")
        if group_info:
            for base, groups in group_info.items():
                summary = ", ".join(
                    f"{g.get('name')} pending={g.get('pending')} consumers={g.get('consumers')}"
                    for g in groups
                )
                logger.info(f"  groups[{base}]={summary}")
        if worker_entries:
            logger.info(f"  worker_metrics_keys={len(worker_entries)} sample={worker_entries[:5]}")
    finally:
        try:
            await client.aclose()
        except Exception as exc:
            logger.warning(f"_dump_redis_debug: failed to close client for {redis_url}: {exc}")


def _load_corpus(corpus_path: Optional[str], job_count: int, text_bytes: int) -> List[str]:
    """Load or generate benchmark text samples.

    Args:
        corpus_path (Optional[str]): Path to a UTF-8 corpus file, or None to generate text.
        job_count (int): Number of strings to return.
        text_bytes (int): Desired byte/character length for generated text; values <= 0
            default to the base Lorem ipsum length.

    Returns:
        List[str]: List of length job_count containing text samples.

    Behavior:
        - Reads UTF-8 lines from corpus_path, stripping empty lines.
        - Cycles non-empty lines to reach job_count.
        - Raises ValueError if the corpus file is empty after filtering.
        - When corpus_path is None, generates repeated Lorem ipsum text.

    Example:
        texts = _load_corpus(None, job_count=3, text_bytes=120)
    """
    if corpus_path:
        lines: List[str] = []
        with open(corpus_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if s:
                    lines.append(s)
        if not lines:
            raise ValueError(f"Corpus file is empty: {corpus_path}")
        out: List[str] = []
        idx = 0
        while len(out) < job_count:
            out.append(lines[idx % len(lines)])
            idx += 1
        return out
    base = "Lorem ipsum dolor sit amet, consectetur adipiscing elit. "
    if text_bytes <= 0:
        text_bytes = len(base)
    repeat = max(1, int(math.ceil(text_bytes / len(base))))
    text = (base * repeat)[:text_bytes]
    return [text for _ in range(job_count)]


@dataclass
class RunResult:
    """Container for a single benchmark run's metrics and configuration.

    Fields:
        mode (str): Benchmark mode label (e.g., "redis", "jobs").
        job_count (int): Total jobs submitted for the run.
        completed (int): Number of jobs completed successfully.
        failed (int): Number of jobs that failed or were cancelled.
        total_chunks (int): Total chunks processed across completed jobs.
        duration_s (float): Run duration in seconds.
        latencies_ms (List[float]): Per-job latency measurements in milliseconds.
        timed_out (bool): True if the run exceeded the timeout before completion.
        config (Dict[str, Any]): Run configuration snapshot for reporting.
    """
    mode: str
    job_count: int
    completed: int
    failed: int
    total_chunks: int
    duration_s: float
    latencies_ms: List[float] = field(default_factory=list)
    timed_out: bool = False
    config: Dict[str, Any] = field(default_factory=dict)

    def summary(self) -> Dict[str, Any]:
        """Return a rounded summary of throughput and latency statistics.

        Computes per-second throughput for jobs and chunks, plus latency
        percentiles (p50/p95/p99) derived from latencies_ms. Rounds values to
        match report expectations (duration/throughput to 3 decimals; latency
        percentiles to 1 decimal).

        Returns:
            Dict[str, Any]: Summary metrics keyed by name.
        """
        throughput_jobs = self.completed / self.duration_s if self.duration_s > 0 else 0.0
        throughput_chunks = self.total_chunks / self.duration_s if self.duration_s > 0 else 0.0
        return {
            "mode": self.mode,
            "job_count": self.job_count,
            "completed": self.completed,
            "failed": self.failed,
            "timed_out": self.timed_out,
            "duration_s": round(self.duration_s, 3),
            "throughput_jobs_s": round(throughput_jobs, 3),
            "throughput_chunks_s": round(throughput_chunks, 3),
            "latency_p50_ms": round(_percentile(self.latencies_ms, 50), 1),
            "latency_p95_ms": round(_percentile(self.latencies_ms, 95), 1),
            "latency_p99_ms": round(_percentile(self.latencies_ms, 99), 1),
        }


def _write_reports(
    *,
    results: List[RunResult],
    report_dir: Optional[str],
    report_prefix: str,
    out_json: Optional[str],
    out_md: Optional[str],
    run_id: str,
) -> None:
    """Write JSON and Markdown benchmark reports to disk.

    Args:
        results (List[RunResult]): Run results to serialize.
        report_dir (Optional[str]): Directory for auto-generated output paths.
        report_prefix (str): Prefix for auto-generated report filenames.
        out_json (Optional[str]): Explicit JSON output path override.
        out_md (Optional[str]): Explicit Markdown output path override.
        run_id (str): Unique run identifier used in report contents/names.

    Returns:
        None
    """
    payload = {
        "run_id": run_id,
        "generated_at": time.time(),
        "results": [
            {
                "summary": r.summary(),
                "config": r.config,
                "latencies_ms": r.latencies_ms,
            }
            for r in results
        ],
    }

    if report_dir and not (out_json or out_md):
        ts = time.strftime("%Y%m%d_%H%M%S")
        report_base = f"{report_prefix}_{run_id}_{ts}"
        out_json = str(Path(report_dir) / f"{report_base}.json")
        out_md = str(Path(report_dir) / f"{report_base}.md")

    if out_json:
        Path(out_json).parent.mkdir(parents=True, exist_ok=True)
        with open(out_json, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2)
        logger.info(f"Saved JSON report to {out_json}")

    if out_md:
        Path(out_md).parent.mkdir(parents=True, exist_ok=True)
        lines: List[str] = []
        lines.append("# Embeddings Pipeline Benchmark")
        lines.append("")
        lines.append(f"- Run ID: `{run_id}`")
        lines.append(f"- Generated: `{time.strftime('%Y-%m-%d %H:%M:%S')}`")
        lines.append("")
        lines.append("## Results")
        lines.append("")
        lines.append("| Mode | Jobs | Completed | Failed | Duration (s) | Jobs/s | Chunks/s | p50 (ms) | p95 (ms) | p99 (ms) | Timed Out |")
        lines.append("| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |")
        for r in results:
            s = r.summary()
            lines.append(
                f"| {s['mode']} | {s['job_count']} | {s['completed']} | {s['failed']} | "
                f"{s['duration_s']} | {s['throughput_jobs_s']} | {s['throughput_chunks_s']} | "
                f"{s['latency_p50_ms']} | {s['latency_p95_ms']} | {s['latency_p99_ms']} | {s['timed_out']} |"
            )

        if len(results) == 2:
            a, b = results
            a_sum, b_sum = a.summary(), b.summary()
            if a_sum["throughput_jobs_s"] > 0:
                ratio = b_sum["throughput_jobs_s"] / a_sum["throughput_jobs_s"]
            else:
                ratio = 0.0
            if a_sum["latency_p95_ms"] > 0:
                p95_ratio = b_sum["latency_p95_ms"] / a_sum["latency_p95_ms"]
            else:
                p95_ratio = 0.0
            lines.append("")
            lines.append("## Comparison")
            lines.append("")
            lines.append(f"- Throughput ratio (candidate/baseline): `{ratio:.3f}`")
            lines.append(f"- p95 latency ratio (candidate/baseline): `{p95_ratio:.3f}`")

        with open(out_md, "w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")
        logger.info(f"Saved Markdown report to {out_md}")


async def _run_redis_benchmark_synthetic(
    args: argparse.Namespace,
    texts: List[str],
    run_id: str,
) -> RunResult:
    """Run a synthetic Redis Streams benchmark pipeline.

    This fallback uses Redis Streams directly instead of the legacy EmbeddingJobManager.
    It is intentionally minimal and mirrors the Jobs benchmark flow.
    """
    stream_prefix = f"bench:embeddings:{run_id}"
    chunk_stream = f"{stream_prefix}:chunking"
    embed_stream = f"{stream_prefix}:embedding"
    store_stream = f"{stream_prefix}:storage"
    group_chunk = f"bench-chunk-{run_id}"
    group_embed = f"bench-embed-{run_id}"
    group_store = f"bench-store-{run_id}"

    queues = [
        (chunk_stream, group_chunk),
        (embed_stream, group_embed),
        (store_stream, group_store),
    ]
    await _ensure_redis_groups(args.redis_url, queues)

    created_times: Dict[str, float] = {}
    done_ids: set[str] = set()
    latencies_ms: List[float] = []
    total_chunks = 0
    completed = 0
    failed = 0
    done_event = asyncio.Event()
    stop_event = asyncio.Event()
    lock = asyncio.Lock()

    async def mark_done(root_id: str, chunk_count: int, ok: bool) -> None:
        nonlocal completed, failed, total_chunks
        async with lock:
            if root_id not in created_times or root_id in done_ids:
                return
            done_ids.add(root_id)
            if ok:
                completed += 1
                total_chunks += chunk_count
                latency = (_now_s() - created_times[root_id]) * 1000.0
                latencies_ms.append(latency)
            else:
                failed += 1
            if completed + failed >= len(created_times):
                done_event.set()
                stop_event.set()

    async def _worker_loop(
        *,
        stream: str,
        group: str,
        consumer: str,
        handler,
    ) -> None:
        client = redis.from_url(args.redis_url, decode_responses=True)
        try:
            block_ms = max(1, int(args.poll_interval * 1000))
            while not stop_event.is_set():
                try:
                    resp = await client.xreadgroup(
                        group,
                        consumer,
                        streams={stream: ">"},
                        count=1,
                        block=block_ms,
                    )
                except Exception as exc:
                    logger.warning(f"redis worker error stream={stream} consumer={consumer}: {exc}")
                    await asyncio.sleep(args.poll_interval)
                    continue
                if not resp:
                    continue
                for _stream_name, messages in resp:
                    for msg_id, fields in messages:
                        try:
                            await handler(fields, client)
                        except Exception as exc:
                            logger.warning(f"redis worker handler error stream={stream} id={msg_id}: {exc}")
                        finally:
                            try:
                                await client.xack(stream, group, msg_id)
                            except Exception as exc:
                                logger.warning(f"redis xack error stream={stream} id={msg_id}: {exc}")
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

    async def chunking_handler(fields: Dict[str, Any], client) -> None:
        root_id = str(fields.get("root_id", ""))
        text_len = _as_int(fields.get("text_len"), 0)
        chunk_count = _estimate_chunks(text_len, args.chunk_size)
        if args.stage_sleep_ms[0] > 0:
            await asyncio.sleep(args.stage_sleep_ms[0] / 1000.0)
        await client.xadd(
            embed_stream,
            {"root_id": root_id, "chunk_count": str(chunk_count)},
        )

    async def embedding_handler(fields: Dict[str, Any], client) -> None:
        root_id = str(fields.get("root_id", ""))
        chunk_count = _as_int(fields.get("chunk_count"), 0)
        if args.stage_sleep_ms[1] > 0:
            await asyncio.sleep(args.stage_sleep_ms[1] / 1000.0)
        await client.xadd(
            store_stream,
            {"root_id": root_id, "chunk_count": str(chunk_count)},
        )

    async def storage_handler(fields: Dict[str, Any], client) -> None:
        root_id = str(fields.get("root_id", ""))
        chunk_count = _as_int(fields.get("chunk_count"), 0)
        if args.stage_sleep_ms[2] > 0:
            await asyncio.sleep(args.stage_sleep_ms[2] / 1000.0)
        await mark_done(root_id, chunk_count, ok=True)

    workers: List[asyncio.Task] = []
    started = _now_s()
    last_progress = started
    last_report = started
    last_done = 0
    try:
        for i in range(args.jobs_workers[0]):
            workers.append(
                asyncio.create_task(
                    _worker_loop(
                        stream=chunk_stream,
                        group=group_chunk,
                        consumer=f"bench-chunk-{i}",
                        handler=chunking_handler,
                    )
                )
            )
        for i in range(args.jobs_workers[1]):
            workers.append(
                asyncio.create_task(
                    _worker_loop(
                        stream=embed_stream,
                        group=group_embed,
                        consumer=f"bench-embed-{i}",
                        handler=embedding_handler,
                    )
                )
            )
        for i in range(args.jobs_workers[2]):
            workers.append(
                asyncio.create_task(
                    _worker_loop(
                        stream=store_stream,
                        group=group_store,
                        consumer=f"bench-store-{i}",
                        handler=storage_handler,
                    )
                )
            )

        client = redis.from_url(args.redis_url, decode_responses=True)
        try:
            for text in texts:
                root_id = uuid.uuid4().hex
                created_times[root_id] = _now_s()
                await client.xadd(
                    chunk_stream,
                    {
                        "root_id": root_id,
                        "text_len": str(len(text)),
                        "chunk_size": str(args.chunk_size),
                        "chunk_overlap": str(args.chunk_overlap),
                    },
                )
        finally:
            try:
                await client.aclose()
            except Exception:
                pass

        while not done_event.is_set():
            now = _now_s()
            if (now - started) > args.timeout_seconds:
                stop_event.set()
                break
            done_count = completed + failed
            if done_count != last_done:
                last_done = done_count
                last_progress = now
            if args.progress_log_every > 0 and (now - last_report) >= args.progress_log_every:
                logger.info(
                    f"redis progress: done={done_count}/{len(created_times)} "
                    f"completed={completed} failed={failed}"
                )
                last_report = now
            if args.no_progress_seconds > 0 and (now - last_progress) >= args.no_progress_seconds:
                logger.warning("redis progress stalled: no completions observed")
                stop_event.set()
                break
            await asyncio.sleep(args.poll_interval)
    finally:
        stop_event.set()
        for task in workers:
            task.cancel()
        await asyncio.gather(*workers, return_exceptions=True)

    duration = _now_s() - started if created_times else 0.0
    timed_out = (completed + failed) < len(created_times)
    return RunResult(
        mode="redis",
        job_count=len(created_times),
        completed=completed,
        failed=failed,
        total_chunks=total_chunks,
        duration_s=duration,
        latencies_ms=latencies_ms,
        timed_out=timed_out,
        config={
            "redis_url": args.redis_url,
            "redis_streams": [chunk_stream, embed_stream, store_stream],
            "jobs_workers": args.jobs_workers,
            "stage_sleep_ms": args.stage_sleep_ms,
            "job_count": args.job_count,
            "text_bytes": args.text_bytes,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "poll_interval": args.poll_interval,
            "timeout_seconds": args.timeout_seconds,
        },
    )


async def _run_redis_benchmark(args: argparse.Namespace, texts: List[str], run_id: str) -> RunResult:
    """Run the Redis-backed embeddings pipeline benchmark.

    Args:
        args (argparse.Namespace): Benchmark options (redis_url, user_id, user_tier,
            job_count, text_bytes, chunk_size, chunk_overlap, poll_interval,
            timeout_seconds, progress_log_every, no_progress_seconds).
        texts (List[str]): Input text samples to enqueue for processing.
        run_id (str): Unique run identifier for tagging jobs/metrics.

    Returns:
        RunResult: Metrics summary for the Redis pipeline run.

    Side Effects:
        Ensures Redis consumer groups exist, submits jobs via EmbeddingJobManager,
        polls job status until completion or timeout, and emits progress logs.
    """
    try:
        from tldw_Server_API.app.core.Embeddings.job_manager import (
            EmbeddingJobManager,
            JobManagerConfig,
            JobPriority,
            UserTier,
        )
        from tldw_Server_API.app.core.Embeddings.queue_schemas import ChunkingConfig, JobStatus
    except Exception as e:
        logger.warning(
            "Legacy Redis embeddings pipeline is unavailable; "
            "falling back to synthetic Redis Streams benchmark."
        )
        return await _run_redis_benchmark_synthetic(args, texts, run_id)

    user_tier = UserTier(args.user_tier)
    max_jobs = max(10, args.job_count * 2)
    quota = max(10000, args.job_count * _estimate_chunks(args.text_bytes, args.chunk_size) * 2)
    cfg = JobManagerConfig(
        redis_url=args.redis_url,
        max_concurrent_jobs_per_user={
            UserTier.FREE: max_jobs,
            UserTier.PREMIUM: max_jobs,
            UserTier.ENTERPRISE: max_jobs,
        },
        daily_quota_per_user={
            UserTier.FREE: quota,
            UserTier.PREMIUM: quota,
            UserTier.ENTERPRISE: quota,
        },
    )
    priority_enabled = str(os.getenv("EMBEDDINGS_PRIORITY_ENABLED", "false")).lower() in ("1", "true", "yes")
    base_queues = [
        (cfg.chunking_queue, "chunking-workers"),
        (cfg.embedding_queue, "embedding-workers"),
        (cfg.storage_queue, "storage-workers"),
    ]
    ensure_queues = list(base_queues)
    if priority_enabled:
        for base, group in base_queues:
            ensure_queues.extend(
                [
                    (f"{base}:high", group),
                    (f"{base}:normal", group),
                    (f"{base}:low", group),
                ]
            )
    await _ensure_redis_groups(args.redis_url, ensure_queues)
    manager = EmbeddingJobManager(cfg)
    await manager.initialize()

    created: Dict[str, float] = {}
    job_text_len: Dict[str, int] = {}
    latencies_ms: List[float] = []
    total_chunks = 0
    completed = 0
    failed = 0
    last_status: Dict[str, str] = {}

    try:
        for idx, text in enumerate(texts):
            job_id = await manager.create_job(
                media_id=idx + 1,
                user_id=args.user_id,
                user_tier=user_tier,
                content=text,
                content_type="text",
                chunking_config=ChunkingConfig(
                    chunk_size=args.chunk_size,
                    overlap=args.chunk_overlap,
                    separator="\n",
                ),
                priority=JobPriority.NORMAL,
                metadata={"bench_run": run_id},
            )
            created[job_id] = _now_s()
            job_text_len[job_id] = len(text)

        started = _now_s()
        last_progress = started
        last_report = started
        dumped_debug = False
        done: Dict[str, str] = {}
        while len(done) < len(created):
            if _now_s() - started > args.timeout_seconds:
                break
            status_counts: Dict[str, int] = {}
            for job_id in created.keys():
                if job_id in done:
                    continue
                info = await manager.get_job_status(job_id)
                if not info:
                    continue
                status = info.status
                status_value = status.value
                status_counts[status_value] = status_counts.get(status_value, 0) + 1
                if last_status.get(job_id) != status_value:
                    last_status[job_id] = status_value
                    if status != JobStatus.PENDING:
                        last_progress = _now_s()
                if status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
                    done[job_id] = status_value
                    latency = (_now_s() - created[job_id]) * 1000.0
                    latencies_ms.append(latency)
                    if status == JobStatus.COMPLETED:
                        completed += 1
                        total_chunks += int(info.total_chunks or 0) or _estimate_chunks(job_text_len.get(job_id, 0), args.chunk_size)
                    else:
                        failed += 1
            now = _now_s()
            if args.progress_log_every > 0 and (now - last_report) >= args.progress_log_every:
                status_line = ", ".join(f"{k}={v}" for k, v in sorted(status_counts.items()))
                logger.info(
                    f"redis progress: done={len(done)}/{len(created)} "
                    f"status_counts=[{status_line}]"
                )
                last_report = now
            if args.no_progress_seconds > 0 and (now - last_progress) >= args.no_progress_seconds:
                logger.warning(
                    "redis progress stalled: no jobs left pending for too long; "
                    "check orchestrator/workers and stage pause flags."
                )
                if not dumped_debug:
                    dumped_debug = True
                    await _dump_redis_debug(
                        args.redis_url,
                        base_queues=base_queues,
                        priority_enabled=priority_enabled,
                    )
                break
            await asyncio.sleep(args.poll_interval)
    finally:
        await manager.close()

    duration = _now_s() - min(created.values()) if created else 0.0
    timed_out = (completed + failed) < len(created)
    return RunResult(
        mode="redis",
        job_count=len(created),
        completed=completed,
        failed=failed,
        total_chunks=total_chunks,
        duration_s=duration,
        latencies_ms=latencies_ms,
        timed_out=timed_out,
        config={
            "redis_url": args.redis_url,
            "job_count": args.job_count,
            "text_bytes": args.text_bytes,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "poll_interval": args.poll_interval,
            "timeout_seconds": args.timeout_seconds,
            "priority_enabled": priority_enabled,
        },
    )


async def _run_jobs_benchmark(args: argparse.Namespace, texts: List[str], run_id: str) -> RunResult:
    """Run the Jobs-based three-stage benchmark pipeline.

    Args:
        args (argparse.Namespace): Benchmark options (jobs_queues, jobs_db_url/jobs_db_path,
            jobs_workers, stage_sleep_ms, timeout_seconds, chunk_size, chunk_overlap,
            job_count, text_bytes, jobs_owner_id).
        texts (List[str]): Input text samples to enqueue for processing.
        run_id (str): Unique run identifier for tagging jobs/metrics.

    Returns:
        RunResult: Metrics summary for the Jobs pipeline run.

    Side Effects:
        Creates a JobManager, sets JOBS_ALLOWED_QUEUES_EMBEDDINGS, starts WorkerSDK
        workers, and submits jobs via jm.create_job. Uses _estimate_chunks/_now_s and
        waits with a timeout; timeouts yield a RunResult marked timed_out.
    """
    from tldw_Server_API.app.core.Jobs.manager import JobManager
    from tldw_Server_API.app.core.Jobs.worker_sdk import WorkerConfig, WorkerSDK

    queues = [q.strip() for q in args.jobs_queues.split(",") if q.strip()]
    if len(queues) != 3:
        raise ValueError("jobs_queues must have exactly 3 comma-separated queue names")
    chunk_queue, embed_queue, store_queue = queues
    os.environ["JOBS_ALLOWED_QUEUES_EMBEDDINGS"] = ",".join(queues)

    if args.jobs_db_url:
        jm = JobManager(db_url=args.jobs_db_url)
    elif args.jobs_db_path:
        jm = JobManager(db_path=Path(args.jobs_db_path))
    else:
        jm = JobManager()

    created_times: Dict[str, float] = {}
    done_ids: set[str] = set()
    latencies_ms: List[float] = []
    total_chunks = 0
    completed = 0
    failed = 0
    done_event = asyncio.Event()
    lock = asyncio.Lock()

    class _BenchStageError(Exception):
        """Non-retryable benchmark stage failure.

        The `retryable` attribute signals whether callers should retry this
        exception; keep it False for deterministic stage failures and raise
        it to abort the current stage without retries.
        """
        retryable = False

    async def mark_done(root_id: str, chunk_count: int, ok: bool) -> None:
        nonlocal completed, failed, total_chunks
        async with lock:
            if root_id not in created_times or root_id in done_ids:
                return
            done_ids.add(root_id)
            if ok:
                completed += 1
                total_chunks += chunk_count
                latency = (_now_s() - created_times[root_id]) * 1000.0
                latencies_ms.append(latency)
            else:
                failed += 1
            if completed + failed >= len(created_times):
                done_event.set()

    async def chunking_handler(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload") or {}
        root_id = str(payload.get("root_id", ""))
        text_len = int(payload.get("text_len") or 0)
        chunk_count = _estimate_chunks(text_len, args.chunk_size)
        if args.stage_sleep_ms[0] > 0:
            await asyncio.sleep(args.stage_sleep_ms[0] / 1000.0)
        try:
            jm.create_job(
                domain="embeddings",
                queue=embed_queue,
                job_type="bench_embedding",
                payload={"root_id": root_id, "chunk_count": chunk_count, "bench_run": run_id},
                owner_user_id=args.jobs_owner_id,
            )
        except Exception as exc:
            await mark_done(root_id, chunk_count, ok=False)
            raise _BenchStageError(str(exc)) from exc
        return {"chunk_count": chunk_count}

    async def embedding_handler(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload") or {}
        root_id = str(payload.get("root_id", ""))
        chunk_count = int(payload.get("chunk_count") or 0)
        if args.stage_sleep_ms[1] > 0:
            await asyncio.sleep(args.stage_sleep_ms[1] / 1000.0)
        try:
            jm.create_job(
                domain="embeddings",
                queue=store_queue,
                job_type="bench_storage",
                payload={"root_id": root_id, "chunk_count": chunk_count, "bench_run": run_id},
                owner_user_id=args.jobs_owner_id,
            )
        except Exception as exc:
            await mark_done(root_id, chunk_count, ok=False)
            raise _BenchStageError(str(exc)) from exc
        return {"chunk_count": chunk_count}

    async def storage_handler(job: Dict[str, Any]) -> Dict[str, Any]:
        payload = job.get("payload") or {}
        root_id = str(payload.get("root_id", ""))
        chunk_count = int(payload.get("chunk_count") or 0)
        if args.stage_sleep_ms[2] > 0:
            await asyncio.sleep(args.stage_sleep_ms[2] / 1000.0)
        await mark_done(root_id, chunk_count, ok=True)
        return {"chunk_count": chunk_count}

    workers: List[Tuple[WorkerSDK, asyncio.Task]] = []
    started = _now_s()
    try:
        for i in range(args.jobs_workers[0]):
            cfg = WorkerConfig(domain="embeddings", queue=chunk_queue, worker_id=f"bench-chunk-{i}")
            sdk = WorkerSDK(jm, cfg)
            workers.append((sdk, asyncio.create_task(sdk.run(handler=chunking_handler))))
        for i in range(args.jobs_workers[1]):
            cfg = WorkerConfig(domain="embeddings", queue=embed_queue, worker_id=f"bench-embed-{i}")
            sdk = WorkerSDK(jm, cfg)
            workers.append((sdk, asyncio.create_task(sdk.run(handler=embedding_handler))))
        for i in range(args.jobs_workers[2]):
            cfg = WorkerConfig(domain="embeddings", queue=store_queue, worker_id=f"bench-store-{i}")
            sdk = WorkerSDK(jm, cfg)
            workers.append((sdk, asyncio.create_task(sdk.run(handler=storage_handler))))

        for text in texts:
            root_id = uuid.uuid4().hex
            created_times[root_id] = _now_s()
            jm.create_job(
                domain="embeddings",
                queue=chunk_queue,
                job_type="bench_chunking",
                payload={
                    "root_id": root_id,
                    "text_len": len(text),
                    "chunk_size": args.chunk_size,
                    "chunk_overlap": args.chunk_overlap,
                    "bench_run": run_id,
                },
                owner_user_id=args.jobs_owner_id,
            )

        try:
            await asyncio.wait_for(done_event.wait(), timeout=args.timeout_seconds)
        except asyncio.TimeoutError:
            pass
    finally:
        for sdk, task in workers:
            sdk.stop()
            task.cancel()
        await asyncio.gather(*(t for _, t in workers), return_exceptions=True)

    duration = _now_s() - started
    timed_out = (completed + failed) < len(created_times)
    return RunResult(
        mode="jobs",
        job_count=len(created_times),
        completed=completed,
        failed=failed,
        total_chunks=total_chunks,
        duration_s=duration,
        latencies_ms=latencies_ms,
        timed_out=timed_out,
        config={
            "jobs_db_url": args.jobs_db_url,
            "jobs_db_path": args.jobs_db_path,
            "jobs_queues": args.jobs_queues,
            "jobs_workers": args.jobs_workers,
            "stage_sleep_ms": args.stage_sleep_ms,
            "job_count": args.job_count,
            "text_bytes": args.text_bytes,
            "chunk_size": args.chunk_size,
            "chunk_overlap": args.chunk_overlap,
            "timeout_seconds": args.timeout_seconds,
        },
    )


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse CLI arguments for the embeddings jobs-vs-redis benchmark.

    Args:
        argv: Optional argv override for testing or programmatic use.

    Returns:
        argparse.Namespace: Parsed benchmark configuration options.
    """
    parser = argparse.ArgumentParser(description="Embeddings pipeline benchmark: Jobs vs Redis")
    parser.add_argument("--mode", choices=("redis", "jobs", "compare"), default="compare")
    parser.add_argument("--job-count", type=int, default=200)
    parser.add_argument("--text-bytes", type=int, default=8000)
    parser.add_argument("--chunk-size", type=int, default=1000)
    parser.add_argument("--chunk-overlap", type=int, default=200)
    parser.add_argument("--corpus-file", default=None, help="Optional newline-delimited text corpus")
    parser.add_argument("--timeout-seconds", type=float, default=1800)
    parser.add_argument("--poll-interval", type=float, default=1.0)
    parser.add_argument("--progress-log-every", type=float, default=30.0, help="Seconds between progress logs")
    parser.add_argument("--no-progress-seconds", type=float, default=120.0, help="Abort if no progress for this long")

    parser.add_argument("--redis-url", default=os.getenv("REDIS_URL", "redis://localhost:6379"))
    parser.add_argument("--user-id", default="bench_user")
    parser.add_argument("--auto-user-id", action="store_true", default=True, help="Use a unique bench user id per run")
    parser.add_argument("--no-auto-user-id", dest="auto_user_id", action="store_false", help="Disable auto user id")
    parser.add_argument("--user-tier", choices=("free", "premium", "enterprise"), default="enterprise")
    parser.add_argument("--reset-user-keys", action="store_true", default=False, help="Delete Redis active/recent job keys for user_id before run")

    parser.add_argument("--jobs-db-url", default=None)
    parser.add_argument("--jobs-db-path", default=None)
    parser.add_argument("--jobs-owner-id", default="bench_user")
    parser.add_argument("--jobs-queues", default="bench_chunking,bench_embedding,bench_storage")
    parser.add_argument("--jobs-workers", nargs=3, type=int, default=[2, 4, 1], metavar=("CHUNK", "EMBED", "STORE"))
    parser.add_argument("--stage-sleep-ms", nargs=3, type=int, default=[0, 0, 0], metavar=("CHUNK", "EMBED", "STORE"))

    parser.add_argument("--report-dir", default=None)
    parser.add_argument("--report-prefix", default="embeddings_jobs_vs_redis")
    parser.add_argument("--out-json", default=None)
    parser.add_argument("--out-md", default=None)

    return parser.parse_args(argv)


async def _main_async(args: argparse.Namespace) -> int:
    """Run the async benchmark workflow for the selected mode(s).

    Executes Redis/jobs runs, prints progress, and writes report files.

    Args:
        args: Parsed CLI arguments controlling benchmark behavior.

    Returns:
        int: Process exit code (0 on success).
    """
    texts = _load_corpus(args.corpus_file, args.job_count, args.text_bytes)
    run_id = uuid.uuid4().hex[:12]
    if args.auto_user_id and args.user_id == "bench_user":
        args.user_id = f"bench_user_{run_id}"
    if args.auto_user_id and args.jobs_owner_id == "bench_user":
        args.jobs_owner_id = args.user_id
    results: List[RunResult] = []

    if args.mode in {"redis", "compare"}:
        if args.reset_user_keys:
            await _reset_redis_user_keys(args.redis_url, args.user_id)
        logger.info("Running redis baseline...")
        results.append(await _run_redis_benchmark(args, texts, run_id))
    if args.mode in {"jobs", "compare"}:
        logger.info("Running jobs candidate...")
        results.append(await _run_jobs_benchmark(args, texts, run_id))

    for res in results:
        s = res.summary()
        logger.info(
            f"{s['mode']}: jobs={s['job_count']} completed={s['completed']} failed={s['failed']} "
            f"duration={s['duration_s']}s jobs/s={s['throughput_jobs_s']} chunks/s={s['throughput_chunks_s']} "
            f"p50={s['latency_p50_ms']}ms p95={s['latency_p95_ms']}ms timed_out={s['timed_out']}"
        )

    _write_reports(
        results=results,
        report_dir=args.report_dir,
        report_prefix=args.report_prefix,
        out_json=args.out_json,
        out_md=args.out_md,
        run_id=run_id,
    )
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Run the synchronous CLI entrypoint for the benchmark script.

    Calls asyncio.run on _main_async and converts KeyboardInterrupt/Exception
    into conventional exit codes.

    Args:
        argv: Optional argv override for testing or programmatic use.

    Returns:
        int: Process exit code (0 on success, 130 on interrupt, 1 on failure).
    """
    args = _parse_args(argv)
    try:
        return asyncio.run(_main_async(args))
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logger.error(f"Benchmark failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
