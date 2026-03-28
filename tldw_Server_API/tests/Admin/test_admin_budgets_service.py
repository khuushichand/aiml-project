import pytest

from tldw_Server_API.app.services.admin_budgets_service import (
    _flatten_budget_payload,
    _inflate_budget_payload,
    _normalize_budget_payload,
    build_budget_change_log,
    merge_budget_settings,
)


pytestmark = pytest.mark.unit


def test_merge_budget_settings_clears_when_requested():


    existing = {"budget_month_usd": 100.0, "alert_thresholds": {"global": [50, 80]}}
    merged = merge_budget_settings(existing, updates={"budget_month_usd": 200.0}, clear=True)
    assert merged == {}


def test_merge_budget_settings_preserves_when_no_updates():


    existing = {"budget_month_usd": 100.0}
    merged = merge_budget_settings(existing, updates=None, clear=False)
    assert merged == {"budget_month_usd": 100.0}


def test_merge_budget_settings_removes_none_fields():


    existing = {
        "budget_month_usd": 100.0,
        "budget_day_tokens": 1000,
        "alert_thresholds": {"global": [80], "per_metric": {"budget_day_tokens": [90]}},
    }
    merged = merge_budget_settings(
        existing,
        updates={"budget_day_tokens": None, "alert_thresholds": {"per_metric": {"budget_day_tokens": None}}},
        clear=False,
    )
    assert merged == {"budget_month_usd": 100.0, "alert_thresholds": {"global": [80]}}


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

    assert by_field["budgets.alert_thresholds.global"]["old_value"] is None
    assert by_field["budgets.alert_thresholds.global"]["new_value"] == [80, 95]
    assert by_field["budgets.alert_thresholds.global"]["data_type"] == "array"

    assert by_field["budgets.alert_thresholds.per_metric.budget_month_usd"]["old_value"] is None
    assert by_field["budgets.alert_thresholds.per_metric.budget_month_usd"]["new_value"] == [90]
    assert by_field["budgets.alert_thresholds.per_metric.budget_month_usd"]["data_type"] == "array"

    assert by_field["budgets.enforcement_mode.global"]["old_value"] is None
    assert by_field["budgets.enforcement_mode.global"]["new_value"] == "soft"
    assert by_field["budgets.enforcement_mode.global"]["data_type"] == "string"

    assert by_field["budgets.enforcement_mode.per_metric.budget_month_usd"]["old_value"] is None
    assert by_field["budgets.enforcement_mode.per_metric.budget_month_usd"]["new_value"] == "hard"
    assert by_field["budgets.enforcement_mode.per_metric.budget_month_usd"]["data_type"] == "string"


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


def test_merge_budget_settings_normalizes_thresholds():


    existing = {}
    merged = merge_budget_settings(
        existing,
        updates={"alert_thresholds": {"global": [95, 80, 80]}},
        clear=False,
    )
    assert merged["alert_thresholds"]["global"] == [80, 95]


def test_merge_budget_settings_provider_budgets_adds():
    existing = {"budget_month_usd": 100.0}
    merged = merge_budget_settings(
        existing,
        updates={"provider_budgets": {"openai": {"month_usd": 50}, "anthropic": {"month_usd": 80}}},
        clear=False,
    )
    assert merged["provider_budgets"] == {"openai": {"month_usd": 50}, "anthropic": {"month_usd": 80}}
    assert merged["budget_month_usd"] == 100.0


def test_merge_budget_settings_provider_budgets_removes_provider():
    existing = {"provider_budgets": {"openai": {"month_usd": 50}, "anthropic": {"month_usd": 80}}}
    merged = merge_budget_settings(
        existing,
        updates={"provider_budgets": {"openai": None}},
        clear=False,
    )
    assert merged["provider_budgets"] == {"anthropic": {"month_usd": 80}}


def test_merge_budget_settings_provider_budgets_clears_all():
    existing = {"provider_budgets": {"openai": {"month_usd": 50}}}
    merged = merge_budget_settings(
        existing,
        updates={"provider_budgets": None},
        clear=False,
    )
    assert "provider_budgets" not in merged


def test_merge_budget_settings_provider_budgets_merges_keys():
    existing = {"provider_budgets": {"openai": {"month_usd": 50, "day_usd": 5}}}
    merged = merge_budget_settings(
        existing,
        updates={"provider_budgets": {"openai": {"month_usd": 100}}},
        clear=False,
    )
    assert merged["provider_budgets"]["openai"] == {"month_usd": 100, "day_usd": 5}


def test_merge_budget_settings_provider_budgets_replaces_non_dict_existing_value():
    existing = {"provider_budgets": {"openai": 5}}
    merged = merge_budget_settings(
        existing,
        updates={"provider_budgets": {"openai": {"month_usd": 100}}},
        clear=False,
    )
    assert merged["provider_budgets"]["openai"] == {"month_usd": 100}


def test_budget_payload_roundtrip_preserves_provider_budgets():
    flat = {
        "budget_month_usd": 100.0,
        "provider_budgets": {
            "openai": {"month_usd": 50},
            "anthropic": {"month_usd": 80},
        },
    }

    inflated = _inflate_budget_payload(flat)
    assert inflated["provider_budgets"] == flat["provider_budgets"]

    normalized = _normalize_budget_payload(inflated)
    flattened = _flatten_budget_payload(normalized)
    assert flattened["provider_budgets"] == flat["provider_budgets"]
    assert flattened["budget_month_usd"] == 100.0


def test_build_budget_change_log_tracks_provider_budget_updates():
    existing = {"provider_budgets": {"openai": {"month_usd": 50}}}
    updates = {
        "provider_budgets": {
            "openai": {"month_usd": 100},
            "anthropic": {"month_usd": 80},
        }
    }

    merged = merge_budget_settings(existing, updates=updates, clear=False)
    changes = build_budget_change_log(existing, merged, updates, clear_budgets=False)
    by_field = {entry["field_name"]: entry for entry in changes}

    assert by_field["budgets.provider_budgets.openai.month_usd"]["old_value"] == 50
    assert by_field["budgets.provider_budgets.openai.month_usd"]["new_value"] == 100
    assert by_field["budgets.provider_budgets.anthropic.month_usd"]["old_value"] is None
    assert by_field["budgets.provider_budgets.anthropic.month_usd"]["new_value"] == 80
