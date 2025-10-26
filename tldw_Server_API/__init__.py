"""
Top-level package initializer for tldw_Server_API.

Applies conservative environment defaults in test environments to prevent
libraries that rely on joblib/loky from spawning process pools at import or
lightweight usage time. This mitigates leaked semaphore warnings and reduces
the risk of pytest being killed due to resource pressure.
"""

from __future__ import annotations

import os
import sys
from loguru import logger


def _under_pytest() -> bool:
    try:
        if "PYTEST_CURRENT_TEST" in os.environ:
            return True
        return any("pytest" in (arg or "") for arg in sys.argv)
    except Exception as e:
        logger.debug(f"__init__._under_pytest check failed: {e}")
        return False


def _env_flag_true(name: str) -> bool:
    val = os.getenv(name, "").strip().lower()
    return val in {"1", "true", "yes", "on"}


if _env_flag_true("TESTING") or _under_pytest():
    # Prefer threading backend for joblib in tests
    os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
    os.environ.setdefault("JOBLIB_BACKEND", "threading")
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    # Limit BLAS/OMP threads to keep test runs stable
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    # HF tokenizers parallel guard
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
