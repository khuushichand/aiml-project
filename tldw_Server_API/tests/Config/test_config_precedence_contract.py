from __future__ import annotations

import pytest

from tldw_Server_API.app.core import config


@pytest.fixture(autouse=True)
def _reset_config_cache(monkeypatch):
    config.clear_config_cache()
    for key in ("TLDW_CONFIG_FILE", "TLDW_CONFIG_PATH", "TLDW_CONFIG_DIR"):
        monkeypatch.delenv(key, raising=False)
    yield
    config.clear_config_cache()
    for key in ("TLDW_CONFIG_FILE", "TLDW_CONFIG_PATH", "TLDW_CONFIG_DIR"):
        monkeypatch.delenv(key, raising=False)


def load_settings_for_test() -> dict:
    config.clear_config_cache()
    return dict(config.load_settings())


def test_env_overrides_config_file_for_redis_host(tmp_path, monkeypatch):
    cfg = tmp_path / "config.txt"
    cfg.write_text("[Redis]\nredis_host=config-file-host\n", encoding="utf-8")
    monkeypatch.setenv("TLDW_CONFIG_FILE", str(cfg))
    monkeypatch.setenv("REDIS_HOST", "env-host")

    settings = load_settings_for_test()

    assert settings["REDIS_HOST"] == "env-host"  # nosec B101


def test_missing_tts_defaults_never_emit_fixme_literal():
    settings = load_settings_for_test()
    assert "FIXME" not in str(settings.get("TTS_CONFIG", {}))  # nosec B101
