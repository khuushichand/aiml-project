from tldw_Server_API.app.core import startup_logging


def test_startup_api_key_log_value_masks_by_default(monkeypatch) -> None:
    monkeypatch.delenv("SHOW_API_KEY_ON_STARTUP", raising=False)

    api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
    display = startup_logging.startup_api_key_log_value(api_key)

    assert display != api_key
    assert display == startup_logging.mask_api_key_for_startup_logs(api_key)


def test_startup_api_key_log_value_shows_full_key_only_when_explicit(monkeypatch) -> None:
    monkeypatch.setenv("SHOW_API_KEY_ON_STARTUP", "true")

    api_key = "sk-abcdefghijklmnopqrstuvwxyz123456"
    display = startup_logging.startup_api_key_log_value(api_key)

    assert display == api_key
