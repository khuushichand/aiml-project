import pytest
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


pytestmark = pytest.mark.unit


def test_status_endpoint_sets_prometheus_gauges(prompt_studio_dual_backend_client):
    backend_label, client, db = prompt_studio_dual_backend_client

    r = client.get("/api/v1/prompt-studio/status")
    assert r.status_code == 200

    reg = get_metrics_registry()
    # Metrics should be registered and have at least one value after hitting status
    for name in (
        "prompt_studio_queue_depth",
        "prompt_studio_processing",
        "prompt_studio_leases_active",
        "prompt_studio_leases_expiring_soon",
        "prompt_studio_leases_stale_processing",
    ):
        stats = reg.get_metric_stats(name)
        assert isinstance(stats, dict)
        # stats can be empty if nothing recorded, but after endpoint call we expect 'latest'
        assert "latest" in stats
