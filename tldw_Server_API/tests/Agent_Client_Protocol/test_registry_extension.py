"""Tests for AgentRegistryEntry new fields (Task 8)."""
from __future__ import annotations

from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import (
    AgentRegistryEntry,
)


class TestRegistryEntryNewFieldsHaveDefaults:
    """Creating an entry with only type+name should populate all new field defaults."""

    def test_registry_entry_new_fields_have_defaults(self) -> None:
        entry = AgentRegistryEntry(type="test_agent", name="Test Agent")

        # Original defaults still hold
        assert entry.description == ""
        assert entry.command == ""
        assert entry.args == []
        assert entry.env == {}
        assert entry.requires_api_key is None
        assert entry.default is False
        assert entry.install_instructions == []
        assert entry.docs_url is None

        # New field defaults
        assert entry.protocol == "stdio"
        assert entry.tool_execution_mode == "agent_side"
        assert entry.mcp_transport == "stdio"
        assert entry.api_base_url is None
        assert entry.model is None
        assert entry.tools_from == "auto"
        assert entry.sandbox == "none"
        assert entry.trust_level == "standard"


class TestRegistryEntryWithOpenaiProtocol:
    """Creating an entry with openai_tool_use protocol and related fields."""

    def test_registry_entry_with_openai_protocol(self) -> None:
        entry = AgentRegistryEntry(
            type="openai_agent",
            name="OpenAI Agent",
            protocol="openai_tool_use",
            api_base_url="https://api.openai.com/v1",
            model="gpt-4o",
            tool_execution_mode="server_side",
            trust_level="trusted",
        )

        assert entry.protocol == "openai_tool_use"
        assert entry.api_base_url == "https://api.openai.com/v1"
        assert entry.model == "gpt-4o"
        assert entry.tool_execution_mode == "server_side"
        assert entry.trust_level == "trusted"
        # Other new fields still at defaults
        assert entry.mcp_transport == "stdio"
        assert entry.tools_from == "auto"
        assert entry.sandbox == "none"


class TestRegistryEntryFromYamlDictWithNewFields:
    """Simulate YAML parsing by constructing from a dict (as load() does)."""

    def test_registry_entry_from_yaml_dict_with_new_fields(self) -> None:
        yaml_dict = {
            "type": "mcp_agent",
            "name": "MCP Agent",
            "description": "An MCP-based agent",
            "command": "mcp-server",
            "args": ["--port", "8080"],
            "protocol": "mcp",
            "mcp_transport": "sse",
            "tool_execution_mode": "hybrid",
            "sandbox": "required",
            "trust_level": "untrusted",
            "tools_from": "static",
        }

        entry = AgentRegistryEntry(
            type=str(yaml_dict["type"]),
            name=str(yaml_dict["name"]),
            description=str(yaml_dict.get("description", "")),
            command=str(yaml_dict.get("command", "")),
            args=list(yaml_dict.get("args", [])),
            protocol=str(yaml_dict.get("protocol", "stdio")),
            mcp_transport=str(yaml_dict.get("mcp_transport", "stdio")),
            tool_execution_mode=str(yaml_dict.get("tool_execution_mode", "agent_side")),
            sandbox=str(yaml_dict.get("sandbox", "none")),
            trust_level=str(yaml_dict.get("trust_level", "standard")),
            tools_from=str(yaml_dict.get("tools_from", "auto")),
        )

        assert entry.type == "mcp_agent"
        assert entry.name == "MCP Agent"
        assert entry.protocol == "mcp"
        assert entry.mcp_transport == "sse"
        assert entry.tool_execution_mode == "hybrid"
        assert entry.sandbox == "required"
        assert entry.trust_level == "untrusted"
        assert entry.tools_from == "static"
        assert entry.api_base_url is None
        assert entry.model is None
