"""
Guardrail to keep API endpoint authorization claim-first.

The legacy `require_admin` dependency should remain as a compatibility shim in
auth dependencies only, not as a direct endpoint dependency in API route files.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest


@pytest.mark.unit
def test_api_endpoints_do_not_depend_on_legacy_require_admin() -> None:
    project_root = Path(__file__).resolve().parents[3]
    endpoints_root = project_root / "app" / "api" / "v1" / "endpoints"
    assert endpoints_root.exists(), f"Expected endpoints path not found: {endpoints_root}"

    depends_pattern = re.compile(r"Depends\(\s*(?:auth_deps\.)?require_admin\s*\)")
    import_pattern = re.compile(r"from\s+.*auth_deps\s+import\s+.*\brequire_admin\b")
    offending: list[str] = []

    for path in endpoints_root.rglob("*.py"):
        rel = path.relative_to(project_root).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if depends_pattern.search(line) or import_pattern.search(line):
                offending.append(f"{rel}:{lineno}:{line.strip()}")

    assert offending == [], (
        "Found legacy `Depends(require_admin)` callsites in API endpoints: "
        f"{offending}"
    )
