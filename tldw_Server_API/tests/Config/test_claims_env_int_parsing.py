import configparser

from tldw_Server_API.app.core import config


def test_load_settings_claims_invalid_env_ints_fallback_to_config(monkeypatch):
    """Invalid env values should not crash claims integer parsing."""
    monkeypatch.setenv("CLAIMS_CONTEXT_WINDOW_CHARS", "not-an-int")
    monkeypatch.setenv("CLAIMS_EXTRACTION_PASSES", "NaN")

    parser = configparser.ConfigParser()
    parser.add_section("Claims")
    parser.set("Claims", "CLAIMS_CONTEXT_WINDOW_CHARS", "777")
    parser.set("Claims", "CLAIMS_EXTRACTION_PASSES", "4")

    monkeypatch.setattr(config, "_load_env_files_early", lambda: None, raising=True)
    monkeypatch.setattr(config, "load_and_log_configs", lambda: {}, raising=True)
    monkeypatch.setattr(config, "load_comprehensive_config", lambda: parser, raising=True)

    settings = config.load_settings()

    if settings["CLAIMS_CONTEXT_WINDOW_CHARS"] != 777:
        raise AssertionError("CLAIMS_CONTEXT_WINDOW_CHARS should fall back to config value 777")
    if settings["CLAIMS_EXTRACTION_PASSES"] != 4:
        raise AssertionError("CLAIMS_EXTRACTION_PASSES should fall back to config value 4")
