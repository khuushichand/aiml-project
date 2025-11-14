from __future__ import annotations

import shutil
import subprocess
from typing import Iterable


def _tool_available(name: str) -> bool:
    return shutil.which(name) is not None


def maybe_format(paths: Iterable[str]) -> None:
    """Run Black and Ruff on the specified paths if available."""
    paths = list(paths)
    if not paths:
        return
    if _tool_available("black"):
        subprocess.run(["black", *paths], check=False)
    if _tool_available("ruff"):
        subprocess.run(["ruff", "--fix", *paths], check=False)

