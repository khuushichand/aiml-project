"""Regenerate the privilege route registry snapshot used by CI.

Usage:
    python Helper_Scripts/update_privilege_registry_snapshot.py
"""
from __future__ import annotations

import json
import os
from pathlib import Path


def _apply_test_env_defaults() -> None:
    """Align environment with pytest defaults so snapshots match CI expectations."""
    os.environ["MINIMAL_TEST_APP"] = "1"
    os.environ["TEST_MODE"] = "1"
    os.environ["OTEL_SDK_DISABLED"] = "true"
    existing_disable = os.getenv("ROUTES_DISABLE", "")
    disable_parts = [p for p in existing_disable.replace(" ", ",").split(",") if p]
    disable_lower = {p.lower() for p in disable_parts}
    for key in ("research", "evaluations"):
        if key not in disable_lower:
            disable_parts.append(key)
            disable_lower.add(key)
    disable_parts = [p for p in disable_parts if p.lower() != "notes"]
    os.environ["ROUTES_DISABLE"] = ",".join(dict.fromkeys(disable_parts))
    existing_enable = os.getenv("ROUTES_ENABLE", "")
    parts = [p for p in existing_enable.replace(" ", ",").split(",") if p]
    lower_parts = {p.lower() for p in parts}
    for key in ("workflows", "scheduler"):
        if key not in lower_parts:
            parts.append(key)
            lower_parts.add(key)
    os.environ["ROUTES_ENABLE"] = ",".join(dict.fromkeys(parts))


def main() -> None:
    _apply_test_env_defaults()
    from tldw_Server_API.app.main import app as fastapi_app
    from tldw_Server_API.app.core.AuthNZ.privilege_catalog import load_catalog
    from tldw_Server_API.app.core.PrivilegeMaps.introspection import (
        collect_privilege_route_registry,
        serialize_route_registry,
    )

    catalog = load_catalog()
    registry = collect_privilege_route_registry(fastapi_app, catalog, strict=False)
    serialized = serialize_route_registry(registry)

    snapshot_path = Path("tldw_Server_API/tests/fixtures/privilege_route_registry_snapshot.json")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(serialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Updated snapshot written to {snapshot_path}")


if __name__ == "__main__":
    main()
