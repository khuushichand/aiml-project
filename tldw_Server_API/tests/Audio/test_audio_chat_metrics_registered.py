import pytest

from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.unit
def test_audio_chat_latency_metric_registered():
    """Verify that the audio_chat_latency_seconds metric is registered."""
    reg = get_metrics_registry()
    assert "audio_chat_latency_seconds" in reg.metrics
