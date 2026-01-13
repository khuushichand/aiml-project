import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.admin_schemas import BudgetSettings


pytestmark = pytest.mark.unit


def test_budget_settings_rejects_usd_precision():
    with pytest.raises(ValidationError):
        BudgetSettings(budget_day_usd=1.234)


def test_budget_settings_accepts_usd_precision():
    settings = BudgetSettings(budget_day_usd=1.23, budget_month_usd=2.0)
    assert settings.budget_day_usd == 1.23
    assert settings.budget_month_usd == 2.0
