import pytest
from pathlib import Path

from tldw_Server_API.app.core.DB_Management import db_path_utils
from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths
from tldw_Server_API.app.core.config import settings
from tldw_Server_API.app.core.exceptions import InvalidStoragePathError


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


def test_non_numeric_user_id_rejected_outside_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))
    monkeypatch.setattr(db_path_utils, "_is_test_context", lambda: False)

    with pytest.raises(ValueError, match="Invalid user_id"):
        DatabasePaths.get_user_base_directory("user_abc")


def test_non_numeric_user_id_allowed_in_tests(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))
    monkeypatch.setattr(db_path_utils, "_is_test_context", lambda: True)

    user_dir = DatabasePaths.get_user_base_directory("user_abc")
    assert user_dir.name == "user_abc"


def test_user_db_base_dir_relative_escape_rejected(monkeypatch, tmp_path):
    project_root = tmp_path / "project"
    project_root.mkdir()
    monkeypatch.setattr(db_path_utils, "get_project_root", lambda: str(project_root))
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", "../outside")
    monkeypatch.delenv("USER_DB_BASE_DIR", raising=False)

    with pytest.raises(InvalidStoragePathError):
        DatabasePaths.get_user_base_directory(1)


def test_prompts_db_path_salt_rejects_path_separators(monkeypatch, tmp_path):
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    with pytest.raises(InvalidStoragePathError):
        DatabasePaths.get_prompts_db_path(1, salt="../bad")


def test_prompts_db_path_salt_accepts_safe_value(monkeypatch, tmp_path):
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", str(tmp_path / "user_dbs"))

    path = DatabasePaths.get_prompts_db_path(1, salt="safe_123")

    assert path.name == "user_prompts_v2_safe_123.sqlite"


def test_user_db_base_dir_test_fallback_is_not_repo_local(monkeypatch):
    """Test mode fallback should be isolated and must not write into repo-local Databases/user_databases."""
    monkeypatch.delenv("USER_DB_BASE_DIR", raising=False)
    monkeypatch.delenv("USER_DB_BASE", raising=False)
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", None)
    monkeypatch.setitem(settings, "USER_DB_BASE", None)
    monkeypatch.setattr(db_path_utils, "_is_test_context", lambda: True)

    repo_local_default = (Path.cwd() / "Databases" / "user_databases").resolve()
    resolved = DatabasePaths.get_user_db_base_dir()

    assert resolved != repo_local_default
    assert repo_local_default not in resolved.parents


def test_user_db_base_dir_test_fallback_uses_unique_run_tag(monkeypatch):
    monkeypatch.delenv("USER_DB_BASE_DIR", raising=False)
    monkeypatch.delenv("USER_DB_BASE", raising=False)
    monkeypatch.delenv("TLDW_TEST_RUN_ID", raising=False)
    monkeypatch.delenv("PYTEST_XDIST_WORKER", raising=False)
    monkeypatch.setitem(settings, "USER_DB_BASE_DIR", None)
    monkeypatch.setitem(settings, "USER_DB_BASE", None)
    monkeypatch.setattr(db_path_utils, "_is_test_context", lambda: True)

    resolved = DatabasePaths.get_user_db_base_dir()

    assert resolved.name != "default"
