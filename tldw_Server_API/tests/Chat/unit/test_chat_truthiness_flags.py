import pytest

from tldw_Server_API.app.api.v1.endpoints import chat


pytestmark = pytest.mark.unit


def test_chat_connectors_enabled_accepts_single_letter_y(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHAT_CONNECTORS_V2_ENABLED", "y")

    assert chat._chat_connectors_enabled() is True


def test_chat_cfg_bool_cmds_accepts_single_letter_y_from_env(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CHAT_CMDS_TEST_FLAG", "y")

    assert chat._cfg_bool_cmds("CHAT_CMDS_TEST_FLAG", "unused_cfg_key", False) is True


def test_chat_cfg_bool_cmds_accepts_single_letter_y_from_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("CHAT_CMDS_TEST_FLAG", raising=False)
    monkeypatch.setattr(chat, "_chat_commands_config", {"test_cfg_key": "y"}, raising=False)

    assert chat._cfg_bool_cmds("CHAT_CMDS_TEST_FLAG", "test_cfg_key", False) is True
