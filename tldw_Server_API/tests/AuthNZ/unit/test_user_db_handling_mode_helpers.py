from types import SimpleNamespace

from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_handling


def test_is_single_user_mode_true(monkeypatch):
    monkeypatch.setattr(user_handling, "get_settings", lambda: SimpleNamespace(AUTH_MODE="single_user"))
    assert user_handling.is_single_user_mode() is True


def test_is_single_user_mode_false_for_multi_user(monkeypatch):
    monkeypatch.setattr(user_handling, "get_settings", lambda: SimpleNamespace(AUTH_MODE="multi_user"))
    assert user_handling.is_single_user_mode() is False


def test_is_single_user_mode_false_when_settings_lookup_fails(monkeypatch):
    def _boom():
        raise RuntimeError("settings unavailable")

    monkeypatch.setattr(user_handling, "get_settings", _boom)
    assert user_handling.is_single_user_mode() is False

