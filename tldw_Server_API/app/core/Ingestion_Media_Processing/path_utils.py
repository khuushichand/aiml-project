from __future__ import annotations

import os
from pathlib import Path
from typing import Optional

from loguru import logger


def resolve_safe_local_path(path: Path, base_dir: Path) -> Optional[Path]:
    """
    Resolve ``path`` relative to ``base_dir`` and validate containment.

    Returns the resolved safe path when valid; otherwise returns None.
    """
    try:
        base_resolved = Path(base_dir).resolve(strict=False)
        path_obj = Path(path)
        path_resolved = (
            path_obj.resolve(strict=False)
            if path_obj.is_absolute()
            else base_resolved.joinpath(path_obj).resolve(strict=False)
        )
        try:
            common_path = os.path.commonpath([str(base_resolved), str(path_resolved)])
        except ValueError:
            logger.warning(
                "Rejected path on different drive for local media source: %s",
                path,
            )
            return None
        if common_path == str(base_resolved):
            return path_resolved
        logger.warning(
            "Rejected path outside of base directory for local media source: %s (base: %s)",
            path_resolved,
            base_resolved,
        )
        return None
    except Exception as exc:
        logger.warning("Error while validating local media path %s: %s", path, exc)
        return None


def is_safe_local_path(path: Path, base_dir: Path) -> bool:
    """
    Validate that ``path`` is a local file path contained within ``base_dir``.

    This helps prevent directory traversal or absolute-path access outside the
    expected base directory when dealing with user-influenced inputs.
    """
    return resolve_safe_local_path(path, base_dir) is not None
