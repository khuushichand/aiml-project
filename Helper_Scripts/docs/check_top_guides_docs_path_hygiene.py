"""Fail when source/published guide docs reference missing Docs paths."""

from __future__ import annotations

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
GUIDE_DIRS = (
    REPO_ROOT / "Docs/User_Guides",
    REPO_ROOT / "Docs/Getting_Started",
    REPO_ROOT / "Docs/Deployment",
    REPO_ROOT / "Docs/Published/User_Guides",
    REPO_ROOT / "Docs/Published/Getting_Started",
    REPO_ROOT / "Docs/Published/Deployment",
    REPO_ROOT / "Docs/Published/Monitoring",
)
DOC_PATH_PATTERN = re.compile(r"Docs/[A-Za-z0-9_./-]+")


def _collect_missing_paths() -> list[tuple[str, str]]:
    missing: list[tuple[str, str]] = []
    for root in GUIDE_DIRS:
        if not root.exists():
            continue
        for guide_file in sorted(root.rglob("*.md")):
            text = guide_file.read_text(encoding="utf-8")
            for match in DOC_PATH_PATTERN.finditer(text):
                raw_path = match.group(0).rstrip("`),.:;")
                candidate = REPO_ROOT / raw_path
                if not candidate.exists():
                    missing.append((str(guide_file.relative_to(REPO_ROOT)), raw_path))
    return sorted(set(missing))


def main() -> int:
    missing = _collect_missing_paths()
    if missing:
        print("Top guide docs reference missing paths:")
        for source_file, missing_path in missing:
            print(f"- {source_file} -> {missing_path}")
        return 1

    print("Top guide docs path hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
