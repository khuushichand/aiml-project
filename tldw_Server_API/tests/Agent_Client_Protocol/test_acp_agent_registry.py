"""Tests for ACP agent registry (Phase 2)."""
from __future__ import annotations

import os
import tempfile

import pytest

pytestmark = pytest.mark.unit


SAMPLE_REGISTRY = """
agents:
  - type: claude_code
    name: Claude Code
    description: Test agent
    command: nonexistent_binary_xyz
    args: []
    env: {}
    requires_api_key: ANTHROPIC_API_KEY
    default: true

  - type: test_agent
    name: Test Agent
    description: A test agent
    command: python3
    args: ["-c", "pass"]
    env: {}
    requires_api_key: null
    default: false
"""


@pytest.fixture
def registry_file():
    """Create a temporary registry YAML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(SAMPLE_REGISTRY)
        path = f.name
    yield path
    os.unlink(path)


def test_registry_loads_from_yaml(registry_file):
    """Registry loads agent entries from YAML file."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    reg = AgentRegistry(yaml_path=registry_file)
    reg.load()

    assert len(reg.entries) == 2
    assert reg.default_type == "claude_code"


def test_registry_entry_fields(registry_file):
    """Registry entries have correct field values."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    reg = AgentRegistry(yaml_path=registry_file)
    reg.load()

    entry = reg.get_entry("claude_code")
    assert entry is not None
    assert entry.name == "Claude Code"
    assert entry.requires_api_key == "ANTHROPIC_API_KEY"
    assert entry.default is True


def test_registry_get_entry_none(registry_file):
    """get_entry returns None for unknown type."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    reg = AgentRegistry(yaml_path=registry_file)
    reg.load()

    assert reg.get_entry("nonexistent") is None


def test_registry_check_availability(registry_file, monkeypatch):
    """check_availability detects missing binary and API key."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)

    reg = AgentRegistry(yaml_path=registry_file)
    reg.load()

    # claude_code has nonexistent binary and (likely) no API key
    entry = reg.get_entry("claude_code")
    avail = entry.check_availability()
    assert avail["binary_found"] is False
    assert avail["status"] == "unavailable"

    # test_agent uses python3 (should be on PATH) and no API key required
    entry = reg.get_entry("test_agent")
    avail = entry.check_availability()
    assert avail["binary_found"] is True
    assert avail["api_key_set"] is True
    assert avail["status"] == "available"


def test_registry_get_available_agents(registry_file):
    """get_available_agents returns all entries with availability info."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    reg = AgentRegistry(yaml_path=registry_file)
    reg.load()

    available = reg.get_available_agents()
    assert len(available) == 2
    for agent in available:
        assert "type" in agent
        assert "name" in agent
        assert "status" in agent
        assert agent["status"] in ("available", "unavailable", "requires_setup")


def test_registry_missing_file():
    """Registry handles missing YAML file gracefully."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    reg = AgentRegistry(yaml_path="/nonexistent/agents.yaml")
    reg.load()
    assert reg.entries == []
    assert reg.default_type == "custom"


def test_registry_invalid_yaml():
    """Registry handles invalid YAML content gracefully."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write("not: [valid: yaml: content")
        path = f.name

    try:
        reg = AgentRegistry(yaml_path=path)
        reg.load()
        # Should not crash, just produce empty entries
    finally:
        os.unlink(path)


def test_registry_hot_reload(registry_file):
    """Registry detects file changes and reloads."""
    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry

    reg = AgentRegistry(yaml_path=registry_file)
    reg._reload_interval = 0  # Disable throttling
    reg.load()
    assert len(reg.entries) == 2

    # Modify the file
    with open(registry_file, "w") as f:
        f.write("""
agents:
  - type: new_agent
    name: New Agent
    description: Added dynamically
    command: python3
    args: []
    env: {}
    requires_api_key: null
    default: true
""")

    # Touch file to update mtime
    import time
    os.utime(registry_file, (time.time() + 1, time.time() + 1))

    # Access entries to trigger reload
    entries = reg.entries
    assert len(entries) == 1
    assert entries[0].type == "new_agent"


def test_default_agents_yaml_exists():
    """The shipped agents.yaml file exists and is valid."""
    config_path = os.path.join(
        os.path.dirname(__file__),
        "..", "..", "Config_Files", "agents.yaml",
    )
    assert os.path.isfile(config_path), f"agents.yaml not found at {config_path}"

    from tldw_Server_API.app.core.Agent_Client_Protocol.agent_registry import AgentRegistry
    reg = AgentRegistry(yaml_path=config_path)
    reg.load()
    assert len(reg.entries) >= 3  # claude_code, codex, opencode, custom
