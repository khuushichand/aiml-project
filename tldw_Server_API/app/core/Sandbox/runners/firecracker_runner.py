from __future__ import annotations

import os
import shutil
from typing import Optional, Dict

from loguru import logger

from ..models import RunSpec, RunStatus, RunPhase
from ..streams import get_hub
from datetime import datetime
import hashlib
import time
from typing import List
import fnmatch


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
        """Execute a run in a Firecracker microVM (scaffolded).

        This v0 implementation provides a structured lifecycle without booting a real VM:
        - Emits start/end events to the hub
        - Computes a deterministic image "digest" from the base_image (string or file)
        - Honors deny-all network default (policy enforces; we just log intent)
        - Captures placeholder artifacts based on capture_patterns
        - Records basic resource usage (wall time, log bytes, artifact bytes)

        When integrating a real microVM, replace the middle section with:
        - Prepare VM directory, kernel, rootfs, and drives
        - Launch firecracker with a unix socket; drive API to set machine/drives/boot
        - Configure vsock/serial for logs; collect stdout/stderr and metrics
        - Copy artifacts from a shared volume (virtiofs) matching capture_patterns
        """
        started = datetime.utcnow()
        hub = get_hub()
        # Publish start
        try:
            hub.publish_event(run_id, "start", {"ts": started.isoformat(), "runtime": "firecracker", "net": "off"})
        except Exception:
            pass

        # Compute pseudo image digest (string hash or file hash)
        image_digest: Optional[str] = None
        base = spec.base_image or ""
        try:
            if base and os.path.exists(base) and os.path.isfile(base):
                # Hash the file content
                h = hashlib.sha256()
                with open(base, "rb") as rf:
                    for chunk in iter(lambda: rf.read(8192), b""):
                        h.update(chunk)
                image_digest = f"sha256:{h.hexdigest()}"
            else:
                # Hash the descriptor string (e.g., "python:3.11-slim") for traceability
                image_digest = f"sha256:{hashlib.sha256(base.encode('utf-8')).hexdigest()}" if base else None
        except Exception:
            image_digest = None

        # Simulate execution time minimally for observability
        time.sleep(0.01)

        # Placeholder artifacts: match capture_patterns against a virtual workspace tree
        artifacts_map: Dict[str, bytes] = {}
        try:
            patterns: List[str] = list(spec.capture_patterns or [])
            # In fake mode, generate a tiny artifact per pattern for visibility
            for pat in patterns:
                # Normalize to posix-like
                key = pat.strip().lstrip("./") or "artifact.bin"
                # Only add if pattern looks like a file/glob rather than directory
                if any(ch in key for ch in ["*", "?", "["]):
                    # Represent the matched file name derived from pattern
                    sample_name = key.strip("*") or "result.txt"
                    artifacts_map[sample_name] = b""
                else:
                    artifacts_map[key] = b""
        except Exception:
            artifacts_map = {}

        # Publish end
        try:
            hub.publish_event(run_id, "end", {"exit_code": 0})
        except Exception:
            pass

        finished = datetime.utcnow()
        # Usage accounting
        try:
            log_bytes_total = int(hub.get_log_bytes(run_id))
        except Exception:
            log_bytes_total = 0
        art_bytes = 0
        try:
            art_bytes = sum(len(v) for v in artifacts_map.values()) if artifacts_map else 0
        except Exception:
            art_bytes = 0
        usage: Dict[str, int] = {
            "cpu_time_sec": 0,
            "wall_time_sec": int(max(0.0, (finished - started).total_seconds())),
            "peak_rss_mb": 0,
            "log_bytes": int(log_bytes_total),
            "artifact_bytes": int(art_bytes),
        }

        return RunStatus(
            id="",
            phase=RunPhase.completed,
            started_at=started,
            finished_at=finished,
            exit_code=0,
            message="Firecracker execution (scaffold)",
            image_digest=image_digest,
            runtime_version=firecracker_version(),
            resource_usage=usage,
            artifacts=(artifacts_map or None),
        )
