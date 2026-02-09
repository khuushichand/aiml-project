"""
Guardrail to keep API endpoint auth dependencies claim-first.

Legacy `get_current_user` should not be used directly as an endpoint dependency
inside `app/api/v1/endpoints`; endpoint auth should resolve an AuthPrincipal via
`get_auth_principal` and enforce claims from there.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest


@pytest.mark.unit
def test_api_endpoints_do_not_depend_on_legacy_get_current_user() -> None:
    project_root = Path(__file__).resolve().parents[3]
    endpoints_root = project_root / "app" / "api" / "v1" / "endpoints"
    assert endpoints_root.exists(), f"Expected endpoints path not found: {endpoints_root}"

    depends_pattern = re.compile(r"Depends\(\s*(?:auth_deps\.)?get_current_user\s*\)")
    import_pattern = re.compile(r"from\s+.*auth_deps\s+import\s+.*\bget_current_user\b")
    local_def_pattern = re.compile(r"^\s*async\s+def\s+get_current_user\s*\(")
    offending: list[str] = []

    for path in endpoints_root.rglob("*.py"):
        rel = path.relative_to(project_root).as_posix()
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if (
                depends_pattern.search(line)
                or import_pattern.search(line)
                or local_def_pattern.search(line)
            ):
                offending.append(f"{rel}:{lineno}:{stripped}")

    assert offending == [], (
        "Found legacy `Depends(get_current_user)` callsites in API endpoints: "
        f"{offending}"
    )
