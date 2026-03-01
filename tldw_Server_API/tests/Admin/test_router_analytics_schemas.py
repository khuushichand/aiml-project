import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    RouterAnalyticsDataWindow,
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
