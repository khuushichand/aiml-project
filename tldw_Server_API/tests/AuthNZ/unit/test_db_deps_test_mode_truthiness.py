from __future__ import annotations

import os
from pathlib import Path

import pytest

from tldw_Server_API.app.api.v1.API_Deps import DB_Deps as db_deps


pytestmark = pytest.mark.unit


def test_get_db_path_for_user_testing_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("USER_DB_BASE_DIR", raising=False)
    monkeypatch.setenv("TESTING", "y")
    monkeypatch.setenv("TLDW_TEST_RUN_ID", "truthy-y")

    def _fake_get_media_db_path(user_id: int) -> Path:
        base = os.environ["USER_DB_BASE_DIR"]
        return Path(base) / f"{user_id}.db"

    monkeypatch.setattr(
        db_deps.DatabasePaths,
        "get_media_db_path",
        _fake_get_media_db_path,
        raising=True,
    )

    resolved = db_deps._get_db_path_for_user(7)

    base_dir = os.environ.get("USER_DB_BASE_DIR", "")
    assert "user_databases_test" in base_dir
    assert resolved == Path(base_dir) / "7.db"
