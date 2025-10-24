import asyncio
import os
import pytest


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_tools_list_catalog_filter(monkeypatch):
    os.environ["TEST_MODE"] = "true"

    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

    # Stub DB pool with catalog id resolution and entries
    class _PoolStub:
        async def fetchone(self, query: str, *args):
            # Return an id for catalog name resolution
            return {"id": 123}

        async def fetchall(self, query: str, *args):
            # Return only 'media.search' in catalog
            return [{"tool_name": "media.search"}]

    async def _get_db_pool_stub():
        return _PoolStub()

    monkeypatch.setenv("TEST_MODE", "true")
    monkeypatch.setenv("MCP_ENABLE_MEDIA_MODULE", "false")
    monkeypatch.setenv("MCP_MODULES", "")

    # Patch DB pool getter
    import tldw_Server_API.app.core.AuthNZ.database as db_mod
    monkeypatch.setattr(db_mod, "get_db_pool", _get_db_pool_stub)

    # Stub module registry with a single module exposing two tools
    class _ModuleStub:
        name = "Media"

        async def get_tools(self):
            return [
                {"name": "media.search", "inputSchema": {"type": "object"}},
                {"name": "ingest_media", "inputSchema": {"type": "object"}},
            ]

    class _RegistryStub:
        async def get_all_modules(self):
            return {"media": _ModuleStub()}

    # Build protocol and monkeypatch registry and RBAC checks
    proto = MCPProtocol()
    proto.module_registry = _RegistryStub()
    async def _allow_mod(ctx, mid):
        return True

    async def _allow_tool(ctx, name):
        return True

    proto._has_module_permission = _allow_mod  # type: ignore
    proto._has_tool_permission = _allow_tool  # type: ignore

    ctx = RequestContext(request_id="test", user_id="1", client_id="unit", session_id=None, metadata={})

    # Run tools/list with catalog
    result = await proto._handle_tools_list({"catalog": "A"}, ctx)
    assert isinstance(result, dict)
    tools = result.get("tools", [])
    names = {t.get("name") for t in tools}
    assert "media.search" in names
    assert "ingest_media" not in names  # filtered out by catalog


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_catalog_resolution_precedence(monkeypatch):
    os.environ["TEST_MODE"] = "true"

    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

    # Stub DB pool to simulate team/org/global resolution
    class _PoolStub:
        async def fetchone(self, query: str, *args):
            # Team first
            if "team_id = ?" in query and args == ("A", 7):
                return {"id": 100}
            # Org next
            if "org_id = ?" in query and "team_id IS NULL" in query and args == ("A", 5):
                return {"id": 200}
            # Global last
            if "org_id IS NULL" in query and "team_id IS NULL" in query:
                return {"id": 300}
            return None

        async def fetchall(self, query: str, *args):
            # Return a distinct tool per resolved catalog id
            cat_id = args[0]
            if cat_id == 100:
                return [{"tool_name": "team.only"}]
            if cat_id == 200:
                return [{"tool_name": "org.only"}]
            if cat_id == 300:
                return [{"tool_name": "global.only"}]
            return []

    async def _get_db_pool_stub():
        return _PoolStub()

    monkeypatch.setenv("MCP_ENABLE_MEDIA_MODULE", "false")
    monkeypatch.setenv("MCP_MODULES", "")

    import tldw_Server_API.app.core.AuthNZ.database as db_mod
    monkeypatch.setattr(db_mod, "get_db_pool", _get_db_pool_stub)

    # Registry stub provides two tools; catalog should filter to the resolved one
    class _ModuleStub:
        name = "Media"
        async def get_tools(self):
            return [
                {"name": "team.only", "inputSchema": {"type": "object"}},
                {"name": "org.only", "inputSchema": {"type": "object"}},
                {"name": "global.only", "inputSchema": {"type": "object"}},
            ]

    class _RegistryStub:
        async def get_all_modules(self):
            return {"media": _ModuleStub()}

    proto = MCPProtocol()
    proto.module_registry = _RegistryStub()
    async def _allow_mod(*_args, **_kwargs):
        return True
    async def _allow_tool(*_args, **_kwargs):
        return True
    proto._has_module_permission = _allow_mod  # type: ignore
    proto._has_tool_permission = _allow_tool  # type: ignore

    # team_id present: prefer team scoped catalog
    ctx_team = RequestContext(request_id="r", user_id="1", client_id="c", metadata={"team_id": 7, "org_id": 5})
    res_team = await proto._handle_tools_list({"catalog": "A"}, ctx_team)
    names_team = {t.get("name") for t in res_team.get("tools", [])}
    assert names_team == {"team.only"}

    # no team: fall back to org scoped
    ctx_org = RequestContext(request_id="r2", user_id="1", client_id="c", metadata={"org_id": 5})
    res_org = await proto._handle_tools_list({"catalog": "A"}, ctx_org)
    names_org = {t.get("name") for t in res_org.get("tools", [])}
    assert names_org == {"org.only"}

    # neither: fall back to global
    ctx_global = RequestContext(request_id="r3", user_id="1", client_id="c", metadata={})
    res_global = await proto._handle_tools_list({"catalog": "A"}, ctx_global)
    names_global = {t.get("name") for t in res_global.get("tools", [])}
    assert names_global == {"global.only"}

    # unresolved catalog (fetchone returns None for all): fail-open (no filter)
    class _PoolNone:
        async def fetchone(self, *a, **k):
            return None
        async def fetchall(self, *a, **k):
            return []

    monkeypatch.setattr(db_mod, "get_db_pool", lambda: _PoolNone())
    res_unres = await proto._handle_tools_list({"catalog": "missing"}, ctx_global)
    names_unres = {t.get("name") for t in res_unres.get("tools", [])}
    assert names_unres == {"team.only", "org.only", "global.only"}


@pytest.mark.unit
@pytest.mark.asyncio
async def test_protocol_resources_list_uses_catalog_filter(monkeypatch):
    os.environ["TEST_MODE"] = "true"

    from tldw_Server_API.app.core.MCP_unified.protocol import MCPProtocol, RequestContext

    class _PoolStub:
        async def fetchone(self, query: str, *args):
            return {"id": 10}

        async def fetchall(self, query: str, *args):
            return [{"tool_name": "allowed.tool"}]

    async def _get_db_pool_stub():
        return _PoolStub()

    import tldw_Server_API.app.core.AuthNZ.database as db_mod
    monkeypatch.setattr(db_mod, "get_db_pool", _get_db_pool_stub)

    class _AllowedModule:
        name = "Allowed"

        async def get_tools(self):
            return [{"name": "allowed.tool"}]

        async def get_resources(self):
            return [{"uri": "allowed://one"}]

    class _BlockedModule:
        name = "Blocked"

        async def get_tools(self):
            return [{"name": "other.tool"}]

        async def get_resources(self):
            return [{"uri": "blocked://one"}]

    class _RegistryStub:
        async def get_all_modules(self):
            return {"allowed": _AllowedModule(), "blocked": _BlockedModule()}

    proto = MCPProtocol()
    proto.module_registry = _RegistryStub()

    async def _allow_module(*_args, **_kwargs):
        return True

    async def _allow_resource(*_args, **_kwargs):
        return True

    proto._has_module_permission = _allow_module  # type: ignore
    proto._has_resource_permission = _allow_resource  # type: ignore

    ctx = RequestContext(request_id="r", user_id="u", client_id="c", metadata={})
    result = await proto._handle_resources_list({"catalog": "A"}, ctx)
    uris = {res.get("uri") for res in result.get("resources", [])}
    assert "allowed://one" in uris
    assert "blocked://one" not in uris
