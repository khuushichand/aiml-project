from __future__ import annotations

from pathlib import Path


def resolve_path(path: Path) -> Path:
    """Expand and resolve a path without requiring it to exist."""
    expanded = path.expanduser()
    try:
        return expanded.resolve(strict=False)
    except TypeError:
        # Python < 3.6 doesn't support strict parameter
        return expanded.resolve()
