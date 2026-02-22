import pytest

from tldw_Server_API.app.core.Claims_Extraction import monitoring
from tldw_Server_API.app.core.Metrics import metrics_manager


@pytest.mark.unit
def test_monitoring_counter_helpers_emit_expected_metrics(monkeypatch):
    calls: list[tuple[str, float, dict[str, str] | None]] = []

    monkeypatch.setattr(monitoring, "_claims_monitoring_enabled", lambda: True)
    monkeypatch.setattr(monitoring, "_register_claims_metrics", lambda: None)

    def _increment(metric_name: str, value: float = 1, labels: dict[str, str] | None = None):
        calls.append((metric_name, value, labels))

    monkeypatch.setattr(metrics_manager, "increment_counter", _increment)

    monitoring.record_claims_response_format_selection(
        provider="openai",
        model="gpt-4o-mini",
        mode="Extract",
        response_format={"type": "json_schema"},
    )
    monitoring.record_claims_output_parse_event(
        provider="openai",
        model="gpt-4o-mini",
        mode="Extract",
        parse_mode="Strict",
        outcome="Error",
        reason="ClaimsOutputSchemaError",
    )
    monitoring.record_claims_fallback(
        provider="openai",
        model="gpt-4o-mini",
        mode="Extract",
        reason="Parse Error",
    )

    assert [name for name, _value, _labels in calls] == [
        "claims_response_format_selected_total",
        "claims_output_parse_events_total",
        "claims_fallback_total",
    ]
    assert calls[0][2] == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mode": "extract",
        "response_format_type": "json_schema",
    }
    assert calls[1][2] == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mode": "extract",
        "parse_mode": "strict",
        "outcome": "error",
        "reason": "claims_output_schema_error",
    }
    assert calls[2][2] == {
        "provider": "openai",
        "model": "gpt-4o-mini",
        "mode": "extract",
        "reason": "parse_error",
    }


@pytest.mark.unit
def test_monitoring_response_format_none_label(monkeypatch):
    calls: list[tuple[str, float, dict[str, str] | None]] = []

    monkeypatch.setattr(monitoring, "_claims_monitoring_enabled", lambda: True)
    monkeypatch.setattr(monitoring, "_register_claims_metrics", lambda: None)
    monkeypatch.setattr(
        metrics_manager,
        "increment_counter",
        lambda metric_name, value=1, labels=None: calls.append((metric_name, value, labels)),
    )

    monitoring.record_claims_response_format_selection(
        provider="openai",
        model="",
        mode="verify",
        response_format=None,
    )

    assert calls
    assert calls[0][0] == "claims_response_format_selected_total"
    assert calls[0][2] is not None
    assert calls[0][2]["response_format_type"] == "none"
