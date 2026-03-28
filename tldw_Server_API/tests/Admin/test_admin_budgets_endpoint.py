import pytest
from fastapi import HTTPException

from tldw_Server_API.app.api.v1.endpoints.admin import admin_budgets


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_admin_get_budget_forecast_preserves_http_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _raise_http_exception(**_kwargs):
        raise HTTPException(status_code=403, detail="forbidden")

    monkeypatch.setattr(admin_budgets.admin_budgets_service, "list_budgets", _raise_http_exception)

    with pytest.raises(HTTPException) as exc_info:
        await admin_budgets.admin_get_budget_forecast(org_id=1, principal=None, db=None)

    assert exc_info.value.status_code == 403
    assert exc_info.value.detail == "forbidden"
