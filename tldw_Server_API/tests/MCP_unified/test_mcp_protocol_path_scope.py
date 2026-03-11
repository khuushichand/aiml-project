from __future__ import annotations

import pytest


class _FakeModule:
    name = "files"

    def __init__(self, tool_def: dict) -> None:
        self._tool_def = dict(tool_def)

    async def get_tools(self) -> list[dict]:
        return [dict(self._tool_def)]

    async def get_tool_def(self, tool_name: str) -> dict | None:
        if tool_name == self._tool_def.get("name"):
            return dict(self._tool_def)
        return None

    def is_write_tool_def(self, tool_def: dict) -> bool:
        return False

    def sanitize_input(self, input_data):  # noqa: ANN001
        return input_data

    def validate_tool_arguments(self, tool_name: str, arguments: dict) -> None:  # noqa: ARG002
        return None

    async def execute_tool(self, tool_name: str, arguments: dict, context=None):  # noqa: ANN001, ARG002
        return {"ok": True}

    async def execute_with_circuit_breaker(
        self,
        func,  # noqa: ANN001
        tool_name: str,
        arguments: dict,
        context=None,  # noqa: ANN001
    ):
        return await func(tool_name, arguments, context=context)


class _FakeRegistry:
    def __init__(self, module: _FakeModule) -> None:
        self.module = module

    async def find_module_for_tool(self, tool_name: str):  # noqa: ANN001
        if tool_name == self.module._tool_def.get("name"):
            return self.module
        return None

    def get_module_id_for_tool(self, tool_name: str) -> str | None:
        if tool_name == self.module._tool_def.get("name"):
            return self.module.name
        return None


class _FakePathEnforcementService:
    def __init__(self, result: dict) -> None:
        self.result = dict(result)
        self.calls: list[dict] = []

    async def evaluate_tool_call(self, **kwargs) -> dict:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return dict(self.result)


class _FakeApprovalService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def evaluate_tool_call(self, **kwargs) -> dict:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return {
            "status": "approval_required",
            "approval": {
                "approval_policy_id": 1,
                "tool_name": kwargs["tool_name"],
                "reason": kwargs["approval_reason"],
                "scope_context": dict(kwargs["scope_payload"] or {}),
                "duration_options": ["once", "session"],
                "arguments_summary": {"path": "../README.md"},
            },
        }


class _NoopApprovalService:
    def __init__(self) -> None:
        self.calls: list[dict] = []

    async def evaluate_tool_call(self, **kwargs) -> dict:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return {"status": "approval_required", "approval": {"tool_name": kwargs["tool_name"]}}


class _FakeWorkspaceRootResolver:
    def __init__(self, result: dict) -> None:
        self.result = dict(result)
        self.calls: list[dict] = []

    async def resolve_for_context(self, **kwargs) -> dict:  # noqa: ANN003
        self.calls.append(dict(kwargs))
        return dict(self.result)


@pytest.mark.asyncio
async def test_handle_tools_call_raises_approval_for_path_scope_violation(monkeypatch) -> None:
    from tldw_Server_API.app.core.MCP_unified.protocol import ApprovalRequiredError
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
    from tldw_Server_API.app.services import mcp_hub_approval_service as approval_service_mod
    from tldw_Server_API.app.services import mcp_hub_path_enforcement_service as path_service_mod

    tool_def = {
        "name": "files.read",
        "description": "Read a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "metadata": {
            "category": "retrieval",
            "uses_filesystem": True,
            "path_boundable": True,
            "path_argument_hints": ["path"],
        },
    }
    fake_module = _FakeModule(tool_def)
    fake_path_service = _FakePathEnforcementService(
        {
            "enabled": True,
            "within_scope": False,
            "reason": "path_outside_current_folder_scope",
            "force_approval": True,
            "normalized_paths": ["/tmp/project/README.md"],
            "scope_payload": {
                "path_scope_mode": "cwd_descendants",
                "workspace_root": "/tmp/project",
                "scope_root": "/tmp/project/src",
                "normalized_paths": ["/tmp/project/README.md"],
                "reason": "path_outside_current_folder_scope",
            },
        }
    )
    fake_approval_service = _FakeApprovalService()

    async def _fake_get_path_service():
        return fake_path_service

    async def _fake_get_approval_service():
        return fake_approval_service

    monkeypatch.setattr(path_service_mod, "get_mcp_hub_path_enforcement_service", _fake_get_path_service)
    monkeypatch.setattr(approval_service_mod, "get_mcp_hub_approval_service", _fake_get_approval_service)

    protocol = MCPProtocol()
    protocol.module_registry = _FakeRegistry(fake_module)

    async def _resolve_effective_policy(_context):
        return {
            "enabled": True,
            "allowed_tools": ["files.read"],
            "approval_policy_id": 1,
            "policy_document": {
                "path_scope_mode": "cwd_descendants",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        }

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    context = RequestContext(
        request_id="req-path-scope",
        user_id="7",
        client_id="test-client",
        session_id="sess-1",
        metadata={"persona_id": "researcher", "cwd": "src"},
    )

    with pytest.raises(ApprovalRequiredError) as exc:
        await protocol._handle_tools_call(
            {"name": "files.read", "arguments": {"path": "../README.md"}},
            context,
        )

    approval = exc.value.approval or {}
    assert approval["reason"] == "path_outside_current_folder_scope"
    assert approval["scope_context"]["path_scope_mode"] == "cwd_descendants"
    assert approval["scope_context"]["normalized_paths"] == ["/tmp/project/README.md"]
    assert fake_path_service.calls[0]["tool_name"] == "files.read"
    assert fake_approval_service.calls[0]["within_effective_policy"] is False
    assert fake_approval_service.calls[0]["force_approval"] is True
    assert fake_approval_service.calls[0]["approval_reason"] == "path_outside_current_folder_scope"


@pytest.mark.asyncio
async def test_handle_tools_call_raises_approval_for_path_allowlist_violation(monkeypatch) -> None:
    from tldw_Server_API.app.core.MCP_unified.protocol import ApprovalRequiredError
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
    from tldw_Server_API.app.services import mcp_hub_approval_service as approval_service_mod
    from tldw_Server_API.app.services import mcp_hub_path_enforcement_service as path_service_mod

    tool_def = {
        "name": "files.read",
        "description": "Read a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "metadata": {
            "category": "retrieval",
            "uses_filesystem": True,
            "path_boundable": True,
            "path_argument_hints": ["path"],
        },
    }
    fake_module = _FakeModule(tool_def)
    fake_path_service = _FakePathEnforcementService(
        {
            "enabled": True,
            "within_scope": False,
            "reason": "path_outside_allowlist_scope",
            "force_approval": True,
            "normalized_paths": ["/tmp/project/src2/README.md"],
            "scope_payload": {
                "path_scope_mode": "workspace_root",
                "workspace_root": "/tmp/project",
                "scope_root": "/tmp/project",
                "normalized_paths": ["/tmp/project/src2/README.md"],
                "path_allowlist_prefixes": ["src"],
                "reason": "path_outside_allowlist_scope",
            },
        }
    )
    fake_approval_service = _FakeApprovalService()

    async def _fake_get_path_service():
        return fake_path_service

    async def _fake_get_approval_service():
        return fake_approval_service

    monkeypatch.setattr(path_service_mod, "get_mcp_hub_path_enforcement_service", _fake_get_path_service)
    monkeypatch.setattr(approval_service_mod, "get_mcp_hub_approval_service", _fake_get_approval_service)

    protocol = MCPProtocol()
    protocol.module_registry = _FakeRegistry(fake_module)

    async def _resolve_effective_policy(_context):
        return {
            "enabled": True,
            "allowed_tools": ["files.read"],
            "approval_policy_id": 1,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
                "path_allowlist_prefixes": ["src"],
            },
        }

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    context = RequestContext(
        request_id="req-path-allowlist",
        user_id="7",
        client_id="test-client",
        session_id="sess-1",
        metadata={"persona_id": "researcher"},
    )

    with pytest.raises(ApprovalRequiredError) as exc:
        await protocol._handle_tools_call(
            {"name": "files.read", "arguments": {"path": "src2/README.md"}},
            context,
        )

    approval = exc.value.approval or {}
    assert approval["reason"] == "path_outside_allowlist_scope"
    assert approval["scope_context"]["path_allowlist_prefixes"] == ["src"]
    assert fake_approval_service.calls[0]["approval_reason"] == "path_outside_allowlist_scope"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("blocked_reason", "scope_payload"),
    [
        (
            "required_slot_not_granted",
            {
                "server_id": "docs",
                "requested_slots": ["token_readonly"],
                "missing_bound_slots": ["token_readonly"],
                "blocked_reason": "required_slot_not_granted",
            },
        ),
        (
            "required_slot_secret_missing",
            {
                "server_id": "docs",
                "requested_slots": ["token_readonly"],
                "missing_secret_slots": ["token_readonly"],
                "blocked_reason": "required_slot_secret_missing",
            },
        ),
    ],
)
async def test_handle_tools_call_hard_denies_external_slot_blockers_without_approval(
    monkeypatch,
    blocked_reason: str,
    scope_payload: dict,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
    from tldw_Server_API.app.services import mcp_hub_approval_service as approval_service_mod

    tool_def = {
        "name": "ext.docs.search",
        "description": "Search docs",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
            "additionalProperties": False,
        },
        "metadata": {
            "category": "retrieval",
            "uses_network": True,
        },
    }
    fake_module = _FakeModule(tool_def)
    fake_approval_service = _NoopApprovalService()

    async def _fake_get_approval_service():
        return fake_approval_service

    monkeypatch.setattr(approval_service_mod, "get_mcp_hub_approval_service", _fake_get_approval_service)

    protocol = MCPProtocol()
    protocol.module_registry = _FakeRegistry(fake_module)

    async def _resolve_effective_policy(_context):
        return {
            "enabled": True,
            "allowed_tools": ["ext.docs.search"],
            "approval_policy_id": 1,
            "approval_mode": "ask_outside_profile",
            "sources": [{"assignment_id": 11, "profile_id": 7}],
        }

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    async def _path_scope(*_args, **_kwargs):
        return {"enabled": False, "within_scope": True, "reason": None, "scope_payload": None}

    async def _external_access(*_args, **_kwargs):
        return {
            "enabled": True,
            "within_scope": False,
            "reason": blocked_reason,
            "scope_payload": dict(scope_payload),
        }

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]
    protocol._evaluate_path_scope = _path_scope  # type: ignore[method-assign]
    protocol._evaluate_external_access = _external_access  # type: ignore[method-assign]

    context = RequestContext(
        request_id=f"req-{blocked_reason}",
        user_id="7",
        client_id="test-client",
        session_id="sess-ext-deny",
        metadata={"persona_id": "researcher"},
    )

    with pytest.raises(PermissionError):
        await protocol._handle_tools_call(
            {"name": "ext.docs.search", "arguments": {"query": "approval needed"}},
            context,
        )

    assert fake_approval_service.calls == []


def test_external_slot_scope_key_includes_requested_slots() -> None:
    from tldw_Server_API.app.services.mcp_hub_approval_service import _scope_key_for_tool_call

    scope_key_a = _scope_key_for_tool_call(
        "ext.docs.search",
        {"query": "same"},
        scope_payload={
            "server_id": "docs",
            "requested_slots": ["token_readonly"],
            "blocked_reason": "external_confirmation_required",
        },
    )
    scope_key_b = _scope_key_for_tool_call(
        "ext.docs.search",
        {"query": "same"},
        scope_payload={
            "server_id": "docs",
            "requested_slots": ["token_readonly", "token_write"],
            "blocked_reason": "external_confirmation_required",
        },
    )
    scope_key_c = _scope_key_for_tool_call(
        "ext.docs.write",
        {"query": "same"},
        scope_payload={
            "server_id": "docs",
            "requested_slots": ["token_readonly"],
            "blocked_reason": "external_confirmation_required",
        },
    )

    assert scope_key_a != scope_key_b
    assert scope_key_a != scope_key_c


@pytest.mark.asyncio
async def test_handle_tools_call_allows_direct_workspace_scoped_reader(monkeypatch) -> None:
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
    from tldw_Server_API.app.services import mcp_hub_path_enforcement_service as path_service_mod
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    tool_def = {
        "name": "files.read",
        "description": "Read a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "metadata": {
            "category": "retrieval",
            "uses_filesystem": True,
            "path_boundable": True,
            "path_argument_hints": ["path"],
        },
    }
    fake_module = _FakeModule(tool_def)
    fake_resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": "/tmp/mcp-hub-direct/project",
            "workspace_id": "workspace-direct",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    path_service = McpHubPathEnforcementService(
        path_scope_service=McpHubPathScopeService(
            sandbox_service=object(),
            workspace_root_resolver=fake_resolver,
        )
    )

    async def _fake_get_path_service():
        return path_service

    monkeypatch.setattr(path_service_mod, "get_mcp_hub_path_enforcement_service", _fake_get_path_service)

    protocol = MCPProtocol()
    protocol.module_registry = _FakeRegistry(fake_module)

    async def _resolve_effective_policy(_context):
        return {
            "enabled": True,
            "allowed_tools": ["files.read"],
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        }

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    context = RequestContext(
        request_id="req-direct-workspace-root",
        user_id="7",
        client_id="test-client",
        session_id=None,
        metadata={"workspace_id": "workspace-direct", "cwd": "src"},
    )

    result = await protocol._handle_tools_call(
        {"name": "files.read", "arguments": {"path": "notes.txt"}},
        context,
    )

    assert result["tool"] == "files.read"
    assert result["module"] == "files"
    assert result["content"][0]["json"] == {"ok": True}
    assert fake_resolver.calls[0]["user_id"] == "7"
    assert fake_resolver.calls[0]["workspace_id"] == "workspace-direct"


@pytest.mark.asyncio
async def test_handle_tools_call_requires_approval_when_direct_workspace_root_missing(
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.protocol import ApprovalRequiredError
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
    from tldw_Server_API.app.services import mcp_hub_approval_service as approval_service_mod
    from tldw_Server_API.app.services import mcp_hub_path_enforcement_service as path_service_mod
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    tool_def = {
        "name": "files.read",
        "description": "Read a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "metadata": {
            "category": "retrieval",
            "uses_filesystem": True,
            "path_boundable": True,
            "path_argument_hints": ["path"],
        },
    }
    fake_module = _FakeModule(tool_def)
    fake_resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": None,
            "workspace_id": "workspace-direct",
            "source": "sandbox_workspace_lookup",
            "reason": "workspace_root_unavailable",
        }
    )
    fake_approval_service = _FakeApprovalService()
    path_service = McpHubPathEnforcementService(
        path_scope_service=McpHubPathScopeService(
            sandbox_service=object(),
            workspace_root_resolver=fake_resolver,
        )
    )

    async def _fake_get_path_service():
        return path_service

    async def _fake_get_approval_service():
        return fake_approval_service

    monkeypatch.setattr(path_service_mod, "get_mcp_hub_path_enforcement_service", _fake_get_path_service)
    monkeypatch.setattr(approval_service_mod, "get_mcp_hub_approval_service", _fake_get_approval_service)

    protocol = MCPProtocol()
    protocol.module_registry = _FakeRegistry(fake_module)

    async def _resolve_effective_policy(_context):
        return {
            "enabled": True,
            "allowed_tools": ["files.read"],
            "approval_policy_id": 1,
            "policy_document": {
                "path_scope_mode": "workspace_root",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        }

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    context = RequestContext(
        request_id="req-direct-missing-root",
        user_id="7",
        client_id="test-client",
        session_id=None,
        metadata={"workspace_id": "workspace-direct", "cwd": "src"},
    )

    with pytest.raises(ApprovalRequiredError) as exc:
        await protocol._handle_tools_call(
            {"name": "files.read", "arguments": {"path": "notes.txt"}},
            context,
        )

    approval = exc.value.approval or {}
    assert approval["reason"] == "workspace_root_unavailable"
    assert approval["scope_context"]["path_scope_mode"] == "workspace_root"


@pytest.mark.asyncio
async def test_handle_tools_call_direct_cwd_descendants_stays_narrower_than_workspace_root(
    monkeypatch,
) -> None:
    from tldw_Server_API.app.core.MCP_unified.protocol import ApprovalRequiredError
    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol
    from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext
    from tldw_Server_API.app.services import mcp_hub_approval_service as approval_service_mod
    from tldw_Server_API.app.services import mcp_hub_path_enforcement_service as path_service_mod
    from tldw_Server_API.app.services.mcp_hub_path_enforcement_service import (
        McpHubPathEnforcementService,
    )
    from tldw_Server_API.app.services.mcp_hub_path_scope_service import McpHubPathScopeService

    tool_def = {
        "name": "files.read",
        "description": "Read a file",
        "inputSchema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
            "additionalProperties": False,
        },
        "metadata": {
            "category": "retrieval",
            "uses_filesystem": True,
            "path_boundable": True,
            "path_argument_hints": ["path"],
        },
    }
    fake_module = _FakeModule(tool_def)
    fake_resolver = _FakeWorkspaceRootResolver(
        {
            "workspace_root": "/tmp/mcp-hub-direct/project",
            "workspace_id": "workspace-direct",
            "source": "sandbox_workspace_lookup",
            "reason": None,
        }
    )
    fake_approval_service = _FakeApprovalService()
    path_service = McpHubPathEnforcementService(
        path_scope_service=McpHubPathScopeService(
            sandbox_service=object(),
            workspace_root_resolver=fake_resolver,
        )
    )

    async def _fake_get_path_service():
        return path_service

    async def _fake_get_approval_service():
        return fake_approval_service

    monkeypatch.setattr(path_service_mod, "get_mcp_hub_path_enforcement_service", _fake_get_path_service)
    monkeypatch.setattr(approval_service_mod, "get_mcp_hub_approval_service", _fake_get_approval_service)

    protocol = MCPProtocol()
    protocol.module_registry = _FakeRegistry(fake_module)

    async def _resolve_effective_policy(_context):
        return {
            "enabled": True,
            "allowed_tools": ["files.read"],
            "approval_policy_id": 1,
            "policy_document": {
                "path_scope_mode": "cwd_descendants",
                "path_scope_enforcement": "approval_required_when_unenforceable",
            },
        }

    async def _allow(*_args, **_kwargs) -> bool:
        return True

    protocol._resolve_effective_tool_policy = _resolve_effective_policy  # type: ignore[method-assign]
    protocol._has_module_permission = _allow  # type: ignore[method-assign]
    protocol._has_tool_permission = _allow  # type: ignore[method-assign]
    protocol._is_tool_allowed_by_context = lambda *_args, **_kwargs: True  # type: ignore[method-assign]

    context = RequestContext(
        request_id="req-direct-cwd-descendants",
        user_id="7",
        client_id="test-client",
        session_id=None,
        metadata={"workspace_id": "workspace-direct", "cwd": "src"},
    )

    with pytest.raises(ApprovalRequiredError) as exc:
        await protocol._handle_tools_call(
            {"name": "files.read", "arguments": {"path": "../README.md"}},
            context,
        )

    approval = exc.value.approval or {}
    assert approval["reason"] == "path_outside_current_folder_scope"
    assert approval["scope_context"]["path_scope_mode"] == "cwd_descendants"
    assert approval["scope_context"]["scope_root"] == "/private/tmp/mcp-hub-direct/project/src"
