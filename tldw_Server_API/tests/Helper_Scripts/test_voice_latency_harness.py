from __future__ import annotations

import json
from typing import Any, Dict

import numpy as np

from Helper_Scripts.voice_latency_harness.run import (
    HarnessResult,
    _extract_histogram_percentiles,
    _parse_prometheus_histograms,
    _percentiles,
)


def test_percentiles_basic() -> None:
    """_percentiles should compute expected p50/p90 values for a numeric sequence."""
    values = [0.1, 0.2, 0.3, 0.4]
    result = _percentiles(values, pcts=(50, 90))
    assert set(result.keys()) == {"p50", "p90"}
    assert np.isclose(result["p50"], 0.25, atol=1e-6)
    assert np.isclose(result["p90"], 0.37, atol=1e-6)


def test_extract_histogram_percentiles_from_values_list() -> None:
    """_extract_histogram_percentiles should handle plain list and 'values' dict inputs."""
    metrics: Dict[str, Any] = {
        "stt_final_latency_seconds": [0.1, 0.2, 0.3],
        "tts_ttfb_seconds": {"values": [0.05, 0.15, 0.25]},
    }

    stt_p = _extract_histogram_percentiles(metrics, "stt_final_latency_seconds")
    tts_p = _extract_histogram_percentiles(metrics, "tts_ttfb_seconds")

    assert "p50" in stt_p and "p90" in stt_p
    assert "p50" in tts_p and "p90" in tts_p
    assert stt_p["p50"] > 0
    assert tts_p["p50"] > 0


def test_parse_prometheus_histograms_and_extract() -> None:
    """_parse_prometheus_histograms should parse Prom text into bucketed histograms consumable by _extract_histogram_percentiles."""
    prom_text = """
    # HELP stt_final_latency_seconds STT latency
    # TYPE stt_final_latency_seconds histogram
    stt_final_latency_seconds_bucket{le="0.1"} 1
    stt_final_latency_seconds_bucket{le="0.2"} 3
    stt_final_latency_seconds_bucket{le="0.5"} 3
    stt_final_latency_seconds_bucket{le="+Inf"} 3
    stt_final_latency_seconds_count 3
    stt_final_latency_seconds_sum 0.5
    """
    histograms = _parse_prometheus_histograms(prom_text, target_names=["stt_final_latency_seconds"])
    assert "stt_final_latency_seconds" in histograms
    hist = histograms["stt_final_latency_seconds"]
    assert "buckets" in hist and "count" in hist

    # _extract_histogram_percentiles should detect the histogram shape and delegate to the bucket-based helper.
    metrics: Dict[str, Any] = {"stt_final_latency_seconds": hist}
    p = _extract_histogram_percentiles(metrics, "stt_final_latency_seconds")
    assert "p50" in p and "p90" in p
    assert p["p50"] > 0


def test_harness_result_json_schema_shape() -> None:
    """HarnessResult JSON should include Stage 4 schema keys and required metric maps."""
    result = HarnessResult(
        run_id="voice-latency-test",
        fixture={"mode": "short", "base_url": "http://127.0.0.1:8000"},
        runs={"requested": 1, "completed": 1, "mode": "short"},
        metrics={
            "stt_final_latency_seconds": {"p50": 0.1, "p90": 0.2},
            "tts_ttfb_seconds": {"p50": 0.05, "p90": 0.1},
            "voice_to_voice_seconds": {"p50": 0.2, "p90": 0.3},
        },
        raw_metrics={},
    )
    payload = result.to_json()
    data = json.loads(payload)

    assert data["run_id"] == "voice-latency-test"
    assert "fixture" in data and isinstance(data["fixture"], dict)
    assert "runs" in data and isinstance(data["runs"], dict)
    assert "metrics" in data and isinstance(data["metrics"], dict)
    assert "stt_final_latency_seconds" in data["metrics"]
    assert "tts_ttfb_seconds" in data["metrics"]
    assert "voice_to_voice_seconds" in data["metrics"]
