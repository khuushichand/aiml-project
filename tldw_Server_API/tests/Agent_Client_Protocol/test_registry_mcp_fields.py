"""Tests for MCP orchestration fields on AgentRegistryEntry (Phase B)."""
from __future__ import annotations

import pytest

from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistryEntry

pytestmark = pytest.mark.unit


def test_registry_mcp_fields_defaults():
    """Entry with just type+name should have all 7 MCP defaults."""
    entry = AgentRegistryEntry(type="test_agent", name="Test Agent")

    assert entry.mcp_orchestration == "agent_driven"
    assert entry.mcp_entry_tool == "execute"
    assert entry.mcp_structured_response is False
    assert entry.mcp_llm_provider is None
    assert entry.mcp_llm_model is None
    assert entry.mcp_max_iterations == 20
    assert entry.mcp_refresh_tools is False


def test_registry_mcp_llm_driven_config():
    """Entry with mcp_orchestration='llm_driven' and explicit provider/model/iterations."""
    entry = AgentRegistryEntry(
        type="llm_agent",
        name="LLM Agent",
        mcp_orchestration="llm_driven",
        mcp_llm_provider="openai",
        mcp_llm_model="gpt-4o",
        mcp_max_iterations=50,
    )

    assert entry.mcp_orchestration == "llm_driven"
    assert entry.mcp_llm_provider == "openai"
    assert entry.mcp_llm_model == "gpt-4o"
    assert entry.mcp_max_iterations == 50
    # Other defaults unchanged
    assert entry.mcp_entry_tool == "execute"
    assert entry.mcp_structured_response is False
    assert entry.mcp_refresh_tools is False
