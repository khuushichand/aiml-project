#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path


PATTERN = r"\b(mock|patch|monkeypatch)\b.*\b(requests|httpx|aiohttp)\b"
GLOB = "**/tests/**/*.py"


def _run_rg(repo_root: Path) -> int:
    if shutil.which("rg") is None:
        return 2
    cmd = [
        "rg",
        "-n",
        PATTERN,
        "-g",
        GLOB,
        str(repo_root),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode == 0:
        sys.stderr.write(
            "Disallowed patching detected in tests: avoid patching requests/httpx/aiohttp.\n\n"
        )
        sys.stderr.write(result.stdout)
        return 1
    if result.returncode == 1:
        return 0
    sys.stderr.write(result.stderr or "Failed to run rg for http client patch guard.\n")
    return 1


def _run_fallback(repo_root: Path) -> int:
    regex = re.compile(PATTERN)
    offenders: list[str] = []
    for path in repo_root.rglob("*.py"):
        if "tests" not in path.parts:
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except Exception:
            continue
        for idx, line in enumerate(text.splitlines(), start=1):
            if regex.search(line):
                offenders.append(f"{path}:{idx}: {line.strip()}")
    if offenders:
        sys.stderr.write(
            "Disallowed patching detected in tests: avoid patching requests/httpx/aiohttp.\n\n"
        )
        sys.stderr.write("\n".join(offenders) + "\n")
        return 1
    return 0


def main() -> int:
    repo_root = Path(__file__).resolve().parents[2]
    rc = _run_rg(repo_root)
    if rc == 2:
        return _run_fallback(repo_root)
    return rc


if __name__ == "__main__":
    raise SystemExit(main())
