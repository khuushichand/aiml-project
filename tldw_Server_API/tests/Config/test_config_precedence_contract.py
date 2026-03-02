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


def test_section_loaders_return_typed_models():
    sections = config.load_all_sections_for_test()
    assert hasattr(sections, "auth")  # nosec B101
    assert hasattr(sections, "rag")  # nosec B101
    assert hasattr(sections, "audio")  # nosec B101
    assert hasattr(sections, "providers")  # nosec B101


def test_tts_defaults_are_valid_values_not_placeholders(monkeypatch):
    class FakeConfig:
        def __init__(self, values):
            self._values = values

        def get(self, section, key, fallback=None):
            return self._values.get((section, key), fallback)

        def getboolean(self, section, key, fallback=False):  # noqa: ARG002
            value = self._values.get((section, key))
            if value is None:
                return fallback
            if isinstance(value, bool):
                return value
            return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

        def getint(self, section, key, fallback=0):  # noqa: ARG002
            value = self._values.get((section, key))
            if value is None:
                return fallback
            return int(value)

        def getfloat(self, section, key, fallback=0.0):  # noqa: ARG002
            value = self._values.get((section, key))
            if value is None:
                return fallback
            return float(value)

        def has_section(self, section):  # noqa: ARG002
            return False

        def __contains__(self, section):  # noqa: ARG002
            return False

        def __getitem__(self, section):  # noqa: ARG002
            return {}

    def _fake_loader():
        return FakeConfig({})

    _fake_loader.cache_clear = lambda: None
    monkeypatch.setattr(config, "load_comprehensive_config", _fake_loader)

    cfg = config.load_and_log_configs()
    tts = cfg["tts_settings"]

    assert tts["default_eleven_tts_model"] != "FIXME"  # nosec B101
    assert tts["default_eleven_tts_voice"] != "FIXME"  # nosec B101
    assert tts["default_google_tts_model"] != "FIXME"  # nosec B101
    assert tts["default_google_tts_voice"] != "FIXME"  # nosec B101
