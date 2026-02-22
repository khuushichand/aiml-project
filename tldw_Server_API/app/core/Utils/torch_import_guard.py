from __future__ import annotations

import os
import subprocess
import sys
from functools import lru_cache


def _env_flag(name: str) -> bool:
    raw = os.getenv(name, "")
    return str(raw).strip().lower() in {"1", "true", "yes", "y", "on"}


@lru_cache(maxsize=1)
def _probe_torch_import_once() -> tuple[bool, str]:
    """Run a subprocess preflight to verify torch can be imported safely.

    Some environments crash the interpreter process during ``import torch``.
    Running the probe in a subprocess prevents parent-process termination.
    """
    if _env_flag("TLDW_SKIP_TORCH_IMPORT_PREFLIGHT"):
        return True, "preflight skipped by environment override"

    timeout_raw = os.getenv("TLDW_TORCH_IMPORT_PROBE_TIMEOUT_SEC", "8")
    try:
        timeout = max(float(timeout_raw), 0.1)
    except (TypeError, ValueError):
        timeout = 8.0

    cmd = [sys.executable, "-c", "import torch; print('ok')"]
    try:
        result = subprocess.run(
            cmd,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except (OSError, subprocess.SubprocessError, TimeoutError, ValueError) as exc:
        return False, f"{type(exc).__name__}: {exc}"

    if result.returncode != 0:
        detail = (result.stderr or result.stdout or f"exit={result.returncode}").strip()
        if detail:
            detail = detail.splitlines()[-1]
        return False, detail or f"exit={result.returncode}"

    return True, "ok"


def can_import_torch_safely() -> tuple[bool, str]:
    """Return ``(ok, reason)`` for torch import viability in this runtime."""
    return _probe_torch_import_once()


def safe_import_torch():
    """Import torch only after a subprocess preflight check."""
    ok, reason = can_import_torch_safely()
    if not ok:
        raise ImportError(f"torch import preflight failed: {reason}")

    import torch  # type: ignore

    return torch

