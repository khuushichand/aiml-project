import pytest

from tldw_Server_API.app.services.admin_budgets_service import (
    build_budget_change_log,
    merge_budget_settings,
)


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


def test_build_budget_change_log_tracks_updates_and_clears():
    existing = {"budget_month_usd": 100.0, "budget_day_tokens": 1000}
    updates = {
        "budget_month_usd": 150.0,
        "budget_day_tokens": None,
        "alert_thresholds": {"global": [80, 95], "per_metric": {"budget_month_usd": [90]}},
        "enforcement_mode": {"global": "soft", "per_metric": {"budget_month_usd": "hard"}},
    }
    merged = merge_budget_settings(existing, updates=updates, clear=False)

    changes = build_budget_change_log(existing, merged, updates, clear_budgets=False)
    by_field = {entry["field_name"]: entry for entry in changes}

    assert by_field["budgets.budget_month_usd"]["old_value"] == 100.0
    assert by_field["budgets.budget_month_usd"]["new_value"] == 150.0
    assert by_field["budgets.budget_month_usd"]["data_type"] == "number"

    assert by_field["budgets.budget_day_tokens"]["old_value"] == 1000
    assert by_field["budgets.budget_day_tokens"]["new_value"] is None
    assert by_field["budgets.budget_day_tokens"]["data_type"] == "integer"

    assert by_field["budgets.alert_thresholds"]["old_value"] is None
    assert by_field["budgets.alert_thresholds"]["new_value"] == {
        "global": [80, 95],
        "per_metric": {"budget_month_usd": [90]},
    }
    assert by_field["budgets.alert_thresholds"]["data_type"] == "object"

    assert by_field["budgets.enforcement_mode"]["old_value"] is None
    assert by_field["budgets.enforcement_mode"]["new_value"] == {
        "global": "soft",
        "per_metric": {"budget_month_usd": "hard"},
    }
    assert by_field["budgets.enforcement_mode"]["data_type"] == "object"


def test_build_budget_change_log_handles_clear_budgets():
    existing = {"budget_month_usd": 100.0}
    changes = build_budget_change_log(existing, {}, None, clear_budgets=True)
    assert changes == [
        {
            "field_name": "budgets",
            "old_value": {"budget_month_usd": 100.0},
            "new_value": None,
            "data_type": "object",
            "notes": "clear_budgets=true",
        }
    ]


def test_build_budget_change_log_skips_when_no_updates():
    existing = {"budget_month_usd": 100.0}
    merged = merge_budget_settings(existing, updates=None, clear=False)
    changes = build_budget_change_log(existing, merged, None, clear_budgets=False)
    assert changes == []
