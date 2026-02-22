from __future__ import annotations

import os
import subprocess
import sys

import pytest
from fastapi import status

from tldw_Server_API.app.core import exceptions as core_exceptions


pytestmark = pytest.mark.unit


def test_exceptions_import_does_not_emit_deprecated_422_warning() -> None:
    script = "import tldw_Server_API.app.core.exceptions"
    env = os.environ.copy()
    env["PYTHONWARNINGS"] = "always"
    proc = subprocess.run(
        [sys.executable, "-c", script],
        check=False,
        capture_output=True,
        text=True,
        env=env,
    )

    combined = f"{proc.stdout}\n{proc.stderr}"
    assert proc.returncode == 0, combined
    assert "HTTP_422_UNPROCESSABLE_ENTITY' is deprecated" not in combined


def test_api_validation_error_uses_resolved_default_status() -> None:
    expected = (
        status.HTTP_422_UNPROCESSABLE_CONTENT
        if hasattr(status, "HTTP_422_UNPROCESSABLE_CONTENT")
        else status.HTTP_422_UNPROCESSABLE_ENTITY
    )
    exc = core_exceptions.APIValidationError(detail="bad input")
    assert exc.status_code == expected
