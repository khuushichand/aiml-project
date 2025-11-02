import os
import pytest


def test_jobs_metrics_no_registry_noop(monkeypatch):
    # Simulate environment where metrics registry is unavailable
    from tldw_Server_API.app.core.Jobs import metrics as met

    # Force import-time registry symbol to None
    monkeypatch.setattr(met, "get_metrics_registry", None, raising=False)

    # Ensure registration path does not blow up without registry
    met.ensure_jobs_metrics_registered()

    # All metric helpers should short-circuit and not raise
    met.set_queue_gauges("d", "q", "t", queued=1, processing=0, backlog=1, scheduled=0)
    met.increment_created({"domain": "d", "queue": "q", "job_type": "t"})
    met.increment_completed({"domain": "d", "queue": "q", "job_type": "t"})
    met.increment_cancelled({"domain": "d", "queue": "q", "job_type": "t"})
    met.increment_json_truncated({"domain": "d", "queue": "q", "job_type": "t"}, "payload")
    met.increment_sla_breach({"domain": "d", "queue": "q", "job_type": "t"}, "duration")
    met.observe_queue_latency({"domain": "d", "queue": "q", "job_type": "t"}, None, None)
    met.observe_duration({"domain": "d", "queue": "q", "job_type": "t"}, None, None)
