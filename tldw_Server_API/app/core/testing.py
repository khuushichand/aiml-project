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
