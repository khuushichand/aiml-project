import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    RouterAnalyticsDataWindow,
    RouterAnalyticsQuotaMetric,
    RouterAnalyticsQuotaRow,
    RouterAnalyticsQuotaSummary,
    RouterAnalyticsQuotaResponse,
    RouterAnalyticsRangeQuery,
    RouterAnalyticsStatusKpis,
    RouterAnalyticsStatusResponse,
)


pytestmark = pytest.mark.unit


def test_router_analytics_range_rejects_invalid_value():
    with pytest.raises(ValidationError):
        RouterAnalyticsRangeQuery(range="2h")


def test_router_analytics_status_response_constructs():
    payload = RouterAnalyticsStatusResponse(
        kpis=RouterAnalyticsStatusKpis(requests=1, prompt_tokens=10, generated_tokens=5, total_tokens=15),
        generated_at="2026-03-01T00:00:00Z",
        data_window=RouterAnalyticsDataWindow(
            start="2026-03-01T00:00:00Z",
            end="2026-03-01T08:00:00Z",
            range="8h",
        ),
    )
    assert payload.kpis.requests == 1
    assert payload.data_window.range == "8h"


def test_router_analytics_quota_response_constructs():
    payload = RouterAnalyticsQuotaResponse(
        summary=RouterAnalyticsQuotaSummary(keys_total=2, keys_over_budget=1, budgeted_keys=2),
        items=[
            RouterAnalyticsQuotaRow(
                key_id=12,
                token_name="Ops",
                requests=2,
                total_tokens=45,
                total_cost_usd=0.04,
                day_tokens=RouterAnalyticsQuotaMetric(used=45.0, limit=30.0, utilization_pct=150.0, exceeded=True),
                over_budget=True,
                reasons=["day_tokens_exceeded:45/30"],
            )
        ],
        generated_at="2026-03-01T00:00:00Z",
        data_window=RouterAnalyticsDataWindow(
            start="2026-03-01T00:00:00Z",
            end="2026-03-01T08:00:00Z",
            range="8h",
        ),
    )
    assert payload.summary.keys_over_budget == 1
    assert payload.items[0].day_tokens is not None
    assert payload.items[0].day_tokens.exceeded is True
