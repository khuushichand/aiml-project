import time
from pathlib import Path

import pytest

from tldw_Server_API.app.core.Resource_Governance.policy_loader import PolicyLoader, PolicyReloadConfig


pytestmark = pytest.mark.rate_limit


class _StoreWithRouteMap:
    def __init__(self):
        self._ver = 1
        self._updated = time.time()

    async def get_latest_policy(self):
        # Return 5-tuple including route_map that conflicts with file route_map
        policies = {"chat.default": {"requests": {"rpm": 100}}}
        tenant = {}
        db_route_map = {"by_path": {"/api/v1/chat/*": "db.policy"}}
        return self._ver, policies, tenant, db_route_map, float(self._updated)


@pytest.mark.asyncio
async def test_file_route_map_overrides_db_route_map_on_conflict(tmp_path: Path):
    # Create a YAML with a conflicting route_map mapping for the same path
    yaml_path = tmp_path / "rg.yaml"
    yaml_path.write_text(
        (
            "version: 1\n"
            "policies:\n"
            "  chat.default:\n"
            "    requests: { rpm: 60 }\n"
            "route_map:\n"
            "  by_path:\n"
            "    /api/v1/chat/*: file.policy\n"
        ),
        encoding="utf-8",
    )

    loader = PolicyLoader(str(yaml_path), PolicyReloadConfig(enabled=False), store=_StoreWithRouteMap())
    snap = await loader.load_once()
    # Assert route_map exists and file mapping takes precedence over DB mapping
    assert snap.route_map.get("by_path", {}).get("/api/v1/chat/*") == "file.policy"
