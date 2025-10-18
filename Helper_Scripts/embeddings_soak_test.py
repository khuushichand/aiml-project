#!/usr/bin/env python3
"""
Embeddings soak test harness

Drives a steady stream of synthetic jobs into the embeddings pipeline and
observes queue age/rates via the orchestrator summary endpoint (or direct Redis
fallback) to validate SLOs over time.

Usage:
  python Helper_Scripts/embeddings_soak_test.py --duration 300 --rps 20 --redis redis://localhost:6379 \
      --queue embeddings:chunking --summary http://127.0.0.1:8000/api/v1/embeddings/orchestrator/summary

Notes:
  - Expects the API server + orchestrator running for best observability.
  - If --summary is not provided, will compute simplified metrics via Redis.
  - This is a lightweight harness intended for CI/dev. For production load
    testing, consider a dedicated tool.
"""

import argparse
import asyncio
import json
import os
import random
import sys
import time
from typing import Optional


async def _xadd_loop(redis, queue: str, rps: float, stop_ts: float):
    wait = 1.0 / max(0.1, rps)
    sent = 0
    while time.time() < stop_ts:
        payload = {
            "job_id": f"soak-{int(time.time()*1000)}-{random.randint(0, 9999)}",
            "user_id": "admin",
            "media_id": random.randint(1, 1_000_000),
            "priority": 50,
            "user_tier": "pro",
            "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "retry_count": 0,
            "max_retries": 3,
            "content": "lorem ipsum " * 50,
            "chunking_config": {"chunk_size": 1000, "overlap": 100, "separator": "\n"},
        }
        try:
            await redis.xadd(queue, payload)
        except Exception as e:
            print(f"xadd error: {e}", file=sys.stderr)
        sent += 1
        await asyncio.sleep(wait)
    return sent


async def _fetch_summary_http(url: str) -> Optional[dict]:
    try:
        import httpx  # type: ignore
    except Exception:
        return None
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(url)
            if r.status_code == 200:
                return r.json()
    except Exception:
        return None
    return None


async def _summarize(redis, summary_url: Optional[str]):
    if summary_url:
        data = await _fetch_summary_http(summary_url)
        if data:
            return {
                "queue_age": data.get("ages", {}).get("embeddings:chunking", 0.0),
                "dlq_total": sum((data.get("dlq") or {}).values()),
                "queues": data.get("queues"),
            }
    # Fallback: compute minimal stats via Redis
    try:
        age_items = await redis.xrange("embeddings:chunking", "-", "+", count=1)
        if age_items:
            first_id = age_items[0][0]
            ts = float(first_id.split("-", 1)[0]) / 1000.0
            age = max(0.0, time.time() - ts)
        else:
            age = 0.0
    except Exception:
        age = 0.0
    try:
        dlq = await redis.xlen("embeddings:chunking:dlq")
    except Exception:
        dlq = 0
    try:
        qlen = await redis.xlen("embeddings:chunking")
    except Exception:
        qlen = 0
    return {"queue_age": age, "dlq_total": dlq, "queues": {"embeddings:chunking": qlen}}


async def main_async(args):
    try:
        import redis.asyncio as aioredis  # type: ignore
    except Exception:
        print("redis-py not available. pip install redis", file=sys.stderr)
        return 2

    redis_url = args.redis or os.getenv("REDIS_URL", "redis://localhost:6379")
    conn = aioredis.from_url(redis_url, decode_responses=True)
    try:
        import inspect as _inspect
        if _inspect.isawaitable(conn):
            conn = await conn
    except Exception:
        pass
    redis = conn
    stop_ts = time.time() + args.duration

    prod = asyncio.create_task(_xadd_loop(redis, args.queue, args.rps, stop_ts))
    # Periodically print summary
    while time.time() < stop_ts:
        data = await _summarize(redis, args.summary)
        print(json.dumps({"ts": int(time.time()), **data}))
        await asyncio.sleep(args.interval)

    sent = await prod
    print(f"Sent {sent} messages to {args.queue}")
    await redis.close()
    return 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--duration", type=int, default=120, help="Duration in seconds")
    p.add_argument("--rps", type=float, default=5.0, help="Target messages per second")
    p.add_argument("--interval", type=float, default=5.0, help="Summary print interval")
    p.add_argument("--queue", type=str, default="embeddings:chunking")
    p.add_argument("--redis", type=str, default=None, help="Redis URL (override REDIS_URL)")
    p.add_argument("--summary", type=str, default=None, help="API summary endpoint URL")
    args = p.parse_args()
    rc = asyncio.run(main_async(args))
    raise SystemExit(rc)


if __name__ == "__main__":  # pragma: no cover
    main()
