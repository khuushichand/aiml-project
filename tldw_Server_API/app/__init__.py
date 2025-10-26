"""
App package initializer.

Sets conservative parallelism defaults when running under tests to avoid
spawning subprocess pools (e.g., joblib/loky) that can leak semaphores in
constrained CI or sandboxed environments. This reduces flakiness in pytest
and keeps resource usage predictable.

These settings only apply in test environments (detected via TESTING env var
or the presence of PYTEST_CURRENT_TEST). They are no-ops for normal runtime.
"""

from __future__ import annotations

import os
import sys
from loguru import logger


def _under_pytest() -> bool:
    try:
        if "PYTEST_CURRENT_TEST" in os.environ:
            return True
        # Fallback heuristic if PYTEST_CURRENT_TEST isn't set yet
        return any("pytest" in (arg or "") for arg in sys.argv)
    except Exception as e:
        logger.debug(f"app.__init__._under_pytest check failed: {e}")
        return False


def _env_flag_true(name: str) -> bool:
    val = os.getenv(name, "").strip().lower()
    return val in {"1", "true", "yes", "on"}


if _env_flag_true("TESTING") or _under_pytest():
    # Prevent joblib from spawning loky process pools in tests
    os.environ.setdefault("JOBLIB_MULTIPROCESSING", "0")
    os.environ.setdefault("JOBLIB_BACKEND", "threading")
    # Constrain CPU-bound libraries to a single thread for determinism
    os.environ.setdefault("LOKY_MAX_CPU_COUNT", "1")
    os.environ.setdefault("OMP_NUM_THREADS", "1")
    os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")
    os.environ.setdefault("MKL_NUM_THREADS", "1")
    os.environ.setdefault("NUMEXPR_NUM_THREADS", "1")
    # Reduce tokenizers parallel contention and warnings
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
