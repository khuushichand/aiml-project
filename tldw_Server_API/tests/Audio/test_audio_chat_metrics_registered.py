from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


def test_audio_chat_latency_metric_registered():
    reg = get_metrics_registry()
    assert "audio_chat_latency_seconds" in reg.metrics
