from __future__ import annotations

import os
import shutil
from typing import Optional

from loguru import logger

from ..models import RunSpec, RunStatus, RunPhase


def firecracker_available() -> bool:
    # Prefer explicit override for CI/tests; otherwise probe for 'firecracker' binary
    env = os.getenv("TLDW_SANDBOX_FIRECRACKER_AVAILABLE")
    if env is not None:
        return env.lower() in {"1", "true", "yes", "on"}
    # Heuristic: check for known binaries; actual setup may vary
    return shutil.which("firecracker") is not None


class FirecrackerRunner:
    """Stub Firecracker runner (direct integration).

    Ignite is EOL; future implementation should use direct Firecracker SDK/CLI
    with microVM images/snapshots. This scaffold raises NotImplementedError when invoked.
    """

    def __init__(self) -> None:
        pass

    async def start_run(self, spec: RunSpec) -> RunStatus:
        logger.debug(f"FirecrackerRunner.start_run called with spec: {spec}")
        raise NotImplementedError("FirecrackerRunner is not implemented in this scaffold")
