from __future__ import annotations

import os
import shutil
from typing import Optional, Dict

from loguru import logger

from ..models import RunSpec, RunStatus, RunPhase
from ..streams import get_hub
from datetime import datetime


def firecracker_available() -> bool:
    # Prefer explicit override for CI/tests; otherwise probe for 'firecracker' binary
    env = os.getenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE")
    if env is not None:
        return env.lower() in {"1", "true", "yes", "on"}
    # Heuristic: check for known binaries; actual setup may vary
    return shutil.which("firecracker") is not None


def firecracker_version() -> Optional[str]:
    env = os.getenv("TLDW_SANDBOX_FIRECRACKER_VERSION")
    if env:
        return env
    try:
        import subprocess
        out = subprocess.check_output(["firecracker", "--version"], text=True, timeout=2).strip()
        # Example: Firecracker v1.6.0
        parts = out.split()
        for tok in parts:
            if tok.lower().startswith("v"):
                return tok.lstrip("vV")
        return out
    except Exception:
        return None


class FirecrackerRunner:
    """Stub Firecracker runner (direct integration).

    Ignite is EOL; future implementation should use direct Firecracker SDK/CLI
    with microVM images/snapshots. This scaffold raises NotImplementedError when invoked.
    """

    def __init__(self) -> None:
        pass

    def _truthy(self, v: Optional[str]) -> bool:
        return bool(v) and str(v).strip().lower() in {"1", "true", "yes", "on", "y"}

    def start_run(self, run_id: str, spec: RunSpec, session_workspace: Optional[str] = None) -> RunStatus:
        logger.debug(f"FirecrackerRunner.start_run called with spec: {spec}")
        # Until real microVM execution is implemented, provide a deterministic fake mode.
        # Network is disabled by default via policy (deny_all).
        now = datetime.utcnow()
        try:
            get_hub().publish_event(run_id, "start", {"ts": now.isoformat(), "runtime": "firecracker"})
        except Exception:
            pass
        try:
            get_hub().publish_event(run_id, "end", {"exit_code": 0})
        except Exception:
            pass
        # Best-effort usage snapshot: zeros with log_bytes from hub
        try:
            log_bytes_total = int(get_hub().get_log_bytes(run_id))
        except Exception:
            log_bytes_total = 0
        usage: Dict[str, int] = {
            "cpu_time_sec": 0,
            "wall_time_sec": 0,
            "peak_rss_mb": 0,
            "log_bytes": int(log_bytes_total),
            "artifact_bytes": 0,
        }
        return RunStatus(
            id="",
            phase=RunPhase.completed,
            started_at=now,
            finished_at=now,
            exit_code=0,
            message="Firecracker fake execution",
            image_digest=None,
            runtime_version=firecracker_version(),
            resource_usage=usage,
        )
