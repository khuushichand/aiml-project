from __future__ import annotations

import asyncio
import hmac
import hashlib
import json
import os
from typing import Optional

from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


def _truthy(v: Optional[str]) -> bool:
    return str(v or "").lower() in {"1","true","yes","y","on"}


def _sign(secret: bytes, payload: bytes) -> str:
    return hmac.new(secret, payload, hashlib.sha256).hexdigest()


async def run_jobs_webhooks_worker(stop_event: Optional[asyncio.Event] = None) -> None:
    """Emit signed webhooks on job.completed/job.failed from job_events outbox.

    Env:
      - JOBS_WEBHOOKS_ENABLED=true
      - JOBS_WEBHOOKS_URL=https://...
      - JOBS_WEBHOOKS_SECRET_KEYS=key1,key2 (rotating; first used for signing)
      - JOBS_WEBHOOKS_INTERVAL_SEC=1.0
      - JOBS_WEBHOOKS_TIMEOUT_SEC=5
    Headers:
      - X-Jobs-Event: job.completed|job.failed
      - X-Jobs-Event-Id: outbox id
      - X-Jobs-Timestamp: epoch seconds
      - X-Jobs-Signature: v1=<hex>
    Body: JSON of {event, attrs, job}
    """
    url = os.getenv("JOBS_WEBHOOKS_URL")
    if not (_truthy(os.getenv("JOBS_WEBHOOKS_ENABLED")) and url):
        logger.info("Jobs webhooks worker disabled")
        return
    try:
        import httpx
    except Exception:
        logger.info("httpx not available; Jobs webhooks worker disabled")
        return
    secrets = [(s.strip()).encode("utf-8") for s in (os.getenv("JOBS_WEBHOOKS_SECRET_KEYS", "").split(",")) if s.strip()]
    if not secrets:
        logger.warning("Jobs webhooks enabled but no secrets configured; refusing to start")
        return
    interval = float(os.getenv("JOBS_WEBHOOKS_INTERVAL_SEC", "1.0") or "1.0")
    timeout_s = float(os.getenv("JOBS_WEBHOOKS_TIMEOUT_SEC", "5") or "5")
    jm = JobManager()
    after_id = 0
    # Resume from last seen id if provided
    try:
        after_id = int(os.getenv("JOBS_WEBHOOKS_AFTER_ID", "0") or 0)
    except Exception:
        after_id = 0
    logger.info("Starting Jobs webhooks worker")
    async with httpx.AsyncClient(timeout=timeout_s) as client:
        while True:
            if stop_event and stop_event.is_set():
                logger.info("Stopping Jobs webhooks worker on shutdown signal")
                return
            conn = jm._connect()
            try:
                rows = []
                if jm.backend == "postgres":
                    with jm._pg_cursor(conn) as cur:
                        cur.execute(
                            "SELECT id, event_type, attrs_json, job_id, domain, queue, job_type, created_at FROM job_events WHERE id > %s AND event_type IN ('job.completed','job.failed') ORDER BY id ASC LIMIT 200",
                            (int(after_id),),
                        )
                        rows = cur.fetchall() or []
                else:
                    rows = conn.execute(
                        "SELECT id, event_type, attrs_json, job_id, domain, queue, job_type, created_at FROM job_events WHERE id > ? AND event_type IN ('job.completed','job.failed') ORDER BY id ASC LIMIT 200",
                        (int(after_id),),
                    ).fetchall() or []
                if not rows:
                    await asyncio.sleep(interval)
                    continue
                for r in rows:
                    try:
                        if isinstance(r, dict):
                            eid = int(r.get("id")); et = str(r.get("event_type")); attrs = r.get("attrs_json"); job_id = r.get("job_id"); dom=r.get("domain"); que=r.get("queue"); jt=r.get("job_type"); ts=str(r.get("created_at"))
                        else:
                            eid = int(r[0]); et = str(r[1]); attrs = r[2]; job_id = r[3]; dom=r[4]; que=r[5]; jt=r[6]; ts=str(r[7])
                        # Construct payload
                        job_stub = {"id": job_id, "domain": dom, "queue": que, "job_type": jt}
                        try:
                            attrs_obj = json.loads(attrs) if isinstance(attrs, str) else (attrs or {})
                        except Exception:
                            attrs_obj = {}
                        body = json.dumps({"event": et, "attrs": attrs_obj, "job": job_stub, "created_at": ts}).encode("utf-8")
                        # Sign
                        import time
                        ts_epoch = int(time.time())
                        sig = _sign(secrets[0], str(ts_epoch).encode("utf-8") + b"." + body)
                        headers = {
                            "X-Jobs-Event": et,
                            "X-Jobs-Event-Id": str(eid),
                            "X-Jobs-Timestamp": str(ts_epoch),
                            "X-Jobs-Signature": f"v1={sig}",
                            "Content-Type": "application/json",
                        }
                        resp = await client.post(url, headers=headers, content=body)
                        if resp.status_code >= 400:
                            logger.debug(f"Jobs webhook delivery failed {resp.status_code}: {resp.text}")
                        after_id = eid
                    except Exception as e:
                        logger.debug(f"Jobs webhook send error: {e}")
                # Persist after_id optionally via env or omit for simplicity
            finally:
                try:
                    conn.close()
                except Exception:
                    pass
