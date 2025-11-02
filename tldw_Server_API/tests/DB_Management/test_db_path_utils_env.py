import os
import shutil
from pathlib import Path

import pytest


@pytest.mark.unit
def test_user_db_base_dir_env_absolute(monkeypatch, tmp_path):
    # Arrange: point base dir to a tmp path
    base = tmp_path / "user_dbs"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))

    # Ensure settings reload to pick up env
    from tldw_Server_API.app.core import config as cfg
    cfg.clear_config_cache()

    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    # Act
    uid = 7
    out = DatabasePaths.get_user_base_directory(uid)

    # Assert
    assert out == base / str(uid)
    assert out.exists() and out.is_dir()


@pytest.mark.unit
def test_user_db_base_dir_env_relative_anchors_to_project(monkeypatch):
    # Arrange: use a relative path; it should anchor to project root
    rel_dir = Path("Databases") / "tmp_user_dbs_test_env"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(rel_dir))

    # Ensure settings reload to pick up env
    from tldw_Server_API.app.core import config as cfg
    cfg.clear_config_cache()

    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
    from tldw_Server_API.app.core.Utils.Utils import get_project_root

    # Act
    uid = 9
    base_dir = DatabasePaths.get_user_base_directory(uid)

    # Expected absolute path under project root
    expected = Path(get_project_root()) / rel_dir / str(uid)
    try:
        assert base_dir == expected
        assert base_dir.exists() and base_dir.is_dir()
    finally:
        # Cleanup created directories to avoid polluting repo
        try:
            shutil.rmtree(expected.parent)
        except Exception:
            pass
