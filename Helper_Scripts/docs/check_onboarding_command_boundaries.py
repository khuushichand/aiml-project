#!/usr/bin/env python3
"""Fail when setup commands drift into non-canonical onboarding entry docs."""

from __future__ import annotations

import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = PROJECT_ROOT / "Helper_Scripts/docs/onboarding_command_allowlist.txt"

# These are onboarding-adjacent entrypoints where setup commands should not live.
MONITORED_FILES = [
    Path("Docs/User_Guides/Server/CLI_Reference.md"),
    Path("Docs/Deployment/First_Time_Production_Setup.md"),
    Path("Docs/API-related/AuthNZ-API-Guide.md"),
    Path("Docs/Code_Documentation/Code_Map.md"),
]

BLOCKED_PATTERNS: dict[str, re.Pattern[str]] = {
    "uvicorn_start": re.compile(r"\bpython\s+-m\s+uvicorn\b"),
    "docker_compose": re.compile(r"\bdocker\s+compose\b"),
    "editable_install": re.compile(r"\bpip\s+install\s+-e\b"),
    "copy_env_template": re.compile(r"\bcp\s+tldw_Server_API/Config_Files/\.env\.example\b"),
    "set_auth_mode": re.compile(r"\bexport\s+AUTH_MODE="),
    "auth_init": re.compile(r"\bpython\s+-m\s+tldw_Server_API\.app\.core\.AuthNZ\.initialize\b"),
}


def load_allowlist() -> list[tuple[re.Pattern[str], re.Pattern[str]]]:
    if not ALLOWLIST_PATH.exists():
        return []
    entries: list[tuple[re.Pattern[str], re.Pattern[str]]] = []
    for i, raw in enumerate(ALLOWLIST_PATH.read_text(encoding="utf-8").splitlines(), start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "|" not in line:
            raise ValueError(f"{ALLOWLIST_PATH}:{i}: expected '<path_regex>|<line_regex>'")
        path_expr, line_expr = line.split("|", maxsplit=1)
        entries.append((re.compile(path_expr), re.compile(line_expr)))
    return entries


def is_allowlisted(
    allowlist: list[tuple[re.Pattern[str], re.Pattern[str]]], relative_path: str, line: str
) -> bool:
    for path_re, line_re in allowlist:
        if path_re.search(relative_path) and line_re.search(line):
            return True
    return False


def main() -> int:
    try:
        allowlist = load_allowlist()
    except ValueError as exc:
        print(f"Invalid onboarding command allowlist: {exc}")
        return 2

    failures: list[str] = []
    for rel in MONITORED_FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            failures.append(f"{rel}: missing monitored file")
            continue
        rel_text = rel.as_posix()
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for pattern_name, pattern in BLOCKED_PATTERNS.items():
                if not pattern.search(line):
                    continue
                if is_allowlisted(allowlist, rel_text, line):
                    continue
                failures.append(f"{rel_text}:{line_no}: [{pattern_name}] {line.strip()}")

    if failures:
        print("Onboarding command boundary violations found:")
        for item in failures:
            print(f"- {item}")
        print(
            "\nMove setup commands into Docs/Getting_Started profile guides, "
            "or add a justified allowlist entry."
        )
        return 1

    print("Onboarding command boundary check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
