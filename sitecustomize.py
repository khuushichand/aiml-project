"""
sitecustomize
-------------
Loaded automatically by Python when present on sys.path. We use it to set
safe defaults during pytest runs to avoid background process pools (joblib/loky)
and excessive thread fanout that can cause semaphore leaks or OOM kills.

This file only adjusts settings when it detects a pytest run.
"""

from __future__ import annotations

import os
import sys


def _under_pytest() -> bool:
    try:
        if "PYTEST_CURRENT_TEST" in os.environ:
            return True
        return any("pytest" in (arg or "") for arg in sys.argv)
    except Exception:
        return False


if _under_pytest() or os.getenv("TESTING", "").strip().lower() in {"1", "true", "yes", "on"}:
    # Prefer threads for joblib; avoid loky process pools
    os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
    os.environ.setdefault("JOBLIB_BACKEND", "threading")
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    # Constrain math libs parallelism
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    # Reduce HF tokenizers parallelism
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")

    # As a last-resort guard: replace ProcessPoolExecutor with a thread-backed
    # executor to avoid spawning child processes in tests. This helps sidestep
    # semaphore leaks and sandbox/process limits that can kill pytest runs.
    try:
        import concurrent.futures as _f
        from concurrent.futures import ThreadPoolExecutor as _TPE

        class _PatchedProcessPoolExecutor(_TPE):  # type: ignore[misc]
            def __init__(self, max_workers=None, *args, **kwargs):  # noqa: D401
                # Drop kwargs that only ProcessPoolExecutor supports
                for k in ("max_tasks_per_child", "mp_context", "initializer", "initargs"):
                    if k in kwargs:
                        kwargs.pop(k, None)
                super().__init__(max_workers=max_workers, thread_name_prefix="ppool_as_thread")

        _f.ProcessPoolExecutor = _PatchedProcessPoolExecutor  # type: ignore[assignment]
    except Exception:
        pass
