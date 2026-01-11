import os
import pytest
from typing import Dict, Any, List

# Ensure MCP config can load in tests
os.environ.setdefault("MCP_JWT_SECRET", "test_secret_key_for_testing_only_32_chars_minimum")
os.environ.setdefault("MCP_API_KEY_SALT", "test_salt_key_for_testing_only_32_chars_minimum")
os.environ.setdefault("MCP_RATE_LIMIT_ENABLED", "false")

from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, MCPRequest, RequestContext
from tldw_Server_API.app.core.MCP_unified.modules.base import BaseModule, ModuleConfig, create_tool_definition
from tldw_Server_API.app.core.MCP_unified.modules.registry import get_module_registry, reset_module_registry
from tldw_Server_API.app.core.MCP_unified.modules.implementations.knowledge_module import KnowledgeModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.media_module import MediaModule
from tldw_Server_API.app.core.MCP_unified.modules.implementations.sandbox_module import SandboxModule


class AllowAllRBAC:
    async def check_permission(self, *args, **kwargs):
        return True


class DummyScopeModule(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [
            create_tool_definition(
                name="read_tool",
                description="Read-only tool",
                parameters={"properties": {}, "required": []},
                metadata={"category": "search"},
            ),
            create_tool_definition(
                name="write_tool",
                description="Write tool",
                parameters={"properties": {}, "required": []},
                metadata={"category": "management"},
            ),
        ]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        return {"ok": True, "tool": tool_name}


@pytest.mark.asyncio
async def test_api_key_scopes_enforce_read_vs_write():
    registry = get_module_registry()
    await registry.register_module("scope_mod", DummyScopeModule, ModuleConfig(name="scope_mod"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    ctx = RequestContext(request_id="r1", user_id="u1", client_id="c1", metadata={"api_key_scopes": ["read"]})

    read_req = MCPRequest(method="tools/call", params={"name": "read_tool", "arguments": {}}, id="t1")
    read_resp = await proto.process_request(read_req, ctx)
    assert read_resp.error is None

    write_req = MCPRequest(method="tools/call", params={"name": "write_tool", "arguments": {}}, id="t2")
    write_resp = await proto.process_request(write_req, ctx)
    assert write_resp.error is not None
    assert write_resp.error.code == -32001

    # Write scope should allow both
    ctx_write = RequestContext(request_id="r2", user_id="u1", client_id="c1", metadata={"api_key_scopes": ["write"]})
    write_ok = await proto.process_request(write_req, ctx_write)
    assert write_ok.error is None


@pytest.mark.asyncio
async def test_tools_list_can_execute_respects_api_key_scope():
    registry = get_module_registry()
    await registry.register_module("scope_mod_list", DummyScopeModule, ModuleConfig(name="scope_mod_list"))

    proto = MCPProtocol()
    proto.rbac_policy = AllowAllRBAC()

    ctx = RequestContext(request_id="r3", user_id="u1", client_id="c1", metadata={"api_key_scopes": ["read"]})
    req = MCPRequest(method="tools/list", params={}, id="t3")
    resp = await proto.process_request(req, ctx)
    assert resp.error is None
    tools = {t["name"]: t for t in resp.result.get("tools", [])}
    assert tools["read_tool"]["canExecute"] is True
    assert tools["write_tool"]["canExecute"] is False


class StubNotesModuleMany(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "notes.search", "description": "", "inputSchema": {"type": "object"}}]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        return {
            "results": [
                {"id": "n1", "source": "notes", "title": "N1", "snippet": "n1", "uri": "notes://n1", "score": 0.9, "score_type": "fts", "created_at": None, "last_modified": None, "version": 1, "tags": None, "loc": None},
                {"id": "n2", "source": "notes", "title": "N2", "snippet": "n2", "uri": "notes://n2", "score": 0.8, "score_type": "fts", "created_at": None, "last_modified": None, "version": 1, "tags": None, "loc": None},
            ],
            "has_more": False,
            "next_offset": None,
            "total_estimated": 2,
        }


class StubMediaModuleMany(BaseModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return [{"name": "media.search", "description": "", "inputSchema": {"type": "object"}}]

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        return {
            "results": [
                {"id": 1, "source": "media", "title": "M1", "snippet": "m1", "uri": "media://1", "score": 0.7, "score_type": "fts", "created_at": None, "last_modified": None, "version": 1, "tags": None, "media_type": "pdf", "url": None, "loc": None},
            ],
            "has_more": False,
            "next_offset": None,
            "total_estimated": 1,
        }


@pytest.mark.asyncio
async def test_knowledge_search_reports_has_more():
    await reset_module_registry()
    registry = get_module_registry()
    await registry.register_module("notes_many", StubNotesModuleMany, ModuleConfig(name="notes_many"))
    await registry.register_module("media_many", StubMediaModuleMany, ModuleConfig(name="media_many"))

    km = KnowledgeModule(ModuleConfig(name="knowledge"))
    await km.on_initialize()
    ctx = RequestContext(request_id="rk", user_id="1", client_id="cli")

    out = await km.execute_tool("knowledge.search", {"query": "x", "limit": 1, "offset": 0}, context=ctx)
    assert out["has_more"] is True
    assert out["next_offset"] == 1


class DummyMediaModule(MediaModule):
    async def on_initialize(self) -> None:
        return None

    async def on_shutdown(self) -> None:
        return None

    async def check_health(self) -> Dict[str, bool]:
        return {"ok": True}

    async def get_tools(self) -> List[Dict[str, Any]]:
        return []

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any], context: Any | None = None) -> Any:
        return None

    def _validate_url(self, url: str) -> bool:
        return True

    async def _create_ingestion_job(self, **kwargs) -> str:
        return "job-1"

    async def _process_media_job(self, job_id: str):
        self.processed = True


@pytest.mark.asyncio
async def test_ingest_media_falls_back_to_immediate_processing():
    mod = DummyMediaModule(ModuleConfig(name="dummy_media"))
    mod.processed = False

    result = await mod._ingest_media(url="http://example.com", priority="normal")
    assert mod.processed is True
    assert result["status"] == "processing"


def test_sandbox_sanitizer_allows_cli_tokens():
    mod = SandboxModule(ModuleConfig(name="sandbox"))
    payload = {
        "command": ["bash", "-lc", "echo hi --flag && printf 'ok' /*comment*/"],
        "session_id": "sess",
    }
    cleaned = mod.sanitize_input(payload)
    assert cleaned["command"][2].find("--flag") >= 0
    assert "/*comment*/" in cleaned["command"][2]
