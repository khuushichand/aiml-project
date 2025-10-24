import pytest

from tldw_Server_API.app.core.AuthNZ import User_DB_Handling as user_handling
from tldw_Server_API.app.core.AuthNZ.settings import reset_settings


def _reset_single_user_instance():
    user_handling._single_user_instance = None  # type: ignore[attr-defined]


@pytest.mark.parametrize("initial_id,updated_id", [(42, 99)])
def test_single_user_instance_tracks_settings(monkeypatch, initial_id, updated_id):
    monkeypatch.setenv("AUTH_MODE", "single_user")
    monkeypatch.setenv("SINGLE_USER_API_KEY", "fixed-id-test")
    monkeypatch.setenv("SINGLE_USER_FIXED_ID", str(initial_id))
    reset_settings()
    _reset_single_user_instance()

    try:
        first = user_handling.get_single_user_instance()
        assert first.id == initial_id

        monkeypatch.setenv("SINGLE_USER_FIXED_ID", str(updated_id))
        reset_settings()

        second = user_handling.get_single_user_instance()
        assert second.id == updated_id
    finally:
        for env_key in ("AUTH_MODE", "SINGLE_USER_API_KEY", "SINGLE_USER_FIXED_ID"):
            monkeypatch.delenv(env_key, raising=False)
        reset_settings()
        _reset_single_user_instance()
