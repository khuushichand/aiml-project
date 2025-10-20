"""
Re-embed request consumer: scans the embeddings:reembed:requests stream
and schedules re-embed tasks (minimal skeleton).

Behavior:
- Poll XRANGE for up to N items
- For each, emit to embeddings:reembed:scheduled (echo fields + scheduled_at)
- Delete processed items from the request stream

This is a lightweight placeholder; a full implementation would fetch original
content/chunks and enqueue embedding jobs per policy.
"""

import asyncio
import os
from datetime import datetime
from typing import Dict, Any, List, Tuple

from loguru import logger
import redis.asyncio as aioredis

from tldw_Server_API.app.core.Infrastructure.redis_factory import (
    create_async_redis_client,
    ensure_async_client_closed,
)


REQUEST_STREAM = os.getenv("REEMBED_REQUEST_STREAM", "embeddings:reembed:requests")
SCHEDULED_STREAM = os.getenv("REEMBED_SCHEDULED_STREAM", "embeddings:reembed:scheduled")
POLL_INTERVAL_MS = int(os.getenv("REEMBED_POLL_INTERVAL_MS", "1000") or 1000)
BATCH = int(os.getenv("REEMBED_BATCH", "50") or 50)


async def _get_client():
    return await create_async_redis_client(context="reembed_consumer")


async def process_once(client: aioredis.Redis, max_items: int = BATCH) -> int:
    """Process up to max_items from request stream. Returns count processed."""
    try:
        entries: List[Tuple[str, Dict[str, Any]]] = await client.xrange(REQUEST_STREAM, min='-', max='+', count=max_items)
    except Exception as e:
        logger.debug(f"XRANGE failed: {e}")
        return 0
    count = 0
    for eid, fields in entries:
        try:
            fields = dict(fields or {})
            fields["scheduled_at"] = datetime.utcnow().isoformat()
            try:
                enc = {k: (v if isinstance(v, str) else __import__('json').dumps(v)) for k, v in fields.items()}
            except Exception:
                enc = {k: str(v) for k, v in fields.items()}
            await client.xadd(SCHEDULED_STREAM, enc)
        except Exception as e:
            logger.debug(f"Failed to xadd scheduled: {e}")
            continue
        try:
            await client.xdel(REQUEST_STREAM, eid)
        except Exception:
            pass
        count += 1
    return count


async def run():
    client = await _get_client()
    logger.info("Starting re-embed consumer")
    try:
        while True:
            n = await process_once(client)
            if n == 0:
                await asyncio.sleep(max(0.01, POLL_INTERVAL_MS / 1000.0))
    finally:
        await ensure_async_client_closed(client)


if __name__ == "__main__":
    asyncio.run(run())
