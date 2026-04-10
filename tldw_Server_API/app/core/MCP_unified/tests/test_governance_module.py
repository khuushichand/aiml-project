from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tldw_Server_API.app.core.MCP_unified.modules.base import ModuleConfig
from tldw_Server_API.app.core.MCP_unified.modules.implementations.governance_module import GovernanceModule
from tldw_Server_API.app.core.MCP_unified.protocol import RequestContext


@dataclass
class _FakeValidationResult:
    action: str
    status: str
    category: str
    category_source: str
    fallback_reason: str | None = None
    matched_rules: tuple[str, ...] = ()


@dataclass
class _FakeKnowledgeResult:
    query: str
    category: str
    category_source: str
    rules: tuple[dict[str, Any], ...] = ()


@dataclass
class _FakeGap:
    id: int
    question: str
    category: str
    status: str = "open"


class _FakeGovernanceService:
    def __init__(self) -> None:
        self.last_query: dict[str, Any] | None = None
        self.last_validate: dict[str, Any] | None = None
        self.last_gap: dict[str, Any] | None = None

    async def query_knowledge(self, **kwargs: Any) -> _FakeKnowledgeResult:
        self.last_query = kwargs
        return _FakeKnowledgeResult(
            query=str(kwargs.get("query")),
            category=str(kwargs.get("category") or "general"),
            category_source="explicit",
            rules=(),
        )

    async def validate_change(self, **kwargs: Any) -> _FakeValidationResult:
        self.last_validate = kwargs
        return _FakeValidationResult(
            action="warn",
            status="warn",
            category=str(kwargs.get("category") or "general"),
            category_source="explicit",
            fallback_reason="backend_unavailable",
        )

    async def resolve_gap(self, **kwargs: Any) -> _FakeGap:
        self.last_gap = kwargs
        return _FakeGap(
            id=1,
            question=str(kwargs.get("question")),
            category=str(kwargs.get("category") or "general"),
        )


@pytest.mark.asyncio
async def test_governance_tools_are_listed():
    mod = GovernanceModule(ModuleConfig(name="governance"), governance_service=_FakeGovernanceService())

    tools = await mod.get_tools()
    tool_names = {tool["name"] for tool in tools}

    assert tool_names >= {
        "governance.query_knowledge",
        "governance.validate_change",
        "governance.resolve_gap",
    }


@pytest.mark.asyncio
async def test_validate_change_dispatches_to_service():
    fake_service = _FakeGovernanceService()
    mod = GovernanceModule(ModuleConfig(name="governance"), governance_service=fake_service)
    ctx = RequestContext(request_id="gov-test-validate", user_id="1", metadata={"workspace_id": "ws-1"})

    out = await mod.execute_tool(
        "governance.validate_change",
        {
            "surface": "mcp_tool",
            "summary": "Enable tool usage for docs export",
            "category": "compliance",
            "metadata": {"org_id": 77},
        },
        context=ctx,
    )

    assert out["status"] == "warn"
    assert out["fallback_reason"] == "backend_unavailable"
    assert fake_service.last_validate is not None
    assert fake_service.last_validate["metadata"]["org_id"] == 77
    assert fake_service.last_validate["metadata"]["workspace_id"] == "ws-1"


@pytest.mark.asyncio
async def test_resolve_gap_uses_context_scope_when_args_missing():
    fake_service = _FakeGovernanceService()
    mod = GovernanceModule(ModuleConfig(name="governance"), governance_service=fake_service)
    ctx = RequestContext(
        request_id="gov-test-gap",
        user_id="1",
        metadata={"org_id": 55, "team_id": 66, "workspace_id": "ws-gap"},
    )

    out = await mod.execute_tool(
        "governance.resolve_gap",
        {"question": "Should this action require approval?", "metadata": {"category": "security"}},
        context=ctx,
    )

    assert out["status"] == "open"
    assert fake_service.last_gap is not None
    assert fake_service.last_gap["org_id"] == 55
    assert fake_service.last_gap["team_id"] == 66
    assert fake_service.last_gap["workspace_id"] == "ws-gap"


@pytest.mark.asyncio
async def test_resolve_gap_rejects_conflicting_workspace_scope():
    fake_service = _FakeGovernanceService()
    mod = GovernanceModule(ModuleConfig(name="governance"), governance_service=fake_service)
    ctx = RequestContext(
        request_id="gov-scope-conflict",
        user_id="1",
        metadata={"org_id": 55, "team_id": 66, "persona_id": "persona-1", "workspace_id": "ws-ctx"},
    )

    with pytest.raises(PermissionError, match="workspace_id must match authenticated context"):
        await mod.execute_tool(
            "governance.resolve_gap",
            {"question": "gap?", "workspace_id": "ws-arg"},
            context=ctx,
        )
