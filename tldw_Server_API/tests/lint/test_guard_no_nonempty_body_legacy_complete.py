import os
from pathlib import Path


def test_no_nonempty_body_post_to_legacy_complete():
    """Guard: prevent tests from posting non-empty JSON bodies to legacy /complete endpoint.

    Allowed exceptions:
    - Explicit deprecation test file: test_legacy_complete_deprecation.py
    - Empty JSON bodies (json={}) are allowed for legacy endpoint.
    """
    root = Path(__file__).resolve().parents[2] / "tldw_Server_API" / "tests"
    offenders = []
    for py in root.rglob("*.py"):
        # Skip the deprecation test which intentionally verifies 422
        if py.name == "test_legacy_complete_deprecation.py":
            continue
        text = py.read_text(encoding="utf-8")
        if "/api/v1/chats/" not in text or "/complete" not in text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "/api/v1/chats/" in line and "/complete" in line and ".post(" in line:
                window = "\n".join(lines[i : i + 8])
                if "json={}" in window or "json = {}" in window:
                    continue
                if "json={" in window or "json = {" in window:
                    offenders.append((py, i + 1, line.strip()))

    assert not offenders, (
        "Found tests posting non-empty JSON bodies to legacy /complete endpoint.\n"
        + "\n".join(f"{p}:{ln}: {snip}" for p, ln, snip in offenders)
    )

