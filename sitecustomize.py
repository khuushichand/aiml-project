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

    # Avoid monkeypatching ProcessPoolExecutor; rely on env/threading controls above.
    try:
        # Configure Hypothesis to suppress function_scoped_fixture health check globally in tests
        # This aligns with several tests which intentionally use function-scoped fixtures with @given
        from hypothesis import settings as _hyp_settings
        from hypothesis import HealthCheck as _HypHealthCheck
        _hyp_settings.register_profile(
            "tldw_pytest_defaults",
            deadline=None,
            suppress_health_check=[_HypHealthCheck.function_scoped_fixture],
        )
        _hyp_settings.load_profile("tldw_pytest_defaults")
    except Exception:
        # Hypothesis may not be installed in all environments; ignore if unavailable
        pass
