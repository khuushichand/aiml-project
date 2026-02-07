"""
Lightweight helpers for test-mode detection and truthy env parsing.

Kept dependency-free (stdlib only) to avoid import-time side effects.
"""

from __future__ import annotations

import os

_TRUTHY = {"1", "true", "yes", "y", "on"}


def _env_truthy(val: str | None) -> bool:
    try:
        return str(val or "").strip().lower() in _TRUTHY
    except Exception:
        return False


def is_test_mode() -> bool:
    """Return True when server-side test mode is enabled.

    Checks both TEST_MODE and TLDW_TEST_MODE, using a consistent truthy set.
    Never reads client data; only server environment variables.
    """
    try:
        raw = os.getenv("TEST_MODE", "") or os.getenv("TLDW_TEST_MODE", "")
        return _env_truthy(raw)
    except Exception:
        return False


def is_explicit_pytest_runtime() -> bool:
    """Return True only when running under explicit pytest runtime context.

    The runtime signal is `PYTEST_CURRENT_TEST`, which pytest sets for active
    test execution phases. This intentionally avoids looser heuristics such as
    checking `sys.modules`.
    """
    try:
        return bool(str(os.getenv("PYTEST_CURRENT_TEST") or "").strip())
    except Exception:
        return False


def validate_test_runtime_flags() -> None:
    """Fail fast when test-mode flags are enabled outside explicit pytest runtime.

    Guarded flags:
    - TEST_MODE
    - TESTING
    - TLDW_TEST_MODE
    """
    try:
        test_mode = _env_truthy(os.getenv("TEST_MODE"))
        testing = _env_truthy(os.getenv("TESTING"))
        tldw_test_mode = _env_truthy(os.getenv("TLDW_TEST_MODE"))
    except Exception:
        test_mode = False
        testing = False
        tldw_test_mode = False

    if (test_mode or testing or tldw_test_mode) and not is_explicit_pytest_runtime():
        raise RuntimeError(
            "Unsafe startup configuration: TEST_MODE/TESTING/TLDW_TEST_MODE "
            "is enabled outside explicit pytest runtime (PYTEST_CURRENT_TEST)."
        )
