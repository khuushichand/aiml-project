from __future__ import annotations

import pytest
from fastapi import HTTPException

from tldw_Server_API.app.services.admin_usage_service import get_cost_attribution


pytestmark = pytest.mark.unit


class _FailingUsageCursor:
    async def fetchall(self) -> list[dict]:
        raise AssertionError("fetchall should not be reached after execute failure")


class _FailingUsageDb:
    _is_sqlite = True

    async def execute(self, _query: str) -> _FailingUsageCursor:
        raise RuntimeError("llm_usage_v2 missing")


@pytest.mark.asyncio
async def test_get_cost_attribution_surfaces_backend_failures() -> None:
    with pytest.raises(HTTPException) as exc_info:
        await get_cost_attribution(db=_FailingUsageDb(), group_by="user", range_days=7)

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Cost attribution is currently unavailable"
