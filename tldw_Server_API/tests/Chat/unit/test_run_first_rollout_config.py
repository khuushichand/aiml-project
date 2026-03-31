from __future__ import annotations

import configparser

import pytest


pytestmark = pytest.mark.unit


def test_resolve_chat_run_first_rollout_mode_defaults_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.core import config

    monkeypatch.delenv("CHAT_RUN_FIRST_ROLLOUT_MODE", raising=False)
    monkeypatch.delenv("CHAT_RUN_FIRST_PROVIDER_ALLOWLIST", raising=False)
    monkeypatch.delenv("CHAT_RUN_FIRST_PRESENTATION_VARIANT", raising=False)
    monkeypatch.delenv("ACP_RUN_FIRST_ROLLOUT_MODE", raising=False)
    monkeypatch.delenv("ACP_RUN_FIRST_PROVIDER_ALLOWLIST", raising=False)
    monkeypatch.delenv("ACP_RUN_FIRST_PRESENTATION_VARIANT", raising=False)

    assert config.resolve_chat_run_first_rollout_mode() == "off"


def test_resolve_chat_run_first_provider_allowlist_parses_csv(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.core import config

    monkeypatch.setenv(
        "CHAT_RUN_FIRST_PROVIDER_ALLOWLIST",
        "openai:gpt-4o-mini,anthropic:claude-3-7-sonnet",
    )

    assert config.resolve_chat_run_first_provider_allowlist() == [
        "openai:gpt-4o-mini",
        "anthropic:claude-3-7-sonnet",
    ]


def test_resolve_chat_run_first_rollout_mode_uses_chat_module_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.core import config

    monkeypatch.delenv("CHAT_RUN_FIRST_ROLLOUT_MODE", raising=False)

    parser = configparser.ConfigParser()
    parser.add_section("Chat-Module")
    parser.set("Chat-Module", "run_first_rollout_mode", "gated")
    monkeypatch.setattr(config, "load_comprehensive_config", lambda: parser)

    assert config.resolve_chat_run_first_rollout_mode() == "gated"


def test_resolve_chat_run_first_provider_allowlist_uses_chat_module_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.core import config

    monkeypatch.delenv("CHAT_RUN_FIRST_PROVIDER_ALLOWLIST", raising=False)

    parser = configparser.ConfigParser()
    parser.add_section("Chat-Module")
    parser.set(
        "Chat-Module",
        "run_first_provider_allowlist",
        "openai:gpt-4o-mini,anthropic:claude-3-7-sonnet",
    )
    monkeypatch.setattr(config, "load_comprehensive_config", lambda: parser)

    assert config.resolve_chat_run_first_provider_allowlist() == [
        "openai:gpt-4o-mini",
        "anthropic:claude-3-7-sonnet",
    ]


def test_resolve_chat_run_first_presentation_variant_uses_chat_module_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from tldw_Server_API.app.core import config

    monkeypatch.delenv("CHAT_RUN_FIRST_PRESENTATION_VARIANT", raising=False)

    parser = configparser.ConfigParser()
    parser.add_section("Chat-Module")
    parser.set("Chat-Module", "run_first_presentation_variant", "chat_phase2a_v2")
    monkeypatch.setattr(config, "load_comprehensive_config", lambda: parser)

    assert config.resolve_chat_run_first_presentation_variant() == "chat_phase2a_v2"
