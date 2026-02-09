from pathlib import Path

from tldw_Server_API.app.api.v1.endpoints import config_info
from tldw_Server_API.app.core.config import _route_toggle_policy
from tldw_Server_API.app.core.config import settings as core_settings


def _write_minimal_config(path: Path) -> None:
    path.write_text(
        "\n".join(
            [
                "[Authentication]",
                "auth_mode = single_user",
                "single_user_api_key = test-key",
                "",
                "[Server]",
                "host = 127.0.0.1",
                "port = 8000",
                "",
                "[API-Routes]",
                "stable_only = true",
            ]
        ),
        encoding="utf-8",
    )


def test_docs_info_persona_capability_respects_route_policy(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", True)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is False
    assert safe_config["supported_features"]["persona"] is False
    assert safe_config["capabilities"] == safe_config["supported_features"]


def test_docs_info_persona_capability_can_be_enabled_via_route_toggle(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ROUTES_ENABLE", "persona")
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", True)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is True
    assert safe_config["supported_features"]["persona"] is True


def test_docs_info_persona_feature_flag_disables_capability_even_when_route_enabled(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ROUTES_ENABLE", "persona")
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", False)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is False
    assert safe_config["supported_features"]["persona"] is False

