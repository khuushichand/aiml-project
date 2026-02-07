from __future__ import annotations

from pathlib import Path
import json

import pytest
from pydantic import ValidationError

from tldw_Server_API.app.core.UserProfiles import user_profile_catalog as catalog_module
from tldw_Server_API.app.core.UserProfiles.user_profile_catalog import (
    clear_user_profile_catalog_cache,
    load_user_profile_catalog,
)


def _write_catalog(tmp_path: Path, editable_by: str = "user") -> Path:
    payload = f"""
version: 1.0.0
updated_at: 2025-01-01T00:00:00Z
entries:
  - key: preferences.ui.theme
    label: Theme
    description: Preferred UI theme.
    type: string
    default: null
    editable_by: [{editable_by}]
    sensitivity: public
    ui: select
""".strip()
    path = tmp_path / "user_profile_catalog.yaml"
    path.write_text(payload, encoding="utf-8")
    return path


def test_user_profile_catalog_load_success(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path)
    catalog = load_user_profile_catalog(catalog_path)
    assert catalog.version == "1.0.0"
    assert catalog.entries[0].key == "preferences.ui.theme"


def test_user_profile_catalog_invalid_role(tmp_path: Path) -> None:
    catalog_path = _write_catalog(tmp_path, editable_by="invalid_role")
    with pytest.raises(ValidationError):
        load_user_profile_catalog(catalog_path)


@pytest.mark.asyncio
async def test_user_profile_catalog_endpoint_etag(tmp_path: Path, monkeypatch) -> None:
    catalog_path = _write_catalog(tmp_path)
    monkeypatch.setattr(catalog_module, "CATALOG_PATH", catalog_path)
    clear_user_profile_catalog_cache()
    from tldw_Server_API.app.api.v1.endpoints.users import get_user_profile_catalog

    resp = await get_user_profile_catalog(
        current_user={"id": 1, "username": "test-user"},
        if_none_match=None,
    )
    assert resp.status_code == 200
    etag = resp.headers.get("ETag")
    assert etag
    assert resp.headers.get("Cache-Control") == "max-age=3600"
    payload = json.loads(resp.body.decode("utf-8"))
    assert payload["version"] == "1.0.0"

    resp_304 = await get_user_profile_catalog(
        current_user={"id": 1, "username": "test-user"},
        if_none_match=etag,
    )
    assert resp_304.status_code == 304
    assert resp_304.headers.get("ETag") == etag
