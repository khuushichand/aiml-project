import pytest

from tldw_Server_API.app.core import config


@pytest.fixture(autouse=True)
def _reset_config_cache():
    """Ensure config caches are cleared before and after each test."""
    config.clear_config_cache()
    yield
    config.clear_config_cache()


def test_load_settings_uses_configured_redis_url(monkeypatch):
    """Settings should respect Redis connection details from config.txt."""
    # Ensure environment overrides are not present
    for key in ("REDIS_URL", "REDIS_HOST", "REDIS_PORT", "REDIS_DB", "REDIS_ENABLED", "CACHE_TTL"):
        monkeypatch.delenv(key, raising=False)

    # Provide a minimal comprehensive config with Redis settings
    def fake_load_and_log_configs():
        return {
            "Redis": {
                "redis_host": "redis.example.internal",
                "redis_port": "6381",
                "redis_db": "7",
                "redis_enabled": "true",
                "cache_ttl": "86400",
            },
            "Chat-Dictionaries": {},
            "Web-Scraping": {},
        }

    monkeypatch.setattr(config, "load_and_log_configs", fake_load_and_log_configs, raising=True)

    settings = config.settings

    assert settings["REDIS_HOST"] == "redis.example.internal"
    assert settings["REDIS_PORT"] == 6381
    assert settings["REDIS_DB"] == 7
    assert settings["CACHE_TTL"] == 86400
    assert settings["REDIS_URL"] == "redis://redis.example.internal:6381/7"
    assert settings["REDIS_ENABLED"] is True
