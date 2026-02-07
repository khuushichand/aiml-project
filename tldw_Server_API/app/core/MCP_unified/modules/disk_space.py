"""Cross-platform disk space helpers for MCP module health checks."""

from __future__ import annotations

import os
import shutil
from pathlib import Path


def get_free_disk_space_gb(path: str | Path) -> float:
    """Return free disk space for ``path`` in GiB."""
    path_str = str(path)
    try:
        stat = os.statvfs(path_str)
        free_bytes = stat.f_bavail * stat.f_frsize
    except AttributeError:
        # Windows does not expose os.statvfs.
        free_bytes = shutil.disk_usage(path_str).free
    return free_bytes / (1024 ** 3)
