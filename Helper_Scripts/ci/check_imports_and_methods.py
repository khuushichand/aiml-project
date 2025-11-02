"""
CI pre-test helper:

1) Clears Python bytecode caches (`__pycache__` folders and `*.pyc` files).
2) Imports `MediaDatabase` and asserts required CRUD methods exist.
3) Prints module file paths to verify imports come from the workspace.
4) Runs `pytest` with bytecode disabled (`-B` and `PYTHONDONTWRITEBYTECODE=1`).

Usage:
  python ci/check_imports_and_methods.py            # run full test suite
  python ci/check_imports_and_methods.py -m unit    # pass args through to pytest

Exits non-zero on assertion or test failures.
"""

from __future__ import annotations

import os
import sys
import shutil
import inspect
import subprocess
from pathlib import Path
from typing import Iterable, List


REPO_ROOT = Path(__file__).resolve().parent.parent


def clear_bytecode_caches(root: Path) -> tuple[int, int]:
    """Remove `__pycache__` directories and `*.pyc` files under `root`.

    Returns a tuple of (removed_dirs, removed_files).
    """
    removed_dirs = 0
    removed_files = 0
    for dirpath, dirnames, filenames in os.walk(root):
        # Remove __pycache__ directories
        if "__pycache__" in dirnames:
            target = Path(dirpath) / "__pycache__"
            try:
                shutil.rmtree(target, ignore_errors=True)
                removed_dirs += 1
            except Exception as e:
                print(f"WARN: Failed to remove {target}: {e}")
            # Prevent descending into now-removed directory
            try:
                dirnames.remove("__pycache__")
            except ValueError:
                pass

        # Remove stray .pyc files
        for fn in filenames:
            if fn.endswith((".pyc", ".pyo")):
                fp = Path(dirpath) / fn
                try:
                    fp.unlink(missing_ok=True)
                    removed_files += 1
                except Exception as e:
                    print(f"WARN: Failed to remove {fp}: {e}")

    return removed_dirs, removed_files


def assert_mediadatabase_methods() -> None:
    """Import MediaDatabase and assert required methods exist on the class."""
    # Import here to ensure we do it after clearing caches
    import tldw_Server_API  # type: ignore
    from tldw_Server_API.app.core.DB_Management.Media_DB_v2 import (  # type: ignore
        MediaDatabase,
    )

    print(f"tldw_Server_API module file: {getattr(tldw_Server_API, '__file__', 'unknown')}")
    try:
        media_db_file = inspect.getsourcefile(MediaDatabase) or inspect.getfile(
            MediaDatabase
        )
    except TypeError:
        media_db_file = "<unknown>"
    print(f"MediaDatabase source file: {media_db_file}")

    # Warn if the imported package is not from this workspace
    repo_root_str = str(REPO_ROOT)
    module_path = str(getattr(tldw_Server_API, "__file__", ""))
    if module_path and not module_path.startswith(repo_root_str):
        print(
            "WARNING: tldw_Server_API is imported from outside this workspace: "
            f"{module_path}\n         (Expected prefix: {repo_root_str})"
        )

    required = [
        "create_chunking_template",
        "get_chunking_template",
        "list_chunking_templates",
        "update_chunking_template",
        "delete_chunking_template",
        "seed_builtin_templates",
    ]

    missing: list[str] = []
    for name in required:
        if not hasattr(MediaDatabase, name):
            missing.append(name)

    if missing:
        raise AssertionError(
            "MediaDatabase is missing required methods: " + ", ".join(missing)
        )


def run_pytest(pytest_args: Iterable[str]) -> int:
    """Run pytest with -B and PYTHONDONTWRITEBYTECODE=1, forwarding args."""
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    cmd: List[str] = [sys.executable, "-B", "-m", "pytest", "-v", *pytest_args]
    print("Running:", " ".join(cmd))
    print("PYTHONDONTWRITEBYTECODE=", env["PYTHONDONTWRITEBYTECODE"])

    proc = subprocess.run(cmd, cwd=str(REPO_ROOT), env=env)
    return proc.returncode


def main(argv: List[str]) -> int:
    print(f"Repo root: {REPO_ROOT}")

    removed_dirs, removed_files = clear_bytecode_caches(REPO_ROOT)
    print(
        f"Cleared bytecode caches: {removed_dirs} __pycache__ dirs, {removed_files} *.pyc files"
    )

    # Ensure imports resolve correctly and required methods exist
    assert_mediadatabase_methods()
    print("MediaDatabase CRUD methods present ✅")

    # Forward any remaining args to pytest
    rc = run_pytest(argv)
    return rc


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
