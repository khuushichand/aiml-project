import pytest

from tldw_Server_API.app.core.Metrics.metrics_manager import MetricsRegistry
import tldw_Server_API.app.core.TTS.tts_service_v2 as tts_service_v2


@pytest.mark.asyncio
async def test_tts_metrics_registered(monkeypatch):
    registry = MetricsRegistry()
    monkeypatch.setattr(tts_service_v2, "get_metrics_registry", lambda: registry)

    service = tts_service_v2.TTSServiceV2()

    assert "tts_requests_total" in registry.metrics
    assert "tts_request_duration_seconds" in registry.metrics
    assert "tts_ttfb_seconds" in registry.metrics

    await service.shutdown()
