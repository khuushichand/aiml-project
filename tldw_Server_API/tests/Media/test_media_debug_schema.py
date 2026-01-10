from __future__ import annotations

import pytest


def test_media_debug_schema_basic(client_user_only) -> None:


     response = client_user_only.get("/api/v1/media/debug/schema")
    assert response.status_code == 200

    data = response.json()
    assert isinstance(data, dict)
    assert "tables" in data
    assert "media_columns" in data
    assert "media_mods_columns" in data
    assert "media_count" in data

    assert isinstance(data["tables"], list)
    assert isinstance(data["media_columns"], list)
    assert isinstance(data["media_mods_columns"], list)
    assert isinstance(data["media_count"], int)
