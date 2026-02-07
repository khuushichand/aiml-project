import threading
import time
from concurrent.futures import ThreadPoolExecutor

import pytest

import tldw_Server_API.app.core.Chat.chat_metrics as chat_metrics_module
import tldw_Server_API.app.core.Metrics.telemetry as telemetry_module


pytestmark = pytest.mark.unit


def _call_concurrently(fn, workers: int = 20):
    barrier = threading.Barrier(workers)

    def _worker():
        barrier.wait()
        return fn()

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_worker) for _ in range(workers)]
        return [future.result() for future in futures]


def test_get_telemetry_manager_singleton_is_thread_safe(monkeypatch):
    monkeypatch.setattr(telemetry_module, "_telemetry_manager", None, raising=False)

    call_count = {"value": 0}
    call_lock = threading.Lock()

    class SlowTelemetryManager:
        def __init__(self):
            with call_lock:
                call_count["value"] += 1
            time.sleep(0.02)

    monkeypatch.setattr(telemetry_module, "TelemetryManager", SlowTelemetryManager, raising=True)

    instances = _call_concurrently(telemetry_module.get_telemetry_manager, workers=25)

    assert call_count["value"] == 1
    first_instance = instances[0]
    assert all(instance is first_instance for instance in instances)


def test_get_chat_metrics_singleton_is_thread_safe(monkeypatch):
    monkeypatch.setattr(chat_metrics_module, "_chat_metrics_collector", None, raising=False)

    call_count = {"value": 0}
    call_lock = threading.Lock()

    class SlowChatMetricsCollector:
        def __init__(self):
            with call_lock:
                call_count["value"] += 1
            time.sleep(0.02)

    monkeypatch.setattr(chat_metrics_module, "ChatMetricsCollector", SlowChatMetricsCollector, raising=True)

    instances = _call_concurrently(chat_metrics_module.get_chat_metrics, workers=25)

    assert call_count["value"] == 1
    first_instance = instances[0]
    assert all(instance is first_instance for instance in instances)
