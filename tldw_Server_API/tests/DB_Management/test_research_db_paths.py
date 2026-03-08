import pytest


pytestmark = pytest.mark.unit


def test_research_db_path_is_per_user(monkeypatch, tmp_path):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("USER_DB_BASE_DIR", str(tmp_path / "user_databases"))

    from tldw_Server_API.app.core import config as cfg

    cfg.clear_config_cache()

    from tldw_Server_API.app.core.DB_Management.db_path_utils import DatabasePaths

    path = DatabasePaths.get_research_sessions_db_path(42)
    assert path.name == "ResearchSessions.db"
    assert path.parent == tmp_path / "user_databases" / "42"
    assert path.parent.exists()
