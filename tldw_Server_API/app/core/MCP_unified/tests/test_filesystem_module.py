from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.filesystem_module import (
    FilesystemModule,
)
from tldw_Server_API.app.core.MCP_unified.protocol import InvalidParamsException
from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext


class _FakeWorkspaceRootResolver:
    def __init__(self, result: dict[str, Any]) -> None:
        self.result = dict(result)
        self.calls: list[dict[str, Any]] = []

    async def resolve_for_context(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        return dict(self.result)


class _FilesystemRegistry:
    def __init__(self, module: FilesystemModule) -> None:
        self.module = module
        self._tool_names = {"fs.list", "fs.read_text", "fs.write_text"}

    async def find_module_for_tool(self, tool_name: str):  # noqa: ANN001
        if tool_name in self._tool_names:
            return self.module
        return None

    def get_module_id_for_tool(self, tool_name: str) -> str | None:
        if tool_name in self._tool_names:
            return self.module.name
        return None


@pytest.mark.asyncio
async def test_server_registers_filesystem_module_by_default(monkeypatch, tmp_path: Path) -> None:
    from tldw_Server_API.app.core.MCP_unified.server import MCPServer

    server = MCPServer()
    registered_module_ids: list[str] = []

    async def _capture_registration(module_id, module_type, config):  # noqa: ANN001, ARG001
        registered_module_ids.append(str(module_id))

    monkeypatch.setattr(server.module_registry, "register_module", _capture_registration)
    monkeypatch.setenv("MCP_MODULES_CONFIG", str(tmp_path / "missing-modules.yaml"))
    monkeypatch.setenv("MCP_MODULES", "")
    monkeypatch.setenv("MCP_ENABLE_MEDIA_MODULE", "0")
    monkeypatch.setenv("MCP_ENABLE_FILESYSTEM_MODULE", "1")

    await server._register_default_modules()

    assert "filesystem" in registered_module_ids


@pytest.mark.asyncio
async def test_filesystem_tools_include_path_scope_metadata() -> None:
    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": "/workspace/mcp-filesystem-workspace",
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(ModuleConfig(name="filesystem"), workspace_root_resolver=resolver)

    tools = await mod.get_tools()
    by_name = {tool["name"]: tool for tool in tools}

    assert {"fs.list", "fs.read_text", "fs.write_text"} <= set(by_name)

    for tool_name in ("fs.list", "fs.read_text", "fs.write_text"):
        metadata = by_name[tool_name]["metadata"]
        assert metadata["uses_filesystem"] is True
        assert metadata["path_boundable"] is True
        assert metadata["path_argument_hints"] == ["path"]

    assert by_name["fs.write_text"]["metadata"]["category"] == "management"


@pytest.mark.asyncio
async def test_filesystem_list_read_and_write_text_within_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    docs_dir = workspace_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    source_file = docs_dir / "hello.txt"
    source_file.write_text("hello world", encoding="utf-8")

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": str(workspace_root),
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(ModuleConfig(name="filesystem"), workspace_root_resolver=resolver)
    context = RequestContext(
        request_id="req-filesystem-roundtrip",
        user_id="7",
        session_id="sess-1",
        metadata={"workspace_id": "workspace-1"},
    )

    listed = await mod.execute_tool("fs.list", {"path": "docs"}, context=context)
    assert listed["path"] == "docs"
    assert any(entry["name"] == "hello.txt" and entry["type"] == "file" for entry in listed["entries"])

    read_result = await mod.execute_tool("fs.read_text", {"path": "docs/hello.txt"}, context=context)
    assert read_result["path"] == "docs/hello.txt"
    assert read_result["text"] == "hello world"

    write_result = await mod.execute_tool(
        "fs.write_text",
        {"path": "docs/new.txt", "content": "created by fs.write_text"},
        context=context,
    )
    assert write_result["path"] == "docs/new.txt"
    assert write_result["bytes_written"] == len("created by fs.write_text".encode("utf-8"))
    assert (docs_dir / "new.txt").read_text(encoding="utf-8") == "created by fs.write_text"
    assert len(resolver.calls) == 3


@pytest.mark.asyncio
async def test_protocol_rejects_unknown_fs_read_text_arguments(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    docs_dir = workspace_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    (docs_dir / "hello.txt").write_text("hello world", encoding="utf-8")

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": str(workspace_root),
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(ModuleConfig(name="filesystem"), workspace_root_resolver=resolver)

    protocol = MCPProtocol()
    protocol.module_registry = _FilesystemRegistry(mod)

    async def _resolve_effective_policy(_context):
        return {"enabled": True, "allowed_tools": ["fs.read_text"], "policy_document": {"path_scope_mode": "none"}}

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    context = RequestContext(
        request_id="req-fs-read-unknown-arg",
        user_id="7",
        session_id="sess-1",
        metadata={"workspace_id": "workspace-1"},
    )

    with pytest.raises(InvalidParamsException, match="Unknown parameters"):
        await protocol._handle_tools_call(
            {"name": "fs.read_text", "arguments": {"path": "docs/hello.txt", "unknown": "boom"}},
            context,
        )


@pytest.mark.asyncio
async def test_filesystem_list_does_not_leak_symlink_targets_outside_workspace(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    docs_dir = workspace_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    outside_dir = tmp_path / "outside"
    outside_dir.mkdir(parents=True, exist_ok=True)
    outside_file = outside_dir / "secret.txt"
    outside_file.write_text("outside", encoding="utf-8")
    (docs_dir / "secret-link").symlink_to(outside_file)

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": str(workspace_root),
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(ModuleConfig(name="filesystem"), workspace_root_resolver=resolver)
    context = RequestContext(
        request_id="req-filesystem-symlink-leak",
        user_id="7",
        session_id="sess-1",
        metadata={"workspace_id": "workspace-1"},
    )

    listed = await mod.execute_tool("fs.list", {"path": "docs"}, context=context)
    symlink_entry = next(entry for entry in listed["entries"] if entry["name"] == "secret-link")

    assert listed["path"] == "docs"
    assert symlink_entry["path"] == "docs/secret-link"
    assert symlink_entry["type"] == "symlink"
    assert str(outside_file.resolve()) not in str(listed)


@pytest.mark.asyncio
async def test_filesystem_read_text_rejects_binary_payload(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    binary_path = workspace_root / "blob.bin"
    binary_path.write_bytes(b"\x00\x01\x02\x03")

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": str(workspace_root),
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(ModuleConfig(name="filesystem"), workspace_root_resolver=resolver)
    context = RequestContext(
        request_id="req-filesystem-binary",
        user_id="7",
        metadata={"workspace_id": "workspace-1"},
    )

    with pytest.raises(ValueError, match="binary"):
        await mod.execute_tool("fs.read_text", {"path": "blob.bin"}, context=context)


@pytest.mark.asyncio
async def test_filesystem_write_text_rejects_path_escape(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": str(workspace_root),
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(ModuleConfig(name="filesystem"), workspace_root_resolver=resolver)
    context = RequestContext(
        request_id="req-filesystem-escape",
        user_id="7",
        metadata={"workspace_id": "workspace-1"},
    )

    with pytest.raises(PermissionError, match="outside"):
        await mod.execute_tool(
            "fs.write_text",
            {"path": "../escape.txt", "content": "forbidden"},
            context=context,
        )


@pytest.mark.asyncio
async def test_filesystem_list_caps_large_directories(tmp_path: Path) -> None:
    workspace_root = tmp_path / "workspace"
    docs_dir = workspace_root / "docs"
    docs_dir.mkdir(parents=True, exist_ok=True)
    for index in range(12):
        (docs_dir / f"file-{index:02d}.txt").write_text("x", encoding="utf-8")

    resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": str(workspace_root),
            "workspace_id": "workspace-1",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    mod = FilesystemModule(
        ModuleConfig(name="filesystem", settings={"list_entry_limit": 5}),
        workspace_root_resolver=resolver,
    )
    context = RequestContext(
        request_id="req-filesystem-list-cap",
        user_id="7",
        session_id="sess-1",
        metadata={"workspace_id": "workspace-1"},
    )

    listed = await mod.execute_tool("fs.list", {"path": "docs"}, context=context)

    assert listed["truncated"] is True
    assert listed["remaining_count"] == 7
    assert len(listed["entries"]) == 5


@pytest.mark.asyncio
async def test_server_resolves_env_placeholders_in_module_settings(monkeypatch, tmp_path: Path) -> None:
    from tldw_Server_API.app.core.MCP_unified.server import MCPServer

    config_path = tmp_path / "mcp_modules.yaml"
    config_path.write_text(
        """
modules:
  - id: run_command
    class: tldw_Server_API.app.core.MCP_unified.modules.implementations.run_command_module:RunCommandModule
    enabled: true
    name: Run Command
    version: "0.1.0"
    department: system
    settings:
      spill_dir: ${MCP_RUN_COMMAND_SPILL_DIR:-.mcp/spills}
""".strip(),
        encoding="utf-8",
    )

    server = MCPServer()
    captured_settings: dict[str, Any] = {}

    async def _capture_registration(module_id, module_type, config):  # noqa: ANN001, ARG001
        if str(module_id) == "run_command":
            captured_settings.update(dict(config.settings or {}))

    monkeypatch.setattr(server.module_registry, "register_module", _capture_registration)
    monkeypatch.setenv("MCP_MODULES_CONFIG", str(config_path))
    monkeypatch.setenv("MCP_MODULES", "")
    monkeypatch.setenv("MCP_ENABLE_MEDIA_MODULE", "0")
    monkeypatch.setenv("MCP_ENABLE_FILESYSTEM_MODULE", "0")
    monkeypatch.setenv("MCP_RUN_COMMAND_SPILL_DIR", ".workspace-spills")

    await server._register_default_modules()

    assert captured_settings["spill_dir"] == ".workspace-spills"
