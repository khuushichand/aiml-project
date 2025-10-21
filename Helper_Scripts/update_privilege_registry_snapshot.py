"""Regenerate the privilege route registry snapshot used by CI.

Usage:
    python Helper_Scripts/update_privilege_registry_snapshot.py
"""
from __future__ import annotations

import json
from pathlib import Path

from tldw_Server_API.app.main import app as fastapi_app
from tldw_Server_API.app.core.AuthNZ.privilege_catalog import load_catalog
from tldw_Server_API.app.core.PrivilegeMaps.introspection import (
    collect_privilege_route_registry,
    serialize_route_registry,
)


def main() -> None:
    catalog = load_catalog()
    registry = collect_privilege_route_registry(fastapi_app, catalog, strict=False)
    serialized = serialize_route_registry(registry)

    snapshot_path = Path("tldw_Server_API/tests/fixtures/privilege_route_registry_snapshot.json")
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(serialized, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"Updated snapshot written to {snapshot_path}")


if __name__ == "__main__":
    main()
