from __future__ import annotations

import os
from pathlib import Path
from typing import Dict, Optional

from loguru import logger

from .files import atomic_write


def _write_env_lines(path: Path, env: Dict[str, Optional[str]]) -> None:
    lines = []
    for k, v in env.items():
        if v is None:
            continue
        lines.append(f"{k}={v}\n")
    atomic_write(path, "".join(lines))
    try:
        # Restrictive permissions (0600)
        os.chmod(path, 0o600)
    except Exception as e:
        logger.debug(f"chmod on {path} ignored: {e}")


def ensure_env(path: Path, defaults: Dict[str, Optional[str]] | None = None) -> None:
    """Create or update a .env file idempotently (scaffold).

    - Creates the file if it does not exist using provided defaults
    - Does not attempt key-by-key merge yet (keeps skeleton simple)
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _write_env_lines(path, defaults or {})
        return
    # For now, keep existing .env untouched; full implementation will merge.
    logger.debug(f".env exists at {path}; skipping write in scaffold")

