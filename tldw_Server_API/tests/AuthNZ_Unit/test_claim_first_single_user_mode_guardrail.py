"""
Guardrail audit for claim-first authorization in API endpoint layers.

This test prevents endpoint/auth-dependency authorization logic from drifting
back to mode-based branching on ``is_single_user_mode()``. Claim-first checks
should rely on principal roles/permissions. A single compatibility fallback in
``auth_deps`` remains allowlisted for explicit opt-out behavior.
"""

from __future__ import annotations

from pathlib import Path

import pytest


@pytest.mark.unit
def test_api_auth_layers_avoid_single_user_mode_authorization_branches():
    project_root = Path(__file__).resolve().parents[2]
    api_root = project_root / "app" / "api" / "v1"
    assert api_root.exists(), f"Expected API root path not found: {api_root}"

    allowlisted = {
        (
            "app/api/v1/API_Deps/auth_deps.py",
            "return bool(is_single_user_mode() or is_single_user_profile_mode())",
        ),
    }

    offending: list[str] = []

    for path in api_root.rglob("*.py"):
        rel = path.relative_to(project_root).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if "is_single_user_mode(" not in line:
                continue
            match = (rel, line.strip())
            if match not in allowlisted:
                offending.append(f"{rel}:{lineno}:{line.strip()}")

    assert offending == [], (
        "Found non-allowlisted is_single_user_mode authorization branches in API layer: "
        f"{offending}"
    )
