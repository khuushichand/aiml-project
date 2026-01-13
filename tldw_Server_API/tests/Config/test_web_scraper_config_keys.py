def test_web_scraper_router_config_keys(monkeypatch):
    from tldw_Server_API.app.core import config as cfg

    monkeypatch.delenv("CUSTOM_SCRAPERS_YAML_PATH", raising=False)
    monkeypatch.delenv("WEB_SCRAPER_DEFAULT_BACKEND", raising=False)
    monkeypatch.delenv("WEB_SCRAPER_UA_MODE", raising=False)

    class FakeConfig:
        def __init__(self, values):
            self._values = values

        def get(self, section, key, fallback=None):
            return self._values.get((section, key), fallback)

        def getboolean(self, section, key, fallback=False):  # noqa: ARG002
            return fallback

        def getint(self, section, key, fallback=0):  # noqa: ARG002
            return fallback

        def has_section(self, section):  # noqa: ARG002
            return False

        def __contains__(self, section):  # noqa: ARG002
            return False

        def __getitem__(self, section):  # noqa: ARG002
            return {}

    fake = FakeConfig(
        {
            ("Web-Scraper", "custom_scrapers_yaml_path"): "/tmp/custom_scrapers.yaml",
            ("Web-Scraper", "web_scraper_default_backend"): "curl",
            ("Web-Scraper", "web_scraper_ua_mode"): "rotate",
        }
    )

    monkeypatch.setattr(cfg, "load_comprehensive_config", lambda: fake)

    data = cfg.load_and_log_configs()
    ws_cfg = data["web_scraper"]

    assert ws_cfg["custom_scrapers_yaml_path"] == "/tmp/custom_scrapers.yaml"
    assert ws_cfg["web_scraper_default_backend"] == "curl"
    assert ws_cfg["web_scraper_ua_mode"] == "rotate"
