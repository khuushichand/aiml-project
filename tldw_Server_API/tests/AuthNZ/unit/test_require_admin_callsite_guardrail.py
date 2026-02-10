"""
Guardrail to keep API endpoint authorization claim-first.

Legacy `require_admin`/`require_role` shims are removed. Endpoints must keep
using claim-first dependencies (`require_roles`, `require_permissions`) only.
"""

from __future__ import annotations

from pathlib import Path
import re

import pytest


@pytest.mark.unit
def test_api_endpoints_do_not_depend_on_legacy_admin_shims() -> None:
    project_root = Path(__file__).resolve().parents[3]
    endpoints_root = project_root / "app" / "api" / "v1" / "endpoints"
    assert endpoints_root.exists(), f"Expected endpoints path not found: {endpoints_root}"

    depends_pattern = re.compile(r"Depends\(\s*(?:auth_deps\.)?require_admin\s*\)")
    depends_role_pattern = re.compile(r"Depends\(\s*(?:auth_deps\.)?require_role\s*\(")
    import_pattern = re.compile(r"from\s+.*auth_deps\s+import\s+.*\brequire_admin\b")
    import_role_pattern = re.compile(r"from\s+.*auth_deps\s+import\s+.*\brequire_role\b")
    offending: list[str] = []

    for path in endpoints_root.rglob("*.py"):
        rel = path.relative_to(project_root).as_posix()
        lines = path.read_text(encoding="utf-8").splitlines()
        for lineno, line in enumerate(lines, start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if (
                depends_pattern.search(line)
                or depends_role_pattern.search(line)
                or import_pattern.search(line)
                or import_role_pattern.search(line)
            ):
                offending.append(f"{rel}:{lineno}:{line.strip()}")

    assert offending == [], (
        "Found legacy `require_admin`/`require_role` callsites in API endpoints: "
        f"{offending}"
    )


@pytest.mark.unit
def test_auth_deps_module_no_longer_exports_legacy_admin_shims() -> None:
    from tldw_Server_API.app.api.v1.API_Deps import auth_deps

    assert not hasattr(auth_deps, "require_admin")
    assert not hasattr(auth_deps, "require_role")
