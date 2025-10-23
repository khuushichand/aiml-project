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
