from __future__ import annotations

from tldw_Server_API.app.core.MCP_unified.command_runtime.registry import build_default_registry


def test_registry_hides_commands_without_visible_backing_tools():
    registry = build_default_registry()
    visible = registry.visible_commands(allowed_tools={"fs.list", "mcp.tools.list"})

    assert "ls" in visible
    assert "grep" in visible
    assert "head" in visible
    assert "tail" in visible
    assert "json" in visible
    assert "mcp" in visible
    assert "cat" not in visible
    assert "write" not in visible
    assert "knowledge" not in visible
    assert "media" not in visible
    assert "sandbox" not in visible


def test_registry_exposes_phase_one_mappings():
    registry = build_default_registry()

    assert registry.get_command("ls").backend_tools == ("fs.list",)
    assert registry.get_command("cat").backend_tools == ("fs.read_text",)
    assert registry.get_command("write").backend_tools == ("fs.write_text",)
    assert registry.get_command("knowledge").backend_tools == ("knowledge.search", "knowledge.get")
    assert registry.get_command("media").backend_tools == ("media.search", "media.get")
    assert registry.get_command("mcp").backend_tools == ("mcp.modules.list", "mcp.tools.list")
    assert registry.get_command("sandbox").backend_tools == ("sandbox.run",)
    assert registry.get_command("grep").pure_transform is True
