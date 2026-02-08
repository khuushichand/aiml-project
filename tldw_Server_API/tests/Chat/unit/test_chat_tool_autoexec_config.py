from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Chat import chat_service


@pytest.mark.unit
def test_tool_autoexec_getters_use_defaults_when_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    keys = (
        "CHAT_AUTO_EXECUTE_TOOLS",
        "CHAT_MAX_TOOL_CALLS",
        "CHAT_TOOL_TIMEOUT_MS",
        "CHAT_TOOL_ALLOW_CATALOG",
        "CHAT_TOOL_IDEMPOTENCY",
        "CHAT_TOOL_AUTO_CONTINUE_ONCE",
    )
    for key in keys:
        monkeypatch.delenv(key, raising=False)

    assert chat_service.should_auto_execute_tools() is chat_service.CHAT_AUTO_EXECUTE_TOOLS
    assert chat_service.get_chat_max_tool_calls() == chat_service.CHAT_MAX_TOOL_CALLS
    assert chat_service.get_chat_tool_timeout_ms() == chat_service.CHAT_TOOL_TIMEOUT_MS
    assert chat_service.get_chat_tool_allow_catalog() == chat_service.CHAT_TOOL_ALLOW_CATALOG
    assert chat_service.should_attach_tool_idempotency() is chat_service.CHAT_TOOL_IDEMPOTENCY
    assert chat_service.should_auto_continue_tools_once() is chat_service.CHAT_TOOL_AUTO_CONTINUE_ONCE


@pytest.mark.unit
def test_tool_autoexec_env_overrides(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_AUTO_EXECUTE_TOOLS", "true")
    monkeypatch.setenv("CHAT_MAX_TOOL_CALLS", "7")
    monkeypatch.setenv("CHAT_TOOL_TIMEOUT_MS", "3200")
    monkeypatch.setenv("CHAT_TOOL_ALLOW_CATALOG", "notes.search,media.*")
    monkeypatch.setenv("CHAT_TOOL_IDEMPOTENCY", "false")
    monkeypatch.setenv("CHAT_TOOL_AUTO_CONTINUE_ONCE", "true")

    assert chat_service.should_auto_execute_tools() is True
    assert chat_service.get_chat_max_tool_calls() == 7
    assert chat_service.get_chat_tool_timeout_ms() == 3200
    assert chat_service.get_chat_tool_allow_catalog() == ["notes.search", "media.*"]
    assert chat_service.should_attach_tool_idempotency() is False
    assert chat_service.should_auto_continue_tools_once() is True


@pytest.mark.unit
def test_tool_autoexec_numeric_bounds_are_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_MAX_TOOL_CALLS", "0")
    assert chat_service.get_chat_max_tool_calls() == 1

    monkeypatch.setenv("CHAT_MAX_TOOL_CALLS", "999")
    assert chat_service.get_chat_max_tool_calls() == 20

    monkeypatch.setenv("CHAT_TOOL_TIMEOUT_MS", "-50")
    assert chat_service.get_chat_tool_timeout_ms() == 1000

    monkeypatch.setenv("CHAT_TOOL_TIMEOUT_MS", "999999")
    assert chat_service.get_chat_tool_timeout_ms() == 120000


@pytest.mark.unit
def test_parse_tool_allow_catalog_parses_and_filters_tokens() -> None:
    assert chat_service._parse_tool_allow_catalog("*") is None
    assert chat_service._parse_tool_allow_catalog("  ") is None
    assert chat_service._parse_tool_allow_catalog("notes.search, media.*,notes.search") == [
        "notes.search",
        "media.*",
    ]
    assert chat_service._parse_tool_allow_catalog("bad*middle*, !!!, notes.search") == ["notes.search"]


@pytest.mark.unit
def test_tool_allow_catalog_fail_open_for_invalid_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CHAT_TOOL_ALLOW_CATALOG", "@@@,%%%")
    assert chat_service.get_chat_tool_allow_catalog() is None
