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


def test_get_config_section_and_value_reads_file(tmp_path, monkeypatch):
    cfg = tmp_path / "config.txt"
    cfg.write_text("[Server]\nhost=0.0.0.0\nport=1234\n", encoding="utf-8")
    monkeypatch.setenv("TLDW_CONFIG_FILE", str(cfg))

    section = config.get_config_section("Server")
    assert section["host"] == "0.0.0.0"
    assert config.get_config_value("Server", "port") == "1234"
    assert config.get_config_value("Server", "missing", default="fallback") == "fallback"

    metadata = config.get_config_source_metadata()
    assert metadata["path"] == str(cfg)
    assert metadata["loaded"] is True


def test_config_cache_reload(tmp_path, monkeypatch):
    cfg = tmp_path / "config.txt"
    cfg.write_text("[Server]\nhost=first\n", encoding="utf-8")
    monkeypatch.setenv("TLDW_CONFIG_FILE", str(cfg))

    assert config.get_config_value("Server", "host") == "first"

    cfg.write_text("[Server]\nhost=second\n", encoding="utf-8")
    assert config.get_config_value("Server", "host") == "first"
    assert config.get_config_value("Server", "host", reload=True) == "second"


def test_missing_config_path_returns_empty(tmp_path, monkeypatch):
    monkeypatch.setenv("TLDW_CONFIG_PATH", str(tmp_path))

    section = config.get_config_section("Server")
    assert section == {}

    metadata = config.get_config_source_metadata()
    assert metadata["path"] == str(tmp_path / "config.txt")
    assert metadata["loaded"] is False


def test_missing_config_file_env_raises(tmp_path, monkeypatch):
    missing = tmp_path / "missing-config.txt"
    monkeypatch.setenv("TLDW_CONFIG_FILE", str(missing))

    with pytest.raises(FileNotFoundError):
        config.get_config_section("Server")
