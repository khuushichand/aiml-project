"""Fail when README references Docs paths that do not exist."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
README_PATH = REPO_ROOT / "README.md"
DOC_PATH_PATTERN = re.compile(r"Docs/[A-Za-z0-9_./-]+")


def _collect_docs_paths(text: str) -> list[str]:
    return sorted({match.group(0).rstrip("`),.:;") for match in DOC_PATH_PATTERN.finditer(text)})


def main() -> int:
    text = README_PATH.read_text(encoding="utf-8")
    missing: list[str] = []

    for raw_path in _collect_docs_paths(text):
        candidate = REPO_ROOT / raw_path
        if not candidate.exists():
            missing.append(raw_path)

    if missing:
        print("README references missing docs paths:")
        for path in missing:
            print(f"- {path}")
        return 1

    print("README docs path hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
