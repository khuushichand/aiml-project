from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from tldw_Server_API.app.core.Governance.service import GovernanceService

pytestmark = pytest.mark.unit


@dataclass
class _FakeGap:
    id: int
    question: str
    category: str
    status: str = "open"


class _FakeStore:
    def __init__(self) -> None:
        self.last_upsert: dict[str, Any] | None = None

    async def upsert_open_gap(self, **kwargs: Any) -> _FakeGap:
        self.last_upsert = kwargs
        return _FakeGap(id=1, question=str(kwargs["question"]), category=str(kwargs["category"]))


class _FakePolicyLoader:
    def __init__(
        self,
        fallback_mode: str = "warn_only",
        *,
        should_fail: bool = True,
        candidates: list[dict[str, Any]] | None = None,
    ) -> None:
        self.fallback_mode = fallback_mode
        self.should_fail = should_fail
        self.candidates = candidates or []

    async def get_candidates(self, **_: Any) -> list[dict[str, Any]]:
        if self.should_fail:
            raise RuntimeError("backend unavailable")
        return list(self.candidates)


@pytest.mark.asyncio
async def test_validate_change_uses_shared_fallback_mode():
    svc = GovernanceService(
        store=_FakeStore(),
        policy_loader=_FakePolicyLoader("warn_only", should_fail=True),
    )

    out = await svc.validate_change(
        surface="mcp_tool",
        summary="Allow tool to update dependency versions",
        category="dependencies",
    )

    assert out.status in {"warn", "allow"}
    assert out.fallback_reason == "backend_unavailable"


@pytest.mark.asyncio
async def test_query_knowledge_returns_category_source():
    svc = GovernanceService(store=_FakeStore(), policy_loader=_FakePolicyLoader(should_fail=False))

    out = await svc.query_knowledge(query="auth rules", category="security")

    assert out.category_source in {"explicit", "metadata", "pattern", "default"}


@pytest.mark.asyncio
async def test_resolve_gap_uses_metadata_category_when_missing_explicit():
    store = _FakeStore()
    svc = GovernanceService(store=store, policy_loader=_FakePolicyLoader(should_fail=False))

    gap = await svc.resolve_gap(
        question="Should we require MFA for admins?",
        category=None,
        metadata={"category": "security"},
        org_id=7,
    )

    assert gap.status == "open"
    assert store.last_upsert is not None
    assert store.last_upsert["category"] == "security"
