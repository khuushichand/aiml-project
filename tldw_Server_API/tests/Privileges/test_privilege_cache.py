from __future__ import annotations

import os

import pytest

from tldw_Server_API.app.core.PrivilegeMaps.cache import (
    DistributedPrivilegeCache,
    get_privilege_cache,
    reset_privilege_cache,
)
from tldw_Server_API.app.core.Metrics.metrics_manager import get_metrics_registry


@pytest.mark.parametrize("backend", ["memory", "redis"])
def test_distributed_privilege_cache_basic_roundtrip(monkeypatch, backend):
    monkeypatch.setenv("PRIVILEGE_CACHE_BACKEND", backend)
    if backend == "redis":
        # Force fallback to in-memory stub when real Redis is unavailable.
        monkeypatch.setenv("PRIVILEGE_CACHE_REDIS_URL", "redis://127.0.0.1:6399/15")
    else:
        monkeypatch.delenv("PRIVILEGE_CACHE_REDIS_URL", raising=False)

    reset_privilege_cache()
    cache = get_privilege_cache()
    registry = get_metrics_registry()
    tracked_metrics = [
        "privilege_cache_hits_total",
        "privilege_cache_misses_total",
        "privilege_cache_invalidations_total",
        "privilege_cache_generation",
        "privilege_cache_entries",
    ]
    for metric in tracked_metrics:
        registry.values[metric].clear()

    try:
        before_generation = cache.generation
        cache_key = f"demo::{before_generation}"
        payload = {"value": 42}

        cache.set(cache_key, payload, ttl_sec=120)
        cached = cache.get(cache_key)
        assert cached == payload

        cache.invalidate()
        after_generation = cache.generation
        assert after_generation >= before_generation

        next_cache_key = f"demo::{after_generation}"
        # No entry stored yet for the new generation.
        assert cache.get(next_cache_key) is None
        cache.set(next_cache_key, payload, ttl_sec=60)
        assert cache.get(next_cache_key) == payload

        def metric_sum(name: str, **labels) -> float:
            samples = [
                sample.value
                for sample in registry.values[name]
                if all(sample.labels.get(k) == v for k, v in labels.items())
            ]
            return sum(samples)

        backend_labels = {
            sample.labels.get("backend")
            for sample in registry.values["privilege_cache_hits_total"]
        }
        backend_labels.discard(None)
        assert backend_labels
        backend_label = backend_labels.pop()

        assert metric_sum("privilege_cache_hits_total", backend=backend_label, layer="local") >= 1
        assert metric_sum("privilege_cache_misses_total", backend=backend_label, layer="local") >= 1
        if backend == "redis":
            # Expect at least one backend miss when the stub redis is consulted after invalidate.
            assert metric_sum("privilege_cache_misses_total", backend=backend_label, layer="backend") >= 1
        assert metric_sum("privilege_cache_invalidations_total", backend=backend_label) == 1

        generation_samples = [
            sample.value
            for sample in registry.values["privilege_cache_generation"]
            if sample.labels.get("backend") == backend_label
        ]
        assert generation_samples
        assert generation_samples[-1] == float(cache.generation)

        entry_samples = [
            sample.value
            for sample in registry.values["privilege_cache_entries"]
            if sample.labels.get("backend") == backend_label
        ]
        assert entry_samples
        final_entry_value = entry_samples[-1]
        local_store = getattr(cache._local, "_store", {})  # noqa: SLF001 - test visibility
        assert final_entry_value == float(len(local_store))
    finally:
        cache.close()
        reset_privilege_cache()
