"""Tests for ACP run-first MCP tool presentation."""

from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.adapters.mcp_tool_presentation import (
    present_acp_tools,
)


pytestmark = pytest.mark.unit


RUN_TOOL = {
    "name": "run",
    "description": "Execute governed virtual CLI commands.",
    "inputSchema": {
        "type": "object",
        "properties": {"command": {"type": "string"}},
    },
}

NOTES_TOOL = {
    "name": "notes.search",
    "description": "Search notes for relevant passages.",
    "inputSchema": {
        "type": "object",
        "properties": {"query": {"type": "string"}},
    },
}


def test_present_acp_tools_orders_run_first_for_eligible_session() -> None:
    presented = present_acp_tools(
        session_id="s1",
        tools=[NOTES_TOOL, RUN_TOOL],
        rollout_mode="gated",
        provider_key="openai:gpt-4o-mini",
        provider_allowlist=["openai:gpt-4o-mini"],
    )

    assert [tool["function"]["name"] for tool in presented.openai_tools] == [
        "run",
        "notes.search",
    ]
    assert presented.effective_tool_names == ["run", "notes.search"]
    assert presented.prompt_fragment is not None
    assert presented.eligible is True
    assert presented.ineligible_reason is None


def test_present_acp_tools_demotes_typed_tool_descriptions_when_eligible() -> None:
    presented = present_acp_tools(
        session_id="s2",
        tools=[RUN_TOOL, NOTES_TOOL],
        rollout_mode="gated",
        provider_key="openai:gpt-4o-mini",
        provider_allowlist=["openai:gpt-4o-mini"],
    )

    assert presented.openai_tools[0]["function"]["description"].startswith(
        "Execute governed virtual CLI commands."
    )
    assert "Preferred first tool" in presented.openai_tools[0]["function"]["description"]
    assert presented.openai_tools[1]["function"]["description"].startswith("Fallback tool:")


def test_present_acp_tools_leaves_tools_untouched_when_run_missing() -> None:
    presented = present_acp_tools(
        session_id="s3",
        tools=[NOTES_TOOL],
        rollout_mode="gated",
        provider_key="openai:gpt-4o-mini",
        provider_allowlist=["openai:gpt-4o-mini"],
    )

    assert [tool["function"]["name"] for tool in presented.openai_tools] == ["notes.search"]
    assert presented.prompt_fragment is None
    assert presented.eligible is False
    assert presented.ineligible_reason == "run_missing"


def test_present_acp_tools_ignores_rollout_when_provider_not_in_cohort() -> None:
    presented = present_acp_tools(
        session_id="s4",
        tools=[RUN_TOOL, NOTES_TOOL],
        rollout_mode="gated",
        provider_key="anthropic:claude-3-7-sonnet",
        provider_allowlist=["openai:gpt-4o-mini"],
    )

    assert [tool["function"]["name"] for tool in presented.openai_tools] == [
        "run",
        "notes.search",
    ]
    assert presented.prompt_fragment is None
    assert presented.eligible is False
    assert presented.ineligible_reason == "provider_not_in_rollout_allowlist"
