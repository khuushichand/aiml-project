from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


_SCRIPT_PATH = (
    Path(__file__).resolve().parents[3]
    / "Helper_Scripts"
    / "ci"
    / "check_imports_and_methods.py"
)
_SPEC = importlib.util.spec_from_file_location("check_imports_and_methods", _SCRIPT_PATH)
assert _SPEC is not None and _SPEC.loader is not None
script = importlib.util.module_from_spec(_SPEC)
sys.modules[_SPEC.name] = script
_SPEC.loader.exec_module(script)


def test_ci_check_imports_repo_root_points_to_workspace_root() -> None:
    assert script.REPO_ROOT == Path(__file__).resolve().parents[3]


def test_ci_check_imports_can_load_mediadatabase_methods() -> None:
    script.assert_mediadatabase_methods()
