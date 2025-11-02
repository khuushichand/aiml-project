"""
Minimal example worker using batch_* APIs and adaptive leases.

Usage:
  export TEST_MODE=true AUTH_MODE=single_user
  # Enable adaptive leases so lease_seconds=0 computes from recent P95 with headroom
  export JOBS_ADAPTIVE_LEASE_ENABLE=true
  # Optional: enable counters to see gauge updates faster
  export JOBS_COUNTERS_ENABLED=true

  python Samples/Jobs/batch_worker_example.py

Notes:
  - By passing lease_seconds=0, JobManager acquires with an adaptive lease.
  - The example uses batch_renew_leases and batch_complete_jobs to reduce
    round-trips at higher throughputs.
"""

from __future__ import annotations

import os
import time
from typing import List, Dict, Any

from tldw_Server_API.app.core.Jobs.manager import JobManager


def main():
    # Use Postgres if JOBS_DB_URL points to a postgres DSN; else SQLite
    db_url = os.getenv("JOBS_DB_URL")
    backend = "postgres" if (db_url and db_url.startswith("postgres")) else None
    jm = JobManager(backend=backend, db_url=db_url)

    domain = os.getenv("JOBS_SAMPLE_DOMAIN", "chatbooks")
    queue = os.getenv("JOBS_SAMPLE_QUEUE", "default")
    worker_id = os.getenv("HOSTNAME", "worker-1")

    # Seed a few jobs if none exist
    existing = jm.list_jobs(domain=domain, queue=queue, status="queued", limit=1)
    if not existing:
        for i in range(5):
            jm.create_job(
                domain=domain,
                queue=queue,
                job_type="sample",
                payload={"i": i},
                owner_user_id="demo",
                priority=5,
            )

    print("Starting batch worker. Press Ctrl+C to stop.")
    try:
        while True:
            # Acquire up to N jobs with adaptive leases (lease_seconds=0)
            jobs: List[Dict[str, Any]] = jm.acquire_next_jobs(
                domain=domain,
                queue=queue,
                lease_seconds=0,  # adaptive lease
                worker_id=worker_id,
                limit=5,
            )

            if not jobs:
                time.sleep(0.25)
                continue

            # Do pretend work
            time.sleep(0.1)

            # Periodically renew in batch (here, just extend by 10s)
            renew_items = [
                {
                    "job_id": j["id"],
                    "seconds": 10,
                    "worker_id": j.get("worker_id"),
                    "lease_id": j.get("lease_id"),
                }
                for j in jobs
            ]
            jm.batch_renew_leases(renew_items)

            # Mark all completed in one batch
            complete_items = [
                {
                    "job_id": j["id"],
                    "result": {"ok": True},
                    "worker_id": j.get("worker_id"),
                    "lease_id": j.get("lease_id"),
                    # Best practice: pass completion_token to guarantee exactly-once finalize when enforced
                    "completion_token": j.get("lease_id"),
                }
                for j in jobs
            ]
            jm.batch_complete_jobs(complete_items)

    except KeyboardInterrupt:
        print("Stopping worker...")


if __name__ == "__main__":
    main()
