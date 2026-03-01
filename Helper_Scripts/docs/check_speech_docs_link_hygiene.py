#!/usr/bin/env python3
"""Fail when speech docs drift back to deprecated link patterns."""

from __future__ import annotations

import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]

MONITORED_FILES = [
    Path("README.md"),
    Path("Docs/API-related/Audio_Transcription_API.md"),
    Path("Docs/Published/API-related/Audio_Transcription_API.md"),
    Path("Docs/API-related/TTS_API.md"),
    Path("Docs/Published/API-related/TTS_API.md"),
    Path("Docs/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md"),
    Path("Docs/Published/User_Guides/WebUI_Extension/Getting-Started-STT_and_TTS.md"),
    Path("Docs/User_Guides/WebUI_Extension/TTS_Getting_Started.md"),
    Path("Docs/Published/User_Guides/WebUI_Extension/TTS_Getting_Started.md"),
    Path("Docs/User_Guides/WebUI_Extension/TTS-SETUP-GUIDE.md"),
    Path("Docs/Published/User_Guides/WebUI_Extension/TTS-SETUP-GUIDE.md"),
]

BLOCKED_PATTERNS: dict[str, re.Pattern[str]] = {
    "legacy_stt_tts_blob_link": re.compile(
        r"https://github\.com/rmusser01/tldw_server/blob/main/Docs/Getting-Started-STT_and_TTS\.md"
    ),
    "legacy_stt_tts_runbook_blob_prefix": re.compile(
        r"https://github\.com/rmusser01/tldw_server/blob/main/Docs/STT-TTS/"
    ),
    "bad_tts_user_guide_path": re.compile(r"Docs/User_Guides/TTS_Getting_Started\.md"),
    "removed_installation_setup_guide": re.compile(r"Installation-Setup-Guide\.md"),
}


def main() -> int:
    failures: list[str] = []
    for rel in MONITORED_FILES:
        path = PROJECT_ROOT / rel
        if not path.exists():
            failures.append(f"{rel}: missing monitored file")
            continue
        for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            for name, pattern in BLOCKED_PATTERNS.items():
                if pattern.search(line):
                    failures.append(f"{rel}:{line_no}: [{name}] {line.strip()}")

    if failures:
        print("Speech docs link hygiene violations found:")
        for item in failures:
            print(f"- {item}")
        return 1

    print("Speech docs link hygiene check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
