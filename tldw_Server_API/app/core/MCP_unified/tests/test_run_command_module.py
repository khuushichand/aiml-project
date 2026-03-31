from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Any

import pytest

from tldw_Server_API.app.core.MCP_unified.command_runtime.adapters import (
    derive_step_idempotency_key,
)
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.run_command_module import (
    RunCommandModule,
)
from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext


@dataclass
class _PreparedCall:
    params: dict[str, Any]
    idempotency_key: str | None = None


class _ProtocolStub:
    def __init__(self) -> None:
        self.prepare_calls: list[_PreparedCall] = []
        self.execute_calls: list[_PreparedCall] = []
        self.tools_list_calls = 0
        self.raise_on_prepare_for_tool: str | None = None

    async def _handle_tools_list(self, params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
        self.tools_list_calls += 1
        return {
            "tools": [
                {"name": "fs.list", "module": "filesystem", "canExecute": True},
                {"name": "fs.read_text", "module": "filesystem", "canExecute": True},
                {"name": "fs.write_text", "module": "filesystem", "canExecute": True},
            ]
        }

    async def prepare_tool_call(
        self,
        *,
        params: dict[str, Any],
        context: RequestContext,
        idempotency_key: str | None = None,
    ) -> _PreparedCall:
        prepared = _PreparedCall(params=dict(params), idempotency_key=idempotency_key)
        self.prepare_calls.append(prepared)
        if self.raise_on_prepare_for_tool and params.get("name") == self.raise_on_prepare_for_tool:
            raise PermissionError("blocked by policy")
        return prepared

    async def execute_prepared_tool_call(self, prepared: _PreparedCall) -> dict[str, Any]:
        self.execute_calls.append(prepared)
        tool_name = prepared.params.get("name")
        if tool_name == "fs.list":
            return {
                "content": [
                    {
                        "type": "json",
                        "json": {
                            "path": ".",
                            "entries": [
                                {"name": "alpha.txt", "type": "file"},
                                {"name": "docs", "type": "directory"},
                            ],
                        },
                    }
                ],
                "tool": tool_name,
            }
        if tool_name == "fs.write_text":
            return {
                "content": [{"type": "json", "json": {"path": "notes.txt", "bytes_written": 5}}],
                "tool": tool_name,
            }
        if tool_name == "fs.read_text":
            return {
                "content": [{"type": "json", "json": {"path": "notes.txt", "text": "hello"}}],
                "tool": tool_name,
            }
        raise AssertionError(f"Unexpected tool execution: {tool_name}")


class _WorkspaceRootResolverStub:
    def __init__(self, workspace_root: Path) -> None:
        self.workspace_root = workspace_root
        self.calls: list[dict[str, Any]] = []

    async def resolve_for_context(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(dict(kwargs))
        return {
            "workspace_root": str(self.workspace_root),
            "workspace_id": kwargs.get("workspace_id") or "workspace-1",
            "source": "test",
            "reason": None,
        }


def _build_module(protocol: _ProtocolStub) -> RunCommandModule:
    return RunCommandModule(
        ModuleConfig(
            name="run",
            settings={"protocol": protocol},
        )
    )


@pytest.mark.asyncio
async def test_run_ls_uses_fs_list_and_returns_footer() -> None:
    protocol = _ProtocolStub()
    module = _build_module(protocol)
    context = RequestContext(request_id="run-ls", user_id="1", client_id="unit")

    rendered = await module.execute_tool("run", {"command": "ls"}, context=context)

    assert "alpha.txt" in rendered
    assert "docs/" in rendered
    assert "[exit:0 |" in rendered
    assert len(protocol.prepare_calls) == 1
    assert protocol.prepare_calls[0].params["name"] == "fs.list"
    assert protocol.prepare_calls[0].params["arguments"] == {"path": "."}


@pytest.mark.asyncio
async def test_run_cat_without_path_returns_usage() -> None:
    protocol = _ProtocolStub()
    module = _build_module(protocol)
    context = RequestContext(request_id="run-cat-usage", user_id="1", client_id="unit")

    rendered = await module.execute_tool("run", {"command": "cat"}, context=context)

    assert "usage: cat <path>" in rendered.lower()
    assert "[exit:2 |" in rendered
    assert protocol.prepare_calls == []
    assert protocol.execute_calls == []


@pytest.mark.asyncio
async def test_run_preflights_write_chain_before_executing_first_step() -> None:
    protocol = _ProtocolStub()
    protocol.raise_on_prepare_for_tool = "fs.write_text"
    module = _build_module(protocol)
    context = RequestContext(request_id="run-preflight", user_id="1", client_id="unit")

    with pytest.raises(PermissionError, match="blocked by policy"):
        await module.execute_tool("run", {"command": "ls ; write notes.txt hello"}, context=context)

    assert [call.params["name"] for call in protocol.prepare_calls] == ["fs.list", "fs.write_text"]
    assert protocol.execute_calls == []


@pytest.mark.asyncio
async def test_run_derives_step_idempotency_from_parent_key() -> None:
    protocol = _ProtocolStub()
    module = _build_module(protocol)
    context = RequestContext(request_id="run-idempotency", user_id="1", client_id="unit")

    first = await module.execute_tool(
        "run",
        {"command": "write notes.txt hello", "idempotencyKey": "parent-idem-1"},
        context=context,
    )
    second = await module.execute_tool(
        "run",
        {"command": "write notes.txt hello", "idempotencyKey": "parent-idem-1"},
        context=context,
    )

    assert first == second
    assert "[exit:0 |" in first
    assert len(protocol.prepare_calls) == 2
    assert protocol.prepare_calls[0].params["name"] == "fs.write_text"
    assert protocol.prepare_calls[0].idempotency_key == derive_step_idempotency_key(
        "parent-idem-1",
        ["write", "notes.txt", "hello"],
        0,
    )
    assert protocol.prepare_calls[0].idempotency_key == protocol.prepare_calls[1].idempotency_key


@pytest.mark.asyncio
async def test_run_help_keeps_argument_sensitive_allowed_commands_visible() -> None:
    class _PatternProtocolStub:
        async def _handle_tools_list(self, params: dict[str, Any], context: RequestContext) -> dict[str, Any]:
            return {
                "tools": [
                    {"name": "sandbox.run", "module": "sandbox", "canExecute": True},
                ]
            }

        def _extract_allowed_tools(self, context: RequestContext) -> list[str]:
            return ["sandbox.run(ls *)"]

        async def _resolve_effective_tool_policy(self, context: RequestContext) -> dict[str, Any]:
            return {
                "enabled": True,
                "allowed_tools": ["sandbox.run(ls *)"],
                "denied_tools": [],
            }

        def _is_tool_allowed_by_context(self, tool_name: str, tool_args: dict[str, Any], context: RequestContext) -> bool:
            return False

        def _is_tool_allowed_by_effective_policy(
            self,
            tool_name: str,
            tool_args: dict[str, Any],
            policy: dict[str, Any],
        ) -> bool:
            return False

    module = RunCommandModule(
        ModuleConfig(name="run", settings={"protocol": _PatternProtocolStub()}),
    )
    context = RequestContext(
        request_id="run-help-arg-sensitive",
        user_id="1",
        client_id="unit",
        metadata={"allowed_tools": ["sandbox.run(ls *)"]},
    )

    rendered = await module.execute_tool("run", {"command": "help"}, context=context)

    assert "sandbox" in rendered


@pytest.mark.asyncio
async def test_run_uses_configured_spill_settings_and_workspace_relative_spill_dir(tmp_path: Path) -> None:
    class _SpillProtocolStub(_ProtocolStub):
        async def execute_prepared_tool_call(self, prepared: _PreparedCall) -> dict[str, Any]:
            self.execute_calls.append(prepared)
            return {
                "content": [
                    {
                        "type": "json",
                        "json": {
                            "path": "notes.txt",
                            "text": "line one\nline two\nline three\n",
                        },
                    }
                ],
                "tool": prepared.params.get("name"),
            }

    workspace_root = tmp_path / "workspace"
    workspace_root.mkdir(parents=True, exist_ok=True)
    protocol = _SpillProtocolStub()
    resolver = _WorkspaceRootResolverStub(workspace_root)
    module = RunCommandModule(
        ModuleConfig(
            name="run",
            settings={
                "protocol": protocol,
                "spill_dir": ".mcp/spills",
                "spill_threshold_bytes": 8,
                "preview_line_limit": 1,
                "preview_byte_limit": 8,
                "workspace_root_resolver": resolver,
            },
        )
    )
    context = RequestContext(
        request_id="run-spill-settings",
        user_id="1",
        client_id="unit",
        metadata={"workspace_id": "workspace-1"},
    )

    rendered = await module.execute_tool("run", {"command": "cat notes.txt"}, context=context)

    match = re.search(r"Full stdout spilled to (.+)", rendered)
    assert match is not None
    spill_path = Path(match.group(1))
    assert spill_path.parent == workspace_root / ".mcp" / "spills"
    assert "line one" in rendered
    assert "line two" not in rendered
    assert resolver.calls


@pytest.mark.asyncio
async def test_run_supports_json_paths_with_escaped_dots() -> None:
    class _JsonProtocolStub(_ProtocolStub):
        async def execute_prepared_tool_call(self, prepared: _PreparedCall) -> dict[str, Any]:
            self.execute_calls.append(prepared)
            return {
                "content": [
                    {
                        "type": "json",
                        "json": {
                            "path": "payload.json",
                            "text": '{"a.b": {"nested.value": 7}}',
                        },
                    }
                ],
                "tool": prepared.params.get("name"),
            }

    protocol = _JsonProtocolStub()
    module = _build_module(protocol)
    context = RequestContext(request_id="run-json-dot-path", user_id="1", client_id="unit")

    rendered = await module.execute_tool(
        "run",
        {"command": r"cat payload.json | json a\.b.nested\.value"},
        context=context,
    )

    assert "\n7\n" in f"\n{rendered}\n"
    assert "[exit:0 |" in rendered


@pytest.mark.asyncio
async def test_run_resolve_protocol_logs_before_falling_back(monkeypatch: pytest.MonkeyPatch) -> None:
    from tldw_Server_API.app.core.MCP_unified import server as server_module
    from tldw_Server_API.app.core.MCP_unified.modules.implementations import run_command_module as run_module_impl

    warnings: list[str] = []

    def _boom() -> Any:
        raise RuntimeError("missing server")

    monkeypatch.setattr(server_module, "get_mcp_server", _boom)
    monkeypatch.setattr(
        run_module_impl.logger,
        "warning",
        lambda message, *args: warnings.append(str(message).format(*args)),
    )

    module = RunCommandModule(ModuleConfig(name="run"))

    protocol = await module._resolve_protocol()

    assert isinstance(protocol, MCPProtocol)
    assert warnings
