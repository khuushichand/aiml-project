from __future__ import annotations

import shutil
import subprocess
from typing import Any, Dict, List, Tuple

from ..utils.waf_result_parser import parse_wafw00f_output


def detect_waf(url: str, find_all: bool = False) -> Dict[str, Any]:
    """
    Run wafw00f to detect a WAF and parse its output.

    Returns the WAF name(s) if found, otherwise an empty list. A friendly error
    is returned when wafw00f is not available.
    """
    if shutil.which("wafw00f") is None:
        return {
            "status": "error",
            "message": "wafw00f missing",
            "error_code": "missing_dependency",
        }

    command = ["wafw00f", url]
    if find_all:
        command.append("-a")

    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=60,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {"status": "error", "message": "timeout", "error_code": "timeout"}

    wafs_found: List[Tuple[str, str | None]] = parse_wafw00f_output(result.stdout, result.stderr)

    if wafs_found:
        return {"status": "success", "wafs": wafs_found}

    if result.returncode != 0:
        error_message = result.stderr.strip() or (
            f"wafw00f failed with exit code {result.returncode} but no error message."
        )
        return {"status": "error", "message": error_message}

    return {"status": "success", "wafs": []}
