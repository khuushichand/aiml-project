import pytest

from tldw_Server_API.app.core.DB_Management import db_path_utils
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings


def test_get_user_base_directory_expands_user(monkeypatch, tmp_path):

    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", "~/custom_db_root")

    user_dir = DatabasePaths.get_user_base_directory(42)

    expected = tmp_path / "custom_db_root" / "42"
    assert user_dir == expected
    assert expected.exists()


def test_get_user_base_directory_resolves_relative(monkeypatch, tmp_path):

    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", "relative_root")
    monkeypatch.setattr(db_path_utils, "get_project_root", lambda: str(tmp_path))

    user_dir = DatabasePaths.get_user_base_directory(7)

    expected = tmp_path / "relative_root" / "7"
    assert user_dir == expected
    assert expected.exists()


def test_get_user_base_directory_single_user_none_resolves_fixed_id(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setitem(settings, "SINGLE_USER_FIXED_ID", "42")
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    user_dir = DatabasePaths.get_user_base_directory(None)

    expected = tmp_path / "user_dbs" / "42"
    assert user_dir == expected
    assert expected.exists()


def test_get_user_base_directory_multi_user_none_raises(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "multi_user")
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    with pytest.raises(ValueError, match="user_id is required in multi-user mode"):
        DatabasePaths.get_user_base_directory(None)


def test_user_db_base_dir_settings_override_env_outside_tests(monkeypatch, tmp_path):
    env_base = tmp_path / "env_base"
    settings_base = tmp_path / "settings_base"
    monkeypatch.setenv("USER_DB_BASE_DIR", str(env_base))
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(settings_base))
    monkeypatch.setattr(db_path_utils, "_is_test_context", lambda: False)

    base_dir = DatabasePaths.get_user_db_base_dir()

    assert base_dir == settings_base
    assert base_dir.exists()


def test_invalid_user_id_rejected_outside_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))
    monkeypatch.setattr(db_path_utils, "_is_test_context", lambda: False)

    with pytest.raises(ValueError, match="Invalid user_id"):
        DatabasePaths.get_user_base_directory("..")
