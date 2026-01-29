import pytest

from tldw_Server_API.app.core.MCP_unified.modules.implementations.knowledge_module import KnowledgeModule
from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext


@pytest.mark.asyncio
async def test_knowledge_search_filters_sources(monkeypatch):
    module = KnowledgeModule(ModuleConfig(name="knowledge"))

    async def _allowed(tool: str, _context):
        return tool in {"notes.search"}

    async def _call(tool: str, _args, _context):
        return {"results": [{"uri": f"{tool}://1", "score": 1.0, "last_modified": None}]}

    monkeypatch.setattr(module, "_tool_allowed", _allowed)
    monkeypatch.setattr(module, "_call_tool", _call)

    ctx = RequestContext(request_id="req-1", user_id="1", client_id="client", session_id=None, metadata={})
    result = await module._search(
        {
            "query": "hello",
            "sources": ["notes", "chats"],
            "limit": 10,
            "offset": 0,
            "snippet_length": 300,
            "order_by": "relevance",
        },
        ctx,
    )

    assert all(r.get("uri", "").startswith("notes.search") for r in result.get("results", []))


@pytest.mark.asyncio
async def test_knowledge_get_denied_when_source_disallowed(monkeypatch):
    module = KnowledgeModule(ModuleConfig(name="knowledge"))

    async def _deny(_tool: str, _context):
        return False

    monkeypatch.setattr(module, "_tool_allowed", _deny)

    ctx = RequestContext(request_id="req-2", user_id="1", client_id="client", session_id=None, metadata={})
    with pytest.raises(PermissionError):
        await module._get({"source": "notes", "id": "1"}, ctx)
