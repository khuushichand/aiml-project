from __future__ import annotations

import os
import shlex
import shutil
from typing import Any


def _mineru_command_tokens() -> list[str]:
    raw = os.getenv("MINERU_CMD", "mineru").strip() or "mineru"
    return shlex.split(raw)


def _mineru_available() -> bool:
    cmd = _mineru_command_tokens()
    executable = cmd[0] if cmd else "mineru"
    return shutil.which(executable) is not None


def describe_mineru_backend() -> dict[str, Any]:
    return {
        "available": _mineru_available(),
        "pdf_only": True,
        "document_level": True,
        "opt_in_only": True,
        "supports_per_page_metrics": True,
        "mode": "cli",
    }
