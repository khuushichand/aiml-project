#!/usr/bin/env python3
"""Fail when canonical onboarding docs reference deprecated media process endpoint."""

from __future__ import annotations

import re
import sys
from pathlib import Path

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = PROJECT_ROOT / "Docs/Getting_Started/onboarding_manifest.yaml"
LEGACY_PATTERN = re.compile(r"/api/v1/media/process(?!-)")


def load_onboarding_paths() -> list[Path]:
    data = yaml.safe_load(MANIFEST_PATH.read_text(encoding="utf-8")) or {}
    profiles = data.get("profiles", {})
    docs: list[Path] = [PROJECT_ROOT / "Docs/Getting_Started/README.md"]
    for meta in profiles.values():
        rel_path = meta.get("path")
        if not rel_path:
            continue
        docs.append(PROJECT_ROOT / rel_path)
    # keep stable order and dedupe
    deduped: list[Path] = []
    seen: set[Path] = set()
    for path in docs:
        if path in seen:
            continue
        seen.add(path)
        deduped.append(path)
    return deduped


def find_legacy_refs(path: Path) -> list[tuple[int, str]]:
    hits: list[tuple[int, str]] = []
    if not path.exists():
        hits.append((0, "missing file"))
        return hits
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if LEGACY_PATTERN.search(line):
            hits.append((line_no, line.strip()))
    return hits


def main() -> int:
    docs = load_onboarding_paths()
    failures: list[str] = []

    for doc in docs:
        matches = find_legacy_refs(doc)
        if not matches:
            continue
        for line_no, line in matches:
            if line_no == 0:
                failures.append(f"{doc}: missing file")
            else:
                failures.append(f"{doc}:{line_no}: {line}")

    if failures:
        print("Found deprecated onboarding endpoint references:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Onboarding endpoint drift check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
