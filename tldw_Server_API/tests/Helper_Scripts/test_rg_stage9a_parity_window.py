"""Tests for RG Stage 9A/Stage 5 parity-window helper analysis."""

from __future__ import annotations

from pathlib import Path

import pytest

from Helper_Scripts import rg_stage9a_parity_window as script


def _meta(ts: int) -> script.SnapshotMeta:
    return script.SnapshotMeta(
        captured_at_unix=ts,
        metrics_url="http://127.0.0.1:8000/metrics",
        health_url=None,
        health_status_code=None,
        rg_policy_version=1,
        rg_policy_store="file",
        rg_policy_count=20,
    )


def _samples(text: str) -> dict[script.SampleKey, float]:
    return script.parse_prometheus_text(text)


@pytest.mark.unit
def test_analyze_release_window_passes_full_window_zero_mismatch() -> None:
    t0 = 1_700_000_000
    snapshots = [
        (
            Path("snap1.prom"),
            _meta(t0),
            _samples(
                """
                rg_decisions_total{policy_id="chat.default"} 100
                rg_decisions_total{policy_id="authnz.default"} 50
                rg_shadow_decision_mismatch_total{module="chat",route="/api/v1/chat/completions",policy_id="chat.default",legacy="allow",rg="allow"} 0
                """
            ),
        ),
        (
            Path("snap2.prom"),
            _meta(t0 + 4 * 24 * 3600),
            _samples(
                """
                rg_decisions_total{policy_id="chat.default"} 150
                rg_decisions_total{policy_id="authnz.default"} 75
                rg_shadow_decision_mismatch_total{module="chat",route="/api/v1/chat/completions",policy_id="chat.default",legacy="allow",rg="allow"} 0
                """
            ),
        ),
        (
            Path("snap3.prom"),
            _meta(t0 + 8 * 24 * 3600),
            _samples(
                """
                rg_decisions_total{policy_id="chat.default"} 180
                rg_decisions_total{policy_id="authnz.default"} 90
                rg_shadow_decision_mismatch_total{module="chat",route="/api/v1/chat/completions",policy_id="chat.default",legacy="allow",rg="allow"} 0
                """
            ),
        ),
    ]

    result = script._analyze_release_window(
        snapshots=snapshots,
        expected_policy_ids=["chat.default", "authnz.default"],
        min_window_hours=168.0,
        mismatch_threshold=0.0,
        mismatch_rate_threshold=0.01,
        allow_resets=False,
        allow_missing_coverage=False,
        top_mismatches=10,
        top_policies=10,
        top_denials=10,
    )

    assert result["ok"] is True
    assert result["window_hours"] >= 168.0
    assert result["mismatch_total"] == 0.0
    assert result["mismatch_rate"] == 0.0
    assert result["missing_policy_ids"] == []


@pytest.mark.unit
def test_analyze_release_window_fails_on_rate_and_missing_coverage() -> None:
    t0 = 1_700_000_000
    snapshots = [
        (
            Path("snap1.prom"),
            _meta(t0),
            _samples(
                """
                rg_decisions_total{policy_id="chat.default"} 100
                rg_decisions_total{policy_id="authnz.default"} 100
                rg_shadow_decision_mismatch_total{module="chat",route="/api/v1/chat/completions",policy_id="chat.default",legacy="allow",rg="deny"} 0
                """
            ),
        ),
        (
            Path("snap2.prom"),
            _meta(t0 + 8 * 24 * 3600),
            _samples(
                """
                rg_decisions_total{policy_id="chat.default"} 200
                rg_decisions_total{policy_id="authnz.default"} 200
                rg_shadow_decision_mismatch_total{module="chat",route="/api/v1/chat/completions",policy_id="chat.default",legacy="allow",rg="deny"} 10
                """
            ),
        ),
    ]

    result = script._analyze_release_window(
        snapshots=snapshots,
        expected_policy_ids=["chat.default", "authnz.default", "rag.default"],
        min_window_hours=168.0,
        mismatch_threshold=100.0,
        mismatch_rate_threshold=0.01,
        allow_resets=False,
        allow_missing_coverage=False,
        top_mismatches=10,
        top_policies=10,
        top_denials=10,
    )

    assert result["ok"] is False
    assert any("mismatch_rate=" in reason for reason in result["fail_reasons"])
    assert any("missing_policy_ids=" in reason for reason in result["fail_reasons"])
    assert "rag.default" in result["missing_policy_ids"]
