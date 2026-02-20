from __future__ import annotations

import importlib
import sys
import types

import pytest
from fastapi import APIRouter


@pytest.mark.unit
def test_media_router_keeps_core_routes_when_optional_module_import_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    module_name = "tldw_Server_API.app.api.v1.endpoints.media"
    sys.modules.pop(module_name, None)
    original_import_module = importlib.import_module

    listing_router = APIRouter()

    @listing_router.get("/")
    async def _fake_list_media():
        return {}

    item_router = APIRouter()

    @item_router.get("/{media_id}")
    async def _fake_get_media_item(media_id: int):
        return {"id": media_id}

    fake_listing_module = types.SimpleNamespace(router=listing_router)
    fake_item_module = types.SimpleNamespace(router=item_router)

    def _patched_import_module(name: str, package: str | None = None):
        if name == module_name:
            return original_import_module(name, package)
        if name == f"{module_name}.listing":
            return fake_listing_module
        if name == f"{module_name}.item":
            return fake_item_module
        if name.startswith(f"{module_name}."):
            raise ImportError(f"simulated endpoint import failure for {name}")
        if "Ingestion_Media_Processing.Audio" in name:
            raise ImportError(f"simulated heavy-import block for {name}")
        if name.endswith("Video.Video_DL_Ingestion_Lib"):
            raise ImportError(f"simulated heavy-import block for {name}")
        return original_import_module(name, package)

    monkeypatch.setattr(importlib, "import_module", _patched_import_module)
    media_module = importlib.import_module(module_name)
    route_paths = {route.path for route in media_module.router.routes}

    assert "/" in route_paths
    assert "/{media_id}" in route_paths
    assert "/process-audios" not in route_paths
