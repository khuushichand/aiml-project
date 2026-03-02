import pytest
from pydantic import ValidationError

from tldw_Server_API.app.api.v1.schemas.admin_schemas import (
    RouterAnalyticsAccessResponse,
    RouterAnalyticsAccessSummary,
    RouterAnalyticsBreakdownRow,
    RouterAnalyticsConversationRow,
    RouterAnalyticsConversationsResponse,
    RouterAnalyticsConversationsSummary,
    RouterAnalyticsDataWindow,
    RouterAnalyticsLogResponse,
    RouterAnalyticsLogRow,
    RouterAnalyticsLogSummary,
    RouterAnalyticsModelRow,
    RouterAnalyticsModelsResponse,
    RouterAnalyticsModelsSummary,
    RouterAnalyticsNetworkResponse,
    RouterAnalyticsNetworkSummary,
    RouterAnalyticsProviderRow,
    RouterAnalyticsProvidersResponse,
    RouterAnalyticsProvidersSummary,
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


def test_router_analytics_providers_response_constructs():
    payload = RouterAnalyticsProvidersResponse(
        summary=RouterAnalyticsProvidersSummary(
            providers_total=2,
            providers_online=1,
            failover_events=1,
        ),
        items=[
            RouterAnalyticsProviderRow(
                provider='groq',
                requests=2,
                prompt_tokens=35,
                completion_tokens=10,
                total_tokens=45,
                total_cost_usd=0.04,
                avg_latency_ms=350.0,
                errors=1,
                success_rate_pct=50.0,
                online=True,
            )
        ],
        generated_at='2026-03-01T00:00:00Z',
        data_window=RouterAnalyticsDataWindow(
            start='2026-03-01T00:00:00Z',
            end='2026-03-01T08:00:00Z',
            range='8h',
        ),
    )
    assert payload.summary.providers_online == 1
    assert payload.items[0].provider == 'groq'


def test_router_analytics_access_response_constructs():
    payload = RouterAnalyticsAccessResponse(
        summary=RouterAnalyticsAccessSummary(
            token_names_total=2,
            remote_ips_total=1,
            user_agents_total=1,
            anonymous_requests=1,
        ),
        token_names=[
            RouterAnalyticsBreakdownRow(
                key="Admin",
                label="Admin",
                requests=1,
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                errors=0,
            )
        ],
        remote_ips=[
            RouterAnalyticsBreakdownRow(
                key="unknown",
                label="unknown",
                requests=1,
                prompt_tokens=7,
                completion_tokens=2,
                total_tokens=9,
                errors=1,
            )
        ],
        user_agents=[
            RouterAnalyticsBreakdownRow(
                key="curl/8.8.0",
                label="curl/8.8.0",
                requests=1,
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                errors=0,
            )
        ],
        generated_at='2026-03-01T00:00:00Z',
        data_window=RouterAnalyticsDataWindow(
            start='2026-03-01T00:00:00Z',
            end='2026-03-01T08:00:00Z',
            range='8h',
        ),
    )
    assert payload.summary.anonymous_requests == 1
    assert payload.remote_ips[0].key == "unknown"


def test_router_analytics_network_response_constructs():
    payload = RouterAnalyticsNetworkResponse(
        summary=RouterAnalyticsNetworkSummary(
            remote_ips_total=2,
            endpoints_total=1,
            operations_total=1,
            error_requests=1,
        ),
        remote_ips=[
            RouterAnalyticsBreakdownRow(
                key="127.0.0.1",
                label="127.0.0.1",
                requests=1,
                prompt_tokens=10,
                completion_tokens=20,
                total_tokens=30,
                errors=0,
            )
        ],
        endpoints=[
            RouterAnalyticsBreakdownRow(
                key="/api/v1/chat/completions",
                label="/api/v1/chat/completions",
                requests=2,
                prompt_tokens=17,
                completion_tokens=22,
                total_tokens=39,
                errors=1,
            )
        ],
        operations=[
            RouterAnalyticsBreakdownRow(
                key="chat",
                label="chat",
                requests=2,
                prompt_tokens=17,
                completion_tokens=22,
                total_tokens=39,
                errors=1,
            )
        ],
        generated_at='2026-03-01T00:00:00Z',
        data_window=RouterAnalyticsDataWindow(
            start='2026-03-01T00:00:00Z',
            end='2026-03-01T08:00:00Z',
            range='8h',
        ),
    )
    assert payload.summary.remote_ips_total == 2
    assert payload.endpoints[0].key == "/api/v1/chat/completions"


def test_router_analytics_models_response_constructs():
    payload = RouterAnalyticsModelsResponse(
        summary=RouterAnalyticsModelsSummary(
            models_total=2,
            models_online=1,
            providers_total=2,
            error_requests=1,
        ),
        items=[
            RouterAnalyticsModelRow(
                model="llama-3.3-70b",
                provider="groq",
                requests=2,
                prompt_tokens=35,
                completion_tokens=10,
                total_tokens=45,
                total_cost_usd=0.04,
                avg_latency_ms=350.0,
                errors=1,
                success_rate_pct=50.0,
                online=True,
            )
        ],
        generated_at='2026-03-01T00:00:00Z',
        data_window=RouterAnalyticsDataWindow(
            start='2026-03-01T00:00:00Z',
            end='2026-03-01T08:00:00Z',
            range='8h',
        ),
    )
    assert payload.summary.models_total == 2
    assert payload.items[0].provider == "groq"


def test_router_analytics_conversations_response_constructs():
    payload = RouterAnalyticsConversationsResponse(
        summary=RouterAnalyticsConversationsSummary(
            conversations_total=3,
            active_conversations=2,
            avg_requests_per_conversation=1.33,
            error_requests=2,
        ),
        items=[
            RouterAnalyticsConversationRow(
                conversation_id="conv-2",
                requests=2,
                prompt_tokens=35,
                completion_tokens=10,
                total_tokens=45,
                total_cost_usd=0.04,
                avg_latency_ms=350.0,
                errors=1,
                success_rate_pct=50.0,
                last_seen_at="2026-03-01T10:26:00Z",
            )
        ],
        generated_at='2026-03-01T00:00:00Z',
        data_window=RouterAnalyticsDataWindow(
            start='2026-03-01T00:00:00Z',
            end='2026-03-01T08:00:00Z',
            range='8h',
        ),
    )
    assert payload.summary.conversations_total == 3
    assert payload.items[0].conversation_id == "conv-2"


def test_router_analytics_log_response_constructs():
    payload = RouterAnalyticsLogResponse(
        summary=RouterAnalyticsLogSummary(
            requests_total=4,
            error_requests=2,
            estimated_requests=2,
            request_ids_total=4,
        ),
        items=[
            RouterAnalyticsLogRow(
                ts="2026-03-01T10:27:00Z",
                request_id="req-4",
                conversation_id="conv-3",
                provider="anthropic",
                model="claude-3.5",
                token_name="unknown",
                endpoint="/api/v1/chat/completions",
                operation="chat",
                status=503,
                latency_ms=300.0,
                prompt_tokens=7,
                completion_tokens=2,
                total_tokens=9,
                total_cost_usd=0.0,
                remote_ip="unknown",
                user_agent="unknown",
                estimated=True,
                error=True,
            )
        ],
        generated_at='2026-03-01T00:00:00Z',
        data_window=RouterAnalyticsDataWindow(
            start='2026-03-01T00:00:00Z',
            end='2026-03-01T08:00:00Z',
            range='8h',
        ),
    )
    assert payload.summary.requests_total == 4
    assert payload.items[0].error is True
