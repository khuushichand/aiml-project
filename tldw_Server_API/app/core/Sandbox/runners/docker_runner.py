from __future__ import annotations

import os
import shutil
from typing import Optional

from loguru import logger

from ..models import RunSpec, RunStatus, RunPhase


def docker_available() -> bool:
    # Prefer explicit override for CI/tests; otherwise probe PATH
    env = os.getenv("TLDW_SANDBOX_DOCKER_AVAILABLE")
    if env is not None:
        return env.lower() in {"1", "true", "yes", "on"}
    return shutil.which("docker") is not None


class DockerRunner:
    """Stub Docker runner. Real container lifecycle management is out of scope for this scaffold.

    For now, this runner returns a NotImplementedError when invoked. Availability detection
    is provided for feature discovery endpoints.
    """

    def __init__(self) -> None:
        pass

    async def start_run(self, spec: RunSpec) -> RunStatus:
        logger.debug(f"DockerRunner.start_run called with spec: {spec}")
        raise NotImplementedError("DockerRunner is not implemented in this scaffold")

