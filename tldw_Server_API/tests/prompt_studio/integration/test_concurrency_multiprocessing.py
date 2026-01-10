import os
import time
from typing import Any, Dict, Tuple

import pytest
from multiprocessing import Process, Manager

from tldw_Server_API.app.core.DB_Management.PromptStudioDatabase import PromptStudioDatabase
from tldw_Server_API.app.core.DB_Management.backends.base import BackendType, DatabaseConfig
from tldw_Server_API.app.core.DB_Management.backends.factory import DatabaseBackendFactory


def _spec_from_db(db: PromptStudioDatabase) -> Dict[str, Any]:
    """Build a serializable spec for child processes to reconnect to the same DB."""
    spec: Dict[str, Any] = {}
    if db.backend_type == BackendType.SQLITE:
        # PromptsDatabase exposes db_path_str via base
        path = getattr(db, "db_path_str", None)
        if not path:
            # Fallback: try _impl chain
            impl = getattr(db, "_impl", None)
            path = getattr(impl, "db_path_str", None)
        spec = {"backend": "sqlite", "sqlite_path": path}
    else:
        backend = db.backend
        cfg = getattr(backend, "config", None)
        spec = {
            "backend": "postgres",
            "pg": {
                "host": cfg.pg_host,
                "port": cfg.pg_port,
                "database": cfg.pg_database,
                "user": cfg.pg_user,
                "password": cfg.pg_password,
            },
        }
    return spec


def _open_db_from_spec(spec: Dict[str, Any]) -> PromptStudioDatabase:
    if spec["backend"] == "sqlite":
        return PromptStudioDatabase(spec["sqlite_path"], client_id="mp-worker")
    pg = spec["pg"]
    cfg = DatabaseConfig(
        backend_type=BackendType.POSTGRESQL,
        pg_host=pg["host"],
        pg_port=int(pg["port"]),
        pg_database=pg["database"],
        pg_user=pg["user"],
        pg_password=pg["password"],
        connect_timeout=2,
    )
    be = DatabaseBackendFactory.create_backend(cfg)
    return PromptStudioDatabase(db_path="/tmp/placeholder.sqlite", client_id="mp-worker", backend=be)


def _worker_acquire_loop(spec: Dict[str, Any], out_ids):
    db = _open_db_from_spec(spec)
    idle_spins = 0
    try:
        while True:
            job = db.acquire_next_job()
            if not job:
                idle_spins += 1
                if idle_spins > 20:  # ~2s total with 0.1s sleeps
                    break
                time.sleep(0.1)
                continue
            idle_spins = 0
            out_ids.append(int(job["id"]))
            # Light delay to encourage interleaving
            time.sleep(0.01)
    finally:
        try:
            db.close()
        except Exception:
            pass


@pytest.mark.integration
def test_parallel_acquire_distinct_jobs_multiprocessing(prompt_studio_dual_backend_db):
    label, db = prompt_studio_dual_backend_db
    # Prepare a moderate number of jobs
    total = 18
    for i in range(total):
        db.create_job(
            job_type="evaluation",
            entity_id=100 + i,
            payload={"i": i},
            priority=5,
        )

    spec = _spec_from_db(db)

    # Spawn a handful of workers
    with Manager() as manager:
        out_ids = manager.list()
        procs = [Process(target=_worker_acquire_loop, args=(spec, out_ids)) for _ in range(4)]
        try:
            for p in procs:
                p.start()
            for p in procs:
                p.join(timeout=10)
        except KeyboardInterrupt:
            # On interrupt, terminate all child processes promptly
            for p in procs:
                if p.is_alive():
                    p.terminate()
            for p in procs:
                try:
                    p.join(2)
                except Exception:
                    pass
            raise
        # Ensure processes are terminated if hanging
        for p in procs:
            if p.is_alive():
                p.terminate()
                p.join(2)

        got = list(out_ids)
        assert len(got) == total, f"Expected {total} acquired jobs, got {len(got)} for backend {label}"
        assert len(set(got)) == total, "Duplicate job acquisitions detected across processes"
