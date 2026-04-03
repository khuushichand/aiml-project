"""
Guardrail tests for AuthNZ admin CLI module docstrings.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest


@pytest.mark.unit
def test_admin_cli_modules_define_module_docstrings() -> None:
    project_root = Path(__file__).resolve().parents[3]
    target_paths = (
        project_root / "app" / "core" / "AuthNZ" / "create_admin.py",
        project_root / "app" / "core" / "AuthNZ" / "reset_admin_password.py",
    )

    missing_docstrings: list[str] = []

    for path in target_paths:
        module_ast = ast.parse(path.read_text(encoding="utf-8"))
        module_docstring = ast.get_docstring(module_ast, clean=False)
        if not module_docstring or not module_docstring.strip():
            missing_docstrings.append(path.relative_to(project_root).as_posix())

    assert missing_docstrings == [], (  # nosec B101
        "Expected AuthNZ admin CLI modules to define non-empty module docstrings: "
        f"{missing_docstrings}"
    )
