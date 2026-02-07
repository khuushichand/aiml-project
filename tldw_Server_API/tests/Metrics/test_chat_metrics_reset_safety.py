import pytest

from tldw_Server_API.app.core.Chat.chat_metrics import ChatMetricsCollector


pytestmark = pytest.mark.unit


@pytest.mark.asyncio
async def test_reset_active_metrics_does_not_underflow_requests():
    collector = ChatMetricsCollector()

    async with collector.track_request(
        provider="openai",
        model="gpt-4",
        streaming=False,
        client_id="test-client",
    ):
        assert collector.get_active_metrics()["active_requests"] == 1
        collector.reset_active_metrics()
        assert collector.get_active_metrics()["active_requests"] == 0

    assert collector.get_active_metrics()["active_requests"] == 0


@pytest.mark.asyncio
async def test_reset_active_metrics_does_not_underflow_streams():
    collector = ChatMetricsCollector()

    async with collector.track_streaming("conversation-1"):
        assert collector.get_active_metrics()["active_streams"] == 1
        collector.reset_active_metrics()
        assert collector.get_active_metrics()["active_streams"] == 0

    assert collector.get_active_metrics()["active_streams"] == 0
