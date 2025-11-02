import pytest

from tldw_Server_API.app.core.LLM_Calls.LLM_API_Calls import _apply_tool_choice


def test_apply_tool_choice_none_when_no_tools_and_no_choice():
    payload = {}
    _apply_tool_choice(payload, tools=None, tool_choice=None)
    assert "tool_choice" not in payload


def test_apply_tool_choice_none_choice_sets_none_even_without_tools():
    payload = {}
    _apply_tool_choice(payload, tools=None, tool_choice="none")
    assert payload.get("tool_choice") == "none"


def test_apply_tool_choice_does_not_set_when_no_tools():
    payload = {}
    _apply_tool_choice(payload, tools=None, tool_choice={"type": "function", "function": {"name": "f"}})
    assert "tool_choice" not in payload


def test_apply_tool_choice_sets_when_tools_present():
    payload = {}
    tool_choice = {"type": "function", "function": {"name": "f", "arguments": "{}"}}
    _apply_tool_choice(payload, tools=[{"type": "function", "function": {"name": "f"}}], tool_choice=tool_choice)
    assert payload.get("tool_choice") == tool_choice
