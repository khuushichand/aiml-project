import pytest

from tldw_Server_API.app.services.admin_budgets_service import merge_budget_settings


pytestmark = pytest.mark.unit


def test_merge_budget_settings_clears_when_requested():
    existing = {"budget_month_usd": 100.0, "alert_thresholds": [50, 80]}
    merged = merge_budget_settings(existing, updates={"budget_month_usd": 200.0}, clear=True)
    assert merged == {}


def test_merge_budget_settings_preserves_when_no_updates():
    existing = {"budget_month_usd": 100.0}
    merged = merge_budget_settings(existing, updates=None, clear=False)
    assert merged == {"budget_month_usd": 100.0}


def test_merge_budget_settings_removes_none_fields():
    existing = {"budget_month_usd": 100.0, "budget_day_tokens": 1000}
    merged = merge_budget_settings(existing, updates={"budget_day_tokens": None}, clear=False)
    assert merged == {"budget_month_usd": 100.0}
