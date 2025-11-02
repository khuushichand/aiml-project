from __future__ import annotations

import py_compile
from pathlib import Path
import pytest


@pytest.mark.unit
def test_tools_endpoint_module_compiles():
    """Guard against syntax regressions in tools endpoint.

    Compiles the module source directly so failures (e.g., IndentationError)
    are caught even if route gating prevents importing the module at startup.
    """
    tools_path = (
        Path(__file__).resolve().parents[2]
        / "app"
        / "api"
        / "v1"
        / "endpoints"
        / "tools.py"
    )
    assert tools_path.exists(), f"Missing tools endpoint at: {tools_path}"
    # Raises an exception (e.g., IndentationError) on syntax problems
    py_compile.compile(str(tools_path), doraise=True)
