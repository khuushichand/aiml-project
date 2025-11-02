from __future__ import annotations

import os
import asyncio
from typing import Optional, List
from loguru import logger

from tldw_Server_API.app.core.Jobs.manager import JobManager


async def run_jobs_crypto_rotate(stop_event: asyncio.Event) -> None:
    """Periodic background rotation of encrypted JSON envelopes in Jobs.

    Controlled by env:
      - JOBS_CRYPTO_ROTATE_SERVICE_ENABLED (true/false)
      - JOBS_CRYPTO_ROTATE_INTERVAL_SEC (default 60)
      - JOBS_CRYPTO_ROTATE_BATCH (default 200)
      - JOBS_CRYPTO_ROTATE_OLD_KEY, JOBS_CRYPTO_ROTATE_NEW_KEY (base64 keys)
      - JOBS_CRYPTO_ROTATE_DOMAIN/QUEUE/JOB_TYPE filters
      - JOBS_CRYPTO_ROTATE_FIELDS (comma: payload,result)
    """
    interval = float(os.getenv("JOBS_CRYPTO_ROTATE_INTERVAL_SEC", "60") or "60")
    batch = int(os.getenv("JOBS_CRYPTO_ROTATE_BATCH", "200") or "200")
    db_url = os.getenv("JOBS_DB_URL", "")
    backend = "postgres" if db_url.startswith("postgres") else None
    old_key = os.getenv("JOBS_CRYPTO_ROTATE_OLD_KEY", "").strip()
    new_key = os.getenv("JOBS_CRYPTO_ROTATE_NEW_KEY", "").strip()
    domain = os.getenv("JOBS_CRYPTO_ROTATE_DOMAIN", "").strip() or None
    queue = os.getenv("JOBS_CRYPTO_ROTATE_QUEUE", "").strip() or None
    job_type = os.getenv("JOBS_CRYPTO_ROTATE_JOB_TYPE", "").strip() or None
    fields_env = os.getenv("JOBS_CRYPTO_ROTATE_FIELDS", "payload,result").strip()
    fields: List[str] = [f.strip() for f in fields_env.split(",") if f.strip() in {"payload", "result"}]
    if not fields:
        fields = ["payload", "result"]
    jm = JobManager(backend=backend, db_url=db_url)
    logger.info("Jobs Crypto Rotate Service: started (interval={}s, batch={})", interval, batch)
    try:
        while not stop_event.is_set():
            try:
                if not old_key or not new_key:
                    await asyncio.sleep(interval)
                    continue
                affected = jm.rotate_encryption_keys(
                    domain=domain,
                    queue=queue,
                    job_type=job_type,
                    old_key_b64=old_key,
                    new_key_b64=new_key,
                    fields=fields,
                    limit=batch,
                    dry_run=False,
                )
                if affected:
                    logger.info("Jobs Crypto Rotate Service: re-encrypted {} rows", affected)
            except Exception as e:
                logger.warning(f"Jobs Crypto Rotate Service error: {e}")
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
    except asyncio.TimeoutError:
        # normal wake-up
        pass
    except Exception as e:
        logger.warning(f"Jobs Crypto Rotate Service stopped with error: {e}")
    finally:
        logger.info("Jobs Crypto Rotate Service: stopped")
