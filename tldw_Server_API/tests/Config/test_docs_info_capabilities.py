from pathlib import Path

from tldw_Server_API.app.api.v1.endpoints import config_info
from tldw_Server_API.app.core.config import _route_toggle_policy
from tldw_Server_API.app.core.config import settings as core_settings


def _write_minimal_config(path: Path, *, stable_only: bool = True) -> None:
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
                f"stable_only = {'true' if stable_only else 'false'}",
            ]
        ),
        encoding="utf-8",
    )


def test_docs_info_persona_capability_enabled_by_default_even_when_stable_only_true(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "true")
    monkeypatch.delenv("ROUTES_DISABLE", raising=False)
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", True)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is True
    assert safe_config["supported_features"]["persona"] is True
    assert safe_config["capabilities"] == safe_config["supported_features"]


def test_docs_info_persona_capability_can_be_disabled_via_route_toggle(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "true")
    monkeypatch.setenv("ROUTES_DISABLE", "persona")
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", True)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is False
    assert safe_config["supported_features"]["persona"] is False


def test_docs_info_persona_feature_flag_disables_capability_even_when_route_enabled(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "true")
    monkeypatch.setenv("ROUTES_ENABLE", "persona")
    monkeypatch.delenv("ROUTES_DISABLE", raising=False)
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", False)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is False
    assert safe_config["supported_features"]["persona"] is False


def test_docs_info_persona_capability_enabled_by_default_when_stable_only_false(
    monkeypatch, tmp_path: Path
) -> None:
    config_path = tmp_path / "config.txt"
    _write_minimal_config(config_path, stable_only=False)

    monkeypatch.setenv("TLDW_CONFIG_PATH", str(config_path))
    monkeypatch.setenv("ROUTES_STABLE_ONLY", "false")
    monkeypatch.delenv("ROUTES_DISABLE", raising=False)
    monkeypatch.delenv("ROUTES_ENABLE", raising=False)
    monkeypatch.setitem(core_settings, "PERSONA_ENABLED", True)
    _route_toggle_policy.cache_clear()

    safe_config = config_info.load_safe_config()

    assert safe_config["capabilities"]["persona"] is True
    assert safe_config["supported_features"]["persona"] is True
