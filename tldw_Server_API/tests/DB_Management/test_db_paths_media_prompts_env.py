import os
from pathlib import Path

import pytest


@pytest.mark.unit
def test_media_and_prompts_paths_follow_env_base(monkeypatch, tmp_path):
    # Arrange
    base = tmp_path / "user_data_base"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(base))

    # Reload settings so DatabasePaths picks env
    from tldw_Server_API.app.core import config as cfg
    cfg.clear_config_cache()

    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    uid = 3

    # Act
    media_path = DatabasePaths.get_media_db_path(uid)
    prompts_path = DatabasePaths.get_prompts_db_path(uid)

    # Assert media path under base/<uid>/Media_DB_v2.db
    assert media_path.parent == base / str(uid)
    assert media_path.name == DatabasePaths.MEDIA_DB_NAME

    # Assert prompts path under base/<uid>/prompts_user_dbs/user_prompts_v2.sqlite
    expected_prompts_dir = base / str(uid) / DatabasePaths.PROMPTS_SUBDIR
    assert prompts_path.parent == expected_prompts_dir
    assert prompts_path.name == DatabasePaths.PROMPTS_DB_NAME

    # Ensure directories are created
    assert media_path.parent.exists()
    assert prompts_path.parent.exists()
