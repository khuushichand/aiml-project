#!/usr/bin/env python3
"""
Lightweight Python syntax check to catch indentation and parse errors early.

Intended for use as a quick pre-commit hook; compiles provided files only.
"""
from __future__ import annotations

import argparse
import os
import py_compile
from pathlib import Path
from typing import Iterator
import sys


def _iter_python_files(paths: list[str]) -> Iterator[Path]:
    """Yield Path objects for .py files from file/directory inputs.

    Args:
        paths: List of file or directory paths to inspect.

    Nonexistent paths are ignored. Directories are searched recursively for
    ``*.py`` files; file paths are yielded only when they end with ``.py``.
    """
    for raw in paths:
        path = Path(raw)
        if not path.exists():
            continue
        if path.is_dir():
            yield from path.rglob("*.py")
        elif path.suffix == ".py":
            yield path


def main(argv: list[str]) -> int:
    """Compile Python files to catch syntax errors early.

    Args:
        argv: Command-line arguments passed to argparse.

    Returns:
        int: Exit code (0 when no paths or no failures; 1 when failures exist).
    """
    parser = argparse.ArgumentParser(description="Compile Python files to catch syntax errors.")
    parser.add_argument("paths", nargs="*", help="File or directory paths to check.")
    args = parser.parse_args(argv)

    if not args.paths:
        # No files provided (e.g., pre-commit with no matching files).
        return 0

    failures = 0
    for path in _iter_python_files(args.paths):
        try:
            py_compile.compile(str(path), cfile=os.devnull, doraise=True)
        except py_compile.PyCompileError as exc:
            failures += 1
            msg = exc.msg or str(exc)
            print(f"[python-syntax] {path}: {msg}", file=sys.stderr)
        except Exception as exc:
            failures += 1
            print(f"[python-syntax] {path}: {exc}", file=sys.stderr)

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
